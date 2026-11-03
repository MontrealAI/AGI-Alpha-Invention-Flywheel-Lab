"""Executed adapter-policy synthesis and empirical self-improvement, not AGI.

No generated Python is evaluated. The executable object is a validated sequence
of sound pruning operations, optionally compiled into reusable column summaries.
Construction and independent confirmation reuse the existing service substrate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import itertools
import json
import math
from pathlib import Path

from adaptive_enterprise import instruments as substrate
from adaptive_enterprise.checkers import audit_delivery
from enterprise.services import produce as deliver
from commercial.ledger import canonical, digest, strict_json

FILTERS = ('unit', 'unique', 'text')
ROOT = Path(__file__).resolve().parents[1]
TRAIN_SEEDS = (41001, 41002, 41003, 41004)
TRAIN_INDICES = (8, 9, 14, 15)
TEST_SEEDS = tuple(range(72001, 72013))
TEST_INDICES = (8, 9, 14, 15, 22, 23)


def policy(filters=(), cache=False):
    return {'schema': 'omega/discovery-policy/v1', 'filters': list(filters),
            'cache_columns': cache}


def validate_policy(p):
    if (type(p) is not dict or set(p) != {'schema','filters','cache_columns'}
            or p['schema'] != 'omega/discovery-policy/v1'
            or type(p['cache_columns']) is not bool or type(p['filters']) is not list
            or any(type(x) is not str or x not in FILTERS for x in p['filters'])
            or len(p['filters']) != len(set(p['filters']))):
        raise ValueError('EXACT_DATA_ONLY_DISCOVERY_POLICY_REQUIRED')
    return p


def genomes():
    for k in range(len(FILTERS)+1):
        for order in itertools.permutations(FILTERS,k):
            for cache in (False, True):
                yield policy(order,cache)


def construct(raw, p):
    """Synthesize an actual adapter. No expected mapping or verifier is consulted."""
    validate_policy(p)
    substrate._raw(raw)
    if raw['service_id'] != 'reconciliation':
        raise ValueError('REGISTERED_RECONCILIATION_SCOPE_REQUIRED')
    work=0; cache={}; possibilities={}; count=0
    def values(table,column):
        nonlocal work
        key=(table,column)
        if p['cache_columns'] and key in cache:
            work += 1  # charge retrieval, not just data scans
            return cache[key]
        result=[r[column] for r in raw['tables'][table]]
        work += len(result)
        if p['cache_columns']: cache[key]=result
        return result
    for table in ('invoices','payments'):
        candidates=substrate._assignments(raw['tables'][table], table=='payments')
        count += len(candidates)
        for op in p['filters']:
            kept=[]
            for m in candidates:
                work+=1  # every predicate decision is charged
                if op=='unit':
                    ok=raw['units'].get(table,{}).get(m['amount_cents']) in ('USD','cents')
                elif op=='unique':
                    v=values(table,m['id'])
                    ok=all(type(x) is str and x for x in v) and len(set(v))==len(v)
                else:
                    v=values(table,m['id'])+values(table,m['customer'])
                    ok=all(type(x) is str and x for x in v)
                if ok: kept.append(m)
            candidates=kept
        possibilities[table]=candidates
    valid=[]; attempted=0
    for inv,pay in itertools.product(possibilities['invoices'],possibilities['payments']):
        attempted+=1; work+=1
        mapping={'invoices':inv,'payments':pay}
        units={t:raw['units'].get(t,{}).get(mapping[t]['amount_cents']) for t in mapping}
        meter=[0]
        try:
            substrate._normalize(raw,mapping,units,meter)
            valid.append((mapping,units))
        except (ValueError,KeyError,TypeError):
            pass
        finally:
            work+=meter[0]
        if len(valid)>1: break  # genuine ambiguity, never first-match guessing
    ready=len(valid)==1
    plan={'schema':'adaptive012/intake-plan/v1','service_id':'reconciliation',
          'status':'READY' if ready else 'BLOCKED',
          'mapping':valid[0][0] if ready else None,
          'units':valid[0][1] if ready else {},'constraints':list(substrate.CONSTRAINTS),
          'search':{'candidates_tested':attempted,'candidate_count':count,
                    'operation_count':work,'retained_constraints_used':[]},
          'failure':None if ready else ('AMBIGUOUS_MAPPING' if len(valid)>1 else 'MISSING_TYPED_MAPPING_OR_FACTS')}
    return plan


def execute(raw, p):
    plan=construct(raw,p)
    normalized=substrate.execute_plan(raw,plan) if plan['status']=='READY' else None
    if normalized is not None:
        useful=deliver('reconciliation',normalized)
    else:
        useful={'order_id':raw['order_id'], 'source_rows':{t:len(rs) for t,rs in raw['tables'].items()},
                'missing_or_ambiguous':[plan['failure']], 'production_ready':False,
                'promised_outcome':'Intake readiness only; no completed reconciliation, KPI analysis or evidence response.',
                'source_sha256':substrate.digest(raw)}
    artifact={'order_id':raw['order_id'],'service_id':'reconciliation','scope':raw['scope'],'currency':'USD',
              'outcome_scope':'complete_outcome' if normalized is not None else 'intake_readiness',
              'method':'generated_schema' if normalized is not None else 'staged_readiness',
              'plan':plan,'normalized_input':normalized,'useful_outcome':useful}
    return artifact


def measure(raw,p):
    artifact=execute(raw,p)
    check=audit_delivery('reconciliation',raw,artifact)
    return {'source_sha256':digest(raw),'policy_sha256':digest(p),
            'accepted':check['accepted'],'complete':artifact['outcome_scope']=='complete_outcome',
            'work':artifact['plan']['search']['operation_count'],
            'outcome_sha256':digest(artifact['useful_outcome']),
            'artifact_sha256':digest(artifact),'errors':check['errors']}


def inputs(seeds, indices):
    return [substrate.synthetic_raw('reconciliation',i,s) for s in seeds for i in indices]


def learn(development):
    """Search discovery procedures, not just retain the final adapter."""
    if type(development) is not list or not development:
        raise ValueError('NONEMPTY_DEVELOPMENT_REQUIRED')
    scores=[]; acquisition_work=0
    for p in genomes():
        rows=[measure(raw,p) for raw in development]
        work=sum(r['work'] for r in rows); acquisition_work+=work
        scores.append({'policy':p,'work':work,'accepted':all(r['accepted'] for r in rows),
                       'outcomes':[r['outcome_sha256'] for r in rows]})
    baseline=scores[0]['outcomes']
    eligible=[s for s in scores if s['accepted'] and s['outcomes']==baseline]
    if not eligible: raise ValueError('NO_VALID_DISCOVERY_POLICY')
    winner=min(eligible,key=lambda s:(s['work'],len(s['policy']['filters']),digest(s['policy'])))
    return {'policy':winner['policy'],'development_inputs':[digest(x) for x in development],
            'development_candidates':scores,'acquisition_work':acquisition_work,
            'freeze_sha256':digest(winner['policy']),
            'scope':'Automatic finite program composition; predicates and interpreter human supplied.'}


def confirm(frozen, fresh):
    if type(fresh) is not list or not fresh:
        raise ValueError('NONEMPTY_CONFIRMATION_REQUIRED')
    validate_policy(frozen['policy'])
    if digest(frozen['policy'])!=frozen['freeze_sha256']:raise ValueError('FROZEN_POLICY_CHANGED')
    if set(frozen['development_inputs']) & {digest(x) for x in fresh}:raise ValueError('CONFIRMATION_LEAKAGE')
    rows=[]
    for raw in fresh:
        old=measure(raw,policy());new=measure(raw,frozen['policy'])
        # Strong existing ordinary constructor is a real independent execution.
        cplan=substrate.infer_plan(raw,mode='conventional')
        conventional=substrate.produce(raw,'generated_schema' if cplan['status']=='READY' else 'staged_readiness',mode='conventional')
        checked=audit_delivery('reconciliation',raw,conventional)
        ordinary={'accepted':checked['accepted'], 'work':conventional['plan']['search']['operation_count'],
                  'outcome_sha256':digest(conventional['useful_outcome'])}
        rows.append({'old':old,'new':new,'ordinary':ordinary,
                     'equal_content_reuse':measure(raw,copy.deepcopy(frozen['policy']))})
    compatible=all(r['new']['accepted'] and r['old']['accepted'] and r['ordinary']['accepted']
                   and r['old']['outcome_sha256']==r['new']['outcome_sha256']==r['ordinary']['outcome_sha256'] for r in rows)
    gain=sum(r['old']['work']-r['new']['work'] for r in rows)
    promoted=compatible and gain>0 and all(r['new']['work']<=r['old']['work'] for r in rows)
    return {'cases':rows,'case_count':len(rows),'promoted_in_scope':promoted,
            'old_work':sum(r['old']['work'] for r in rows),'new_work':sum(r['new']['work'] for r in rows),
            'ordinary_work':sum(r['ordinary']['work'] for r in rows),
            'ordinary_metric_warning':'Existing counter counts mapping-stage row visits; our counter also charges decisions/retrieval. Do not claim apples-to-apples superiority from these totals.',
            'same_content_reuse_ties':all(r['new']==r['equal_content_reuse'] for r in rows),
            'discovery_acquisition_work':frozen['acquisition_work'],
            'metered_reuse_break_even_cases':math.ceil(frozen['acquisition_work']*len(rows)/gain) if gain>0 else None,
            'inference':'Registered finite deterministic cohort, not a population confidence statement; acquisition and verifier costs remain distinct.'}


def source_identity():
    from connected_enterprise.finance import SOURCE_PATHS
    paths=set(SOURCE_PATHS)|set(substrate.SOURCE_PATHS)|{
        'mechanism_harness/inventor.py','mechanism_harness/inventor_native.py',
        'campaign/omega-inventor/PROTOCOL.md'}
    for name in paths:
        path=ROOT/name
        if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):
            raise ValueError('REGULAR_EXECUTABLE_SOURCE_REQUIRED:'+name)
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}


def write_new(path,value):
    with Path(path).open('xb') as out:out.write(canonical(value)+b'\n')


def checked_output(output):
    output=Path(output).absolute()
    if any(p.is_symlink() for p in (output,*output.parents)):
        raise ValueError('REGULAR_OWNED_OUTPUT_REQUIRED')
    return output


def run(output, *, resume=False):
    from .inventor_native import begin, operate
    output=checked_output(output)
    source=source_identity()
    if resume:
        if not output.is_dir() or strict_json((output/'SOURCE.json').read_bytes())!=source:
            raise ValueError('SOURCE_MATCHED_EXISTING_CAMPAIGN_REQUIRED')
        if (output/'REPORT.json').exists():
            audit(output)
            return strict_json((output/'REPORT.json').read_bytes())
    else:
        output.mkdir(parents=True,exist_ok=True)
        if any(output.iterdir()):raise FileExistsError('NEW_CAMPAIGN_REQUIRED_USE_RESUME')
        write_new(output/'SOURCE.json',source)
    session=begin(output,source)
    try:
        frozen_path=output/'FROZEN_POLICY.json'
        if frozen_path.exists():
            learned=strict_json(frozen_path.read_bytes())
            if learned!=learn(inputs(TRAIN_SEEDS,TRAIN_INDICES)):
                raise ValueError('DISCOVERY_HISTORY_CHANGED')
        else:
            learned=learn(inputs(TRAIN_SEEDS,TRAIN_INDICES))
            write_new(frozen_path,learned)  # durable BEFORE confirmation generation
        confirmation=confirm(learned,inputs(TEST_SEEDS,TEST_INDICES))
        confirmation_path=output/'CONFIRMATION.json'
        if confirmation_path.exists():
            if confirmation!=strict_json(confirmation_path.read_bytes()):
                raise ValueError('CONFIRMATION_CHANGED')
        else:write_new(confirmation_path,confirmation)
        promoted=learned['policy'] if confirmation['promoted_in_scope'] else policy()
        native=operate(output, promoted, source, learned['acquisition_work'],session=session)
    finally:
        session[2].close()
    report={'schema':'omega/executed-inventor/v1','source':source,'learning':learned,
            'confirmation':confirmation,'native':native,'actual_revenue_usd':0,
            'full_open_world_objective_achieved':False,
            'achieved_scope':'Executed finite adapter/discovery-policy synthesis, independent artifact checks, and native simulated commercial integration.',
            'unestablished':['Open-ended new productive primitives','Unrestricted strategic superiority','Empirical buyer demand','Independent general discovery improvement','USD3B trailing-year profit','Production release']}
    write_new(output/'REPORT.json',report)
    body=html.escape(json.dumps({k:v for k,v in report.items() if k not in {'learning','confirmation','source'}},indent=2))
    (output/'REPORT.html').write_text('<!doctype html><meta charset="utf-8"><title>FLYWHEEL Ω evidence</title><style>body{max-width:960px;margin:3rem auto;font:18px system-ui;padding:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:2rem}</style><h1>FLYWHEEL Ω — executed evidence</h1><p>Simulated commerce. Scope and failures remain explicit.</p><pre>'+body+'</pre>',encoding='utf-8')
    return report


def audit(output):
    from .inventor_native import audit_operation
    output=checked_output(output)
    report=strict_json((output/'REPORT.json').read_bytes())
    if report['source']!=source_identity():raise ValueError('EXECUTABLE_SOURCE_CHANGED')
    frozen=strict_json((output/'FROZEN_POLICY.json').read_bytes())
    if frozen!=report['learning'] or frozen!=learn(inputs(TRAIN_SEEDS,TRAIN_INDICES)):
        raise ValueError('DISCOVERY_HISTORY_CHANGED')
    actual=confirm(frozen,inputs(TEST_SEEDS,TEST_INDICES))
    if actual!=report['confirmation'] or actual!=strict_json((output/'CONFIRMATION.json').read_bytes()):
        raise ValueError('CONFIRMATION_CHANGED')
    if report.get('actual_revenue_usd')!=0 or report.get('full_open_world_objective_achieved') is not False:
        raise ValueError('UNSUPPORTED_COMPLETION_CLAIM')
    expected_policy=frozen['policy'] if actual['promoted_in_scope'] else policy()
    if report['native']['acquisition_work']!=frozen['acquisition_work']:
        raise ValueError('ACQUISITION_COST_HISTORY_CHANGED')
    audit_operation(output,report['native'],report['source'],expected_policy)
    return {'accepted':True,'scope':'Source-matched deterministic audit, not external certification',
            'report_sha256':digest(report)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('run','resume','audit'));p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    result=audit(a.output) if a.command=='audit' else run(a.output,resume=a.command=='resume')
    print(json.dumps(result if a.command=='audit' else {'scope':result['achieved_scope'],'native':result['native'],'confirmation_cases':result['confirmation']['case_count']},indent=2))

if __name__=='__main__':main()
