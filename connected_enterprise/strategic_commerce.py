"""Connected finite price/method choice using inherited portfolio buyer-choice model.

Public authored beliefs are not calibrated demand. Exhaustive finite numerical
Stackelberg optimization is not a global equilibrium or enterprise scale proof.
"""
import copy
import math
from commercial.ledger import digest
from portfolio25.pricing import validate_scenarios, _choice_prices
from .mechanism_choice import MODES, validate_policy as validate_method_policy

PUBLIC_FIELDS = {'anchor','public_rival_price','base_cost','payment_bps','payment_fixed',
                 'available','reserve_buffer','quote_cost','native_state_digest','profit_tax_bps'}
POLICY_FIELDS = {'schema','public_basis','price_bps','rival_price_bps','rival_cost_bps',
                 'rival_response','scenarios'}
RANK = {'default':0,'conventional':1,'generated':2,'ordinary_reuse':3,'critic_retain':4}

def validate_policy(policy):
    if set(policy)-{'demand_model','connected_beliefs'}!=POLICY_FIELDS or policy['schema']!='connected-strategic-commerce/v1':
        raise ValueError('EXPLICIT_FINITE_STRATEGIC_POLICY_REQUIRED')
    if not isinstance(policy['public_basis'],str) or not policy['public_basis'].strip():
        raise ValueError('PUBLIC_BELIEF_PROVENANCE_REQUIRED')
    for field in ('price_bps','rival_price_bps'):
        grid=policy[field]
        if not isinstance(grid,list) or not 1<=len(grid)<=101 or grid!=sorted(set(grid)) or any(type(v) is not int or not 1<=v<=30000 for v in grid):
            raise ValueError('BOUNDED_UNIQUE_PRICE_GRID_REQUIRED')
    if type(policy['rival_cost_bps']) is not int or not 0<=policy['rival_cost_bps']<=30000 or policy['rival_response'] not in {'observed_quote','finite_best_response'}:
        raise ValueError('DECLARED_RIVAL_RESPONSE_REQUIRED')
    validate_scenarios(policy['scenarios'])
    if len({s['id'] for s in policy['scenarios']})!=len(policy['scenarios']):raise ValueError('UNIQUE_PUBLIC_SCENARIO_IDS_REQUIRED')
    model=policy.get('demand_model','portfolio_logit')
    if model not in {'portfolio_logit','connected_range'}:raise ValueError('DECLARED_BUYER_MODEL_REQUIRED')
    if model=='connected_range':
        beliefs=policy.get('connected_beliefs',{})
        if set(beliefs)!={s['id'] for s in policy['scenarios']} or policy['rival_response']!='observed_quote':
            raise ValueError('CONNECTED_PUBLIC_PRIORS_AND_OBSERVED_RIVAL_REQUIRED')
        for b in beliefs.values():
            if set(b)!={'min_value_bps','max_value_bps','min_budget_microUSD','max_budget_microUSD','rival_available_bps'} or any(type(v) is not int or not 0<=v<=10**15 for v in b.values()):raise ValueError('BOUNDED_PUBLIC_BUYER_PRIOR_REQUIRED')
            if b['min_value_bps']>b['max_value_bps'] or b['min_budget_microUSD']>b['max_budget_microUSD'] or b['rival_available_bps']>10000:raise ValueError('VALID_PUBLIC_BUYER_INTERVAL_REQUIRED')
    elif 'connected_beliefs' in policy:raise ValueError('UNUSED_BUYER_BELIEFS_REFUSED')
    # This first connected edition deliberately does not monetize hypothetical repeat work.
    if any(s['repeat_horizon']!=0 or s['cost_shock']!=1 for s in policy['scenarios']):
        raise ValueError('SINGLE_ORDER_EXACT_PREPAID_COST_EDITION_REQUIRED')
    return policy

def _public(public):
    if set(public)!=PUBLIC_FIELDS:raise ValueError('ONLY_EXPLICIT_PUBLIC_OBSERVATIONS_ALLOWED')
    for field in PUBLIC_FIELDS-{'native_state_digest'}:
        if type(public[field]) is not int or not 0<=public[field]<=10**15:raise ValueError('BOUNDED_PUBLIC_INTEGER_REQUIRED')
    if public['anchor']<1 or public['payment_bps']>10000 or public['profit_tax_bps']>10000:
        raise ValueError('VALID_PUBLIC_PRICE_AND_TAX_REQUIRED')
    h=public['native_state_digest']
    if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('NATIVE_STATE_BINDING_REQUIRED')

