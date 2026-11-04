"""Exact cost-pruned discovery and automatically retained search ordering.

Reuses inventor's executable grammar and independent delivery checker. It learns
search order, not new primitive semantics. A bound excludes only a proved loser;
remaining candidates are never discarded for disagreeing with previous tasks.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from commercial.ledger import canonical, digest, strict_json
from . import inventor as i

SCHEMA = 'omega/economical-discovery/v2'
DEVELOPMENT = tuple(tuple(range(s, s+4)) for s in (180101, 180201, 180301))
CONFIRMATION = tuple(tuple(range(s, s+6)) for s in (280101, 280201, 280301))


def key(p, work):
    return work, len(p['filters']), digest(p)


def order_from(record):
    """Extract an executable ordering from fully evaluated successful programs."""
    if record.get('status') != 'EXACT_FINITE_OPTIMUM':
        raise ValueError('NO_ORDER_FROM_UNRESOLVED_SEARCH')
    complete = [r for r in record['development_candidates'] if r['status'] == 'COMPLETE' and r['accepted']]
    preferred = [digest(r['policy']) for r in sorted(complete, key=lambda r: key(r['policy'], r['work']))]
    all_ids = [digest(p) for p in i.genomes()]
    return {'schema': SCHEMA+'/ordering', 'programs': preferred+[p for p in all_ids if p not in preferred],
            'parent_sha256': digest(record), 'development_inputs': record['development_inputs']}


def learn(development, ordering=None, *, prune=True, max_evaluations=4096):
    if type(development) is not list or not development or len(development)>256:
        raise ValueError('NONEMPTY_BOUNDED_DEVELOPMENT_REQUIRED')
    if type(max_evaluations) is not int or max_evaluations<1 or type(prune) is not bool:
        raise ValueError('EXACT_EXECUTION_BUDGET_REQUIRED')
    ids = [digest(raw) for raw in development]
    if len(ids)!=len(set(ids)): raise ValueError('DUPLICATE_DEVELOPMENT_CASE')
    programs = {digest(p):p for p in i.genomes()}
    if ordering is None:
        sequence=list(programs)
    else:
        if (type(ordering) is not dict or set(ordering)!={'schema','programs','parent_sha256','development_inputs'}
                or ordering['schema']!=SCHEMA+'/ordering'
                or type(ordering['programs']) is not list
                or len(ordering['programs'])!=len(programs)
                or set(ordering['programs'])!=set(programs)
                or type(ordering['parent_sha256']) is not str
                or len(ordering['parent_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in ordering['parent_sha256'])
                or type(ordering['development_inputs']) is not list):
            raise ValueError('COMPLETE_VALIDATED_SEARCH_ORDER_REQUIRED')
        if set(ids)&set(ordering['development_inputs']): raise ValueError('FRESH_CAMPAIGN_REQUIRED')
        sequence=ordering['programs']
    reference=[]; calls=work=source_bytes=0; controller=len(programs)+len(ids)
    def measured(raw, p):
        nonlocal calls,work,source_bytes,controller
        if calls>=max_evaluations: raise StopIteration
        result=i.measure(raw,p)
        if type(result['work']) is not int or result['work']<0:
            raise ValueError('NONNEGATIVE_EXACT_PRUNING_COST_REQUIRED')
        calls+=1;work+=result['work'];source_bytes+=len(canonical(raw));controller+=1
        return result
    rows=[]; winner=None; best_key=None; status='EXACT_FINITE_OPTIMUM'
    try:
        for raw in development:
            r=measured(raw,i.policy())
            if not r['accepted']: raise ValueError('REFERENCE_ACCEPTANCE_REQUIRED')
            reference.append(r)
        for ident in sequence:
            p=programs[ident]; partial=0; outcomes=[]; checks=[]; accepted=True; disposition='COMPLETE'
            for j,raw in enumerate(development):
                r=reference[j] if p==i.policy() else measured(raw,p)
                checks.append(r);partial+=r['work'];outcomes.append(r['outcome_sha256']);controller+=1
                if not r['accepted'] or r['outcome_sha256']!=reference[j]['outcome_sha256']:
                    accepted=False;disposition='REJECTED';break
                # Nonnegative future work proves this cannot beat the incumbent.
                if prune and best_key is not None and key(p,partial)>=best_key and j+1<len(development):
                    disposition='PRUNED';break
            row={'policy':p,'work':partial,'accepted':accepted if disposition=='COMPLETE' else False,
                 'status':disposition,'outcomes':outcomes,'measurements':checks,
                 'pruning_incumbent_key':list(best_key) if disposition=='PRUNED' else None}
            rows.append(row)
            if disposition=='COMPLETE' and accepted and (best_key is None or key(p,partial)<best_key):
                winner=row;best_key=key(p,partial)
    except StopIteration:
        status='BUDGET_EXHAUSTED'
    return {'schema':SCHEMA,'status':status,'policy':copy.deepcopy(winner['policy']) if winner and status=='EXACT_FINITE_OPTIMUM' else None,
            'freeze_sha256':digest(winner['policy']) if winner and status=='EXACT_FINITE_OPTIMUM' else None,
            'development_inputs':ids,'development_candidates':rows,'acquisition_work':work,
            'verification_calls':calls,'source_bytes_read':source_bytes,'controller_operations':controller,
            'ordering':copy.deepcopy(ordering),'prune':prune,'max_evaluations':max_evaluations,
            'claim':'Exact finite development objective, not a new productive primitive or global economic optimum.'}


def audit_learning(development, record):
    expected=learn(development,record['ordering'],prune=record['prune'],max_evaluations=record['max_evaluations'])
    if expected!=record: raise ValueError('DISCOVERY_TRACE_CHANGED')
    if record['status']!='EXACT_FINITE_OPTIMUM':
        return {'accepted':True,'optimum_established':False}
    # Independent exhaustive execution, not reliance on the pruning proof alone.
    ordinary=i.learn(development)
    if ordinary['policy']!=record['policy']:raise ValueError('EXHAUSTIVE_WINNER_MISMATCH')
    return {'accepted':True,'optimum_established':True,'exhaustive_acquisition_work':ordinary['acquisition_work']}


def timed(fn, *args, **kwargs):
    start=time.process_time_ns();value=fn(*args,**kwargs)
    return value,time.process_time_ns()-start


def ordinary_measure(raw):
    plan=i.substrate.infer_plan(raw,mode='conventional')
    if plan['status']=='READY':
        normalized=i.substrate.execute_plan(raw,plan)
        artifact={'order_id':raw['order_id'],'service_id':'reconciliation','scope':raw['scope'],'currency':'USD',
                  'outcome_scope':'complete_outcome','method':'generated_schema','plan':plan,
                  'normalized_input':normalized,'useful_outcome':i.deliver('reconciliation',normalized)}
    else:
        artifact=i.substrate.produce(raw,'staged_readiness',mode='conventional')
    check=i.audit_delivery('reconciliation',raw,artifact)
    return {'accepted':check['accepted'],'outcome_sha256':i.digest(artifact['useful_outcome'])}


def study():
    """Three registered successor campaigns; all outcomes, costs and ties retained."""
    ordering=None;rows=[];prior_order_work=0
    for seeds,holdout in zip(DEVELOPMENT,CONFIRMATION):
        development=i.inputs(seeds,i.TRAIN_INDICES)
        cold,cold_ns=timed(learn,development)
        inherited,inherited_ns=timed(learn,development,ordering)
        exhaustive,exhaustive_ns=timed(learn,development,prune=False)
        fixed=i.policy(('unit','unique','text'),True)
        frozen=digest(inherited)  # constructed before generating holdout inputs
        fresh=i.inputs(holdout,i.TEST_INDICES)
        confirmation,confirm_ns=timed(i.confirm,inherited,fresh)
        ordinary,ordinary_ns=timed(lambda:[ordinary_measure(raw) for raw in fresh])
        fixed_rows,fixed_ns=timed(lambda:[i.measure(raw,fixed) for raw in fresh])
        # Copy the exact inherited policy without inventing a special reuse advantage.
        reuse,reuse_ns=timed(lambda:[i.measure(raw,inherited['policy']) for raw in fresh])
        same=(cold['policy']==inherited['policy']==exhaustive['policy'])
        checked=all(x['accepted'] for x in ordinary+fixed_rows+reuse)
        same_outputs=all(a['outcome_sha256']==r['outcome_sha256']==f['outcome_sha256'] for a,r,f in zip(ordinary,reuse,fixed_rows))
        rows.append({'development_seeds':list(seeds),'holdout_seeds':list(holdout),
                     'inherited_order_parent':None if ordering is None else ordering['parent_sha256'],
                     'prior_order_acquisition_work':prior_order_work,
                     'frozen_before_holdout_sha256':frozen,'cold':cold,'inherited':inherited,'exhaustive':exhaustive,
                     'confirmation':confirmation,'all_comparator_outcomes_equal':checked and same_outputs and same,
                     'fixed_conventional_policy':fixed,'fixed_policy_work':sum(r['work'] for r in fixed_rows),
                     'equal_content_reuse_ties':reuse==[x['new'] for x in confirmation['cases']],
                     'ordinary_scope':'Full checked output parity; differently defined legacy work counter not used for a superiority claim.',
                     'cpu_ns':{'cold_search':cold_ns,'inherited_search':inherited_ns,'exhaustive_search':exhaustive_ns,
                               'whole_confirmation':confirm_ns,'ordinary_with_check':ordinary_ns,'fixed_measure':fixed_ns,'equal_content_measure':reuse_ns},
                     'prior_plus_current_search_and_use':prior_order_work+inherited['acquisition_work']+confirmation['new_work'],
                     'cold_search_and_use':cold['acquisition_work']+confirmation['new_work'],
                     'exhaustive_search_and_use':exhaustive['acquisition_work']+confirmation['new_work']})
        ordering=order_from(inherited)
        prior_order_work+=inherited['acquisition_work']
    return {'schema':SCHEMA+'/study','campaigns':rows,'retained_order':ordering,
            'all_exact_winners_and_outcomes_match':all(r['all_comparator_outcomes_equal'] for r in rows),
            'inherited_order_incremental_work_saved':sum(r['cold']['acquisition_work']-r['inherited']['acquisition_work'] for r in rows),
            'complete_discovery_work':sum(r['inherited']['acquisition_work'] for r in rows),
            'ordinary_discovery_work':sum(r['cold']['acquisition_work'] for r in rows),
            'strong_fixed_policy_remains_a_control':True,
            'mapping_metric_is_not_complete_lifecycle_cost':True,
            'actual_revenue_usd':0,'full_objective_achieved':False}


def deterministic(value):
    if isinstance(value,dict):return {k:deterministic(v) for k,v in value.items() if k not in {'cpu_ns','source'}}
    if isinstance(value,list):return [deterministic(v) for v in value]
    return value


def audit_study(record):
    if record.get('source')!=source_identity():raise ValueError('EXECUTABLE_SOURCE_CHANGED')
    if deterministic(record)!=deterministic(study()):raise ValueError('STUDY_OR_CLAIM_CHANGED')
    return {'accepted':True,'scope':'Deterministic registered cohort reexecution; CPU is a recorded observation, not reproduced proof.'}


def source_identity():
    root=Path(__file__).resolve().parents[1]
    paths={'mechanism_harness/economical_learning.py','mechanism_harness/inventor.py',
           'adaptive_enterprise/instruments.py','adaptive_enterprise/checkers.py',
           'enterprise/services.py','enterprise/checkers.py','commercial/service.py',
           'commercial/service_verifier.py','commercial/ledger.py'}
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(paths)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--audit',action='store_true')
    args=p.parse_args(argv);out=i.checked_output(args.output)
    if args.audit:
        print(json.dumps(audit_study(strict_json(out.read_bytes())),indent=2));return
    if out.exists():raise FileExistsError('PRESERVE_PRIOR_EVIDENCE')
    source=source_identity();result=study()
    if source_identity()!=source:raise ValueError('SOURCE_CHANGED_DURING_EXECUTION')
    result['source']=source
    out.parent.mkdir(parents=True,exist_ok=True);i.write_new(out,result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'campaigns','retained_order','source'}},indent=2))

if __name__=='__main__':main()
