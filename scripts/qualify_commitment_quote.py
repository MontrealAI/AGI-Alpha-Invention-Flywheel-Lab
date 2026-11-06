"""Reproduce or independently replay key-free pricing engineering evidence."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def audit_packet(path):
    # Only native canonical auditor and bound acceptance decide delivery/finance.
    from connected_enterprise.finance import audit_journal
    from commercial.ledger import strict_json
    from campaign.genesis_commitment001 import service
    path=Path(path)
    with gzip.open(path,'rb') as stream:
        raw=stream.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('BOUNDED_ENGINEERING_PACKET_REQUIRED')
    p=strict_json(raw)
    from tests.test_commitment_quote_policy import public_observation
    from research.commitment_quote_policy import decide
    from campaign.genesis_commitment001.delivery import default_requests
    obs=public_observation()
    if p['public_observation']!=obs:raise ValueError('FROZEN_PUBLIC_OBSERVATION_CHANGED')
    arm=p['result']['arm']
    if arm not in ('fixed','ordinary','constructor'):raise ValueError('REGISTERED_ARM_REQUIRED')
    price=3_000_000_000 if arm=='fixed' else decide(obs)['price_microUSD']
    if p['result']['price_microUSD']!=price:raise ValueError('DISPLAYED_QUOTE_CHANGED')
    with tempfile.TemporaryDirectory(prefix='quote-public-audit-') as temp:
        source=Path(temp)
        expected=set(service.source_paths(ROOT))
        from connected_enterprise.finance import SOURCE_PATHS
        expected.update(SOURCE_PATHS)
        if set(p['source_hashes'])!=expected:raise ValueError('EXACT_SOURCE_CLOSURE_REQUIRED')
        for name,sha in p['source_hashes'].items():
            current=ROOT/name
            if current.is_symlink() or hashlib.sha256(current.read_bytes()).hexdigest()!=sha:
                raise ValueError('SOURCE_CHANGED')
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(current,dest)
        requests=default_requests()
        requests[0]['records']=[{'account_id':'fresh-'+str(i),'name':'Synthetic '+str(i),
                                'balance_cents':1700+i*137} for i in range(17)]
        expected_manifest=service.prepare_manifest(source,[{'id':r['id'],'request':r,
            'delivery_path':service.DELIVERIES+r['id']+'.json'} for r in requests])
        if p['manifest']!=expected_manifest:raise ValueError('FROZEN_NATIVE_REQUEST_CHANGED')
        allowed={r['delivery_path'] for r in p['manifest']['jobs']}
        for name,artifact in p['delivered'].items():
            if name not in allowed or not name.startswith(service.DELIVERIES):
                raise ValueError('UNREGISTERED_DELIVERY')
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(artifact,sort_keys=True,allow_nan=False))
        result=audit_journal(p['native_export'],root=source,manifest=p['manifest'])
        if result['accepted'] is not True:raise ValueError('NATIVE_REPLAY_REJECTED')
        if p['result']['summary']!=p['native_export']['ledger']['summary']:
            raise ValueError('SUMMARY_NOT_NATIVE_BOUND')
        if p['native_export']['ledger']['config']['opening']!=100_000_000_000:
            raise ValueError('EXACT_DISPOSABLE_SEED_REQUIRED')
        if p['native_export']['ledger']['config']['contract']!='public-quote-fixture-'+arm:
            raise ValueError('ACCOUNT_ARM_BINDING_CHANGED')
        # Result booleans are a presentation, not independent authority.
        releases=[r for r in p['native_export']['ledger']['actions']
                  if r['op']=='event' and r['args']['action']=='release']
        accepted=bool(releases)
        if accepted!=p['result']['accepted'] or accepted!=p['result']['buyer_buys']:
            raise ValueError('RELEASE_PRESENTATION_CHANGED')
        if accepted!=(arm!='fixed'):raise ValueError('FROZEN_BUYER_DECISION_CHANGED')
        actions=p['native_export']['ledger']['actions']
        offers=[a for a in actions if a['op']=='offer']
        if accepted and (len(offers)!=1 or offers[0]['args']['price']!=price):
            raise ValueError('NATIVE_QUOTE_CHANGED')
        prior=[a['after'] for a in actions if a['day']==19]
        before=prior[-1] if prior else None
        if p['result']['before_successor']!=before:raise ValueError('SUCCESSOR_SNAPSHOT_CHANGED')
        seed_possible=bool(before and before['available']>=990_000_000)
        if p['result']['seed_can_fund_successor']!=seed_possible:
            raise ValueError('SEED_COUNTERFACTUAL_CHANGED')
        if p['result']['successor_budget_microUSD']!=990_000_000:
            raise ValueError('SUCCESSOR_FULL_BUDGET_CHANGED')
        if before and min(before['available'],before['unrestrictedEarned'])>=990_000_000:
            raise ValueError('DEFERRAL_CLAIM_CONTRADICTED')
        if (p['result']['actual_revenue_microUSD']!=0 or p['result']['trailing_365_profit'] is not None
                or p['result']['scope']!='DISPOSABLE_AUTHORED_ENGINEERING_FIXTURE'):
            raise ValueError('SIMULATION_SCOPE_CHANGED')
        if p['result']['successor_funded'] is not False or any(
            r['id']!='first' for r in p['native_export']['ledger']['orders']):
            raise ValueError('UNREGISTERED_SUCCESSOR_CLAIM')
        return {'accepted':True,'packet_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'native_summary':p['native_export']['ledger']['summary'],
                'scope':'PUBLIC_NATIVE_REPLAY_NOT_DEMAND_OR_PRIMARY_CONTINUATION'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');run.add_argument('--output',required=True)
    audit=sub.add_parser('audit');audit.add_argument('--output',required=True)
    args=parser.parse_args();out=Path(args.output).absolute()
    if any(p.is_symlink() for p in (out,*out.parents)):raise ValueError('NO_SYMLINK_OUTPUT')
    start=time.monotonic();cpu=time.process_time()
    if args.command=='run':
        from tests.test_commitment_quote_policy import execute_native_arm
        out.mkdir(parents=True,exist_ok=False)
        results=[execute_native_arm(arm,out/arm) for arm in ('fixed','ordinary','constructor')]
        (out/'RESULT.json').write_text(json.dumps({'results':results,'unknown_actual_costs':
            ['development','model','host','real acquisition','legal','supplier quotes'],
            'primary_enterprise_modified':False,'source_base':'607c18854db04dc3aa4adf242a4e3d1d9c629880'},indent=2)+'\n')
    receipts={arm:audit_packet(out/arm/'PUBLIC.json.gz') for arm in ('fixed','ordinary','constructor')}
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    report={'audit':receipts,'wall_seconds':time.monotonic()-start,
            'cpu_seconds_including_waited_children':time.process_time()-cpu+child.ru_utime+child.ru_stime}
    if args.command=='run':(out/'AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
