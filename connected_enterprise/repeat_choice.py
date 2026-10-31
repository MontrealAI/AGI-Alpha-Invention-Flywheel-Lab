"""Finite public buyer game and one-next-opportunity planning; no cash authority.

Quality is buyer utility quality, not claimed independently verified outside work.
Atoms are declared hypotheses shared with the opt-in environment. Actual latent
indices remain private. Forecasts condition on observed spending, not balances.
"""
from fractions import Fraction

PROVIDERS=('human','rival','self_service','us')

def validate_contract(c):
    required={'schema','value_bps_atoms','budget_microUSD_atoms','self_service_fee_bps','self_service_effort_bps','self_service_quality_bps','self_service_success_bps','self_service_delay_hours','switching_effort_microUSD','discount_bps'}
    if not isinstance(c,dict) or set(c)!=required or c['schema']!='connected-repeat-choice/v1':raise ValueError('EXPLICIT_FINITE_REPEAT_CHOICE_CONTRACT_REQUIRED')
    for key in ('value_bps_atoms','budget_microUSD_atoms'):
        xs=c[key]
        if not isinstance(xs,list) or not 1<=len(xs)<=5 or xs!=sorted(set(xs)) or any(type(x)is not int or not 1<=x<=10**12 for x in xs):raise ValueError('BOUNDED_PUBLIC_BUYER_ATOMS_REQUIRED')
    for key in required-{'schema','value_bps_atoms','budget_microUSD_atoms'}:
        if type(c[key])is not int or not 0<=c[key]<=10**12:raise ValueError('NONNEGATIVE_PUBLIC_CHOICE_PARAMETER_REQUIRED')
    if c['self_service_success_bps']>10000 or c['self_service_quality_bps']>10000 or c['discount_bps']>10000 or not 1<=c['self_service_delay_hours']<=8760:raise ValueError('VALID_REPEAT_QUALITY_DELAY_DISCOUNT_REQUIRED')
    return c