def _belief_choice(price, rival, public, policy, scenario):
    if policy.get('demand_model','portfolio_logit')=='portfolio_logit':
        return _choice_prices(price,rival,public['anchor'],scenario)
    # Same utility/outside-option ordering as connected buyer_choice. Unknown
    # value and remaining budget use independent PUBLIC uniform interval priors;
    # these are not the buyer's private draw or actual remaining budget.
    b=policy['connected_beliefs'][scenario['id']];h=public['anchor']
    def coverage(x,lo,hi):
        if x<=lo:return 1.0
        if x>hi or hi==lo:return 0.0
        return (hi-x)/(hi-lo)
    def probs(include_rival):
        options={'human':h,'us':price}
        if include_rival and rival is not None:options['rival']=rival
        cheapest=min(options.values());ties=[k for k,v in options.items() if v==cheapest]
        q=coverage(cheapest,h*b['min_value_bps']/10000,h*b['max_value_bps']/10000)*coverage(cheapest,b['min_budget_microUSD'],b['max_budget_microUSD'])
        decline_tie=int(b['min_value_bps']==b['max_value_bps'] and h*b['min_value_bps']==cheapest*10000)
        return tuple(q/(len(ties)+decline_tie) if k in ties else 0.0 for k in ('us','rival'))
    with_rival=probs(True);without=probs(False);a=b['rival_available_bps']/10000
    return tuple(a*x+(1-a)*y for x,y in zip(with_rival,without))

def _response(price, public, policy, scenario):
    anchor=public['anchor']
    if policy['rival_response']=='observed_quote':return public['public_rival_price']
    # Rival cost is independently declared, never derived from our chosen method.
    cost=anchor*policy['rival_cost_bps']/10000
    best=(0.0,None)
    for bps in policy['rival_price_bps']:
        p=anchor*bps//10000
        _, win=_choice_prices(price,p,anchor,scenario)
        value=win*(p*scenario['accept_prob']*scenario['collect_prob']-cost)
        if value>best[0]+1e-9:best=(value,p)
    return best[1] # Rational rival withdrawal remains available.

