"""Source-bound retrospective sensor club: bounded *simulated* complete commerce.

The economic terms, buyer preferences and observations are deliberately authored.
Native receipts are created exclusively via the repository's JournalAccount.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, time
from pathlib import Path

SCHEMA = 'agi-alpha/retroactive-market062/v1'
MICRO = 1_000_000
ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def dump(path, obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():raise FileExistsError('IMMUTABLE_OUTPUT_REQUIRED')
    p.write_text(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def protocol():
    return {'schema':SCHEMA,'scope':'FINITE_SYNTHETIC_AUTHORED_ECONOMIC_EXPERIMENT',
            'opening_microUSD':100_000*MICRO,'working_microUSD':0,
            'initial_buyers':['A','B'],'successor_buyer':'C',
            'buyers':{x:{'valuation_microUSD':1800*MICRO,'budget_microUSD':1500*MICRO,
                         'best_complete_outside_microUSD':2100*MICRO} for x in 'ABC'},
            'quote_microUSD':1500*MICRO,'prices_external_observed':False,
            'fixed_shared':{'archive_setup':1650*MICRO,'failed_search':150*MICRO,'support_and_maintenance':150*MICRO},
            'fixed_per_independent_buyer':1650*MICRO,
            'per_order':{'acquisition':100*MICRO,'production':160*MICRO,
                         'independent_check':120*MICRO,'payment_support_risk':60*MICRO},
            'earned_only_successor_adapter_microUSD':120*MICRO,
            'stage1_tax_microUSD':17*MICRO,'stage2_tax_microUSD':106*MICRO,
            'no_bid_search_microUSD':60*MICRO,'cheap_rival_microUSD':1400*MICRO,
            'seed':2611010621,
            'guardrails':['No real buyer, payments or outside cost measurements','Historical source inputs are synthetic and not physically validated','Cost allocations and willingness-to-pay are conditional hypotheses','No outside provider contracts or third-party data rights are claimed','Actual host/model billing unknown, no annualization','Direct control and shared arm each have a fresh native 100K account']}


def streams():
    # Flat made-up source rows with discontinuities, nulls and a duplicate.
    return {'temperature':[{'id':f'T{i}','time':i,'value':v} for i,v in enumerate([29,33,35,28,36,30,40,34])],
            'humidity':[{'id':f'H{i}','time':i,'value':v} for i,v in enumerate([64,71,78,80,76,69,75,77]) if i!=5]
                       +[{'id':'H3-copy','time':3,'value':80}],
            'flow':[{'id':f'F{i}','time':i,'value':v} for i,v in enumerate([22,19,24,20,31,18,32,27])],
            'pressure':[{'id':f'P{i}','time':i,'value':v} for i,v in enumerate([48,50,47,52,44,53,43,46]) if i!=1]}


def request(buyer):
    if buyer=='A':return {'id':'A','domain':'building-heat','left':'temperature','right':'humidity','left_min':32,'right_min':70,'times':list(range(8))}
    if buyer=='B':return {'id':'B','domain':'road-heat','left':'temperature','right':'humidity','left_min':34,'right_min':75,'times':list(range(8))}
    if buyer=='C':return {'id':'C','domain':'leakage-anomaly','left':'flow','right':'pressure','left_min':25,'right_max':47,'times':list(range(8))}
    raise ValueError('UNADMITTED_QUESTION')


def construct(req, raw):
    """New question-defined series; never infer an event from missing/duplicate rows."""
    if set(req['times'])!=set(range(8)) or len(req['times'])!=8:raise ValueError('FIXED_EIGHT_OBSERVATION_TIMES_REQUIRED')
    lookups={}
    for side in ('left','right'):
        name=req[side];rows=raw[name];indexed={}
        for row in rows:indexed.setdefault(row['time'],[]).append(row)
        lookups[side]=indexed
    result=[]
    for t in req['times']:
        left,right=lookups['left'].get(t,[]),lookups['right'].get(t,[])
        if len(left)!=1 or len(right)!=1 or any(type(x['value']) not in (int,float) for x in left+right):
            label='UNKNOWN';references=[]
        else:
            a,b=left[0]['value'],right[0]['value']
            ok=a>=req['left_min'] and (b>=req['right_min'] if 'right_min' in req else b<=req['right_max'])
            label='EVENT' if ok else 'NO_EVENT';references=[left[0]['id'],right[0]['id']]
        result.append({'time':t,'status':label,'source_ids':references})
    return {'schema':'agi-alpha/historical-sensor062/v1','question':req,
            'source_names':[req['left'],req['right']],
            'source_sha256':{name:digest(raw[name]) for name in (req['left'],req['right'])},
            'measurements':result,'event_count':sum(x['status']=='EVENT' for x in result),
            'unknown_count':sum(x['status']=='UNKNOWN' for x in result),
            'source_scope':'SYNTHETIC_NOT_PHYSICAL_GROUND_TRUTH'}


def deal_decision(p, cohort, *, rival_price=None):
    if set(cohort) != set(p['initial_buyers']) or len(cohort)!=2:
        return {'choice':'NO_BID','reason':'TWO_INDEPENDENT_SPONSORS_REQUIRED'}
    for name in cohort:
        b=p['buyers'][name]
        if b['valuation_microUSD']<p['quote_microUSD'] or b['budget_microUSD']<p['quote_microUSD']:
            return {'choice':'NO_BID','reason':'BUYER_CANNOT_VOLUNTARILY_FUND'}
        if b['best_complete_outside_microUSD']<=p['quote_microUSD'] or (rival_price is not None and rival_price<=p['quote_microUSD']):
            return {'choice':'NO_BID','reason':'BETTER_BUYER_OUTSIDE_OPTION'}
    return {'choice':'SHARED_CONTRACT','reason':'ALL_SPONSORS_HAVE_POSITIVE_BEST_OUTSIDE_SURPLUS_ADVANTAGE',
            'buyer_surplus_microUSD':{k:p['buyers'][k]['valuation_microUSD']-p['quote_microUSD'] for k in cohort}}


def make_manifest(root, out, buyers, raw):
    """Use the existing source-bound evidence_matrix service, not an invented ledger."""
    from enterprise.services import SCOPE,SOURCE_PATHS,produce,load_jobs
    from enterprise.checkers import audit_delivery
    source={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in SOURCE_PATHS}
    jobs=[];measurements={}
    for name in buyers:
        measurement=construct(request(name),raw)
        from experiments.retroactive_market062_verify import check_measurement
        check_measurement(request(name),raw,measurement)
        measurement_path=f'payloads/{name}-measurement.json'
        dump(out/measurement_path,measurement)
        measurements[name]={'path':measurement_path,'sha256':digest(measurement),
                            'events':measurement['event_count'],'unknown':measurement['unknown_count']}
        sources=[{'id':f'M-{name}-{x["time"]}', 'key':f'time-{x["time"]}',
                  'value':f'{x["status"]} at t={x["time"]}; ids={",".join(x["source_ids"]) or "none"}'}
                 for x in measurement['measurements']]
        order={'order_id':f'evidence_matrix-market062-{name}', 'scope':SCOPE,'currency':'USD',
               'sources':sources,'requirements':[{'id':f'R{j}','key':f'time-{j}'} for j in range(8)]}
        artifact=produce('evidence_matrix',order)
        accepted=audit_delivery('evidence_matrix',order,artifact)
        if not accepted['accepted']:raise ValueError('NATIVE_EVIDENCE_ACCEPTANCE_FAILED')
        base=f'payloads/{name}'
        paths={key:f'{base}/{key}.json' for key in ['input','artifact','receipt']}
        i_sha=dump(out/paths['input'],order);a_sha=dump(out/paths['artifact'],artifact)
        receipt={**accepted,'input_sha256':i_sha,'artifact_sha256':a_sha,
                 'checker_source_sha256':source['enterprise/checkers.py'],
                 'execution':'Actual deterministic tool execution on synthetic authorized inputs; no model inference call.'}
        r_sha=dump(out/paths['receipt'],receipt)
        jobs.append({'id':order['order_id'],'service_id':'evidence_matrix','accepted':True,
                     'input':str((out/paths['input']).relative_to(root)), 'input_sha256':i_sha,
                     'artifact':str((out/paths['artifact']).relative_to(root)),'artifact_sha256':a_sha,
                     'receipt':str((out/paths['receipt']).relative_to(root)),'receipt_sha256':r_sha})
    manifest={'schema':'agi-alpha/enterprise011-services/v1','scope':SCOPE,'currency':'USD',
              'source_hashes':source,'jobs':jobs,'attempts':[],
              'resource_receipt':{'scope':'SYNTHETIC_AND_METERED_CPU','model_calls':0,'full_model_host_billing':'UNKNOWN'},
              'acceptance_contracts':{'evidence_matrix':'Native exact supported evidence; independent measurement audit checks raw source join.'}}
    load_jobs(root,manifest)
    return manifest,measurements


def _pay(account,buyer,job,price,day):
    order='market062-'+buyer
    account.execute('wallet',{'buyer':buyer,'amount':price},day)
    account.execute('offer',{'id':order,'buyer':buyer,'price':price,'job_id':job,'deadline':day+10},day)
    for stage in ('consent','fund'):
        account.execute('event',{'id':order,'action':stage,'event_id':order+'-'+stage},day)
    return order


def _deliver(account,order,buyer,terms,day, *, bespoke=False):
    for kind,value in terms['per_order'].items():account.cost(order+'-'+kind,value,day)
    if bespoke:account.cost(order+'-bespoke-source-setup',terms['fixed_per_independent_buyer'],day)
    for stage in ('prepare','release'):
        account.execute('event',{'id':order,'action':stage,'event_id':order+'-'+stage},day)
    return account.snapshot()['summary']


def run(root, output):
    from connected_enterprise.finance import JournalAccount
    root=Path(root).resolve();output=Path(output).resolve()
    if output.exists():raise FileExistsError('NEW_FROZEN_OUTPUT_REQUIRED')
    if root not in output.parents:raise ValueError('OUTPUT_MUST_BE_IN_CURRENT_REPOSITORY')
    output.mkdir(parents=True)
    p=protocol();raw=streams();start=time.process_time()
    dump(output/'PROTOCOL.json',p)
    dump(output/'ARCHIVES.json',raw)
    # Source-bounded native manifest, fresh account per comparison. Buyer funds aren't revenue.
    manifest,measurement=make_manifest(root,output,['A','B','C'],raw)
    dump(output/'MANIFEST.json',manifest)
    results={}
    for arm in ('direct','shared','cheap_rival'):
        account=JournalAccount(root,manifest,output/(arm+'.sqlite'),opening=p['opening_microUSD'],working=0,contract='market062-'+arm)
        sales=[];earned=None
        if arm=='cheap_rival':
            decision=deal_decision(p,['A','B'],rival_price=p['cheap_rival_microUSD'])
            account.cost('cheap-rival-prospecting',p['no_bid_search_microUSD'],0)
        else:
            decision=deal_decision(p,['A','B'])
            if arm=='shared':
                for ident,amount in p['fixed_shared'].items():account.cost('shared-'+ident,amount,0)
            else:
                for ident in ('failed_search','support_and_maintenance'):
                    account.cost('direct-'+ident,p['fixed_shared'][ident],0)
            # Two prospective buyers explicitly fund their separate native orders.
            orders={k:_pay(account,k,'evidence_matrix-market062-'+k,p['quote_microUSD'],0) for k in 'AB'}
            for day,k in enumerate('AB',1):
                _deliver(account,orders[k],k,p,day,bespoke=arm=='direct')
                sales.append({'id':orders[k],'day':day,'status':'ACCEPTED_AND_COLLECTED','artifact':measurement[k],
                              'native_collection_microUSD':p['quote_microUSD']})
            if arm=='shared':
                account.cost('first-stage-profit-tax',p['stage1_tax_microUSD'],2)
                after_two=copy.deepcopy(account.snapshot()['summary'])
                # The native account must classify the successor instrument purchase as EARNED.
                earned=account.spend(ident='third-sensor-adapter',kind='new_archival_signal_instrument',
                     amount=p['earned_only_successor_adapter_microUSD'],day=3,
                     work={'source_measurement':['A','B'],'new_domain':'leakage-anomaly',
                           'new_archives':['flow','pressure'],'expected_successor':'C'},
                     expected_net=834*MICRO,allow_seed=False)
                if earned is None or earned.get('funding')!='EARNED':
                    raise ValueError('NO_EARNINGS_FUNDED_EXPANSION')
                successor=_pay(account,'C','evidence_matrix-market062-C',p['quote_microUSD'],4)
                _deliver(account,successor,'C',p,4)
                account.cost('second-stage-profit-tax',p['stage2_tax_microUSD'],4)
                sales.append({'id':successor,'day':4,'status':'ACCEPTED_AND_COLLECTED','artifact':measurement['C'],
                              'native_collection_microUSD':p['quote_microUSD']})
            else:after_two=copy.deepcopy(account.snapshot()['summary'])
        evidence=account.export();checked=account.audit();summary=copy.deepcopy(account.snapshot()['summary']);account.close()
        if checked.get('accepted') is not True:raise ValueError('NATIVE_FINANCIAL_AUDIT_REJECTED')
        if summary['profit'] != summary['collections']-summary['expenses']-summary.get('refunds',0):
            raise ValueError('NATIVE_PROFIT_EQUATION_FAILED')
        if summary['cash']!=p['opening_microUSD']+summary['profit']:
            raise ValueError('NO_OTHER_CASH_SOURCE_ALLOWED')
        results[arm]={'decision':decision,'summary':summary,'after_two':after_two if arm!='cheap_rival' else None,
                      'sales':sales,'earned_receipt':earned,'native_audit':{'accepted':True},'owner_export_sha256':digest(evidence)}
        dump(output/(arm+'.export.json'),evidence)
    report={'schema':SCHEMA,'protocol_sha256':digest(p),'archive_sha256':digest(raw),
            'manifest_sha256':digest(manifest),'measurements':measurement,'arms':results,
            'process_cpu_seconds':time.process_time()-start,
            'conclusions':{'shared_positive':results['shared']['summary']['profit']>0,
                           'matched_direct_negative':results['direct']['summary']['profit']<0,
                           'earned_funded':results['shared']['earned_receipt']['funding']=='EARNED',
                           'cheap_rival_no_bid':results['cheap_rival']['decision']['choice']=='NO_BID',
                           'actual_revenue_microUSD':0,'real_demand_observed':False,
                           'complete_actual_host_cost_known':False,
                           'recursive_or_market_novelty_proven':False,
                           'successor_output_preconstructed_for_native_registration':True,
                           'causal_necessity_of_adapter_not_proven':True,
                           'ordinary_pooled_rival_excluded':False},
            'sensitivity':{'ten_percent_fixed_cost_overrun_stage1_profit_microUSD':int(2*p['quote_microUSD']-sum(p['fixed_shared'].values())*110//100-2*sum(p['per_order'].values())-p['stage1_tax_microUSD']),
                           'first_stage_profit_hurdle_microUSD':p['earned_only_successor_adapter_microUSD']}}
    dump(output/'RESULT.json',report)
    return report


def verify(root,output):
    from connected_enterprise.finance import audit_journal
    from experiments.retroactive_market062_verify import check_measurement, check_native_claim_binding, check_public_economic_claims
    root=Path(root).resolve();output=Path(output).resolve()
    p=json.loads((output/'PROTOCOL.json').read_text())
    if p!=protocol():raise ValueError('PROTOCOL_TAMPERED')
    raw=json.loads((output/'ARCHIVES.json').read_text())
    if raw!=streams():raise ValueError('ARCHIVE_INPUT_TAMPERED')
    manifest=json.loads((output/'MANIFEST.json').read_text())
    report=json.loads((output/'RESULT.json').read_text())
    for k in 'ABC':
        record=json.loads((output/('payloads/'+k+'-measurement.json')).read_text())
        check_measurement(request(k),raw,record)
        if digest(record)!=report['measurements'][k]['sha256']:raise ValueError('SENSOR_FINGERPRINT_MISMATCH')
    for arm in ('direct','shared','cheap_rival'):
        exported=json.loads((output/(arm+'.export.json')).read_text())
        checked=audit_journal(exported,root=root,manifest=manifest)
        if checked.get('accepted') is not True:raise ValueError('INDEPENDENT_NATIVE_AUDIT_FAILED')
        entry=report['arms'][arm]
        if digest(exported)!=entry['owner_export_sha256'] or exported['ledger']['summary']!=entry['summary']:
            raise ValueError('NATIVE_ACCOUNT_SUMMARY_MISMATCH')
        check_native_claim_binding(arm, exported, entry, report['measurements'], p)
    shared,direct,adverse=(report['arms'][k] for k in ('shared','direct','cheap_rival'))
    if not(shared['summary']['profit']>0 and direct['summary']['profit']<0 and
           adverse['summary']['collections']==0 and shared['after_two']['profit']>0 and
           shared['earned_receipt']['funding']=='EARNED'):
        raise ValueError('CONNECTED_ECONOMIC_BOUNDARY_NOT_DEMONSTRATED')
    if (report['protocol_sha256'],report['archive_sha256'],report['manifest_sha256'])!=(digest(p),digest(raw),digest(manifest)):
        raise ValueError('STATED_EVIDENCE_BOUNDARY_CHANGED')
    check_public_economic_claims(report, p)
    return {'status':'PASSED_CONDITIONAL_SIMULATION_ONLY','shared_profit_microUSD':shared['summary']['profit'],
            'direct_profit_microUSD':direct['summary']['profit'],
            'no_bid_profit_microUSD':adverse['summary']['profit'],
            'after_two_profit_microUSD':shared['after_two']['profit'],
            'earned_funded_instrument_microUSD':shared['earned_receipt']['amount'],
            'native_account_audits':3,'actual_customer_collections':0,
            'customer_pricing_calibrated':False,'physical_sensor_validated':False}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['run','verify']);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv);result=run(ROOT,args.output) if args.operation=='run' else verify(ROOT,args.output)
    print(json.dumps(result if args.operation=='verify' else result['conclusions'],indent=2,sort_keys=True))

if __name__=='__main__':main()