def options(c,anchor,price,rival,value_bps,budget,last_provider):
    """Same full-utility choices for actual environment and public expectation."""
    value=Fraction(anchor*value_bps,10000)
    rows=[{'provider':'decline','cash':0,'utility':Fraction(0)}]
    quotes={'human':anchor,'self_service':anchor*c['self_service_fee_bps']//10000}
    if rival is not None:quotes['rival']=rival
    if price is not None:quotes['us']=price
    for name,fee in quotes.items():
        if budget<fee:continue
        quality=Fraction(c['self_service_quality_bps']*c['self_service_success_bps'],10000) if name=='self_service' else 10000
        effort=Fraction(anchor*c['self_service_effort_bps'],10000) if name=='self_service' else 0
        switching=c['switching_effort_microUSD'] if last_provider is not None and last_provider!=name else 0
        rows.append({'provider':name,'cash':fee,'utility':value*Fraction(quality,10000)-fee-effort-switching})
    best=max(r['utility'] for r in rows)
    return [r for r in rows if r['utility']==best]

def actual_choice(c,anchor,price,rival,value_bps,budget,last_provider,tie):
    rows=options(c,anchor,price,rival,value_bps,budget,last_provider)
    return max(rows,key=lambda r:tie(r['provider']))

def latent_atoms(c,spent):
    # Frozen public prior with observed cash consumption, not a private balance.
    budgets=[b for b in c['budget_microUSD_atoms'] if b>=spent]
    if not budgets:raise ValueError('OBSERVED_SPENDING_OUTSIDE_DECLARED_BUDGET_PRIOR')
    n=len(c['value_bps_atoms'])*len(budgets)
    return [(v,b-spent,Fraction(1,n)) for v in c['value_bps_atoms'] for b in budgets]

def evaluate(c,policy,public,scenario,price,cost,required_cash):
    """Return immediate contribution and incremental continuation against no bid.

    Next action is optimized after observable provider/payment outcome, NEVER
    separately for each hidden atom. No invented capability gain; terminal
    offers use an admitted fixed-capability successor and full resource cost.
    """
    state=public['repeat_state'];paid=Fraction(str(scenario['accept_prob']))*Fraction(str(scenario['collect_prob']))
    rival=public['public_rival_price'];atoms=latent_atoms(c,state['spent_microUSD'])
    def paths(quote):
        groups={};win=Fraction(0)
        for value,budget,weight in atoms:
            choices=options(c,public['anchor'],quote,rival,value,budget,state['last_provider'])
            for choice in choices:
                w=weight/len(choices);provider=choice['provider']
                if provider=='us':
                    win+=w
                    outcomes=[('us_paid',paid,quote),('us_refund',1-paid,0)]
                elif provider=='self_service':
                    success=Fraction(c['self_service_success_bps'],10000)
                    outcomes=[('self_success',success,choice['cash']),('self_failure',1-success,choice['cash'])]
                else:outcomes=[(provider,Fraction(1),choice['cash'])]
                for outcome,prob,cash in outcomes:
                    if prob:groups.setdefault(outcome,[]).append((value,max(0,budget-cash),w*prob))
        return groups,win
    def continuation(quote,groups):
        if policy.get('lookahead_opportunities',1)!=2:return Fraction(0)
        total=Fraction(0)
        for outcome,rows in groups.items():
            ours=outcome=='us_paid';successor=state['successor'] if outcome in {'us_paid','self_success'} else state['same_service']
            if successor is None:continue
            provider='us' if outcome.startswith('us_') else 'self_service' if outcome.startswith('self_') else outcome if outcome!='decline' else state['last_provider']
            when=state['future_times'][outcome]
            if when>=state['horizon_hours']:continue
            cash_bound=max(0,public['available']-(required_cash if quote is not None else 0))
            survival=Fraction(state['retention_bps'],10000) if ours else Fraction(1)
            # Non-owned, not-yet-onboarded prospects do not receive free followup.
            if not state['followup_eligible'] and not outcome.startswith('us_'):continue
            best=Fraction(0)
            for bps in policy['price_bps']:
                q=successor['anchor']*bps//10000
                fee=(q*public['payment_bps']+9999)//10000+public['payment_fixed']
                expense=successor['base_cost']+fee
                if outcome=='us_refund':expense-=state['onboarding_credit']
                elif outcome=='self_success':expense+=state['onboarding_credit']
                if state['future_slots'][outcome]<=0 or q<=expense or expense+q+public['reserve_buffer']>cash_bound:continue
                win=Fraction(0)
                for value,budget,w in rows:
                    choices=options(c,successor['anchor'],q,successor['rival_price'],value,budget,provider)
                    win+=w*sum(x['provider']=='us' for x in choices)/len(choices)
                tax=paid*max(0,q-expense)*Fraction(public['profit_tax_bps'],10000)
                value=win*(paid*q-expense-tax)
                best=max(best,value)
            # Evaluation is committed even if terminal optimal action is hold.
            best-=sum(w for _,_,w in rows)*public['quote_cost']
            total+=best*survival*Fraction(state['arrival_bps'],10000)*Fraction(c['discount_bps'],10000)
        return total
    current,win=paths(price);hold,_=paths(None)
    tax=paid*max(0,price-cost)*Fraction(public['profit_tax_bps'],10000)
    immediate=win*(paid*price-cost-tax) # current evaluated-shortlist costs are sunk for bid AND hold
    continuation_delta=continuation(price,current)-continuation(None,hold)
    return {'win_probability':float(win),'immediate_expected_net':float(immediate),
            'continuation_delta':float(continuation_delta),'objective':float(immediate+continuation_delta),
            'scope':'ONE_NEXT_ELIGIBLE_DAY_FINITE_PUBLIC_GAME_RANKING_ONLY_NOT_CASH_OR_REALIZED_PROFIT'}

def public_state(cfg,buyer,orders,decisions,investments,jobs,used,current_job,moment,rival_bps):
    """Allowlisted observed events only. Never reads initial/remaining buyer cash."""
    services=('reconciliation','kpi_variance','evidence_matrix')
    current=services[buyer['service_index']%3];next_service=services[(buyer['service_index']+1)%3]
    def admitted(service,onboard):
        candidates=[j for j in jobs if j['id'] not in used and j['id']!=current_job and j['service_id']==service and j['accepted']]
        if not candidates:return None
        j=min(candidates,key=lambda j:j['id']);h=cfg['human_comparator'][service];anchor=int((h['hours']*h['loaded_usd_hour']+2)*1000000)
        return {'job_id':j['id'],'anchor':anchor,'rival_price':anchor*rival_bps//10000,
                'base_cost':cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost']+(0 if onboard else cfg['onboarding_cost'])}
    spent=sum(d.get('outside_spend',0) for d in decisions if d['customer_id']==buyer['id'] and d['time']<moment)
    spent+=sum(o['price'] for o in orders if o['customer_id']==buyer['id'] and o['outcome']=='SETTLED' and o['collection_time']<=moment)
    normal=cfg['production_hours']+cfg['acceptance_hours']+cfg['clearing_hours']
    times={'us_paid':moment+normal+168,'us_refund':moment+cfg['payment_deadline_hours']+168,
           'self_success':moment+cfg['repeat_choice']['self_service_delay_hours']+168,'self_failure':moment+cfg['repeat_choice']['self_service_delay_hours']+24,'human':moment+168,'rival':moment+168,'decline':moment+24}
    times={k:((t+23)//24)*24 for k,t in times.items()}
    def slots(when):
        day=when//24
        if cfg['supplier_outage_start_day']<=day<cfg['supplier_outage_start_day']+cfg['supplier_outage_days']:return 0
        return min(cfg['maximum_slots'],cfg['initial_slots']+sum(i['kind']=='capacity' and i['purchased_time']<moment and i['activation_time']<=when and when+cfg['production_hours']<i['expiry_time'] for i in investments))
    return {'customer_id':buyer['id'],'spent_microUSD':spent,'last_provider':buyer.get('last_provider'),
            'moment':moment,'horizon_hours':cfg['horizon_days']*24,'future_slots':{k:slots(t) for k,t in times.items()},
            'future_times':times,'retention_bps':cfg['retention_bps'],'arrival_bps':cfg['arrival_bps'],
            'onboarding_credit':0 if buyer['onboarded'] else cfg['onboarding_cost'],
            'followup_eligible':buyer['onboarded'] or int(buyer['id'].rsplit('-',1)[1])<4,
            'same_service':admitted(current,buyer['onboarded']),'successor':admitted(next_service,True),
            'observability':'Only dated observed outside spending/settlements/provider and current admitted inventory/capacity. Initial cash, remaining cash, latent atom indices and future draws excluded.'}


def validate_public_state(state):
    keys={'customer_id','spent_microUSD','last_provider','moment','horizon_hours','future_slots','future_times','retention_bps','arrival_bps','followup_eligible','onboarding_credit','same_service','successor','observability'}
    if not isinstance(state,dict) or set(state)!=keys:raise ValueError('ONLY_OBSERVED_REPEAT_STATE_ALLOWED')
    if state['last_provider'] not in (*PROVIDERS,None) or type(state['followup_eligible'])is not bool:raise ValueError('OBSERVED_PROVIDER_STATE_REQUIRED')
    if not isinstance(state['customer_id'],str) or not isinstance(state['observability'],str):raise ValueError('IDENTIFIED_PUBLIC_REPEAT_STATE_REQUIRED')
    for key in ('spent_microUSD','moment','horizon_hours','retention_bps','arrival_bps','onboarding_credit'):
        if type(state[key])is not int or not 0<=state[key]<=10**15:raise ValueError('BOUNDED_PUBLIC_REPEAT_INTEGER_REQUIRED')
    if state['retention_bps']>10000 or state['arrival_bps']>10000:raise ValueError('PUBLIC_REPEAT_PROBABILITY_REQUIRED')
    outcomes={'us_paid','us_refund','self_success','self_failure','human','rival','decline'}
    for key in ('future_times','future_slots'):
        if set(state[key])!=outcomes or any(type(v)is not int or not 0<=v<=10**15 for v in state[key].values()):raise ValueError('EXPLICIT_BOUNDED_FUTURE_OPPORTUNITY_REQUIRED')
    if any(t<state['moment'] for t in state['future_times'].values()):raise ValueError('SUCCESSOR_CANNOT_PRECEDE_CURRENT_DECISION')
    for key in ('same_service','successor'):
        row=state[key]
        if row is None:continue
        if set(row)!={'job_id','anchor','rival_price','base_cost'} or not isinstance(row['job_id'],str) or any(type(row[k])is not int or not 0<=row[k]<=10**15 for k in ('anchor','rival_price','base_cost')):raise ValueError('SOURCE_BOUND_ADMITTED_SUCCESSOR_REQUIRED')
    return state
