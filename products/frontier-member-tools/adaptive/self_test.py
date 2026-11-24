"""Qualify the downloaded local workspace, admission and Wasm boundaries."""

from base64 import b64encode
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import time

from check import read
from operate import (admit, control, drain, fact, inventory, observe, open_state, plan,
                     propose, recover, reserve, verify_observed, view)
from pages import canonical, digest
from wasm_policy import Policy, Refused, expression_wat, lower


def wasm_controls():
    wrapper='(module %s (func (export "choose") (param i32 i32 i32 i32 i32) (result i32) %s))'
    assert Policy(wrapper%('','local.get 0'))(21,0,0,0,0)==21
    assert Policy(lower([2,3,'+']))(0,0,0,0,0)==5
    assert Policy(expression_wat('7 if a < b else 23'))(2,1,0,0,0)==23
    try:
        expression_wat('outside()')
    except Refused:
        pass
    else:
        raise AssertionError('Expression call completed')
    denied=(wrapper%('(import "env" "outside" (func))','i32.const 21'),
            wrapper%('(memory 2)','i32.const 21'),
            wrapper%('','(loop br 0) i32.const 21'),
            wrapper%('(table 70 funcref)','i32.const 21'))
    for source in denied:
        try:
            Policy(source)(0,0,0,0,0)
        except Refused:
            continue
        raise AssertionError('Unscoped Wasm completed')
    return len(denied)


def workspace_controls(root,history):
    private=root/'test-key'
    public=root/'test-public'
    subprocess.run(('openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(private)),
                   capture_output=True,check=True,timeout=10)
    subprocess.run(('openssl','pkey','-in',str(private),'-pubout','-out',str(public)),check=True,timeout=8)
    policy=control(sha256(public.read_bytes()).hexdigest())
    with closing(open_state(root,policy)) as db:
        observe(db,history,seed=True)
        plan(db,policy)
        reserve(db,1,policy)
        with db:
            db.execute("UPDATE queue SET state='RUNNING'")
        recover(db)
        drain(db,policy)
        candidate=inventory(db,'latest_candidate')
        assert candidate and inventory(db,'read_reserved')==1 and not inventory(db,'read_pending')
        assert [kind for (kind,) in db.execute('SELECT kind FROM events WHERE kind LIKE ?',('INTERRUPTED%',))] == [
            'INTERRUPTED','INTERRUPTED_READ']
        before=view(db)['stages']
        plan(db,policy)
        drain(db,policy)
        assert view(db)['stages']==before
        decision={'schema':'frontier/learning-admission-v1','authority':digest(policy),'candidate':candidate,
                  'state':'QUALIFIED','expires':int(time())+300,'scope':'public-actions-pages-forecast'}
        receipt=root/'test-decision.json'
        receipt.write_bytes(canonical({'decision':decision,'signature':'AA=='}))
        try:
            admit(db,policy,receipt,public)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsigned candidate was admitted')
        verified=subprocess.run(('openssl','dgst','-sha256','-sign',str(private)),input=canonical(decision),
                                capture_output=True,check=True,timeout=8)
        receipt.write_bytes(canonical({'decision':decision,'signature':b64encode(verified.stdout).decode()}))
        admit(db,policy,receipt,public)
        assert view(db)['admitted_sha256']==candidate
        assert propose(db,{'event':'schedule','base':20})=={'baseline':20,'admitted':None,'shadow':None}
        with db:
            fact(db,'active_expiry',0)
        assert view(db)['admitted_sha256'] is None
        admit(db,policy,receipt,public)
        relative={'baseline':20,'admitted':{'sha256':candidate,'seconds':60},'shadow':None}
        with db:
            for number in range(5):
                verify_observed(db,{'id':number+1,'created':1,'completed':21},relative)
        assert view(db)['admitted_sha256'] is None
        try:
            admit(db,policy,receipt,public)
        except ValueError:
            pass
        else:
            raise AssertionError('A revoked receipt was replayed')
    return {'recovered_queue':True,'forgery_denied':True,'scoped_signature':True,'expiry_fallback':True,
            'unsupported_event_fallback':True,'automatic_regression_suspension':True}


if __name__=='__main__':
    with TemporaryDirectory() as scratch:
        source=Path(__file__).resolve().parent/'study/cohort/fit.json'
        print(json.dumps({'wasm_denials':wasm_controls(),'workspace':workspace_controls(Path(scratch),read(source))}))
