"""Opt-in, bounded method choice bridge; no new ledger or autonomous novelty claim.

Expected collection beliefs and resource envelopes are explicit public hypotheses.
Exact optimization is only over this finite action set, not a global equilibrium.
"""
from fractions import Fraction
import copy
from pathlib import Path
from commercial.ledger import digest, read_bound
from adaptive_enterprise.instruments import execute_offer, retain_failure, compare_methods
from adaptive_enterprise.strategies import offer_catalog, adjudicate_and_adapt

MODES = ('generated', 'conventional', 'ordinary_reuse', 'critic_retain', 'hold')
COST_FIELDS = ('execution', 'discovery', 'integration', 'verification', 'maintenance', 'retrieval', 'failed_attempts')


def validate_cost_contract(contract):
    if not isinstance(contract,dict) or set(contract)!={'schema','basis','production_envelope_microUSD','covered_operations'} or contract['schema']!='connected-method-cost-contract/v1' or contract['basis']!='COMMON_COMPLETE_PRODUCTION_REPLACEMENT' or contract['covered_operations']!=['produce','acceptance_check']:
        raise ValueError('EXPLICIT_COMMON_PRODUCTION_REPLACEMENT_CONTRACT_REQUIRED')
    if type(contract['production_envelope_microUSD']) is not int or contract['production_envelope_microUSD']<=0:
        raise ValueError('POSITIVE_COMMON_PRODUCTION_ENVELOPE_REQUIRED')
    return contract



def validate_common_row(mode,row):
    if set(row)!=set(COST_FIELDS) or any(type(v) is not int or v<0 for v in row.values()):raise ValueError('COMPLETE_INCREMENTAL_COMMON_COSTS_REQUIRED')
    if row['execution']!=0:raise ValueError('EXECUTION_ALREADY_COVERED_BY_PRODUCTION')
    if mode in ('generated','conventional') and any(row.values()):raise ValueError('DIRECT_SUBSTITUTION_ALREADY_COVERED_BY_PRODUCTION')
    if mode=='ordinary_reuse' and (row['retrieval']<=0 or row['verification']<=0):raise ValueError('PAID_MEMORY_RETRIEVAL_AND_REVALIDATION_REQUIRED')
    if mode=='critic_retain' and (row['discovery']+row['integration']<=0 or row['verification']<=0 or row['maintenance']<=0):raise ValueError('PAID_CRITIC_CONSTRUCTION_COMPARISON_RETENTION_REQUIRED')
    return row

def validate_common_costs(costs,contract):
    validate_cost_contract(contract)
    for mode,row in costs.items():validate_common_row(mode,row)
    # These ordinary substitutions execute the same complete admitted service.
    # They receive no claimed speed/cost savings and no duplicate execution fee.
    for mode in ('generated','conventional'):
        if any(costs[mode].values()):raise ValueError('DIRECT_SUBSTITUTION_ALREADY_COVERED_BY_PRODUCTION')
    if any(row['execution'] for row in costs.values()):raise ValueError('EXECUTION_ALREADY_COVERED_BY_PRODUCTION')
    if costs['ordinary_reuse']['retrieval']<=0 or costs['ordinary_reuse']['verification']<=0:
        raise ValueError('PAID_MEMORY_RETRIEVAL_AND_REVALIDATION_REQUIRED')
    if costs['critic_retain']['verification']<=0 or costs['critic_retain']['maintenance']<=0:
        raise ValueError('PAID_CRITIC_COMPARISON_AND_RETENTION_REQUIRED')
    return costs

def checked_memory(memory):
    if memory is None:
        return None
    if set(memory) != {'chain', 'retained'}:
        raise ValueError('SOURCE_GROUNDED_MEMORY_REQUIRED')
    chain = memory['chain']; evidence = chain['adjudication']; raw = evidence['raw_order']
    actual = adjudicate_and_adapt(raw, evidence['rejected_offer'], evidence['rejected_artifact'],
                                  instrument_budget_microUSD=chain['construction_allocation_microUSD'])
    if actual != chain or retain_failure(raw, actual['adjudication']) != memory['retained']:
        raise ValueError('MEMORY_CHAIN_CHANGED')
    return copy.deepcopy(memory['retained'])