def select(policy, method_policy, job_id, offer, memory, public, *, _diagnostic_available=None):
    """Choose one admitted offer's execution method and price, or no bid.

    Cash feasibility is conservative: today's full cost plus native principal
    protection and explicit buffer; expected receipts cannot relax this bound.
    Public prefix/deductions must be reconstructed by the calling operating audit.
    """
    validate_policy(policy);_public(public)
    if _diagnostic_available is not None and (type(_diagnostic_available) is not int or _diagnostic_available < public['available']):
        raise ValueError('DIAGNOSTIC_MUST_ONLY_RELAX_DEPLOYABLE_CASH')
    cash_limit=public['available'] if _diagnostic_available is None else _diagnostic_available
    if method_policy is not None:validate_method_policy(method_policy)
    scoped=method_policy is not None and offer['service_id']=='reconciliation'
    if scoped and method_policy['mode']!='optimize':raise ValueError('DIAGNOSTIC_POLICY_NOT_STRATEGIC_OPTIMUM')
    if scoped and method_policy['future_equivalent_jobs']!=0:
        raise ValueError('JOINT_EDITION_REQUIRES_EXPLICIT_ONE_ORDER_HORIZON')
    # Prior memory is authenticated operating state; fresh evidence replay belongs
    # to the paid execution and independent audit, not unfunded quote preparation.
    if memory is not None and (not isinstance(memory,dict) or set(memory)!={'chain','retained'}):
        raise ValueError('SOURCE_BOUND_MEMORY_REFERENCE_REQUIRED')
    modes=[m for m in MODES if m!='hold'] if scoped else ['default']
    problem={'policy':copy.deepcopy(policy),'method_policy':copy.deepcopy(method_policy),
             'job_id':job_id,'offer':copy.deepcopy(offer),'memory':copy.deepcopy(memory),'public':copy.deepcopy(public)}
    rows=[]; best=None
    for mode in modes:
        if mode=='ordinary_reuse' and memory is None:continue
        if mode=='critic_retain' and offer['method']!='generated_schema':continue
        costs={} if mode=='default' else method_policy['costs'][mode]
        method_cost=sum(costs.values())
        for bps in policy['price_bps']:
            price=public['anchor']*bps//10000
            fee=(price*public['payment_bps']+9999)//10000+public['payment_fixed']
            cost=public['base_cost']+method_cost+fee
            reserve=cost+price+public['reserve_buffer']
            feasible=reserve<=cash_limit and price>cost
            if not feasible:continue
            forecasts=[]; expected=0.0
            for sc in policy['scenarios']:
                rival=_response(price,public,policy,sc)
                win,_=_belief_choice(price,rival,public,policy,sc)
                paid=sc['accept_prob']*sc['collect_prob']
                # All fulfillment costs are prepaid on a win, even on nonpayment.
                net=paid*price-cost
                tax=paid*max(0,price-cost)*public['profit_tax_bps']/10000
                contribution=win*(net-tax)-public['quote_cost']
                expected+=sc['weight']*contribution
                forecasts.append({'belief':sc['id'],'rival_price':rival,'win_probability':win,
                                  'accept_collect_probability':paid,'net_after_modeled_tax':contribution})
            row={'mode':mode,'price':price,'cost':cost,'fee':fee,'required_current_cash':reserve,
                 'expected_net':expected,'forecasts':forecasts}
            rows.append(row)
            # Strict tolerance and declared stable tie order avoid numerical fake superiority.
            if expected>0 and (best is None or expected>best['expected_net']+1e-9 or
               abs(expected-best['expected_net'])<=1e-9 and (RANK[mode],price)<(RANK[best['mode']],best['price'])):best=row
    decision={'schema':'connected-strategic-decision/v1','problem_sha256':digest(problem),
              'selected':copy.deepcopy(best),'feasible_candidates':len(rows),'candidate_rows_sha256':digest(rows),
              'scope':'EXHAUSTIVE_FINITE_NUMERICAL_PRICE_METHOD_BEST_RESPONSE_UNDER_PUBLIC_BELIEFS',
              'collection_belief_source':'strategic policy scenario accept_prob * collect_prob; legacy method_policy accept_collect_bps is not used',
              'buyer_belief_source':'connected public intervals and current quote ordering' if policy.get('demand_model')=='connected_range' else 'inherited portfolio public logit hypotheses',
              'limits':'One admitted service offer, one order, fixed public buyer beliefs. No global equilibrium, calibrated demand, future cash, or long-horizon mechanism advantage claimed.'}
    if _diagnostic_available is not None:
        decision['diagnostic_available']=_diagnostic_available
        decision['scope']='COUNTERFACTUAL_CASH_CANDIDATES_NOT_EXECUTABLE'
        return {'offer':None,'method_plan':None,'decision':decision,'problem':problem,'candidates':rows}
    if best is None:return {'offer':None,'method_plan':None,'decision':decision,'problem':problem,'candidates':rows}
    chosen=copy.deepcopy(offer);chosen['price_microUSD']=best['price']
    plan=None
    if scoped:
        mode=best['mode'];costs=copy.deepcopy(method_policy['costs'][mode])
        plan={'problem':problem,'decision':decision,'mode':mode,'diagnostic':False,'costs':costs,
              'memory':copy.deepcopy(memory),'cost':sum(costs.values()),'joint_decision':True}
    return {'offer':chosen,'method_plan':plan,'decision':decision,'problem':problem,'candidates':rows}

def rederive(result):
    """Structural replay; caller must separately bind public facts to native prefix."""
    p=result['problem']
    expected=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],p['public'])
    if result!=expected:raise ValueError('STRATEGIC_COMMERCE_DECISION_CHANGED')
    return expected

