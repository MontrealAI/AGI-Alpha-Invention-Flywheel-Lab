"""Retained native continuation proof on installed bytes; never restores an existing account."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
import signal
import ctypes

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commercial.ledger import digest
from connected_enterprise.runner import identity


def read(path):return json.loads(path.read_text())
def write(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')

def operate(output):
    from tests.connected_legacy_fixture import materialize
    from adaptive_enterprise.instruments import prepare_services
    output=Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise ValueError('NEW_OWNED_EXPERIMENTAL_OUTPUT_REQUIRED')
    output.mkdir(parents=True,mode=0o700)
    # Reap grandchildren if a CLI launcher is interrupted; their costs remain visible.
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'DESCENDANT_REAP_REQUIRED')
    frozen=identity(ROOT);protocol=read(ROOT/'campaign/successor-022/QUALIFICATION_PROTOCOL.json')
    receipt={'schema':'agi-alpha/completion024-native-installed-operation/v1','accepted':False,
             'source':frozen,'protocol':protocol,'protocol_sha256':digest(protocol),'commands':[],
             'scope':'Exposed authored-world engineering reproduction on a new owned experimental legacy account; not recovery of the unavailable original latest business, annual profit, actual commerce or untouched confirmation'}
    write(output/'PROFILE.json',receipt)
    started=time.monotonic()
    def command(label,arguments,cwd=ROOT,timeout=300):
        with (output/(label+'.stdout')).open('w') as stdout,(output/(label+'.stderr')).open('w') as stderr:
            child=subprocess.Popen([sys.executable,*map(str,arguments)],cwd=cwd,stdout=stdout,stderr=stderr,
                env={**os.environ,'PYTHONPATH':str(cwd),'PYTHONDONTWRITEBYTECODE':'1'},start_new_session=True)
            try:returncode=child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                # Kill any surviving adopted descendants in this owned command group.
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                while True:
                    try:os.waitpid(-1,0)
                    except ChildProcessError:break
                raise
            finally:
                # Successful launchers reap their own children; unexpected orphans fail closed.
                while True:
                    try:
                        pid,status=os.waitpid(-1,os.WNOHANG)
                        if pid==0:break
                    except ChildProcessError:break
        receipt['commands'].append({'label':label,'arguments':list(map(str,arguments)),'returncode':returncode,
                                   'stdout_sha256':hashlib.sha256((output/(label+'.stdout')).read_bytes()).hexdigest(),
                                   'stderr_sha256':hashlib.sha256((output/(label+'.stderr')).read_bytes()).hexdigest()})
        write(output/'PROFILE.json',receipt)
        if returncode:raise RuntimeError('NATIVE_PROFILE_COMMAND_FAILED:'+label)
    try:
        old=output/'legacy-source';materialize(ROOT,protocol['legacy_commit'],old)
        cfg=read(ROOT/protocol['config']);policy=read(ROOT/protocol['policies']['prospective'])
        manifest=prepare_services(old,'service-inputs',cohort_seed=protocol['service_cohort_seed'])
        for name,value in [('CONFIG.json',cfg),('POLICY.json',policy),('SERVICES.json',manifest)]:write(output/name,value)
        business=output/'business'
        payload={'root':str(old),'manifest':manifest,'config':cfg,'seed':protocol['world_seed'],'arm':'growth',
                 'output':str(business),'source':identity(old),'stop_after_events':250}
        write(output/'LEGACY_INPUT.json',payload)
        code='''import json,sys
from pathlib import Path
from connected_enterprise.engine import run_world
p=json.load(open(sys.argv[1]))
def stop(where,state,account):
 checkpoint=json.load(open(Path(p['output'])/'STATE.json'))
 kinds={e['kind'] for e in checkpoint['body']['state']['queue']}
 if {'produce','accept','clear'}<=kinds and account.snapshot()['summary']['tailReserve']>0:
  (Path(p['output']).parent/'LEGACY_RECORD.json').write_text(json.dumps(account.export(),sort_keys=True))
  raise InterruptedError('finite registered legacy queue coverage')
try:run_world(**p,failpoint=stop)
except InterruptedError:pass
else:raise ValueError('REGISTERED_LEGACY_COVERAGE_NOT_REACHED')
'''
        command('01-legacy',['-c',code,output/'LEGACY_INPUT.json'],old)
        checkpoint=read(business/'STATE.json');before=checkpoint['body']['state'];write(output/'ORIGINAL_CHECKPOINT.json',checkpoint)
        key=business/'account.sqlite.adaptive-simulation-key';keyinode=key.stat().st_ino
        command('02-upgrade',['-m','connected_enterprise','upgrade','--output',business,'--historical-source',old,
            '--manifest',output/'SERVICES.json','--policy',output/'POLICY.json','--expected-checkpoint',digest(checkpoint),
            '--id','installed-native-forward-1','--transition-format','v2-cas'])
        after=read(business/'STATE.json')['body']['state']
        for field in ['queue','current','orders','buyers','events','decisions','investments','used_jobs','processed_events','last_time']:
            if after[field]!=before[field]:raise ValueError('MIGRATION_LOST_OPERATING_STATE:'+field)
        # Fixed finite horizon, including settlement drain; no favorable-world substitution.
        for number in range(1,301):
            state=read(business/'STATE.json')['body']['state']
            if not state['queue']:break
            if state['last_time']>protocol['maximum_registered_drain_hour']:raise ValueError('REGISTERED_DRAIN_BOUNDARY')
            command('03-step-'+str(number),['-m','connected_enterprise','operate','--output',business,'--max-events',protocol['quantum_event_limit']])
        else:raise ValueError('FINITE_REGISTERED_EVENT_BOUNDARY')
        result=read(business/'RESULT.json')
        if not result['complete']:raise ValueError('FULL_REGISTERED_HORIZON_REQUIRED')
        command('04-resume',['-m','connected_enterprise','resume','--output',business])
        if read(business/'RESULT.json')['owned_account']['ledger']!=result['owned_account']['ledger']:raise ValueError('RESUME_CHANGED_MONEY_OR_HISTORY')
        command('05-audit',['-m','connected_enterprise','audit','--output',business])
        command('06-scoreboard',['-m','connected_enterprise','scoreboard','--output',business])
        score=read(business/'SCOREBOARD.json');audit=read(business/'OPERATOR_AUDIT.json')
        prior=read(output/'LEGACY_RECORD.json')['ledger']['actions']
        if result['owned_account']['ledger']['actions'][:len(prior)]!=prior or key.stat().st_ino!=keyinode:raise ValueError('ORIGINAL_IDENTITY_OR_HISTORY_CHANGED')
        if score['maturities']<1 or score['profitable_settlements_funded_after_maturity']<2 or score['summary']['profit']<=0 or not audit['accepted']:raise ValueError('PROSPECTIVE_REPEATED_EXPANSION_CRITERION_FAILED')
        if result['source']!=frozen or identity(ROOT)!=frozen:raise ValueError('INSTALLED_EXECUTING_SOURCE_CHANGED')
        oldorders=list(before['orders'])+(before['current'].get('orders',[]) if before['current'] else [])
        protected=sum(o['price']+200000 for o in result['orders'] if o['id'] in {r['id'] for r in oldorders} and o['outcome']=='SETTLED')
        if result['summary']['tailReserve']<protected:raise ValueError('LEGACY_PERMANENT_TAIL_ERASED')
        command('07-portable',[ROOT/'scripts/export_recovered023.py','--business',business,'--output',output/'public','--offline-historical-sources'])
        receipt.update(accepted=True,complete_resume_financially_unchanged=True,original_native_prefix_preserved=True,
            original_queued_state_preserved=True,key_inode_unchanged=True,summary=result['summary'],paid_jobs=result['paid_jobs'],
            planning_horizon_hours=protocol['planning_horizon_hours'],actual_final_hour=result['events'][-1]['time'],
            maturities=score['maturities'],profitable_settlements_funded_after_maturity=score['profitable_settlements_funded_after_maturity'],
            permanent_legacy_protection_microUSD=protected,audit=audit,portable_audit=read(output/'public/PORTABLE_AUDIT.json'),
            public_archive_sha256=hashlib.sha256((output/'public.zip').read_bytes()).hexdigest(),
            funding_lineage=score.get('funding_lineage',[]))
    except BaseException as error:
        receipt['failure']={'type':type(error).__name__,'message':str(error)}
        # Raw key-free failure records survive hosted worker teardown; private keys never enter this transport.
        try:
            files={};total=0
            for name in ['STATE.json','RESULT.json','MIGRATION_INTENT.json','MIGRATION_RECEIPT.json',
                         'account.sqlite.actions.jsonl','account.sqlite.connected-journal.json',
                         'account.sqlite.adaptive-source-transitions.json','account.sqlite.adaptive-proofs.json',
                         'account.sqlite.adaptive-resolutions.json','account.sqlite.adaptive-connected-source.json']:
                path=output/'business'/name
                if path.is_symlink():raise ValueError('FAILED_EVIDENCE_SYMLINK_REFUSED')
                if path.is_file():files['business/'+name.replace('account.sqlite.','native-')]=path.read_bytes()
            store=output/'business/TRANSITION_EVIDENCE'
            if store.is_dir() and not store.is_symlink():
                for path in sorted(store.iterdir()):
                    if path.is_symlink() or not path.is_file():raise ValueError('FAILED_EVIDENCE_REGULAR_OBJECT_REQUIRED')
                    files['TRANSITION_EVIDENCE/'+path.name]=path.read_bytes()
            total=sum(map(len,files.values()))
            if len(files)+1>10000 or total>256_000_000:raise ValueError('FAILED_EVIDENCE_ARCHIVE_BOUND')
            manifest={n:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for n,raw in files.items()}
            with zipfile.ZipFile(output/'failed-keyfree.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,raw in files.items():archive.writestr(name,raw)
                archive.writestr('INTEGRITY.json',json.dumps({'files':manifest,'scope':'Unaudited failed raw records, exact bytes; neither database nor key exported'},sort_keys=True))
            receipt['failed_raw_keyfree_archive_sha256']=hashlib.sha256((output/'failed-keyfree.zip').read_bytes()).hexdigest()
        except BaseException as preservation:
            receipt['failure_preservation_error']={'type':type(preservation).__name__,'message':str(preservation)}
        raise
    finally:
        receipt['wall_seconds']=time.monotonic()-started;write(output/'PROFILE.json',receipt)
    print(json.dumps({'accepted':True,'source_sha256':frozen['sha256'],'summary':receipt['summary'],
                      'maturities':receipt['maturities'],'earned_successors':receipt['profitable_settlements_funded_after_maturity']},sort_keys=True))
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args();operate(args.output)
