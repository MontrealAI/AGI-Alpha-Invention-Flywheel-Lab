#!/usr/bin/env python3
"""Actually export and autonomously import the public synthetic service cohort."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commercial.onboarding import prepare_delivery,prepare_order,synthetic_exports
from commercial.service import canonical,digest,reconcile
from commercial.service_verifier import audit_delivery


def relative(path): return str(Path(path).resolve().relative_to(ROOT))
def save(path,data):
    with Path(path).open('xb') as handle: handle.write(canonical(data))


def run(args):
    manifest_path=Path(args.manifest).resolve();manifest=json.loads(manifest_path.read_text())
    output=Path(args.output).resolve();relative(output);output.mkdir(parents=True,exist_ok=False)
    protocol={'schema':'agi-alpha/commercial010/onboarding-v1','scope':'SYNTHETIC_PUBLIC_EXPORTS_ACTUALLY_PARSED','source_manifest':relative(manifest_path),'source_manifest_sha256':digest(manifest_path),'source_files':{p:digest(ROOT/p) for p in ['commercial/onboarding.py','commercial/service.py','commercial/service_verifier.py','scripts/run_onboarding010.py']},'claim':'Agent creates synthetic CSVexports from existing frozen syntheticJSONrecords, autonomously parses explicitcontract and CSVdata to validatedJSON, compares exactcanonical identity, and reruns independentservicechecker. No customer export/access/attention observed.','payer_policy':{'agent_first_customer_setup':'Agent compute/tool/inference expense. Process timings measured; host monetary billing remainsUNKNOWN and belongs to completecost envelope. No humanstaffhour inserted.','buyer_attention_or_friction':'Separate conditional buyerutility cost, not ourstaffwage and not empirically zero. Actualcustomerattention unobserved.','external_fee':'Separate seller supplier/payment/channelfee when incurred or modeled. No newpaidexternaltransaction executed; sharedhoststorage/toolcost remains unmetered.'}}
    save(output/'PROTOCOL.json',protocol)
    jobs=[]
    for job in manifest['jobs']:
        source=ROOT/job['input']
        if digest(source)!=job['input_sha256']: raise ValueError('FROZEN_SOURCE_CHANGED')
        original=json.loads(source.read_text());jobdir=output/job['id'];jobdir.mkdir()
        wall=time.perf_counter_ns();cpu=time.process_time_ns()
        exports=synthetic_exports(original,jobdir/'synthetic-exports')
        export_time={'wall_seconds':(time.perf_counter_ns()-wall)/1e9,'cpu_seconds':(time.process_time_ns()-cpu)/1e9}
        wall=time.perf_counter_ns();cpu=time.process_time_ns()
        try:
            prepared=prepare_delivery(exports/'contract.json',exports/'invoices.csv',exports/'payments.csv',jobdir/'prepared')
            identity=canonical(prepared)==source.read_bytes()
            if not identity: raise RuntimeError('CANONICAL_ORDER_IDENTITY_FAILED')
            checker=audit_delivery(original,reconcile(prepared))
            prepared_path=jobdir/'prepared/prepared-order.json'
            receipt={'onboarding_accepted':True,'prepared_order':relative(prepared_path),'prepared_order_sha256':digest(prepared_path),'exact_source_identity':identity,'independent_service_accepted':checker['accepted'],'checker_receipt':checker}
        except ValueError as exc:
            receipt={'onboarding_accepted':False,'exact_source_identity':None,'independent_service_accepted':False,'rejection':str(exc)}
        receipt.update({'id':job['id'],'scope':protocol['scope'],'source_input':job['input'],'source_input_sha256':job['input_sha256'],'exports':{name:{'path':relative(exports/name),'sha256':digest(exports/name)} for name in ['contract.json','invoices.csv','payments.csv']},'export_work':export_time,'agent_import_work':{'wall_seconds':(time.perf_counter_ns()-wall)/1e9,'cpu_seconds':(time.process_time_ns()-cpu)/1e9},'human_intervention_seconds':0,'agent_host_bill_usd':None,'buyer_attention_observed':False,'new_paid_external_transactions':0})
        if receipt['independent_service_accepted']!=job['accepted']: raise RuntimeError('COHORT_ACCEPTANCE_CHANGED')
        save(jobdir/'RECEIPT.json',receipt);jobs.append(receipt)
    probe_dir=output/'malformed-probe'
    base=json.loads((ROOT/manifest['jobs'][0]['input']).read_text());exports=synthetic_exports(base,probe_dir)
    (exports/'invoices.csv').write_text('id,id,amount_cents,currency\na,b,100,USD\n')
    try:
        prepare_order(exports/'contract.json',exports/'invoices.csv',exports/'payments.csv')
        raise RuntimeError('MALFORMED_HEADER_ACCEPTED')
    except ValueError as exc:
        probe={'scope':protocol['scope'],'outcome':'REJECTED','reason':str(exc),'files':{name:{'path':relative(exports/name),'sha256':digest(exports/name)} for name in ['contract.json','invoices.csv','payments.csv']}}
    save(output/'MALFORMED_PROBE.json',probe)
    summary={'schema':'agi-alpha/commercial010/onboarding-result-v1','scope':protocol['scope'],'source_manifest_sha256':digest(manifest_path),'jobs':jobs,'orders':len(jobs),'onboarding_accepted':sum(j['onboarding_accepted'] for j in jobs),'input_rejected':sum(not j['onboarding_accepted'] for j in jobs),'independent_service_accepted':sum(j['independent_service_accepted'] for j in jobs),'canonical_identity_matches':sum(j['exact_source_identity'] is True for j in jobs),'agent_import_cpu_seconds':sum(j['agent_import_work']['cpu_seconds'] for j in jobs),'agent_import_wall_seconds':sum(j['agent_import_work']['wall_seconds'] for j in jobs),'agent_host_bill_usd':None,'human_intervention_seconds':0,'buyer_attention_observed':False,'new_paid_external_transactions':0,'malformed_probe':probe,'scope_limit':'PreparedCSVworkflow is realsoftwareexecution on syntheticexports. It does not establishcustomerfriction, actualpriceacceptance or paidcommercialservice.'}
    save(output/'RESULT.json',summary)
    print(json.dumps({k:summary[k] for k in ['orders','onboarding_accepted','input_rejected','independent_service_accepted','canonical_identity_matches','agent_import_cpu_seconds','agent_import_wall_seconds']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',default='campaign/commercial-010/service/executed-002/manifest.json');parser.add_argument('--output',required=True);run(parser.parse_args())
