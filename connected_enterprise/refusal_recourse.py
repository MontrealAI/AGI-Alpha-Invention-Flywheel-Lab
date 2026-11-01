"""Paid finite public-response recourse; no private buyer inputs or new funding."""
import copy
from fractions import Fraction
from commercial.ledger import digest
from .strategic_commerce import allocate_actions,rederive_actions

SCHEMA='connected-refusal-recourse/v1'
SELECTIVE_SCHEMA='connected-selective-refusal-recourse/v2'

def _refusal_probability(row):
    return 1-Fraction(row.get('win_probability_fraction',str(row['win_probability'])))

def validate_policy(policy):
    if isinstance(policy,dict) and policy.get('schema')==SELECTIVE_SCHEMA:
        if set(policy)!={'schema','daily_planning_cost','daily_evaluation_cost'} or any(type(policy[k]) is not int or policy[k]<=0 for k in ('daily_planning_cost','daily_evaluation_cost')):
            raise ValueError('EXPLICIT_POSITIVE_SELECTIVE_RECOURSE_CONTRACT_REQUIRED')
        return policy
    if not isinstance(policy,dict) or set(policy)!={'schema','daily_planning_cost'} or policy['schema']!=SCHEMA:
        raise ValueError('EXPLICIT_PREPAID_RECOURSE_CONTRACT_REQUIRED')
    if type(policy['daily_planning_cost']) is not int or policy['daily_planning_cost']<=0:
        raise ValueError('POSITIVE_PREPAID_DAILY_RECOURSE_COST_REQUIRED')
    return policy

def selective_decision(record,policy,candidate_ids):
    validate_policy(policy)
    if policy['schema']!=SELECTIVE_SCHEMA:raise ValueError('SELECTIVE_RECOURSE_POLICY_REQUIRED')
    rederive_actions(record)
    if len(candidate_ids)!=len(set(candidate_ids)):raise ValueError('UNIQUE_PUBLIC_RECOURSE_CANDIDATES_REQUIRED')
    selected=[o for o in record['decision']['selected_options'] if o['kind']=='delivery']
    selected.sort(key=lambda o:candidate_ids.index(o['execution']['customer_id']))
    result={'schema':'connected-selective-recourse-decision/v2','purchase':False,'first_option_id':None,'new_alternative_ids':[],
        'expected_increment_microUSD':{'numerator':0,'denominator':1},'allowance_cost_microUSD':policy['daily_planning_cost'],
        'scope':'Conservative first-planned-quote refusal branch under public priors. Daily evaluation is charged even on hold; no global retry-policy optimum or calibrated demand claim.'}
    if not selected:return result
    first=selected[0];result['first_option_id']=first['id']
    rows=first['execution']['row']['forecasts'];weights=record['riskpolicy']['scenarios']
    refusal={r['belief']:_refusal_probability(r) for r in rows}
    if set(refusal)!=set(weights) or any(not 0<=p<=1 for p in refusal.values()):raise ValueError('PUBLIC_REFUSAL_PROBABILITY_REQUIRED')
    renewed=recourse(record,[{'customer_id':first['execution']['customer_id'],'option_id':first['id'],'accepted':False}])
    old_customers={o['execution']['customer_id'] for o in selected}
    new=[o for o in renewed['decision']['selected_options'] if o['kind']=='delivery' and o['execution']['customer_id'] not in old_customers]
    if not {o['id'] for o in selected[1:]}<=set(renewed['decision']['selected']):new=[]
    value=max(Fraction(0),sum(Fraction(weights[k],10000)*refusal[k]*(o['future_net_cash'][k]-o['upfront_cost']) for o in new for k in weights))
    result['new_alternative_ids']=sorted(o['id'] for o in new)
    result['expected_increment_microUSD']={'numerator':value.numerator,'denominator':value.denominator}
    result['purchase']=bool(new and value>policy['daily_planning_cost'])
    return result

def recourse(original_record,attempts):
    """Replay all preceding public responses, returning the last allocation.

    Caller binds responses to actual ordered buyer decisions and proves the
    daily planning contract was paid before the original native observation.
    Reuses already evaluated quote alternatives, never private atoms, future
    arrivals or new investments. Original investments and accepted offers are
    mandatory in the full basket, retaining their cash/risk/work/capacity locks.
    Native funding must still reauthorize actual execution.
    """
    if original_record['riskpolicy']['interactions']:raise ValueError('RECOURSE_AUTHORED_INTERACTIONS_NOT_COMPOSED')
    rederive_actions(original_record)
    if original_record.get('mandatory_ids'):raise ValueError('ORIGINAL_RECOURSE_BASE_REQUIRED')
    if not isinstance(attempts,list) or not attempts:raise ValueError('PUBLIC_REFUSAL_HISTORY_REQUIRED')
    contacts=set();accepted=set();current=original_record
    investments=[o for o in original_record['decision']['selected_options'] if o['kind']!='delivery']
    fixed={o['id'] for o in investments}
    for index,response in enumerate(attempts):
        if not isinstance(response,dict) or set(response)!={'customer_id','option_id','accepted'} or type(response['accepted']) is not bool:
            raise ValueError('EXACT_PUBLIC_RESPONSE_REQUIRED')
        customer=response['customer_id'];ident=response['option_id']
        if customer in contacts:raise ValueError('CUSTOMER_ALREADY_CONTACTED')
        matched=[o for o in current['decision']['selected_options'] if o['id']==ident and o['kind']=='delivery' and o['execution']['customer_id']==customer]
        if len(matched)!=1:raise ValueError('RESPONSE_WAS_NOT_TO_SELECTED_QUOTE')
        contacts.add(customer)
        if response['accepted']:
            accepted.add(ident)
            continue
        accepted_customers={o['execution']['customer_id'] for o in current['decision']['selected_options'] if o['id'] in accepted}
        deliveries=[d for d in original_record['deliveries'] if d['customer_id'] not in contacts or d['customer_id'] in accepted_customers]
        current=allocate_actions(original_record['observation'],copy.deepcopy(deliveries),copy.deepcopy(investments),original_record['riskpolicy'],
            allow_seed=original_record['allow_seed'],max_delivery_slots=original_record['max_delivery_slots'],earned_deduction=original_record['earned_deduction'],
            strategic_game=original_record.get('strategic_game'),mandatory_ids=sorted(fixed|accepted),category_upfront_caps=original_record.get('category_upfront_caps'))
        if current['decision']['optimality_scope']=='NONE' and index!=len(attempts)-1:
            raise ValueError('RECOURSE_CONTINUED_AFTER_UNRESOLVED_ALLOCATION')
    if attempts[-1]['accepted']:raise ValueError('RECOURSE_REQUIRES_LATEST_PUBLIC_REFUSAL')
    return current

def trace_digest(original_record,attempts):
    return digest({'original_allocation':digest(original_record),'public_attempts':attempts})
