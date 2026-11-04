"""Connect measured successor search to existing native operation and audit.

This is an opt-in research continuation, not a second ledger, deployment, or
assertion that search acquisition beats a competent fixed conventional route.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from commercial.ledger import digest, strict_json
from . import inventor as i, inventor_native as n, economical_learning as e


def source_identity():
    paths=set(n.SOURCE_PATHS)|set(i.substrate.SOURCE_PATHS)|set(e.source_identity())|{
        'mechanism_harness/economical_native.py','mechanism_harness/inventor_native.py',
        'mechanism_harness/inventor_cost_audit.py','campaign/omega-inventor/PROTOCOL_V2.md'}
    result={}
    for name in sorted(paths):
        path=i.ROOT/name
        if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):
            raise ValueError('REGULAR_SOURCE_REQUIRED:'+name)
        result[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run(output, *, resume=False):
    output=i.checked_output(output);source=source_identity()
    if not resume:
        output.mkdir(parents=True,exist_ok=True)
        if any(output.iterdir()):raise FileExistsError('NEW_ACCOUNT_REQUIRED_USE_RESUME')
        n.save(output/'V2_SOURCE.json',source)
    elif not output.is_dir() or n.read(output/'V2_SOURCE.json')!=source:
        raise ValueError('SOURCE_MATCHED_EXISTING_RUN_REQUIRED')
    if resume:
        n.require_resume_authority(output)
        if (output/'V2_REPORT.json').exists():
            return n.completed_resume(output, opening=n.OPENING, contract=n.CONTRACT,
                                      report_name='V2_REPORT.json', public_audit=audit)
    session=n.begin(output,source)
    try:
        if (output/'V2_STUDY.json').exists():
            study=n.read(output/'V2_STUDY.json');e.audit_study(study)
        else:
            study=e.study();study['source']=e.source_identity()
            if source_identity()!=source:raise ValueError('SOURCE_CHANGED_DURING_EXECUTION')
            n.save(output/'V2_STUDY.json',study)
        if not study['all_exact_winners_and_outcomes_match']:
            raise ValueError('NO_NATIVE_PROMOTION_FROM_FAILED_CONFIRMATION')
        p=study['campaigns'][-1]['inherited']['policy']
        native=n.operate(output,p,source,study['complete_discovery_work'],session=session)
    finally:
        session[2].close()
    n.audit_operation(output,native,source,p)
    if source_identity()!=source:raise ValueError('SOURCE_CHANGED_DURING_EXECUTION')
    report={'schema':'omega/economical-native/v2','source':source,'study_sha256':digest(study),
            'native':native,'selected_policy':p,'actual_revenue_usd':0,'full_objective_achieved':False,
            'scope':'Executed search-order learning, checked work and native simulated commerce. No complete-lifecycle superiority, new primitive invention, market demand or production release claim.',
            'cost_boundary':'Original native authored discovery envelope is unchanged. Logical research work and actual CPU are disclosed separately; this is not actual billed complete-lifecycle profit.'}
    n.save(output/'V2_REPORT.json',report)
    return report


def audit(output):
    output=i.checked_output(output);source=source_identity()
    r=n.read(output/'V2_REPORT.json');s=n.read(output/'V2_STUDY.json')
    if r['source']!=source or n.read(output/'V2_SOURCE.json')!=source:
        raise ValueError('SOURCE_CHANGED')
    e.audit_study(s)
    if r['study_sha256']!=digest(s) or not s['all_exact_winners_and_outcomes_match']:
        raise ValueError('UNCONFIRMED_LEARNING_OR_SOURCE')
    p=s['campaigns'][-1]['inherited']['policy']
    if (r['selected_policy']!=p or r['native']['acquisition_work']!=s['complete_discovery_work']
            or r.get('actual_revenue_usd')!=0 or r.get('full_objective_achieved') is not False):
        raise ValueError('UNSUPPORTED_POLICY_COST_OR_CLAIM')
    n.audit_operation(output,r['native'],source,p)
    return {'accepted':True,'report_sha256':digest(r),'scope':'Source-matched code-path audit; no external certification.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('run','audit','resume'));p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    result=audit(a.output) if a.command=='audit' else run(a.output,resume=a.command=='resume')
    if a.command!='audit':
        result={k:result[k] for k in ('schema','scope','actual_revenue_usd','full_objective_achieved','cost_boundary')}|{
            'native_summary':result['native']['native_summary'],'settled':result['native']['settled'],'refused':result['native']['refused']}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
