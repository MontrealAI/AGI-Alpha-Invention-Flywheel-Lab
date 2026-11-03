"""Continue exact frozen cases with a qualified external read-observation cache.

No frozen file, native financial implementation, account identity, policy,
registration or monetary action is changed. The original operating auditor
checks the same public observations against actual native financial prefixes.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

EXTENSION_ROOT=Path(__file__).resolve().parents[2]
EXPECTED_FROZEN_COMMIT='6ff45e25a85a590d4921aef6e197148252b92cce'
EXPECTED_FROZEN_SHA='048b4ceb0322a2cd2cbd4c2f9cb9e5cdc2929034e3888a375ad650f8cbe37462'
CAMPAIGN='campaign/omega-expandable-5790816e'


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_frozen(output):
    sys.path.insert(0,str(output/'source'))
    original=load_module('registered_expandable_reproduction',output/'source'/CAMPAIGN/'reproduce.py')
    frozen,reg=original.verify_freeze(output)
    if frozen['git_commit']!=EXPECTED_FROZEN_COMMIT or frozen['source_sha256']!=EXPECTED_FROZEN_SHA:
        raise ValueError('EXACT_QUALIFIED_FROZEN_COMPARISON_REQUIRED')
    return original,frozen,reg


def extension_identity():
    names=['omega/recording_cache.py',CAMPAIGN+'/resume_verified.py']
    return {n:hashlib.sha256((EXTENSION_ROOT/n).read_bytes()).hexdigest() for n in names}


def run_one(output,case_id,max_steps=0):
    original,frozen,reg=load_frozen(output)
    from omega.expansion_audit import RecordingBridge,audit_market
    extension=load_module('qualified_external_read_observer',EXTENSION_ROOT/'omega/recording_cache.py')
    identity=extension_identity()
    case=next(r for r in frozen['cases'] if r['id']==case_id)
    directory=output/'accounts'/case_id
    if (directory/'COMPACT.json').exists():
        return {'case':case_id,'complete':True,'scope':'ALREADY_COMPLETED_UNCHANGED'}
    receipt_path=directory/'READ_OBSERVER_CONTINUATION.json'
    before_path=directory/'account.sqlite.actions.jsonl'
    before=before_path.read_bytes() if before_path.exists() else b''
    prior=original.read(receipt_path) if receipt_path.exists() else None
    if prior is not None and prior['extension_source_hashes']!=identity:
        raise ValueError('REGISTERED_READ_OBSERVER_SOURCE_CHANGED')
    with original.NativeBridge(directory,root=output/'source',config=reg['native_config'],resume=directory.exists()) as native:
        receipt=prior or {'schema':'omega/external-read-observer-continuation/v1',
            'frozen_commit':EXPECTED_FROZEN_COMMIT,'frozen_source_sha256':EXPECTED_FROZEN_SHA,
            'extension_source_hashes':identity,'prior_native_tape_bytes':len(before),
            'prior_native_tape_sha256':hashlib.sha256(before).hexdigest(),
            'scope':'External read observation reuse; exact original financial/runtime/policy bytes and same account authority; not a source migration',
            'limits':'Exclusive routed mutations; no protection claimed against hostile same-length in-memory tampering; original full audits remain required'}
        original.save(receipt_path,receipt)
        market_path=directory/'MARKET.json';trace_path=directory/'TRACE.json'
        state=native.account.verify_checkpoint(original.read(market_path)) if market_path.exists() else None
        trace=original.read(trace_path) if trace_path.exists() else None
        runner=original.MarketRunner(reg['worlds'][case['world']],mode=case['mode'],seed=case['seed'],
                                    settings=reg['profiles'][case['profile']],state=state)
        recording=extension.make_recording_bridge(RecordingBridge,native,trace=trace,
                                                 persist=lambda value:original.save(trace_path,value))
        recording.begin_segment(runner.export())
        def checkpoint(value):
            if extension_identity()!=identity:raise ValueError('READ_OBSERVER_SOURCE_CHANGED_DURING_EXECUTION')
            recording.flush()
            original.save(market_path,native.account.seal_checkpoint(value))
        steps=0
        while runner.step(recording,checkpoint):
            steps+=1
            if max_steps and steps>=max_steps:
                recording.flush()
                return {'case':case_id,'complete':False,'scope':'SAME_ACCOUNT_OPERATIONAL_CHECKPOINT',
                        'day':runner.state['day'],'additional_steps':steps}
        recording.end_segment(runner.export())
        result=native.finish(settle=True)
        record=original.read(directory/'PUBLIC_ACCOUNT.json')
        audit=audit_market(world=reg['worlds'][case['world']],mode=case['mode'],seed=case['seed'],
                           settings=reg['profiles'][case['profile']],state=runner.export(),trace=recording.export(),
                           native_record=record,root=native.source,manifest=native.manifest)
        if not audit['accepted']:raise ValueError('ORIGINAL_OPERATING_AUDIT_REJECTED')
        raw=before_path.read_bytes()
        if hashlib.sha256(raw[:receipt['prior_native_tape_bytes']]).hexdigest()!=receipt['prior_native_tape_sha256']:
            raise ValueError('PRIOR_NATIVE_HISTORY_CHANGED')
        if extension_identity()!=identity:raise ValueError('READ_OBSERVER_SOURCE_CHANGED')
        original.save(directory/'OPERATING_AUDIT.json',audit)
        original.save(directory/'MARKET_PUBLIC.json',runner.export())
        compact=original.compact(case,result,runner.export(),audit)
        compact['external_read_observer']=receipt
        original.save(directory/'COMPACT.json',compact)
        return {'case':case_id,'complete':True,'accepted':audit['accepted'],
                'native_actions_sha256':result['native_actions_sha256']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--case')
    parser.add_argument('--workers',type=int,default=7);parser.add_argument('--max-steps',type=int,default=0)
    args=parser.parse_args();output=Path(args.output).resolve()
    if args.workers<1 or args.max_steps<0:raise ValueError('VALID_EXECUTION_CONFIGURATION_REQUIRED')
    if args.case:
        print(json.dumps(run_one(output,args.case,args.max_steps),sort_keys=True),flush=True);return
    original,frozen,_=load_frozen(output)
    pending=[r for r in frozen['cases'] if not (output/'accounts'/r['id']/'COMPACT.json').exists()]
    def launch(case):
        logs=output/'execution';logs.mkdir(exist_ok=True)
        start=time.monotonic()
        with (logs/(case['id']+'-read-cache.txt')).open('a') as stream:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--output',str(output),
                                   '--case',case['id'],'--max-steps',str(args.max_steps)],
                                  stdout=stream,stderr=subprocess.STDOUT)
        receipt={'case':case['id'],'exit_code':result.returncode,'wall_seconds':time.monotonic()-start,
                 'extension_source_hashes':extension_identity()}
        original.save(logs/(case['id']+'-read-cache.json'),receipt)
        return receipt
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(launch,r) for r in pending]):
            print(json.dumps(future.result(),sort_keys=True),flush=True)
    report=original.summary(output)
    print(json.dumps({'complete':report['complete'],'completed':report['completed_cases'],
                      'registered':report['registered_cases']}),flush=True)


if __name__=='__main__':main()
