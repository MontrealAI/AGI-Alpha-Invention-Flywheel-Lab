"""Finite composition of LOCAL authored provider contracts, not supplier consent.

Existing typed grammar searches observed prerequisite/quote alternatives. Every
selected service executes its existing native adapter. Seller reservation is not
an external provider commitment; expiry/default are separate scenario assumptions.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from mechanism_harness import core
from commercial.ledger import digest
from adaptive_enterprise.bundles import _validate_raw, audit_bundle, PROMISE, SCOPE
from adaptive_enterprise.instruments import produce, SOURCE_PATHS as INSTRUMENT_SOURCES

SERVICES=('evidence_matrix','kpi_variance','reconciliation')
ASSEMBLY=250000
# Reuse the native production/checker closure, not a hand-picked subset.
DEPENDENCIES=tuple(sorted(set(INSTRUMENT_SOURCES)|{
    'connected_enterprise/conditional_procurement053.py',
    'connected_enterprise/procurement_verify053.py',
    'mechanism_harness/__init__.py', 'mechanism_harness/core.py',
    'commercial/ledger.py',
}))


def sources():
    root=Path(__file__).resolve().parents[1]
    return {p:sha256((root/p).read_bytes()).hexdigest()for p in DEPENDENCIES}


def fixture_quotes(raw, case='central', now=24):
    """Public scenario inputs, not real suppliers or empirical price quotes."""
    if case not in ('central','expired','provider_default','no_demand','unaffordable'):
        raise ValueError('REGISTERED_CASE_REQUIRED')
    components=_validate_raw(raw);by={r['service_id']:r for r in components};identity=digest(sources());quotes=[]
    for service in SERVICES:
        for name,cost in (('primary',1750000),('alternate',2250000)):
            quotes.append(dict(id=service+'_'+name,service_id=service,
                cost_microUSD=cost+(100000000 if case=='unaffordable' else 0),
                valid_from=0,valid_until=23 if case=='expired'and service=='evidence_matrix'else 72,
                available=True,input_sha256=digest(by[service]['raw_order']),source_sha256=identity,
                scope='LOCAL_AUTHORED_CONTRACT_NOT_EXTERNAL_AGREEMENT'))
    quotes.append(dict(id='integrated_provider',service_id='operations_bundle',
        cost_microUSD=6000000+(100000000 if case=='unaffordable'else 0),
        valid_from=0,valid_until=23 if case=='expired'else 72,available=True,
        input_sha256=digest(raw),source_sha256=identity,
        scope='LOCAL_AUTHORED_CONTRACT_NOT_EXTERNAL_AGREEMENT'))
    return quotes


def coverage(quote):
    return SERVICES if quote['service_id']=='operations_bundle'else(quote['service_id'],)


def validate(raw,quotes,now,budget_microUSD):
    components=_validate_raw(raw);by={r['service_id']:r for r in components}
    if type(now)is not int or now<0 or type(budget_microUSD)is not int or budget_microUSD<0:
        raise ValueError('CURRENT_TIME_AND_FUNDS_REQUIRED')
    if type(quotes)is not list or not quotes or len(quotes)>24:raise ValueError('BOUNDED_QUOTE_OBSERVATIONS_REQUIRED')
    seen=set();source=digest(sources())
    keys={'id','service_id','cost_microUSD','valid_from','valid_until','available','input_sha256','source_sha256','scope'}
    for q in quotes:
        if type(q)is not dict or set(q)!=keys or type(q['id'])is not str or not core.IDENTIFIER.fullmatch(q['id']) or q['id']in seen or q['service_id']not in (*SERVICES,'operations_bundle'):
            raise ValueError('EXACT_UNIQUE_PROVIDER_QUOTE_REQUIRED')
        seen.add(q['id'])
        if type(q['cost_microUSD'])is not int or q['cost_microUSD']<=0 or q['cost_microUSD']%10000 or type(q['valid_from'])is not int or type(q['valid_until'])is not int or not 0<=q['valid_from']<q['valid_until'] or type(q['available'])is not bool:
            raise ValueError('EXACT_CENT_QUOTES_AND_VALIDITY_REQUIRED')
        if q['scope']!='LOCAL_AUTHORED_CONTRACT_NOT_EXTERNAL_AGREEMENT' or q['source_sha256']!=source or q['input_sha256']!=digest(raw if q['service_id']=='operations_bundle'else by[q['service_id']]['raw_order']):
            raise ValueError('QUOTE_SOURCE_OR_INPUT_CHANGED')
    return components


def select(raw,quotes,*,now,budget_microUSD,policy='composed'):
    validate(raw,quotes,now,budget_microUSD)
    from .procurement_verify053 import ordinary_select, audit_selection
    observed=digest(dict(raw=digest(raw),quotes=quotes,now=now,budget_microUSD=budget_microUSD))
    if policy=='ordinary':
        result=ordinary_select(quotes,SERVICES,now,budget_microUSD,ASSEMBLY)
    elif policy=='composed':
        # Exact cents are grammar resource units, never a dollars-per-operation conversion.
        valid=sorted((q for q in quotes if q['available'] and q['valid_from']<=now<q['valid_until']
                      and q['cost_microUSD']+ASSEMBLY<=budget_microUSD),
                     key=lambda q:q['id'])
        # The grammar's bounded integer representation is not a cash ceiling.
        # Use the competent ordinary route explicitly rather than clipping funds.
        if not valid or budget_microUSD//10000>1_000_000:
            result=ordinary_select(quotes,SERVICES,now,budget_microUSD,ASSEMBLY)
            result['search']=dict(route='ordinary_fallback',
                reason=('NO_CURRENT_INDIVIDUALLY_AFFORDABLE_QUOTE' if not valid else
                        'CURRENT_BUDGET_OUTSIDE_GRAMMAR_RESOURCE_RANGE'),
                scope='Ordinary exact enumeration; no symbolic plan or invention advantage claimed')
        else:
            # External identifiers remain unrestricted by internal step names. Fixed-width
            # ranks preserve external lexicographic ties without overflowing ID bounds.
            provider_ids={q['id']:f'provider_{index:02d}' for index,q in enumerate(valid)}
            external_ids={generated:external for external,generated in provider_ids.items()}
            assembly_id='internal_assemble_complete'
            mechanisms=[dict(id=provider_ids[q['id']],requires=sorted('source_'+x for x in coverage(q)),provides=sorted('result_'+x for x in coverage(q)),
                             cost=q['cost_microUSD']//10000,effect='pure',origin='externally_supplied')for q in valid]
            mechanisms.append(dict(id=assembly_id,requires=sorted('result_'+s for s in SERVICES),
                provides=['accepted_complete_bundle'],cost=ASSEMBLY//10000,effect='pure',origin='developer_supplied'))
            # Repository grammar bounds are finite experiment limits, not business ceilings.
            spec=dict(schema=core.SCHEMA,purpose=dict(initial=sorted('source_'+s for s in SERVICES),
                goal=['accepted_complete_bundle'],max_cost=budget_microUSD//10000,
                max_steps=4,max_states=20000,allowed_effects=['pure']),mechanisms=mechanisms,candidate_bridges=[])
            plan=core.compose(spec);checked=core.audit(spec,plan)
            if not checked['accepted']:raise ValueError('SYMBOLIC_PLAN_INDEPENDENT_AUDIT_FAILED')
            if plan['status']=='SYMBOLIC_PLAN_FOUND':
                ids=sorted(external_ids[x] for x in plan['sequence'] if x!=assembly_id)
                result=dict(status='READY',quote_ids=ids,total_microUSD=plan['cost_units']*10000)
            else:result=dict(status='NO_COMPLETE_AFFORDABLE_BUNDLE',quote_ids=[],total_microUSD=None)
            result['search']=dict(route='symbolic_compose',states_expanded=plan['states_expanded'],spec_sha256=digest(spec),
                plan_sha256=digest(plan),scope='Finite supplied grammar search, not autonomous invention')
    else:raise ValueError('REGISTERED_POLICY_REQUIRED')
    audited=audit_selection(result,quotes,SERVICES,now,budget_microUSD,ASSEMBLY)
    if not audited['accepted']:raise ValueError('ORDINARY_COMPLETE_BUNDLE_COMPARISON_REJECTED:'+str(audited))
    result.update(observation_sha256=observed,policy=policy,budget_microUSD=budget_microUSD,now=now)
    return result


def execute(raw,quotes,selection,*,now,default_service=None):
    """Fresh local outputs only; financial caller must reserve complete invoice first."""
    before=sources();validate(raw,quotes,now,selection['budget_microUSD'])
    from .procurement_verify053 import audit_selection
    expected=digest(dict(raw=digest(raw),quotes=quotes,now=now,budget_microUSD=selection['budget_microUSD']))
    if selection.get('observation_sha256')!=expected or selection.get('now')!=now:
        raise ValueError('CURRENT_PROCUREMENT_OBSERVATIONS_REQUIRED')
    checked=audit_selection(selection,quotes,SERVICES,now,selection['budget_microUSD'],ASSEMBLY)
    if not checked['accepted']or selection['status']!='READY':raise ValueError('COMPLETE_CURRENT_PROCUREMENT_REQUIRED')
    if default_service is not None and default_service not in SERVICES:raise ValueError('DECLARED_DEFAULT_SERVICE_REQUIRED')
    by={r['service_id']:r for r in raw['components']};outputs={};trace=[]
    for qid in selection['quote_ids']:
        quote=next(q for q in quotes if q['id']==qid)
        for service in coverage(quote):
            if service==default_service:
                if sources()!=before:raise ValueError('PROCUREMENT_SOURCE_CHANGED_DURING_EXECUTION')
                return dict(accepted=False,artifact=None,completed_components=trace,
                    failure='LOCAL_AUTHORED_PROVIDER_DEFAULT',loss_scope='Whole prepaid invoice retained; no invented refund or customer sale')
            component=by[service];artifact=produce(component['raw_order'],component['artifact']['method'])
            outputs[service]=dict(job_id=component['job_id'],artifact=artifact)
            trace.append(dict(service_id=service,quote_id=qid,artifact_sha256=digest(artifact)))
    artifact=dict(order_id=raw['order_id'],service_id='operations_bundle',scope=SCOPE,currency='USD',
        outcome_scope='complete_outcome',method='operations_bundle',components=[outputs[r['service_id']]for r in raw['components']],
        work_keys=deepcopy(raw['work_keys']),promise=PROMISE)
    check=audit_bundle(raw,artifact)
    if sources()!=before:raise ValueError('PROCUREMENT_SOURCE_CHANGED_DURING_EXECUTION')
    return dict(accepted=check['accepted'],artifact=artifact,check=check,completed_components=trace,
        failure=None if check['accepted']else'INDEPENDENT_COMPLETE_OUTCOME_REJECTED')
