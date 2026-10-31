"""Native funded research wrapper around PR47, not an alternate enterprise ledger.

No default operating cutover: original native production admission remains required.
"""
import hashlib
import json
from pathlib import Path
import threading
import time
from commercial.ledger import digest
from .finance import source_identity
from mechanism_harness import core, operating027, study027

ARMS=('direct','equal_content','replanned','inherited')
FEES={'direct':10000,'equal_content':20000,'replanned':50000,'inherited':20000}
PRODUCTION=1500000
VERIFICATION=50000
LOCK=threading.RLock()


def binding(root):
    root=Path(root).resolve();executing=Path(__file__).resolve().parents[1]
    if Path(operating027.__file__).resolve()!=executing/'mechanism_harness/operating027.py' or Path(core.__file__).resolve()!=executing/'mechanism_harness/core.py':
        raise ValueError('EXECUTING_MODULE_TREE_MISMATCH')
    files=source_identity(root)['files']
    names=set(files)|set(operating027.SOURCE_FILES)|{'connected_enterprise/funded_csv_adapter028.py','connected_enterprise/native_csv_manifest028.py',
        'mechanism_harness/__init__.py','mechanism_harness/__main__.py','mechanism_harness/evidence.py',
        'mechanism_harness/experiment.py','mechanism_harness/study027.py'}
    for name in sorted(names):
        p=root/name;e=executing/name
        if not p.is_file() or any(x.is_symlink() for x in (p,*p.parents)) or not e.is_file() or p.read_bytes()!=e.read_bytes():
            raise ValueError('ROOT_DIFFERS_FROM_EXECUTING_SOURCE:'+name)
        files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'files':files,'sha256':digest(files)}


def paid_once(account,ident,kind,amount,day,work,allow_seed):
    if any(e['request'].get('id')==ident for e in account.export()['connected_journal']['entries']):
        raise ValueError('ALREADY_ATTEMPTED_NO_FREE_REEXECUTION')
    r=account.spend(ident,kind,amount,day,work,0,allow_seed=allow_seed)
    if r is None:raise ValueError('CURRENT_NATIVE_RESEARCH_FUNDS_INSUFFICIENT')
    rows=[e for e in account.export()['connected_journal']['entries'] if e['request'].get('id')==ident]
    if len(rows)!=1 or rows[0]['status']!='COMPLETE' or rows[0]['receipt']!=r or r['amount']!=amount:
        raise ValueError('NATIVE_PAYMENT_NOT_COMPLETED')
    return r