def validate_problem(problem):
    if set(problem)-{'cost_contract'} != {'schema', 'public_basis', 'jobs', 'costs', 'initial_memory'} or problem['schema'] != 'connected-method-choice/v1':
        raise ValueError('FINITE_METHOD_PROBLEM_REQUIRED')
    if not isinstance(problem['public_basis'], str) or not problem['public_basis']:
        raise ValueError('PUBLIC_BELIEFS_REQUIRED')
    if type(problem['initial_memory']) is not bool or not 1 <= len(problem['jobs']) <= 8:
        raise ValueError('BOUNDED_HORIZON_REQUIRED')
    if set(problem['costs']) != set(MODES)-{'hold'}:
        raise ValueError('ALL_DIRECT_REUSE_CRITIC_ALTERNATIVES_REQUIRED')
    for mode, row in problem['costs'].items():
        if set(row) != set(COST_FIELDS) or any(type(v) is not int or v < 0 for v in row.values()):
            raise ValueError('COMPLETE_NONNEGATIVE_COST_ENVELOPE_REQUIRED')
        if sum(row.values()) <= 0 and 'cost_contract' not in problem:
            raise ValueError('POSITIVE_PREPAID_METHOD_COST_REQUIRED')
    if 'cost_contract' in problem:validate_common_costs(problem['costs'],problem['cost_contract'])
    if problem['costs']['critic_retain']['discovery']+problem['costs']['critic_retain']['integration']<=0:
        raise ValueError('EXPLICIT_PAID_CRITIC_CONSTRUCTION_REQUIRED')
    for job in problem['jobs']:
        if set(job) != {'job_id', 'price', 'base_cost', 'win_bps', 'accept_collect_bps', 'critic_applicable'} or not isinstance(job['job_id'], str) or type(job['critic_applicable']) is not bool:
            raise ValueError('PUBLIC_ORDER_BELIEF_REQUIRED')
        if type(job['base_cost']) is not int or job['base_cost'] < 0 or type(job['price']) is not int or job['price'] < 0 or any(type(job[k]) is not int or not 0 <= job[k] <= 10000 for k in ('win_bps','accept_collect_bps')):
            raise ValueError('BOUNDED_PUBLIC_PROBABILITY_REQUIRED')
    return problem

def choose(problem):
    """Exact finite horizon optimization; ordinary and retained have equal content.

    Hold preserves capital. Other prices, rival responses, acceptance/collection
    beliefs are supplied public inputs, not a claim to learn private utilities.
    Financing of any chosen action is checked again at execution.
    """
    validate_problem(problem)
    memo = {}
    def solve(index, memory):
        if index == len(problem['jobs']): return Fraction(0), []
        key = (index, memory)
        if key in memo: return memo[key]
        job = problem['jobs'][index]; rows=[]
        for mode in MODES:
            if mode == 'ordinary_reuse' and not memory: continue
            if mode == 'critic_retain' and not job['critic_applicable']: continue
            cost=0 if mode=='hold' else sum(problem['costs'][mode].values())+job['base_cost']
            revenue=Fraction(0) if mode=='hold' else Fraction(job['price']*job['win_bps']*job['accept_collect_bps'], 10000**2)
            future, tail=solve(index+1, memory or mode=='critic_retain')
            rows.append((revenue-cost+future, mode, tail))
        # Fixed, declared tie rule: prefer the simpler direct mode, then hold over speculative construction.
        rank={'conventional':0,'generated':1,'ordinary_reuse':2,'hold':3,'critic_retain':4}
        value,mode,tail=max(rows,key=lambda r:(r[0],-rank[r[1]]))
        memo[key]=(value,[mode,*tail]);return memo[key]
    value,policy=solve(0,problem['initial_memory'])
    return {'problem_sha256':digest(problem),'policy':policy,'expected_net_fraction':[value.numerator,value.denominator],
            'scope':'EXACT_OPTIMUM_OF_DECLARED_FINITE_METHOD_SET_AND_BELIEFS_NOT_GLOBAL_GAME_EQUILIBRIUM'}

