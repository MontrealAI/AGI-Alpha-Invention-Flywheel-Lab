"""Lossless synthetic native-job/CSV seam; no journal or production dispatch rights.

Caller must pay the complete production envelope before prepare. A qualified
output is compatible with a native manifest, not automatically admitted to an
operating account or the engine's execute_funded method path.
"""
import csv
import json
from pathlib import Path
from commercial.ledger import read_bound,digest
from adaptive_enterprise.instruments import infer_plan,execute_plan,_semantics
from adaptive_enterprise.checkers import audit_delivery


def job_contract(root,manifest,job_id):
    rows=[j for j in manifest['jobs'] if j['id']==job_id]
    if len(rows)!=1 or rows[0]['service_id']!='reconciliation':raise ValueError('SCOPED_NATIVE_RECONCILIATION_JOB_REQUIRED')
    job=rows[0]
    return {'job_id':job_id,'input_sha256':job['input_sha256'],'artifact_sha256':job['artifact_sha256']}


def prepare(root,manifest,job_id,destination,mode):
    job_contract(root,manifest,job_id)
    job=next(j for j in manifest['jobs'] if j['id']==job_id)
    raw=read_bound(root,job['input'],job['input_sha256'])
    if raw.get('scope')!='SYNTHETIC_PUBLIC_WORKLOAD':raise ValueError('PUBLIC_SYNTHETIC_ONLY')
    if mode not in ('conventional','generated'):raise ValueError('UNQUALIFIED_NATIVE_METHOD')
    plan=infer_plan(raw,mode=mode)
    if plan['status']!='READY':raise ValueError('NATIVE_INTAKE_NOT_READY:'+str(plan['failure']))
    normalized=execute_plan(raw,plan)
    destination=Path(destination)
    if destination.exists() or destination.is_symlink() or any(x.is_symlink() for x in destination.parents):raise ValueError('CREATE_ONLY_NATIVE_CSV_INPUTS')
    destination.mkdir()
    contract={k:normalized[k] for k in ('order_id','scope','currency','require_complete')}
    (destination/'contract.json').write_text(json.dumps(contract))
    for table in ('invoices','payments'):
        fields=['id','customer','amount_cents']+(['invoice_refs'] if table=='payments' else [])+['currency']
        with (destination/(table+'.csv')).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for row in normalized[table]:
                item={**row,'currency':'USD'}
                if table=='payments':item['invoice_refs']=json.dumps(row['invoice_refs'])
                writer.writerow(item)
    return {'paths':{k:str(destination/(k+'.json' if k=='contract' else k+'.csv')) for k in ('contract','invoices','payments')},
            'raw':raw,'plan':plan,'normalized':normalized,'mode':mode,'job_contract':job_contract(root,manifest,job_id)}


def qualify(root,manifest,job_id,prepared,output):
    job=next(j for j in manifest['jobs'] if j['id']==job_id)
    raw=read_bound(root,job['input'],job['input_sha256'])
    plan=infer_plan(raw,mode=prepared['mode'])
    normalized=execute_plan(raw,plan)
    if raw!=prepared['raw'] or plan!=prepared['plan'] or normalized!=prepared['normalized'] or prepared['job_contract']!=job_contract(root,manifest,job_id):raise ValueError('NATIVE_INPUT_SEAM_CHANGED')
    report=json.loads((Path(output)/'production/reconciliation.json').read_text())
    saved=read_bound(root,job['artifact'],job['artifact_sha256'])
    if saved['method'] not in ('canonical','generated_schema') or saved['outcome_scope']!='complete_outcome':raise ValueError('NATIVE_MANIFEST_HAS_NO_COMPLETE_SERVICE_CONTRACT')
    artifact={'order_id':raw['order_id'],'service_id':'reconciliation','scope':raw['scope'],'currency':raw['currency'],
              'outcome_scope':'complete_outcome','method':saved['method'],'plan':plan,'normalized_input':normalized,'useful_outcome':report}
    checked=audit_delivery('reconciliation',raw,artifact)
    if not checked['accepted'] or digest(_semantics(artifact))!=digest(_semantics(saved)):
        raise ValueError('CSV_OUTPUT_NOT_EQUIVALENT_TO_NATIVE_MANIFEST')
    return {'accepted':True,'standard_artifact_sha256':digest(artifact),'semantic_sha256':digest(_semantics(artifact)),
            'saved_artifact_sha256':job['artifact_sha256'],'job_contract':prepared['job_contract'],
            'scope':'CHECKED_NATIVE_MANIFEST_SEMANTIC_COMPATIBILITY_NOT_OPERATING_ADOPTION'}


def verify_refusal(root,manifest,job_id,error):
    """Independent intake checker establishes why complete CSV service cannot run."""
    from adaptive_enterprise.instruments import check_job
    from adaptive_enterprise.checkers import _possible_mappings
    if not error.startswith('ValueError: NATIVE_INTAKE_NOT_READY:'):
        return {'verified':False,'scope':'UNCLASSIFIED_PAID_EXECUTION_FAILURE'}
    job=next(j for j in manifest['jobs'] if j['id']==job_id)
    raw=read_bound(root,job['input'],job['input_sha256'])
    admitted=check_job(root,manifest,job)
    possibilities=_possible_mappings(raw)
    if len(possibilities)==1 or admitted['artifact']['outcome_scope']!='intake_readiness':
        raise ValueError('NATIVE_INTAKE_REFUSAL_NOT_INDEPENDENTLY_REPRODUCED')
    return {'verified':True,'scope':'INDEPENDENT_NATIVE_INTAKE_CHECKER_REFUSAL',
            'reason':'No unique supported complete-service mapping','candidate_count':len(possibilities)}
