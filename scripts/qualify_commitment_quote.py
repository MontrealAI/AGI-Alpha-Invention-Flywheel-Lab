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

PACKET_FIELDS={'result','public_observation','manifest','native_export','source_hashes','delivered'}
RESULT_FIELDS={'accepted','actual_revenue_microUSD','arm','audit_accepted','before_successor',
               'buyer_buys','funding_decision','prepaid','price_microUSD','scope',
               'seed_can_fund_successor','successor_budget_microUSD','successor_funded',
               'summary','tamper_rejected','tax_basis','trailing_365_profit'}


def audit_registered_trade(packet, source):
    """Require the frozen contract, buyer budget, lifecycle and evidence scope."""
    from commercial.ledger import digest
    from commercial.terms_exact_v2 import prospective_terms
    from campaign.genesis_commitment001 import service
    r=packet['result'];selling=r['arm']!='fixed'
    name=service.DELIVERIES+'restore-first.json'
    if set(packet['delivered'])!=({name} if selling else set()):
        raise ValueError('REGISTERED_DELIVERY_INVENTORY_CHANGED')
    expected=[]
    if selling:
        artifact=packet['delivered'][name]
        terms=prospective_terms('first',r['price_microUSD'],18,10,residual=50_000_000)
        expected=[('wallet',{'buyer':'buyer-first','amount':3_500_000_000}),
                  ('register_terms',{'id':'first-terms','terms':terms}),
                  ('offer',{'buyer':'buyer-first','deadline':11,'id':'first',
                            'job_id':'restore-first','price':r['price_microUSD'],
                            'terms_id':'first-terms'})]
        for action in ('consent','fund','prepare','release'):
            args={'id':'first','action':action,'event_id':'first-'+action}
            if action=='prepare':args['artifact_sha256']=digest(artifact)
            expected.append(('event',args))
        expected.append(('mature',{'id':'first','event_id':'maturity:first:'+digest(terms)[:20]}))
        broken=dict(artifact);broken['request_id']='wrong'
        if service.verify_delivery(source,packet['manifest'],'restore-first',broken)['accepted']:
            raise ValueError('REGISTERED_TAMPER_PROBE_NOT_REJECTED')
    actual=[(a['op'],a['args']) for a in packet['native_export']['ledger']['actions'] if a['op']!='cost']
    if actual!=expected:raise ValueError('REGISTERED_TRADE_CONTRACT_CHANGED')
    if (r['prepaid'] is not selling or r['audit_accepted'] is not True or
            r['accepted'] is not selling or r['buyer_buys'] is not selling or
            r['tamper_rejected'] is not (True if selling else None) or
            r['successor_funded'] is not False or
            type(r['seed_can_fund_successor']) is not bool or
            type(r['actual_revenue_microUSD']) is not int or
            r['tax_basis']!='20 percent provision at first collection; no subsequent negative-tax credit assumed'):
        raise ValueError('REGISTERED_RESULT_PRESENTATION_CHANGED')


