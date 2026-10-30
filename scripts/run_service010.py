#!/usr/bin/env python3
"""Execute the complete public synthetic reconciliation cohort, never commerce."""
import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from commercial.service import SCOPE, canonical, deliver, digest, reconcile
from commercial.service_verifier import audit_delivery
FAMILIES = ('referenced', 'split', 'bundled', 'unique_implicit', 'partial', 'ambiguous_amount', 'overlapping_refs', 'customer_isolation')
SEEDS = {'development_synthesis': tuple(range(101,109)), 'engineering_replication': tuple(range(901,909))}


def make_order(order_id, family, seed):
    r=random.Random(seed)
    order={'scope':SCOPE,'currency':'USD','order_id':order_id,'require_complete':family not in ('partial','ambiguous_amount','overlapping_refs'),'invoices':[],'payments':[]}
    inv,pay=order['invoices'],order['payments']
    def invoice(i,amount,customer='focus'): inv.append({'id':i,'customer':customer,'amount_cents':amount})
    def payment(p,amount,refs,customer='focus'): pay.append({'id':p,'customer':customer,'amount_cents':amount,'invoice_refs':refs})
    for k in range(5):
        amount=r.randrange(1001,50000)
        invoice(f'i{k}',amount,f'customer-{k}'); payment(f'p{k}',amount,[f'i{k}'],f'customer-{k}')
    a,b=r.randrange(5000,20000),r.randrange(20001,40000)
    if family=='referenced': invoice('focus1',a); payment('focusp1',a,['focus1'])
    elif family=='split':
        invoice('focus1',a); payment('focusp1',a//3,['focus1']); payment('focusp2',a-a//3,['focus1'])
    elif family=='bundled':
        invoice('focus1',a); invoice('focus2',b); payment('focusp1',a+b,['focus1','focus2'])
    elif family=='unique_implicit': invoice('focus1',a); payment('focusp1',a,[])
    elif family=='partial': invoice('focus1',a); payment('focusp1',a-1,['focus1'])
    elif family=='ambiguous_amount':
        invoice('focus1',a); invoice('focus2',a); payment('focusp1',a,[])
    elif family=='overlapping_refs':
        invoice('focus1',a); invoice('focus2',b); payment('focusp1',a,['focus1']); payment('focusp2',a+b,['focus1','focus2']); payment('focusp3',b,[])
    elif family=='customer_isolation':
        invoice('focus1',a); invoice('focus2',a,'other'); payment('focusp1',a,[]); payment('focusp2',a,[],'other')
    else: raise ValueError('unknown family')
    r.shuffle(inv); r.shuffle(pay)
    return order


def scale_order(order, seed, target_rows=1000):
    family_complete = ('referenced','split','bundled','unique_implicit','customer_isolation')
    family_all = FAMILIES
    family_pool = family_complete if order['require_complete'] else family_all
    scaled = {k:v for k,v in order.items() if k not in ('invoices','payments')}
    scaled.update(invoices=[], payments=[])
    remaining = target_rows
    block = 0
    while remaining >= 30:
        family = family_pool[block % len(family_pool)]
        sample = make_order('block',family,seed*10000+block)
        prefix = f'b{block}-'
        for row in sample['invoices']:
            scaled['invoices'].append(dict(row,id=prefix+row['id'],customer=prefix+row['customer']))
        for row in sample['payments']:
            scaled['payments'].append(dict(row,id=prefix+row['id'],customer=prefix+row['customer'],invoice_refs=[prefix+x for x in row['invoice_refs']]))
        remaining -= len(sample['invoices'])+len(sample['payments'])
        block += 1
    if remaining % 2:
        scaled['invoices'].append({'id':'tail-split-i','customer':'tail-split','amount_cents':1003})
        scaled['payments'].extend([{'id':'tail-split-p1','customer':'tail-split','amount_cents':400,'invoice_refs':['tail-split-i']},{'id':'tail-split-p2','customer':'tail-split','amount_cents':603,'invoice_refs':['tail-split-i']}])
        remaining -= 3
    for k in range(remaining//2):
        scaled['invoices'].append({'id':f'tail-i{k}','customer':f'tail-{k}','amount_cents':10001+k*3})
        scaled['payments'].append({'id':f'tail-p{k}','customer':f'tail-{k}','amount_cents':10001+k*3,'invoice_refs':[f'tail-i{k}']})
    random.Random(seed).shuffle(scaled['invoices']); random.Random(seed+1).shuffle(scaled['payments'])
    if len(scaled['invoices'])+len(scaled['payments']) != target_rows: raise ValueError('row scaling invariant')
    return scaled


def naive_attempt(order):
    """Preserved unsafe first-match counterexample; used only as rejection probe."""
    report=reconcile(order); iid,pid='focus1','focusp1'
    amount=next(x['amount_cents'] for x in order['invoices'] if x['id']==iid)
    report['matches'].append({'invoice_ids':[iid],'payment_ids':[pid],'invoice_cents':amount,'payment_cents':amount,'status':'MATCHED'})
    report['unmatched_invoices'].remove(iid); report['unmatched_payments'].remove(pid)
    report['exceptions']=[x for x in report['exceptions'] if x['id'] not in (iid,pid)]
    for key in ('matched_invoice_cents','matched_payment_cents'): report['totals'][key]+=amount
    for key in ('open_invoice_cents','unallocated_payment_cents'): report['totals'][key]-=amount
    return report


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle: handle.write(canonical(value))


def run(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    def relative(path):
        try: return str(path.relative_to(ROOT))
        except ValueError: return str(path)
    protocol={'version':'reconciliation010-v2-1000rows','scope':SCOPE,'source_provenance':'All order records authored synthetic public workload; no client records, outreach or payment execution.','families':list(FAMILIES),'seeds':{k:list(v) for k,v in SEEDS.items()},'frozen_before_execution':True,'source_hashes':{p:digest(ROOT/p) for p in ['commercial/service.py','commercial/service_verifier.py','scripts/run_service010.py']},'acceptance':'Independent exact partition, arithmetic, reference/customer safety and required safe matches. Exception findings accepted only if original order require_complete=false. Strict unmatched orders rejected.','confirmation_scope':'Previously exposed case families and seed sets expanded to1000rows perjob. Engineering replication only; no fresh holdout or population inference. Blocks independent by unique customer/id namespaces.', 'source_rows_per_order':1000,'human_intervention_seconds':0,'model_usage':{'runtime':'system-provided agent execution; exact routed model/version and host token metering unavailable','tokens':None,'billing':'UNKNOWN; use separately declared conservative cost intervals, never zero'},'post_delivery_obligations':{'scope':'No record modification, tax filing, attestation, financial advice or funds movement; correction of arithmetic/classification defects only.','modeled_support_days':7,'market_cost_owner':'market complete-cost interval includes support, acquisition, setup, failures and maintenance'}}
    write(output/'PROTOCOL.json',protocol)
    jobs,attempts,orders=[],[],[]
    for lane,seeds in SEEDS.items():
        for ix,(family,seed) in enumerate(zip(FAMILIES,seeds),1): orders.append((lane,family,scale_order(make_order(f'{lane}-{ix:02d}',family,seed),seed)))
    invalid=scale_order(make_order('rejected-currency','referenced',1201),1201); invalid['currency']='CAD'
    negative=scale_order(make_order('rejected-reversal','referenced',1202),1202); negative['payments'][0]['amount_cents']=-1
    strict=scale_order(make_order('rejected-strict-ambiguity','ambiguous_amount',1203),1203); strict['require_complete']=True
    orders.extend([('boundary','unsupported_currency',invalid),('boundary','unsupported_reversal',negative),('boundary','strict_unresolved',strict)])
    for lane,family,order in orders:
        job_dir=output/order['order_id']; job_dir.mkdir(); input_path=job_dir/'order.json'; write(input_path,order)
        if order['order_id']=='development_synthesis-06':
            probe=make_order('unsafe-first-match-probe','ambiguous_amount',10106)
            write(job_dir/'attempt-000-input.json',probe)
            bad=naive_attempt(probe); bad_path=job_dir/'attempt-000-unsafe-first-match.json'; write(bad_path,bad)
            bad_receipt=audit_delivery(probe,bad); write(job_dir/'attempt-000-rejection.json',bad_receipt)
            if bad_receipt['accepted']: raise RuntimeError('checker accepted unsafe ambiguity probe')
            attempts.append({'id':order['order_id']+'-attempt-000','job':order['order_id'],'stage':'verification','outcome':'REJECTED','artifact':relative(bad_path),'artifact_sha256':digest(bad_path),'reason':bad_receipt['errors'],'repair_constraint':'Never allocate unreferenced equal-amount payments when invoice or payment mapping is ambiguous; preserve exception schedule.','provenance':'Agent-authored unsafe-first-match counterexample; supplied test, not autonomous invention.'})
        start=time.perf_counter_ns(); cpu_start=time.process_time_ns()
        try: report=deliver(order,job_dir/'delivery'); path=job_dir/'delivery/reconciliation.json'
        except ValueError as exc:
            report={'order_id':order['order_id'],'scope':SCOPE,'currency':order.get('currency'),'accepted':False,'rejection':str(exc)}
            path=job_dir/'rejection.json'; write(path,report)
        receipt=audit_delivery(order,report)
        elapsed=time.perf_counter_ns()-start; cpu_ns=time.process_time_ns()-cpu_start
        receipt.update({'artifact_sha256':digest(path),'input_file_sha256':digest(input_path),'checker_source_sha256':digest(ROOT/'commercial/service_verifier.py'),'wall_seconds':elapsed/1e9,'cpu_seconds':cpu_ns/1e9})
        receipt_path=job_dir/'acceptance.json'; write(receipt_path,receipt)
        attempts.append({'id':order['order_id']+'-attempt-001','job':order['order_id'],'stage':'production_verification_delivery','outcome':'ACCEPTED' if receipt['accepted'] else 'REJECTED','artifact':relative(path),'artifact_sha256':digest(path),'wall_seconds':elapsed/1e9,'cpu_seconds':cpu_ns/1e9})
        jobs.append({'id':order['order_id'],'scope':SCOPE,'lane':lane,'family':family,'input':relative(input_path),'input_sha256':digest(input_path),'artifact':relative(path),'artifact_sha256':digest(path),'accepted':receipt['accepted'],'receipt':relative(receipt_path),'receipt_sha256':digest(receipt_path),'market_disposition':'UNALLOCATED; selected only by separate simulated market','human_intervention_seconds':0})
    manifest={'version':'reconciliation010-v2-1000rows','scope':SCOPE,'jobs':jobs,'attempts':attempts,'accepted_count':sum(j['accepted'] for j in jobs),'rejected_count':sum(not j['accepted'] for j in jobs),'orders_count':len(jobs),'host_token_billing':'UNKNOWN','actual_customers':0,'actual_collections_usd':0,'observed_commercial_flywheel':'NOT_ESTABLISHED','source_freeze':relative(output/'PROTOCOL.json'),'source_freeze_sha256':digest(output/'PROTOCOL.json'),'cost_rule':'Every job and failed attempt is included in modeled whole-cohort complete costs; actual host billing remains unknown.','reproduction':'python scripts/run_service010.py --output <new-output-directory>'}
    write(output/'manifest.json',manifest)
    print(json.dumps({'manifest':relative(output/'manifest.json'),'accepted':manifest['accepted_count'],'rejected':manifest['rejected_count'],'attempts':len(attempts),'scope':SCOPE}))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True); run(parser.parse_args().output)