def execute_funded(root, manifest, account, offer, job_id, *, ident, day, mode, costs,
                   memory=None, allow_seed=False, expected_net=1, prepaid_order=None, cost_contract=None):
    """Native prepayment before any diagnostic/search/production work.

    Caller must record returned receipt in its authenticated operating checkpoint.
    Diagnostic mode must be explicitly identified by caller; selection isn't implied.
    """
    if mode not in MODES: raise ValueError('DECLARED_METHOD_REQUIRED')
    if mode=='hold': return {'mode':'hold','accepted':False,'cost':0,'memory':memory}
    if set(costs)!=set(COST_FIELDS) or any(type(v) is not int or v<0 for v in costs.values()) or (sum(costs.values())<=0 and cost_contract is None):
        raise ValueError('COMPLETE_METHOD_COSTS_REQUIRED')
    if cost_contract is not None:
        validate_cost_contract(cost_contract);validate_common_row(mode,costs)
        if prepaid_order is None:raise ValueError('COMMON_ENVELOPE_REQUIRES_NATIVE_PRODUCTION_PREPAYMENT')
    # Bind raw job identity without executing the service or doing search.
    job=next(j for j in manifest['jobs'] if j['id']==job_id)
    if job['service_id']!='reconciliation' or offer['service_id']!='reconciliation':
        raise ValueError('SCOPED_RECONCILIATION_BRIDGE_ONLY')
    request={'mode':mode,'job_id':job_id,'offer_sha256':digest(offer),'costs':costs,'memory_sha256':digest(memory)}
    if cost_contract is not None:request['cost_contract']=copy.deepcopy(cost_contract)
    if prepaid_order is None:
        funding=account.spend(ident,'mechanism_resource_contract',sum(costs.values()),day,request,expected_net,allow_seed=allow_seed)
    else:
        entries=account.export()['connected_journal']['entries']
        rows=[e for e in entries if e['request'].get('operation')=='spend' and e['request'].get('id')==prepaid_order+'-resources']
        if len(rows)!=1 or rows[0]['status']!='COMPLETE':raise ValueError('COMPLETED_NATIVE_METHOD_PREPAYMENT_REQUIRED')
        native=rows[0]['request'];plan=native['work'].get('method_plan')
        if native['kind']!='production_contract' or native['day']>day or native['amount']<sum(costs.values()) or not plan or plan['mode']!=mode or plan['costs']!=costs or digest(plan['memory'])!=digest(memory) or native['work']['job_id']!=job_id or digest(native['work']['offer'])!=digest(offer):
            raise ValueError('NATIVE_METHOD_PREPAYMENT_MISMATCH')
        if cost_contract is not None and (plan.get('cost_contract')!=cost_contract or native['work'].get('production_envelope_microUSD')!=cost_contract['production_envelope_microUSD'] or native['amount']<cost_contract['production_envelope_microUSD']+sum(costs.values())):
            raise ValueError('COMMON_PRODUCTION_PREPAYMENT_CHANGED')
        funding=rows[0]['receipt']
    if funding is None:return {'mode':mode,'accepted':False,'reason':'CURRENT_NATIVE_FUNDS_INSUFFICIENT','cost':0,'memory':memory}
    paid_id=prepaid_order+'-resources' if prepaid_order else ident
    paid=[e for e in account.export()['connected_journal']['entries'] if e['request'].get('operation')=='spend' and e['request'].get('id')==paid_id]
    if len(paid)!=1 or paid[0]['status']!='COMPLETE' or paid[0]['receipt']!=funding or funding.get('amount')!=paid[0]['request']['amount'] or funding.get('funding') not in {'SEED','EARNED'}:
        raise ValueError('COMPLETED_NATIVE_PAYMENT_RECEIPT_REQUIRED')
    # Failures remain paid. Never invent missing source facts or silently retry.
    try:
        retained=checked_memory(memory) if memory is not None and (cost_contract is None or mode in {'ordinary_reuse','critic_retain'}) else None
        comparison=None
        if mode=='ordinary_reuse' and retained is None:raise ValueError('VERIFIED_MEMORY_REQUIRED')
        if mode=='critic_retain':
            raw=read_bound(root,job['input'],job['input_sha256']);saved=read_bound(root,job['artifact'],job['artifact_sha256'])
            canonical=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='canonical')
            # The original canonical method is actually rerun and rejected by the adjudicator.
            chain=adjudicate_and_adapt(raw,canonical,saved,instrument_budget_microUSD=max(1,costs['discovery']+costs['integration']))
            retained=retain_failure(raw,chain['adjudication']);memory={'chain':chain,'retained':retained}
            comparison=compare_methods(raw,retained)
        context={'mode':'retained' if mode=='critic_retain' else mode}
        if mode in {'ordinary_reuse','critic_retain'}:context['retained']=retained
        service=execute_offer(root,manifest,offer,job_id,context=context)
        result={'mode':mode,'accepted':service['accepted'],'service':service,'context':context,
                'memory':memory,'comparison':comparison,'cost':sum(costs.values()),'costs':copy.deepcopy(costs),
                'funding':funding,'resource_request':request,'job_id':job_id,'offer':copy.deepcopy(offer),'ident':ident,'day':day,'prepaid_order':prepaid_order}
    except (ValueError,KeyError,TypeError) as error:
        result={'mode':mode,'accepted':False,'error':str(error),'cost':sum(costs.values()),'costs':copy.deepcopy(costs),
                'funding':funding,'resource_request':request,'memory':memory,'job_id':job_id,'offer':copy.deepcopy(offer),'ident':ident,'day':day,'prepaid_order':prepaid_order}
    if cost_contract is not None:result['cost_contract']=copy.deepcopy(cost_contract)
    return result

