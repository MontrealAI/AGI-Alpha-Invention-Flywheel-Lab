"""Finite capacity complements over an observed, uncommitted delivery menu.

Forecast only: no native reservation, execution, fabricated balances or new demand.
Caller must independently bind the snapshot, calendar, admitted work, quote-cost
and current-commitment envelopes to the operating state. Quotes in the recourse
menu exclude the separately declared common evaluation expense.
"""
import copy
from fractions import Fraction
from commercial.ledger import digest
from .strategic_commerce import allocate_actions


def _int(x, minimum=0):
    if type(x) is not int or x < minimum:
        raise ValueError('NONNEGATIVE_EXACT_INTEGER_REQUIRED')
    return x


def _id(x):
    if not isinstance(x,str) or not x or len(x)>100:
        raise ValueError('BOUNDED_PUBLIC_IDENTIFIER_REQUIRED')
    return x


def _slots(calendar, start, finish):
    # Inclusive finish check: production must finish strictly before expiry.
    points={start,finish}|{x['expires_at'] for x in calendar if start<=x['expires_at']<=finish}|{x['active_at'] for x in calendar if start<=x['active_at']<=finish}
    return min(sum(x['units'] for x in calendar if x['active_at']<=t<x['expires_at']) for t in points)


def evaluate(observation, deliveries, riskpolicy, *, now, opportunity_time,
             finish_time, calendar, contract, max_quantity,
             current_commitment_lock, future_evaluation_cost, earned_deduction,
             retention_bps, shared_benefit_id):
    """Return EARNED quantity options and stripped, replayable recourse evidence.

    k=0..max_quantity share exactly one provided finite future menu. All current
    order locks and unpaid operating costs belong in current_commitment_lock.
    Earned deduction independently covers the currently committed earned funds.
    Cash reserved for future work is neutral liquidity, never another expense.
    The EARNED invoice is separate from seed-or-earned future production locks.
    Total cash remains protected; no projected receipts or loss leader.
    """
    for x in (now,opportunity_time,finish_time,max_quantity,current_commitment_lock,future_evaluation_cost,earned_deduction):_int(x)
    if not now<=opportunity_time<finish_time:raise ValueError('FUTURE_PRODUCTION_INTERVAL_REQUIRED')
    _int(retention_bps)
    if retention_bps>10000:raise ValueError('DECLARED_RETENTION_PROBABILITY_REQUIRED')
    _id(shared_benefit_id)
    if not isinstance(calendar,list):raise ValueError('PUBLIC_CAPACITY_CALENDAR_REQUIRED')
    ids=[]
    for c in calendar:
        if set(c)!={'id','units','active_at','expires_at'}:raise ValueError('EXACT_CALENDAR_CONTRACT_REQUIRED')
        ids.append(_id(c['id']));_int(c['units'],1);_int(c['active_at']);_int(c['expires_at'])
        if c['expires_at']<=c['active_at']:raise ValueError('POSITIVE_CAPACITY_LIFETIME_REQUIRED')
    if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_CAPACITY_CONTRACT')
    if set(contract)!={'id','unit_invoice','lead_hours','duration_hours'}:raise ValueError('EXACT_CAPACITY_UNIT_CONTRACT_REQUIRED')
    _id(contract['id']);_int(contract['unit_invoice'],1);_int(contract['lead_hours']);_int(contract['duration_hours'],1)
    if riskpolicy['interactions']:raise ValueError('RECOURSE_DELIVERY_ONLY_INTERACTIONS_REQUIRED')
    if max_quantity+1>riskpolicy['max_states']:raise ValueError('FINITE_QUANTITY_COMPUTATION_BOUND_EXCEEDED')
    if deliveries and future_evaluation_cost<1:raise ValueError('EXPLICIT_COSTED_FUTURE_EVALUATION_REQUIRED')
    for d in deliveries:
        if 'capacity_units' not in d or 'work_keys' not in d:raise ValueError('WEIGHTED_ADMITTED_WORK_REQUIRED')
        if d['requires']:raise ValueError('RECOURSE_MENU_MUST_ALREADY_BE_ADMITTED')
        if d['selection']['problem']['public']['quote_cost']!=0:raise ValueError('COMMON_EVALUATION_MUST_NOT_BE_CHARGED_TWICE')
    inputs=copy.deepcopy(dict(observation=observation,deliveries=deliveries,riskpolicy=riskpolicy,now=now,opportunity_time=opportunity_time,finish_time=finish_time,calendar=calendar,contract=contract,max_quantity=max_quantity,current_commitment_lock=current_commitment_lock,future_evaluation_cost=future_evaluation_cost,earned_deduction=earned_deduction,retention_bps=retention_bps,shared_benefit_id=shared_benefit_id))
    evidence=digest(inputs);rows=[];options=[]
    available=observation['summary']['available'];earned=observation['summary']['unrestrictedEarned']
    base_slots=_slots(calendar,opportunity_time,finish_time)
    active=now+contract['lead_hours'];expires=active+contract['duration_hours']
    covers=active<=opportunity_time and finish_time<expires
    for k in range(max_quantity+1):
        invoice=k*contract['unit_invoice']
        feasible=(k==0 or covers) and invoice<=max(0,earned-earned_deduction) and invoice+current_commitment_lock+future_evaluation_cost<=available
        if not feasible:
            rows.append({'quantity':k,'status':'INFEASIBLE_CONTRACT_OR_PRESENT_CASH','invoice':invoice});continue
        risk=copy.deepcopy(riskpolicy)
        risk['authorized_allocation']=max(0,min(risk['authorized_allocation'],available)-current_commitment_lock-future_evaluation_cost-invoice)
        r=allocate_actions(observation,deliveries,[],risk,allow_seed=True,max_delivery_slots=base_slots+k,earned_deduction=earned_deduction+invoice+future_evaluation_cost)['decision']
        net={s:Fraction(r.get('predicted_scenario_cash_fraction',r['predicted_scenario_cash']).get(s,0))-future_evaluation_cost for s in risk['scenarios']}
        rows.append({'quantity':k,'status':'RESOLVED' if r['optimality_scope']!='NONE' else 'UNRESOLVED_ENUMERATION_BOUND','invoice':invoice,'slots':base_slots+k,'selected_work':[{'job_id':o['execution']['job_id'],'customer_id':o['execution']['customer_id'],'price':o['execution']['row']['price'],'mode':o['execution']['row']['mode'],'capacity_units':o['execution']['capacity_units'],'work_keys':o['execution']['work_keys']} for o in r['selected_options']], 'future_reserve':r['reserve_amount']+future_evaluation_cost,'scenario_net':{s:str(v) for s,v in net.items()},'states_evaluated':r['states_evaluated']})
    baseline=rows[0]
    if baseline['status']=='RESOLVED':
        for row in rows[1:]:
            if row['status']!='RESOLVED':continue
            gain={s:Fraction(retention_bps,10000)*(Fraction(row['scenario_net'][s])-Fraction(baseline['scenario_net'][s])) for s in riskpolicy['scenarios']}
            # Floor forecast conservatively. No positive return is invented for
            # unserved menu/capacity, and no quantity is forced into selection.
            forecast={s:v.numerator//v.denominator for s,v in gain.items()}
            if not any(v>0 for v in forecast.values()):continue
            locks=row['future_reserve'];liability=max(0,-min(forecast.values()))
            if row['invoice']+liability>max(0,earned-earned_deduction):continue
            if row['invoice']+locks+liability+current_commitment_lock>available:continue
            benefits=[shared_benefit_id]+sorted({'delivery-'+w['job_id'] for w in row['selected_work']})
            options.append({'id':'capacity-'+contract['id']+'-'+str(row['quantity']),'kind':'capacity','upfront_cost':row['invoice'],'later_liabilities':dict.fromkeys(forecast,0),'future_net_cash':forecast,'benefit_ids':benefits,'requires':[],'exclusive_group':'capacity-menu-'+contract['id'],'authorized':True,'evidence':evidence,'execution':{'funding':'EARNED','purchased_units':row['quantity'],'contract_id':contract['id'],'active_at':active,'expires_at':expires,'cash_lock':locks,'earned_cash_lock':0,'capacity_recourse_schema':'connected-capacity-recourse/v1','recourse_work_keys':sorted({key for w in row['selected_work'] for key in w['work_keys']}),'recourse_sha256':digest(row)}})
    return {'schema':'connected-capacity-recourse/v1','inputs':inputs,'inputs_sha256':evidence,'recourse':rows,'options':options,'authorized_digest':None,'scope':'Finite provided observed unserved menu, conservative current-cash recourse with earned invoice and seed-or-earned future production locks; common evaluation expense, weighted capacity, no invented arrivals. Scenario incremental conditional expectations only, not realized profit or global horizon optimum. Quantity bound is computational, not an enterprise ceiling. Outer native allocation and current-state reservation remain mandatory.'}


def rederive(record):
    i=record['inputs'];expected=evaluate(**i)
    if expected!=record:raise ValueError('CAPACITY_RECOURSE_CHANGED')
    return expected
