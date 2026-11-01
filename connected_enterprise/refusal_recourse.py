"""Paid finite public-response recourse; no private buyer inputs or new funding."""
import copy
from commercial.ledger import digest
from .strategic_commerce import allocate_actions,rederive_actions

SCHEMA='connected-refusal-recourse/v1'

def validate_policy(policy):
    if not isinstance(policy,dict) or set(policy)!={'schema','daily_planning_cost'} or policy['schema']!=SCHEMA:
        raise ValueError('EXPLICIT_PREPAID_RECOURSE_CONTRACT_REQUIRED')
    if type(policy['daily_planning_cost']) is not int or policy['daily_planning_cost']<=0:
        raise ValueError('POSITIVE_PREPAID_DAILY_RECOURSE_COST_REQUIRED')
    return policy

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
            strategic_game=original_record.get('strategic_game'),mandatory_ids=sorted(fixed|accepted))
        if current['decision']['optimality_scope']=='NONE' and index!=len(attempts)-1:
            raise ValueError('RECOURSE_CONTINUED_AFTER_UNRESOLVED_ALLOCATION')
    if attempts[-1]['accepted']:raise ValueError('RECOURSE_REQUIRES_LATEST_PUBLIC_REFUSAL')
    return current

def trace_digest(original_record,attempts):
    return digest({'original_allocation':digest(original_record),'public_attempts':attempts})