def run_funded(root,account,spec,plan,paths,output,*,arm,ident,day=0,allow_seed=False,native_manifest=None,native_job_id=None,native_policy=None,native_offer=None):
    """Same producer/checker in every arm; additional work explicitly prepaid.

    Includes full wrapper/source checks, planning, producer, extra replay and native
    audit in reported whole-invocation CPU/wall. USD envelopes are authored, not bills.
    """
    with LOCK:
        start_cpu=time.process_time_ns();start_wall=time.monotonic_ns()
        if arm not in ARMS:raise ValueError('DECLARED_MATCHED_ARM_REQUIRED')
        source=binding(root)
        native_contract=None;native_selection=None;prepared=None;qualified=None;refusal=None
        if native_manifest is not None:
            from . import native_csv_manifest028 as seam
            from .mechanism_choice import order_plan
            native_contract=seam.job_contract(root,native_manifest,native_job_id)
            if paths is not None or native_policy is None or native_offer is None or native_offer.get('service_id')!='reconciliation' or native_offer.get('method') not in ('canonical','generated_schema') or native_policy.get('cost_contract',{}).get('production_envelope_microUSD')!=PRODUCTION:
                raise ValueError('EXPLICIT_NATIVE_MANIFEST_COMMON_COST_SEAM_REQUIRED')
            inputs=native_contract
        else:inputs=operating027._frozen_inputs(paths)
        request={'schema':'funded-csv028-request/v1','source':source,'input_sha256':inputs,
                 'spec_sha256':digest(spec),'plan_sha256':digest(plan),'arm':arm,
                 'native_manifest_sha256':digest(native_manifest),'native_policy':native_policy,'native_offer':native_offer,
                 'scope':'EXPLICIT_SEED_FUNDED_RESEARCH_NOT_EARNED_BUSINESS',
                 'production_cost_basis':'COMMON_COMPLETE_SERVICE_ONCE_NOT_SYMBOLIC_COST_CONVERSION'}
        paid_once(account,ident+'-proposal','mechanism_proposal',FEES[arm],day,request,allow_seed)
        # Admission reuses PR47. No second compiler or expanded effect authority.
        operating027._validate_plan(spec,plan)
        selected=core.compose(spec) if arm=='replanned' else plan
        operating027._validate_plan(spec,selected)
        if native_manifest is not None:
            native_selection=order_plan(native_policy,native_job_id,native_offer,None,PRODUCTION)
            if native_selection['mode'] not in ('generated','conventional'):
                raise ValueError('NATIVE_METHOD_NOT_QUALIFIED_FOR_CSV_SEAM')
        production={**request,'native_selection':native_selection,'selected_plan_sha256':digest(selected),'common_production_envelope_microUSD':PRODUCTION}
        paid_once(account,ident+'-production','research_service_contract',PRODUCTION,day,production,allow_seed)
        error=None;receipt=None;check=None
        try:
            if native_manifest is not None:
                prepared=seam.prepare(root,native_manifest,native_job_id,Path(output).with_name(Path(output).name+'-inputs'),native_selection['mode'])
                paths=prepared['paths']
            if arm=='direct':receipt=study027._direct(paths,Path(output))
            else:receipt=operating027.execute(spec,selected,paths,output,execution_mode='inherited_existing_plan' if arm=='inherited' else 'composed')
        except (ValueError,KeyError,TypeError,OSError) as exc:
            error=type(exc).__name__+': '+str(exc)
        verification={**request,'production_receipt_sha256':digest(receipt),'error':error}
        paid_once(account,ident+'-verification','independent_service_replay',VERIFICATION,day,verification,allow_seed)
        if error is None:
            if arm=='direct':
                checked=operating027._audit_outputs(paths,output)
                if checked!=receipt['checker']:raise ValueError('DIRECT_RECEIPT_DIFFERS_FROM_FRESH_CHECK')
                check={'accepted':checked['accepted'],'scope':'FRESH_EXISTING_SERVICE_REDERIVATION'}
            else:check=operating027.verify(spec,selected,paths,output)
            if native_manifest is not None:qualified=seam.qualify(root,native_manifest,native_job_id,prepared,output)
        if error is not None and native_manifest is not None:
            refusal=seam.verify_refusal(root,native_manifest,native_job_id,error)
        current_inputs=seam.job_contract(root,native_manifest,native_job_id) if native_manifest is not None else operating027._frozen_inputs(paths)
        if binding(root)!=source or current_inputs!=inputs:
            raise ValueError('SOURCE_OR_INPUT_CHANGED')
        native=account.audit()
        if not native['accepted']:raise ValueError('NATIVE_ACCOUNT_AUDIT_REJECTED')
        artifact=Path(output)/'production/reconciliation.json'
        return {'schema':'funded-csv028-result/v1','arm':arm,'request_sha256':digest(request),
                'source':source,'input_sha256':inputs,'accepted':bool(check and check['accepted']),
                'independent_refusal':refusal,'native_manifest_qualification':qualified,'native_selected_mode':native_selection['mode'] if native_selection else None,
                'error':error,'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest() if error is None else None,
                'native_audit_accepted':True,'native_cost_microUSD':FEES[arm]+PRODUCTION+VERIFICATION,
                'proposal_microUSD':FEES[arm],'production_microUSD':PRODUCTION,'verification_microUSD':VERIFICATION,
                'whole_invocation_cpu_ns':time.process_time_ns()-start_cpu,'whole_invocation_wall_ns':time.monotonic_ns()-start_wall,
                'current_proof':None,'authority':[],'actual_profit':None,
                'scope':'NATIVE_FUNDED_SYNTHETIC_SERVICE_RESEARCH_NOT_OPERATING_ENTERPRISE_ADOPTION'}