def audit_execution(root, manifest, account, record):
    """Fresh service execution plus exact native resource binding, not a stored pass."""
    if record.get('mode')=='hold':return {'accepted':False,'scope':'NO_DELIVERY'}
    checked_memory(record.get('memory'))
    journal=account.export()['connected_journal']['entries']
    native_id=(record['prepaid_order']+'-resources') if record.get('prepaid_order') else record['ident']
    matching=[e for e in journal if e['request'].get('id')==native_id and e['request'].get('operation')=='spend']
    if len(matching)!=1 or matching[0]['status']!='COMPLETE' or matching[0]['receipt']!=record['funding'] or record['funding'].get('amount')!=matching[0]['request']['amount'] or record['funding'].get('funding') not in {'SEED','EARNED'}:raise ValueError('COMPLETED_NATIVE_PAYMENT_RECEIPT_REQUIRED')
    req=matching[0]['request']
    if 'cost_contract' in record:
        contract=validate_cost_contract(record['cost_contract']);validate_common_row(record['mode'],record['costs'])
        if record['cost']!=sum(record['costs'].values()):raise ValueError('INCREMENTAL_COST_TOTAL_CHANGED')
        if not record.get('prepaid_order') or req['work'].get('production_envelope_microUSD')!=contract['production_envelope_microUSD'] or req['amount']<contract['production_envelope_microUSD']+record['cost'] or req['work'].get('method_plan',{}).get('cost_contract')!=contract or record['resource_request'].get('cost_contract')!=contract:
            raise ValueError('COMMON_PRODUCTION_AUDIT_BINDING_CHANGED')
    if record.get('prepaid_order'):
        plan=req['work'].get('method_plan')
        if not plan or req['amount']<record['cost'] or plan['mode']!=record['mode'] or plan['costs']!=record['costs'] or req['work']['job_id']!=record['job_id'] or req['day']>record['day'] or digest(plan['memory'])!=record['resource_request']['memory_sha256']:
            raise ValueError('METHOD_NATIVE_COST_BINDING_CHANGED')
    elif req['amount']!=record['cost'] or req['work']!=record['resource_request'] or req['day']!=record['day']:
        raise ValueError('METHOD_NATIVE_COST_BINDING_CHANGED')
    if record['mode']=='critic_retain' and not record.get('error'):
        job=next(j for j in manifest['jobs'] if j['id']==record['job_id'])
        raw=read_bound(root,job['input'],job['input_sha256']);saved=read_bound(root,job['artifact'],job['artifact_sha256'])
        canonical=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='canonical')
        chain=adjudicate_and_adapt(raw,canonical,saved,instrument_budget_microUSD=max(1,record['costs']['discovery']+record['costs']['integration']))
        retained=retain_failure(raw,chain['adjudication'])
        if record['memory']!={'chain':chain,'retained':retained}:
            raise ValueError('CRITIC_MEMORY_NOT_FROM_THIS_FUNDED_INPUT')
        comparison=compare_methods(raw,retained)
        def semantic(value):
            if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if k!='process_cpu_seconds'}
            if isinstance(value,list):return [semantic(v) for v in value]
            return value
        if semantic(record.get('comparison'))!=semantic(comparison):
            raise ValueError('METHOD_COMPARISON_NOT_REPRODUCED')
    elif record['mode']!='critic_retain' and digest(record.get('memory'))!=record['resource_request']['memory_sha256']:
        raise ValueError('REUSE_MEMORY_DIFFERS_FROM_PREFUNDED_CONTEXT')
    if record.get('error'):return {'accepted':False,'paid_failure':True,'native_audit':account.audit()['accepted']}
    context=record['context'];expected={'mode':'retained' if record['mode']=='critic_retain' else record['mode']}
    if record['mode'] in {'ordinary_reuse','critic_retain'}:expected['retained']=record['memory']['retained']
    if context!=expected:raise ValueError('EXECUTED_CONTEXT_CHANGED')
    fresh=execute_offer(root,manifest,record['offer'],record['job_id'],context=context)
    if fresh.get('accepted')!=record['accepted'] or fresh.get('useful_outcome_sha256')!=record['service'].get('useful_outcome_sha256'):
        raise ValueError('FRESH_METHOD_EXECUTION_CHANGED')
    return {'accepted':fresh['accepted'],'native_audit':account.audit()['accepted'],
            'fresh_operation_count':fresh['operation_count'],'useful_outcome_sha256':fresh['useful_outcome_sha256']}

