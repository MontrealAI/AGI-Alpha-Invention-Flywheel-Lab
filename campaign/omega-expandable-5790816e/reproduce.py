"""Freeze and execute registered independent native enterprises; never pool cash."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import source_paths_for_manifest
from experiments.commerce006 import PINS
from omega.expansion_market import MarketRunner
from omega.expansion_native import NativeBridge, SCHEMA

CAMPAIGN = 'campaign/omega-expandable-5790816e'


def save(path, value):
    atomic_bytes(Path(path), canonical(value) + b'\n')


def read(path):
    return strict_json(Path(path).read_bytes())


def cases(reg):
    rows=[]
    for profile in reg['profiles']:
        for world in reg['worlds']:
            for seed in reg['seeds']:
                for mode in reg['policies']:
                    row=dict(profile=profile,world=world,seed=seed,mode=mode)
                    row['id']=f'{profile}--{world}--{seed}--{mode}'
                    row['primary']=all(row[k]==v for k,v in reg['primary'].items())
                    rows.append(row)
    return sorted(rows,key=lambda r:(not r['primary'],r['id']))


def source_files():
    paths=set(source_paths_for_manifest({'schema':SCHEMA}))|set(PINS)
    paths|={'omega/expansion_audit.py','omega/COMPATIBILITY.md'}
    paths|={p.relative_to(ROOT).as_posix() for p in (ROOT/CAMPAIGN).iterdir()
            if p.name in {'reproduce.py','REGISTRATION.json','PROTOCOL.md','OPPORTUNITIES.md','PAPERS.md','OFFERS_COSTS.md','CORRECTIONS.md'}}
    return sorted(paths)


def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    source=output/'source'
    hashes={}
    for name in source_files():
        path=ROOT/name
        if not path.is_file() or path.is_symlink():raise ValueError('REGULAR_REGISTERED_SOURCE_REQUIRED:'+name)
        raw=path.read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    try: commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except subprocess.CalledProcessError:commit=None
    registration=read(source/CAMPAIGN/'REGISTRATION.json')
    save(output/'FROZEN.json',{'schema':'omega/expandable-source-freeze/v1','git_commit':commit,
         'source_hashes':hashes,'source_sha256':digest(hashes),'registration_sha256':digest(registration),
         'cases':cases(registration),'account_rule':'Each separate independent USD100000; never pooled'})
    return source


def verify_freeze(output):
    frozen=read(output/'FROZEN.json');source=output/'source'
    if digest(frozen['source_hashes'])!=frozen['source_sha256']:raise ValueError('SOURCE_MANIFEST_CHANGED')
    for name,sha in frozen['source_hashes'].items():
        p=source/name
        if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
            raise ValueError('FROZEN_SOURCE_CHANGED:'+name)
    reg=read(source/CAMPAIGN/'REGISTRATION.json')
    if digest(reg)!=frozen['registration_sha256'] or cases(reg)!=frozen['cases']:
        raise ValueError('REGISTERED_ARMS_CHANGED')
    return frozen,reg


def run_case(output, case_id, *, interrupt_after=None):
    from omega.expansion_audit import RecordingBridge, audit_market
    frozen,reg=verify_freeze(output)
    case=next(r for r in frozen['cases'] if r['id']==case_id)
    directory=output/'accounts'/case_id
    exists=directory.exists()
    with NativeBridge(directory,root=ROOT,config=reg['native_config'],resume=exists,
                      interrupt_after=interrupt_after) as native:
        market_path=directory/'MARKET.json';trace_path=directory/'TRACE.json'
        state=native.account.verify_checkpoint(read(market_path)) if market_path.exists() else None
        trace=read(trace_path) if trace_path.exists() else None
        runner=MarketRunner(reg['worlds'][case['world']],mode=case['mode'],seed=case['seed'],
                            settings=reg['profiles'][case['profile']],state=state)
        proxy=RecordingBridge(native,trace=trace,persist=lambda value:save(trace_path,value))
        proxy.begin_segment(runner.export())
        def checkpoint(value):
            proxy.flush()
            save(market_path,native.account.seal_checkpoint(value))
        runner.run(proxy,checkpoint=checkpoint)
        proxy.end_segment(runner.export())
        operating_state=runner.export()
        result=native.finish(settle=True)
        record=read(directory/'PUBLIC_ACCOUNT.json')
        audit=audit_market(world=reg['worlds'][case['world']],mode=case['mode'],seed=case['seed'],
                           settings=reg['profiles'][case['profile']],state=operating_state,
                           trace=proxy.export(),native_record=record,root=native.source,manifest=native.manifest)
        save(directory/'OPERATING_AUDIT.json',audit)
        if not audit['accepted']:raise ValueError('INDEPENDENT_OPERATING_AUDIT_REJECTED')
        save(directory/'MARKET_PUBLIC.json',operating_state)
        summary=compact(case,result,operating_state,audit)
        save(directory/'COMPACT.json',summary)
        print(json.dumps(summary,sort_keys=True),flush=True)
        return summary


def compact(case,result,state,audit):
    funded=[s for s in result['spends'].values() if s['funded']]
    earnings=[s for s in funded if (s.get('receipt') or {}).get('funding')=='EARNED']
    statuses={}
    for row in result['orders'].values():statuses[row['status']]=statuses.get(row['status'],0)+1
    return {'case':case,'accepted':result['accepted'] and audit['accepted'],'scope':result['scope'],
            'native_actions_sha256':result['native_actions_sha256'],'source_sha256':result['source_sha256'],
            'rolling_year':result['rolling_year'],'summary':result['summary'],'tax':result['tax'],
            'orders_by_status':statuses,'campaigns':len(state['campaigns']),
            'requested_contacts':sum(c['size'] for c in state['campaigns']),
            'unique_contacts':len(state['contacted']),
            'largest_campaign':max([0]+[c['size'] for c in state['campaigns']]),
            'earned_funded_actions':len(earnings),
            'earned_funded_spend_cents':sum(s['request']['amount_cents'] for s in earnings),
            'buyer_net_cents':state['buyer_net_cents'],'buyer_incremental_cents':state['buyer_incremental_cents'],
            'operating_audit':audit,'market_sha256':digest(state),
            'actual_complete_cost_profit':None,'founder_service_minutes':0}


def summary(output):
    frozen,reg=verify_freeze(output)
    rows=[];missing=[]
    for case in frozen['cases']:
        p=output/'accounts'/case['id']/'COMPACT.json'
        if p.exists(): rows.append(read(p))
        else:missing.append(case['id'])
    result={'schema':'omega/expandable-comparison/v1','source':frozen,
            'registered_cases':len(frozen['cases']),'completed_cases':len(rows),
            'missing_cases':missing,'complete':not missing,'cases':rows,
            'accounts_pooled':False,'weights':None,'actual_complete_cost_profit':None,
            'three_billion_objective_achieved':False,'invention_advantage_established':False}
    save(output/'COMPARISON.json',result)
    return result


def development_smoke(output):
    """An explicit seven-day engineering fixture, never an annual result."""
    from omega.expansion_audit import RecordingBridge,audit_market
    from omega.expansion_market import config,worlds
    from omega.expansion_native import default_config
    cfg=default_config();cfg.update(operating_hours=168,engineering_fixture=True)
    settings=config(horizon_days=7,cadence_days=7,risk_bps=1000)
    with NativeBridge(output,root=ROOT,config=cfg) as native:
        runner=MarketRunner(worlds()['capability_gap'],mode='joint',seed=17,settings=settings)
        recording=RecordingBridge(native,persist=lambda value:save(output/'TRACE.json',value))
        recording.begin_segment(runner.export())
        def checkpoint(state):
            recording.flush();save(output/'MARKET.json',native.account.seal_checkpoint(state))
        runner.run(recording,checkpoint);recording.end_segment(runner.export())
        report=native.finish()
        audit=audit_market(worlds()['capability_gap'],'joint',17,settings,runner.export(),
                           recording.export(),native.account.export(),root=native.source,manifest=native.manifest)
        save(output/'OPERATING_AUDIT.json',audit)
        if report['rolling_year']['complete_365_day_operating_history']:
            raise ValueError('SHORT_FIXTURE_MISLABELED_ANNUAL')
        if not audit['accepted']:raise ValueError('OPERATING_AUDIT_REQUIRED')
        print(json.dumps({'scope':'SEVEN_DAY_DEVELOPMENT_NOT_ANNUAL','accepted':audit['accepted'],
                          'native_actions_sha256':report['native_actions_sha256']}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--summary',action='store_true')
    parser.add_argument('--development-smoke',action='store_true')
    parser.add_argument('--interrupt-after',choices=['fund','tax'])
    args=parser.parse_args();output=Path(args.output).resolve()
    if args.development_smoke:
        development_smoke(output);return
    if args.case:
        run_case(output,args.case,interrupt_after=args.interrupt_after);return
    if args.summary:
        report=summary(output);print(json.dumps({'complete':report['complete'],'completed':report['completed_cases'],
                                               'registered':report['registered_cases']}));return
    if args.workers<1:raise ValueError('POSITIVE_CONCURRENCY_REQUIRED')
    if not args.resume:freeze(output)
    frozen,_=verify_freeze(output)
    script=output/'source'/CAMPAIGN/'reproduce.py'
    pending=[r for r in frozen['cases'] if not (output/'accounts'/r['id']/'COMPACT.json').exists()]
    def launch(case):
        logs=output/'execution';logs.mkdir(exist_ok=True)
        start=time.monotonic()
        with (logs/(case['id']+'.txt')).open('a') as stream:
            process=subprocess.run([sys.executable,str(script),'--output',str(output),'--case',case['id']],
                                   cwd=output/'source',stdout=stream,stderr=subprocess.STDOUT)
        receipt={'case':case['id'],'exit_code':process.returncode,'wall_seconds':time.monotonic()-start}
        save(logs/(case['id']+'.json'),receipt)
        return receipt
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(launch,c) for c in pending]
        for future in as_completed(futures):
            print(json.dumps(future.result(),sort_keys=True),flush=True)
    report=summary(output)
    print(json.dumps({'complete':report['complete'],'completed':report['completed_cases'],
                      'registered':report['registered_cases']}),flush=True)
    if not report['complete']:raise SystemExit(1)


if __name__=='__main__':main()