def allocate_actions(observation, deliveries, investments, riskpolicy, *, allow_seed=True, max_delivery_slots=1, earned_deduction=0):
    """Joint finite native-state-bound delivery/price/method and expansion choice.

    deliveries contain ALL alternatives of the declared finite shortlist. No
    per-offer winner pruning: lower price/cost can unlock a better joint basket.
    Existing allocator enforces dependencies, exclusivity, overlap, cash, earned
    expansion funding and risk, and returns NONE optimality if bound is exceeded.
    """
    from adaptive_enterprise.allocation import allocate
    options=_action_options(observation,deliveries,investments,riskpolicy)
    decision=allocate(observation,options,riskpolicy,allow_seed=allow_seed,max_delivery_slots=max_delivery_slots,earned_deduction=earned_deduction)
    return {'schema':'connected-joint-actions/v1','risk_scope':'Scenario conditional expectations, not realized worst-case losses; conservative floor to microUSD. Native cash locks bound present commitments.','observation':copy.deepcopy(observation),
            'deliveries':copy.deepcopy(deliveries),'investments':copy.deepcopy(investments),
            'riskpolicy':copy.deepcopy(riskpolicy),'allow_seed':allow_seed,'max_delivery_slots':max_delivery_slots,'earned_deduction':earned_deduction,'decision':decision}

def rederive_actions(record):
    expected=allocate_actions(record['observation'],record['deliveries'],record['investments'],record['riskpolicy'],allow_seed=record['allow_seed'],max_delivery_slots=record['max_delivery_slots'],earned_deduction=record['earned_deduction'])
    if record!=expected:raise ValueError('JOINT_ALLOCATION_CHANGED')
    return expected

def selected_delivery(record, option_id):
    """Materialize a selected quote/method contract; no spending authority.

    Operating verifier must rederive_actions on the referenced planning record
    and its native prefix before accepting this compact per-order reference.
    """
    options=[o for o in record['decision']['selected_options'] if o['id']==option_id and o['kind']=='delivery']
    if len(options)!=1:raise ValueError('SELECTED_JOINT_DELIVERY_REQUIRED')
    selected=options[0];execution=selected['execution'];row=execution['row']
    delivery=next(d for d in record['deliveries'] if d['id']==execution['delivery_id'])
    result=delivery['selection'];p=result['problem']
    if digest(result)!=execution['selection_sha256'] or row not in result['candidates']:
        raise ValueError('SELECTED_DELIVERY_NOT_IN_PUBLIC_FINITE_SET')
    offer=copy.deepcopy(p['offer']);offer['price_microUSD']=row['price'];plan=None
    if row['mode']!='default':
        costs=copy.deepcopy(p['method_policy']['costs'][row['mode']])
        plan={'problem':p,'decision':result['decision'],'mode':row['mode'],'diagnostic':False,
              'costs':costs,'memory':copy.deepcopy(p['memory']),'cost':sum(costs.values()),
              'joint_decision':True,'joint_allocation_sha256':digest(record),'joint_option_id':option_id}
    return {'offer':offer,'method_plan':plan,'price':row['price'],'complete_cost':row['cost'],
            'fee':row['fee'],'joint_allocation_sha256':digest(record),'joint_option_id':option_id}


def _action_options(observation,deliveries,investments,riskpolicy,diagnostic_available=None):
    if not isinstance(deliveries,list) or len(deliveries)>8:raise ValueError('FINITE_DELIVERY_SHORTLIST_REQUIRED')
    options=[]
    for d in deliveries:
        if set(d)!={'id','customer_id','onboarding','exclusive_group','selection','requires'}:raise ValueError('EXACT_DELIVERY_ACTION_REQUIRED')
        result=d['selection']
        if diagnostic_available is None:rederive(result)
        else:
            p=result['problem']
            if result!=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],p['public'],_diagnostic_available=diagnostic_available):raise ValueError('DIAGNOSTIC_CANDIDATES_CHANGED')
        p=result['problem'];pub=p['public']
        if pub['native_state_digest']!=observation['state_digest']:raise ValueError('JOINT_NATIVE_PREFIX_CHANGED')
        if any(abs(s['weight']-riskpolicy['scenarios'].get(s['id'],-1)/10000)>1e-12 for s in p['policy']['scenarios']):
            raise ValueError('JOINT_SCENARIO_WEIGHTS_MUST_MATCH_PUBLIC_BELIEFS')
        for n,row in enumerate(result['candidates']):
            sc_net={x['belief']:math.floor(x['net_after_modeled_tax']) for x in row['forecasts']}
            if set(sc_net)!=set(riskpolicy['scenarios']):raise ValueError('MATCHED_JOINT_BELIEFS_REQUIRED')
            option={'id':d['id']+'-'+str(n),'kind':'delivery','upfront_cost':row['cost'],
                    'later_liabilities':dict.fromkeys(sc_net,0),
                    'future_net_cash':{k:v+row['cost'] for k,v in sc_net.items()},
                    'benefit_ids':['delivery-'+p['job_id']], 'requires':d['requires'],
                    'exclusive_group':d['exclusive_group'],'authorized':True,
                    'evidence':result['decision']['problem_sha256'],
                    'execution':{'job_id':p['job_id'],'customer_id':d['customer_id'],'payment_bps':pub['payment_bps'],'payment_fixed_microUSD':pub['payment_fixed'],'onboarding_microUSD':d['onboarding'],'funding':'SEED_OR_EARNED','cash_lock':row['price']+pub['reserve_buffer'],'delivery_id':d['id'],'row':row,
                                 'selection_sha256':digest(result)}}
            options.append(option)
    if not isinstance(investments,list) or len(investments)>8:raise ValueError('FINITE_COSTED_INVESTMENTS_REQUIRED')
    for o in investments:
        if o['kind'] not in {'acquisition','capacity','instrument'} or o['execution'].get('funding')!='EARNED':
            raise ValueError('EARNED_COSTED_EXPANSION_ONLY')
        # Existing allocation validates full liabilities, benefit overlap, source evidence and dependencies.
        options.append(copy.deepcopy(o))
    return options