def validate_policy(policy):
    if set(policy)-{'cost_contract'}!={'mode','costs','accept_collect_bps','future_equivalent_jobs','public_basis'} or policy['mode'] not in {'optimize','diagnostic_critic_then_reuse'}:
        raise ValueError('EXPLICIT_OPT_IN_METHOD_POLICY_REQUIRED')
    if type(policy['future_equivalent_jobs']) is not int or not 0<=policy['future_equivalent_jobs']<=7:
        raise ValueError('BOUNDED_PUBLIC_FUTURE_JOB_HYPOTHESIS_REQUIRED')
    validate_problem({'schema':'connected-method-choice/v1','public_basis':policy['public_basis'],'initial_memory':False,
        'jobs':[{'job_id':'validation','price':1,'base_cost':0,'critic_applicable':True,'win_bps':10000,'accept_collect_bps':policy['accept_collect_bps']}], 'costs':policy['costs'],**({'cost_contract':policy['cost_contract']} if 'cost_contract' in policy else {})})
    return policy

def order_plan(policy, job_id, offer, memory, base_cost):
    validate_policy(policy)
    if offer['service_id']!='reconciliation':return None
    problem={'schema':'connected-method-choice/v1','public_basis':policy['public_basis'],'initial_memory':memory is not None,
        'jobs':[{'job_id':job_id if i==0 else 'PUBLIC_EQUIVALENT_JOB_HYPOTHESIS-'+str(i),'price':offer['price_microUSD'],'base_cost':base_cost,
                 'win_bps':10000,'accept_collect_bps':policy['accept_collect_bps'],'critic_applicable':offer['method']=='generated_schema'}
                for i in range(policy['future_equivalent_jobs']+1)], 'costs':policy['costs']}
    if 'cost_contract' in policy:problem['cost_contract']=copy.deepcopy(policy['cost_contract'])
    decision=choose(problem);mode=decision['policy'][0]
    if policy['mode']=='diagnostic_critic_then_reuse':
        mode=('ordinary_reuse' if memory else 'critic_retain') if offer['method']=='generated_schema' else 'conventional'
    return {'problem':problem,'decision':decision,'mode':mode,'diagnostic':policy['mode']!='optimize',
            'costs':{} if mode=='hold' else copy.deepcopy(policy['costs'][mode]),'memory':copy.deepcopy(memory),
            'cost':0 if mode=='hold' else sum(policy['costs'][mode].values()),
            **({'cost_contract':copy.deepcopy(policy['cost_contract'])} if 'cost_contract' in policy else {})}