def audit_registered_costs(export, arm, price):
    """Bind a coherent native history to this experiment's frozen cost schedule.

    Native replay proves accounting consistency, not that an experiment paid all
    registered costs. Derive the required schedule independently of the producer
    and compare exact native amounts, identifiers, ordering and integer hours.
    """
    from commercial.ledger import digest
    actions=export['ledger']['actions']
    costs=[(a['day'],a['args']['id'],a['args']['amount'])
           for a in actions if a['op']=='cost']
    expected=[(0,'quote-setup',880_000_000),(1,'quote-acquisition',100_000_000)]
    sequence=[('cost',0),('cost',1)]
    spends=[e for e in export['connected_journal']['entries']
            if e['request']['operation']=='spend']
    if arm!='fixed':
        sequence.extend([('cost',3),('wallet',3),('register_terms',3),('offer',3),
                         ('event',3),('event',3),('event',7),('event',10),
                         ('cost',10),('cost',10),('mature',19)])
        required={'operation':'spend','id':'capacity-first','kind':'committed_delivery',
                  'amount':840_000_000,'day':3,'expected_net':1,'allow_seed':True,
                  'work':{'buyer':'buyer-first','order':'first','job':'restore-first',
                          'capacity':{'supplier':'shared-worker','start':4,'end':8,'units':1},
                          'costs':{'complete-first-production':840_000_000},'expected_net':1}}
        if (len(spends)!=1 or spends[0]['request']!=required or
                spends[0]['status']!='COMPLETE' or spends[0]['funding']!='SEED' or
                spends[0]['receipt']['native_event_sequence']!=2):
            raise ValueError('REGISTERED_PREPAID_COST_CHANGED')
        seed_id='connected014-seed-'+digest({'request':required,
            'source_sha256':spends[0]['receipt']['source_sha256']})[:32]
        expected.extend([(3,seed_id,840_000_000),(10,'payment',30_000_000),
                         (10,'tax-first',max(0,price-1_850_000_000)//5)])
    elif spends:
        raise ValueError('UNREGISTERED_FIXED_ARM_SPEND')
    expected.append((120,'closing',100_000_000));sequence.append(('cost',120))
    if costs!=expected or [(a['op'],a['day']) for a in actions]!=sequence:
        raise ValueError('REGISTERED_COST_SCHEDULE_CHANGED')


def audit_packet(path):
    # Only native canonical auditor and bound acceptance decide delivery/finance.
    from connected_enterprise.finance import audit_journal
    from commercial.ledger import strict_json, digest
    from campaign.genesis_commitment001 import service
    path=Path(path)
    with gzip.open(path,'rb') as stream:
        raw=stream.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('BOUNDED_ENGINEERING_PACKET_REQUIRED')
    p=strict_json(raw)
    if type(p) is not dict or set(p)!=PACKET_FIELDS or type(p['result']) is not dict or set(p['result'])!=RESULT_FIELDS:
        raise ValueError('EXACT_REGISTERED_PUBLIC_PACKET_REQUIRED')
    if any(type(p['result'][name]) is not int for name in
           ('price_microUSD','successor_budget_microUSD','actual_revenue_microUSD')):
        raise ValueError('EXACT_RESULT_MONEY_REQUIRED')
    from tests.test_commitment_quote_policy import public_observation
    from research.commitment_quote_policy import decide, successor_funding_decision
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
        if digest(p['result']['summary'])!=digest(p['native_export']['ledger']['summary']):
            raise ValueError('SUMMARY_NOT_NATIVE_BOUND')
        if p['native_export']['ledger']['config']['opening']!=100_000_000_000:
            raise ValueError('EXACT_DISPOSABLE_SEED_REQUIRED')
        if p['native_export']['ledger']['config']['contract']!='public-quote-fixture-'+arm:
            raise ValueError('ACCOUNT_ARM_BINDING_CHANGED')
        if type(p['native_export']['ledger']['config']['working']) is not int or p['native_export']['ledger']['config']['working']!=0:
            raise ValueError('REGISTERED_WORKING_RESERVE_CHANGED')
        audit_registered_costs(p['native_export'],arm,price)
        audit_registered_trade(p,source)
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
        if digest(p['result']['before_successor'])!=digest(before):raise ValueError('SUCCESSOR_SNAPSHOT_CHANGED')
        seed_possible=bool(before and before['available']-100_000_000>=990_000_000)
        if p['result']['seed_can_fund_successor']!=seed_possible:
            raise ValueError('SEED_COUNTERFACTUAL_CHANGED')
        if p['result']['successor_budget_microUSD']!=990_000_000:
            raise ValueError('SUCCESSOR_FULL_BUDGET_CHANGED')
        funding=successor_funding_decision(before['available'],before['unrestrictedEarned'],
                    100_000_000,990_000_000) if before else None
        if p['result']['funding_decision']!=funding:
            raise ValueError('KNOWN_UNPAID_WORK_OR_FUNDING_PRESENTATION_CHANGED')
        if funding and funding['decision']!='DEFER':
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