def cash_opportunity_diagnostic(record, *, relaxed_available, declared_allocation_ceiling, operating_envelope=0):
    """Replay identical finite game with only deployable cash relaxed.

    record must use the actual unmodified native snapshot. The caller supplies
    the source-bound economic ceiling; only its derived cash clipping is relaxed.
    Earned-only requirements, slots, beliefs,
    costs, liabilities and max_states stay fixed. Returned IDs are diagnostic
    labels, never instructions to execute. No native snapshot is fabricated.
    """
    from adaptive_enterprise.allocation import allocate, _diagnostic_result
    from fractions import Fraction
    rederive_actions(record)
    if type(operating_envelope) is not int or operating_envelope<0:raise ValueError('NONNEGATIVE_OPERATING_ENVELOPE_REQUIRED')
    observation=record['observation']
    if type(relaxed_available) is not int or relaxed_available<observation['summary']['available']:raise ValueError('DIAGNOSTIC_MUST_ONLY_RELAX_CASH')
    if type(declared_allocation_ceiling) is not int or declared_allocation_ceiling<0:raise ValueError('DECLARED_ECONOMIC_CEILING_REQUIRED')
    actual_deployable=max(0,observation['summary']['available']-operating_envelope)
    if record['riskpolicy']['authorized_allocation']!=min(declared_allocation_ceiling,actual_deployable):raise ValueError('ORIGINAL_CASH_CLIPPED_CEILING_MISMATCH')
    deployable=max(0,relaxed_available-operating_envelope)
    risk=copy.deepcopy(record['riskpolicy']);risk['authorized_allocation']=min(declared_allocation_ceiling,deployable)
    deliveries=copy.deepcopy(record['deliveries'])
    for d in deliveries:
        p=d['selection']['problem']
        d['selection']=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],p['public'],_diagnostic_available=deployable)
    options=_action_options(observation,deliveries,record['investments'],risk,deployable)
    counter=allocate(observation,options,risk,allow_seed=record['allow_seed'],max_delivery_slots=record['max_delivery_slots'],earned_deduction=record['earned_deduction'],_diagnostic_cash_limit=relaxed_available)
    actual=_diagnostic_result(record['decision'])
    resolved=actual['optimality_scope']!='NONE' and counter['optimality_scope']!='NONE'
    return {'schema':'connected-cash-opportunity-diagnostic/v1','scope':counter['scope'],
            'source_record_sha256':digest(record),'native_observation_sha256':digest(observation),
            'relaxed_available':relaxed_available,'declared_allocation_ceiling':declared_allocation_ceiling,'operating_envelope':operating_envelope,
            'actual':actual,'counterfactual':counter,'resolved':resolved,
            'predicted_objective_gain':str(Fraction(counter['risk_adjusted_value'])-Fraction(actual['risk_adjusted_value'])) if resolved else None,
            'authorized_digest':None,
            'limits':'Decision-local conditional expected opportunity only; not causal realized profit. Earned funding, risk ceiling, slots and enumerated game unchanged.'}
