"""Executable, source-bound P0 synthetic-service comparison; not calibrated commerce."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from .core import audit, capability_capsule, compose, digest, canonical
from .operating027 import execute, verify, _regular, _load_json, _frozen_inputs, _sources, sha

CASES = ('complete', 'ambiguous', 'composite')


def _inputs(root, case):
    d=Path(root)/'campaign/mechanism-harness-027/cases'/case
    return {'contract':str(d/'contract.json'),'invoices':str(d/'invoices.csv'),'payments':str(d/'payments.csv')}


def _direct(paths, destination):
    """Strong direct existing P0 route; no planner and no invented additional operators."""
    from commercial.onboarding import prepare_order
    from commercial.service import deliver, canonical as service_canonical
    from commercial.service_verifier import audit_delivery
    from .operating027 import _csv_expected
    started_cpu,started_wall=time.process_time_ns(),time.monotonic_ns()
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    order=prepare_order(paths['contract'],paths['invoices'],paths['payments'])
    (destination/'prepared-order.json').write_bytes(service_canonical(order))
    report=deliver(order,destination/'production')
    checked=audit_delivery(order,report)
    if (destination/'production/exceptions.csv').read_bytes()!=_csv_expected(report):raise ValueError('DIRECT_EXCEPTION_SCHEDULE_CHANGED')
    return {'accepted':checked['accepted'],'scope':'ACTUAL_SYNTHETIC_P0_SERVICE_CHECKER','work_cpu_ns':time.process_time_ns()-started_cpu,'work_wall_ns':time.monotonic_ns()-started_wall,'checker':checked,'artifact_sha256':sha((destination/'production/reconciliation.json').read_bytes())}


def run_study(root, output):
    """Compare one actual P0 service with replanned and inherited compositions.

    Three public, developer-authored fixtures; no protected holdout or paid demand.
    Never assume that lower symbolic operator costs measure true service efficiency.
    """
    root,output=Path(root).resolve(),Path(output).absolute()
    spec_file=root/'campaign/mechanism-harness-027/EXISTING_OPERATIONS.json'
    spec=_load_json(_regular(spec_file,1_000_000))
    if output.exists() or output.is_symlink():raise ValueError('CREATE_ONLY_STUDY_REQUIRED')
    output.mkdir(parents=True)
    before_sources=_sources()
    before_spec=digest(spec)
    planned_cpu=time.process_time_ns()
    plan=compose(spec)
    candidate_planning_ns=time.process_time_ns()-planned_cpu
    checked=audit(spec,plan)
    capsule=capability_capsule(spec,plan,checked)
    rows=[]
    for case in CASES:
        paths=_inputs(root,case)
        src_hash=_frozen_inputs(paths)
        direct=_direct(paths,output/(case+'-direct'))
        # This arm recompiles the same supplied mechanism language for each task.
        plan_start=time.process_time_ns()
        recompiled=compose(spec)
        new_planning_ns=time.process_time_ns()-plan_start
        run=execute(spec,recompiled,paths,output/(case+'-replanned'),execution_mode='composed')
        fresh_check=verify(spec,recompiled,paths,output/(case+'-replanned'))
        # This arm inherits only executable structure. Current proof/authority remain empty.
        inherited=execute(spec,plan,paths,output/(case+'-inherited'),execution_mode='inherited_existing_plan')
        inherited_check=verify(spec,plan,paths,output/(case+'-inherited'))
        if any(x!=direct['accepted'] for x in (fresh_check['accepted'],inherited_check['accepted'])):
            raise ValueError('COMPARED_ARMS_HAVE_DIFFERENT_ACCEPTANCE')
        if len({direct['artifact_sha256'],run['artifacts_sha256']['production/reconciliation.json'],inherited['artifacts_sha256']['production/reconciliation.json']})!=1:
            raise ValueError('COMPARED_ARMS_HAVE_DIFFERENT_OUTPUTS')
        if _frozen_inputs(paths)!=src_hash or _sources()!=before_sources:raise ValueError('SOURCE_OR_INPUT_CHANGED')
        rows.append({'case':case,'input_sha256':digest(src_hash),'accepted':direct['accepted'],
                     'direct':{'checker_sha256':digest(direct['checker']),'work_cpu_ns':direct['work_cpu_ns'],'work_wall_ns':direct['work_wall_ns'],'artifact_sha256':direct['artifact_sha256']},
                     'replanned':{'planning_cpu_ns':new_planning_ns,'work_cpu_ns':sum(x['cpu_ns'] for x in run['stage_cpu_ns']),'work_wall_ns':run['elapsed_wall_ns'],'audit_sha256':fresh_check['receipt_sha256']},
                     'inherited':{'work_cpu_ns':sum(x['cpu_ns'] for x in inherited['stage_cpu_ns']),'work_wall_ns':inherited['elapsed_wall_ns'],'audit_sha256':inherited_check['receipt_sha256']},
                     'same_semantic_output':True,'same_acceptance':True})
    results={'schema':'agi-alpha/mechanism-delivery-study027/v1','scope':'ACTUAL_REPOSITORY_SYNTHETIC_P0_SERVICE_WITH_THREE_EXPOSED_FIXTURES',
             'spec_sha256':before_spec,'source_sha256':digest(before_sources),'preparation_cpu_ns':candidate_planning_ns,
             'parent_capsule':capsule,'cases':rows,'accepted_cases':sum(r['accepted'] for r in rows),'rejected_cases':sum(not r['accepted'] for r in rows),
             'actual_customers':0,'actual_collected_usd':0,'observed_invention_advantage':None,'measured_complete_dollar_cost':None,
             'causal_successor_inheritance_benefit':None,'independent_blinded_confirmation':False,
             'claim':'EXECUTED_SOURCE_BOUND_COMPOSITION_WITH_P0_SYNTHETIC_PRODUCER_AND_CHECKER',
             'limits':'Visible developer-authored mechanisms and cases; CPU/wall reflect local process only. No actual paid model calls, external checker independence, financial accounting, commercial acceptance or discovery advantage. Inherited plan is rechecked with fresh source/output semantics.'}
    (output/'STUDY.json').write_bytes(canonical(results)+b'\n')
    return results


def main(argv=None):
    p=argparse.ArgumentParser(description='Finite P0 actual-service comparison, with no financial authority')
    p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    p.add_argument('--output',required=True)
    a=p.parse_args(argv)
    try:
        result=run_study(a.root,a.output)
        print(json.dumps({'claim':result['claim'],'accepted_cases':result['accepted_cases'],'rejected_cases':result['rejected_cases'],'case_count':len(result['cases']),'actual_collections':0,'output':str(Path(a.output).absolute())}))
        return 0
    except (ValueError,OSError,KeyError) as e:
        p.exit(2,type(e).__name__+': '+str(e)+'\n')

if __name__=='__main__':raise SystemExit(main())