def audit_order(root,manifest,record,owned_account,policy,joint_actions=None):
    """Recompute strategic choice, method context, native prepayment and output."""
    plan=record.get('method_plan')
    if plan is None:
        if policy and record['offer']['service_id']=='reconciliation':raise ValueError('METHOD_SELECTION_OMITTED')
        return None
    if plan.get('joint_allocation_sha256'):
        from .strategic_commerce import selected_delivery
        wrapper=(joint_actions or {}).get(plan['joint_allocation_sha256'])
        if wrapper is None:raise ValueError('JOINT_ALLOCATION_REFERENCE_REQUIRED')
        selection=selected_delivery(wrapper['allocation'],plan['joint_option_id']);expected=selection['method_plan']
        if selection['offer']!=record['offer']:raise ValueError('JOINT_SELECTED_OFFER_CHANGED')
    elif plan.get('joint_decision'):
        from .strategic_commerce import select
        p=plan['problem'];selection=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],p['public'])
        expected=selection['method_plan']
        if selection['offer']!=record['offer']:raise ValueError('JOINT_SELECTED_OFFER_CHANGED')
    else:expected=order_plan(policy,record['job_id'],record['offer'],plan['memory'],record['complete_cost']-plan['cost'])
    if plan!=expected:raise ValueError('STRATEGIC_METHOD_SELECTION_CHANGED')
    checked_memory(plan['memory'])
    result=record['method_execution']
    if plan.get('cost_contract')!=result.get('cost_contract'):raise ValueError('EXECUTED_COST_CONTRACT_CHANGED')
    if result['mode']!=plan['mode'] or result['costs']!=plan['costs'] or result['cost']!=plan['cost']:
        raise ValueError('EXECUTED_METHOD_DIFFERS_FROM_FUNDED_SELECTION')
    # An account facade exposes only inspected exported native evidence; it grants no mutation.
    class Evidence:
        def export(self):return owned_account
        def audit(self):
            from .finance import audit_journal
            return audit_journal(owned_account,root=root,manifest=manifest)
    checked=audit_execution(root,manifest,Evidence(),result)
    if checked['accepted']!=record['service_receipt'].get('accepted') or result['accepted']!=record['service_receipt'].get('accepted'):
        raise ValueError('METHOD_FAILURE_AND_SERVICE_ACCEPTANCE_DISAGREE')
    return checked
