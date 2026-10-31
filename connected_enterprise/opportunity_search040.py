"""Finite observed-state search over complete-service opportunities and means of reaching them.

Opt-in only. Native execution, customer choice and JournalAccount authorization remain
in engine.py; this file never mutates cash, buyer budgets or source inventories.
"""
from __future__ import annotations
from collections import defaultdict
from commercial.ledger import digest

SCHEMA = 'agi-alpha/opportunity-search040/v1'
POLICY = frozenset({'schema','conversion_bps','max_new_deliveries','buffer_microUSD','minimum_settlements','min_expected_surplus_microUSD'})
SERVICE_IDS = ('reconciliation','kpi_variance','evidence_matrix')

def validate_policy(p):
    if type(p) is not dict or set(p) not in (POLICY, POLICY|{'game'}) or p['schema']!=SCHEMA:
        raise ValueError('EXACT_OPPORTUNITY_POLICY_REQUIRED')
    for name in ('conversion_bps','max_new_deliveries','buffer_microUSD','minimum_settlements','min_expected_surplus_microUSD'):
        if type(p[name]) is not int or p[name]<0:
            raise ValueError('BOUNDED_OPPORTUNITY_INTEGER_REQUIRED:'+name)
    if not 1<=p['conversion_bps']<=10000 or not 1<=p['max_new_deliveries']<=48 or p['buffer_microUSD']>10**12 or not 1<=p['minimum_settlements']<=32 or p['min_expected_surplus_microUSD']>10**12:
        raise ValueError('FINITE_OPPORTUNITY_POLICY_REQUIRED')
    if 'game' in p:
        from .strategic_game042 import validate
        validate(p['game'])
    return p


def search(state,prepared,jobs,candidates,slots,operating_envelope,offer_fn):
    """Choose a *conditional* additional means while preserving direct deliveries.

    Only qualified source jobs, known buyer needs, settled orders and audited
    native balances are observed. No unseen buyer value, channel realization,
    future receipts, projected profit or unearned funding is used for a commit.
    """
    cfg=state['config'];p=validate_policy(cfg['opportunity_policy']);now=prepared['event']['time'];day=now//24
    if state['arm']!='growth' or prepared['event']['kind']!='plan':
        raise ValueError('OPPORTUNITY_SEARCH_REQUIRES_GROWTH_PLAN')
    known=[b for b in candidates if b['known'] and b['active'] and b['remaining_budget']>0]
    direct=[]
    for buyer in known:
        offered=offer_fn(jobs,state,buyer,cfg)
        if offered is None:continue
        entry,offer,_=offered
        fee=(offer['price_microUSD']*cfg['payment_bps']+9999)//10000+cfg['payment_fixed']
        cost=cfg['production_cost']+cfg['support_cost']+cfg['supplier_unit_cost']+fee+(0 if buyer['onboarded'] else cfg['onboarding_cost'])+cfg.get('prospective_policy',{}).get('premium_microUSD',0)
        surplus=offer['price_microUSD']-cost
        if surplus>0:
            direct.append({'customer_id':buyer['id'],'service_id':entry['job']['service_id'],
                           'job_id':entry['job']['id'],'price_microUSD':offer['price_microUSD'],
                           'prepaid_surplus_before_tax_microUSD':surplus})
    direct.sort(key=lambda x:(-x['prepaid_surplus_before_tax_microUSD'],x['customer_id']))
    source_services=sorted({item['job']['service_id'] for item in jobs.values() if item['job']['accepted'] and item['artifact'].get('outcome_scope')=='complete_outcome' and item['job']['service_id'] in SERVICE_IDS})
    settled=[x for x in state['orders'] if x['outcome']=='SETTLED' and x.get('collection_time') is not None and x['collection_time']<now]
    by_service=defaultdict(list)
    for order in settled:
        by_service[order['offer']['service_id']].append(order['price']-order['complete_cost'])
    observed={key:{'settlements':len(by_service[key]),'mean_contribution_microUSD':sum(by_service[key])//len(by_service[key])} for key in sorted(by_service)}
    observed_margins=[margin for entries in by_service.values() for margin in entries]
    summary=prepared['before']['summary']
    available,earned=summary['available'],summary['unrestrictedEarned']
    # No private unknown buyer state enters target value. Any unsold service is an
    # explicit public-catalog opportunity hypothesis, never a verified sale.
    target=direct[0]['service_id'] if direct else None
    if source_services:
        def estimated_target(svc):
            # Human cost is only an authored pricing reference, not willingness to pay.
            anchor=int((cfg['human_comparator'][svc]['hours']*cfg['human_comparator'][svc]['loaded_usd_hour']+2)*1000000)
            price=max(5*1000000,anchor*93//100)
            fee=(price*cfg['payment_bps']+9999)//10000+cfg['payment_fixed']
            cost=cfg['production_cost']+cfg['supplier_unit_cost']+cfg['support_cost']+cfg['onboarding_cost']+fee
            # A declared 50%-of-positive-contribution initial prior, blended with
            # actual settlements. This is *not* an empirically calibrated demand prior.
            prior=max(0,price-cost)//2
            n=len(by_service[svc]);actual=sum(by_service[svc])
            return (2*prior+actual)//(2+n)
        target=max(source_services,key=lambda svc:(estimated_target(svc),-SERVICE_IDS.index(svc)))
    game_basis={'continue_direct':{'count':0,'margin_microUSD':0,
                  'complete_incremental_cost_microUSD':0,'native_invoice_microUSD':0,'eligible':True}}
    feasible=[{'id':'continue_direct','kind':'delivery','cost_microUSD':0,'net_microUSD':0,'target_service_id':direct[0]['service_id'] if direct else target,
               'premise':'No new investment; native buyer-choice and delivery remain independently gated.'}]
    prior=sum(observed_margins)
    if len(settled)>=p['minimum_settlements'] and prior>0 and not summary['investmentStopped']:
        margin=sum(observed_margins)//len(observed_margins)
        pilot=cfg['channels']['pilot'];invoice=pilot['price_microUSD']+pilot['support_microUSD']
        live=[v for v in prepared['channel_after']['instances'].values() if v['state'] not in {'FAILED','EXPIRED'} and v['expiry_day']>day]
        owned=set(sorted(b['id'] for b in state['buyers'])[:pilot['owned_audience_count']])
        reachable=sum(b['id'] not in owned and not b['onboarded'] and len(prepared['channel_after']['contacts'].get(b['id'],[]))<pilot['max_contacts_per_customer'] for b in state['buyers'])
        remaining=cfg['horizon_days']-day-pilot['lead_days']
        if not live and reachable>0 and remaining>1:
            # Expected outcome is an authored conversion hypothesis, not a buyer.
            possible=min(reachable,p['max_new_deliveries'],max(0,remaining*max(slots,0)))
            expected_deliveries=possible*pilot['activation_reliability_bps']*pilot['realization_bps']*p['conversion_bps']//10**12
            expected_net=expected_deliveries*margin*(10000-cfg['profit_tax_bps'])//10000-invoice
            expected_net-=pilot['slots_per_day']*min(pilot['duration_days'],remaining)*cfg['exposure_cost']
            expected_net-=possible*cfg['qualification_cost']
            game_basis['partner_access']={'count':possible,
                'margin_microUSD':max(0,margin)*(10000-cfg['profit_tax_bps'])//10000,
                'complete_incremental_cost_microUSD':invoice+pilot['slots_per_day']*min(pilot['duration_days'],remaining)*cfg['exposure_cost']+possible*cfg['qualification_cost'],
                'native_invoice_microUSD':invoice,
                'eligible':earned>=invoice+p['buffer_microUSD']+operating_envelope and available>=invoice+p['buffer_microUSD']+operating_envelope}
            feasible.append({'id':'partner_access','kind':'acquisition','cost_microUSD':invoice,'net_microUSD':expected_net,
                 'target_service_id':target,'premise':'Declared conversion, observed settled margins, paid channel costs and eligible native earned cash; no future buyer is presumed.',
                 'eligible_current_cash':earned>=invoice+p['buffer_microUSD']+operating_envelope and available>=invoice+p['buffer_microUSD']+operating_envelope})
        recent_declines=sum(d.get('kind')=='capacity_decline' and now-3*24<=d['time']<now for d in state['decisions'])
        if recent_declines>0 and slots<cfg['maximum_slots'] and remaining>2:
            net=min(recent_declines,p['max_new_deliveries'])*margin*(10000-cfg['profit_tax_bps'])//10000-cfg['capacity_price']
            game_basis['add_capacity']={'count':min(recent_declines,p['max_new_deliveries']),
                'margin_microUSD':max(0,margin)*(10000-cfg['profit_tax_bps'])//10000,
                'complete_incremental_cost_microUSD':cfg['capacity_price'],
                'native_invoice_microUSD':cfg['capacity_price'],
                'eligible':earned>=cfg['capacity_price']+p['buffer_microUSD']+operating_envelope and available>=cfg['capacity_price']+p['buffer_microUSD']+operating_envelope}
            feasible.append({'id':'add_capacity','kind':'capacity','cost_microUSD':cfg['capacity_price'],'net_microUSD':net,
                 'target_service_id':target,'premise':'Observed capacity declines and completed margins; hypothetical extra acceptance is not already earned.',
                 'eligible_current_cash':earned>=cfg['capacity_price']+p['buffer_microUSD']+operating_envelope and available>=cfg['capacity_price']+p['buffer_microUSD']+operating_envelope})
    if 'game' in p:
        from .strategic_game042 import solve
        game_certificate=solve(p['game'],game_basis)
        selected=next(x for x in feasible if x['id']==game_certificate['selected'])
    else:
        selected=max((x for x in feasible if x['kind']=='delivery' or x.get('eligible_current_cash') and x['net_microUSD']>p['min_expected_surplus_microUSD']),
                     key=lambda x:(x['net_microUSD'],-x['cost_microUSD'],x['id']))
    decision={'kind':'opportunity_search','time':now,'schema':SCHEMA,'source':'OBSERVED_NATIVE_STATE_AND_DECLARED_CONTRACTS',
              'observed':observed,'direct_outcomes':direct[:24],'source_services':source_services,
              'unseen_buyer_outcomes':'UNKNOWN','binding_constraint':'NEEDS_DISTRIBUTION' if not direct and len(settled)>=p['minimum_settlements'] else 'CURRENT_DEMAND_AND_FINANCING',
              'alternatives':feasible,'selected':selected['id'],'target_service_id':selected['target_service_id'],
              'native_state_sha256':prepared['before']['state_digest'],
              'available_microUSD':available,'unrestricted_earned_microUSD':earned,
              'policy_sha256':digest(p),'decision_scope':'FINITE_ESTIMATES_NOT_OBSERVED_CAUSAL_BENEFIT_OR_SPENDING_PERMISSION'}
    if 'game' in p:
        decision['game_basis']=game_basis
        decision['game_certificate']=game_certificate
        decision['decision_scope']='SCOPED_FINITE_FOLLOWER_BEST_RESPONSE_NOT_GLOBAL_MARKET_OPTIMUM_OR_SPENDING_PERMISSION'
    decision['id']=digest(decision)
    return decision


def audit_history(result,manifest):
    """Independently check prior-collection observations and selected native acts.

    Historical features are rederived from executed native-audited orders. This is
    not an exogenous validation of a channel-conversion prior or market demand.
    """
    cfg=result['config'];validate_policy(cfg['opportunity_policy'])
    rows=[d for d in result['decisions'] if d.get('kind')=='opportunity_search']
    events=[e for e in result['events'] if e['kind']=='OPPORTUNITY_SELECTION']
    if result['arm']!='growth':
        if rows or events:raise ValueError('BASELINE_MUST_NOT_EXECUTE_SEARCH')
        return {'opportunity_search_decisions_checked':0,'successful_constraint_transfers':0}
    expected_days=set(range(cfg['horizon_days']))
    if len(rows)!=len(expected_days) or len(events)!=len(rows):raise ValueError('ONE_SEARCH_PER_PLANNING_DAY_REQUIRED')
    byday={d['time']//24:d for d in rows}
    byevent={e['time']//24:e for e in events}
    if set(byday)!=expected_days or set(byevent)!=expected_days:raise ValueError('OPPORTUNITY_SEARCH_DAY_MISMATCH')
    settlements=[o for o in result['orders'] if o['outcome']=='SETTLED' and o['collection_time'] is not None]
    service_ids={job['service_id'] for job in manifest['jobs'] if job.get('accepted') and job['service_id'] in SERVICE_IDS}
    transfers=0
    for day in sorted(expected_days):
        d=byday[day];e=byevent[day];t=day*24
        if d['time']!=t or d['schema']!=SCHEMA or d['source']!='OBSERVED_NATIVE_STATE_AND_DECLARED_CONTRACTS' or d['unseen_buyer_outcomes']!='UNKNOWN' or d['policy_sha256']!=digest(cfg['opportunity_policy']):raise ValueError('UNAUTHORIZED_OPPORTUNITY_OBSERVATION')
        identity=digest({key:value for key,value in d.items() if key!='id'})
        if identity!=d['id'] or e['decision_sha256']!=d['id'] or e['selected']!=d['selected'] or e['target_service_id']!=d['target_service_id']:
            raise ValueError('OPPORTUNITY_DECISION_EVENT_IDENTITY_CHANGED')
        past=[o for o in settlements if o['collection_time']<t]
        service={}
        for svc in sorted({o['offer']['service_id'] for o in past}):
            margins=[o['price']-o['complete_cost'] for o in past if o['offer']['service_id']==svc]
            service[svc]={'settlements':len(margins),'mean_contribution_microUSD':sum(margins)//len(margins)}
        if d['observed']!=service or not set(d['source_services'])<=service_ids or d['selected'] not in {'continue_direct','partner_access','add_capacity'}:raise ValueError('OPPORTUNITY_CLAIM_NOT_SUPPORTED_BY_PRIOR_SETTLEMENTS')
        alternatives=d['alternatives']
        if type(alternatives) is not list or not alternatives or len(alternatives)>3 or len({x['id'] for x in alternatives})!=len(alternatives):raise ValueError('FINITE_OPPORTUNITY_SEARCH_NOT_RECORDABLE')
        if 'game' in cfg['opportunity_policy']:
            from .strategic_game042 import solve
            basis=d.get('game_basis')
            if d.get('game_certificate')!=solve(cfg['opportunity_policy']['game'],basis):
                raise ValueError('GAME_CERTIFICATE_NOT_REDERIVABLE_FROM_DECLARED_STRATEGIC_GAME')
            if set(basis)!=set(x['id'] for x in alternatives):
                raise ValueError('GAME_ACTIONS_NOT_SOURCE_LINKED_TO_NATIVE_ALTERNATIVES')
            margins=[o['price']-o['complete_cost'] for o in past]
            expected_margin=(max(0,sum(margins)//len(margins))*(10000-cfg['profit_tax_bps'])//10000) if margins else 0
            for alternative in alternatives:
                name=alternative['id']
                if name=='continue_direct':continue
                b=basis[name]
                if (b['native_invoice_microUSD']!=alternative['cost_microUSD']
                    or b['eligible'] is not alternative['eligible_current_cash']
                    or b['margin_microUSD']!=expected_margin):
                    raise ValueError('GAME_BASIS_NOT_MATCHED_NATIVE_CURRENT_COST_AND_SETTLEMENT')
                if name=='partner_access':
                    terms=cfg['channels']['pilot']
                    invoice=terms['price_microUSD']+terms['support_microUSD']
                    remaining=cfg['horizon_days']-day-terms['lead_days']
                    if b['count']>cfg['opportunity_policy']['max_new_deliveries'] or b['count']>max(0,remaining*cfg['maximum_slots']):
                        raise ValueError('GAME_REACH_EXCEEDS_DECLARED_SOURCE_CAPACITY')
                    cost=invoice+terms['slots_per_day']*min(terms['duration_days'],remaining)*cfg['exposure_cost']+b['count']*cfg['qualification_cost']
                    if b['native_invoice_microUSD']!=invoice or b['complete_incremental_cost_microUSD']!=cost:
                        raise ValueError('GAME_PARTNER_COST_NOT_REDERIVED')
                elif name=='add_capacity':
                    declines=sum(d0.get('kind')=='capacity_decline' and t-3*24<=d0['time']<t for d0 in result['decisions'])
                    if (b['count']!=min(declines,cfg['opportunity_policy']['max_new_deliveries'])
                            or b['complete_incremental_cost_microUSD']!=cfg['capacity_price']):
                        raise ValueError('GAME_CAPACITY_COST_OR_PRIOR_DECLINES_CHANGED')
            best=next(x for x in alternatives if x['id']==d['game_certificate']['selected'])
        else:
            if 'game_certificate' in d or 'game_basis' in d:
                raise ValueError('UNREGISTERED_STRATEGIC_GAME_EVIDENCE')
            valid=[x for x in alternatives if x['kind']=='delivery' or x.get('eligible_current_cash') and x['net_microUSD']>cfg['opportunity_policy']['min_expected_surplus_microUSD']]
            best=max(valid,key=lambda x:(x['net_microUSD'],-x['cost_microUSD'],x['id']))
        if best['id']!=d['selected'] or best['target_service_id']!=d['target_service_id']:raise ValueError('OPPORTUNITY_SELECTION_NOT_FINITE_OPTIMUM')
        day_invest=[i for i in result['investments'] if i['purchased_time']==t]
        if d['selected']=='continue_direct' and day_invest:raise ValueError('NO_OPPORTUNITY_INVESTMENT_ALLOWED_ON_HOLD')
        if any(i['kind']!=('acquisition' if d['selected']=='partner_access' else 'capacity') for i in day_invest):raise ValueError('WRONG_OPPORTUNITY_MEANS_EXECUTED')
        for i in day_invest:
            if i['funding_receipt'].get('funding')!='EARNED':raise ValueError('OPPORTUNITY_REQUIRES_ACTUAL_EARNED_FINANCING')
            if not past:raise ValueError('UNFUNDED_OPPORTUNITY_BEFORE_ACCEPTED_COLLECTION')
            later=[o for o in settlements if o['collection_time']>t and o.get('acquisition_source_plan_id' if i['kind']=='acquisition' else 'capacity_source_plan_id')==i['plan_id']]
            if later and any(o['offer']['service_id']!=past[-1]['offer']['service_id'] for o in later):transfers+=1
    return {'opportunity_search_decisions_checked':len(rows),'source_linked_new_service_transfers':transfers,
            'scope':'NATIVE_SIMULATED_DECISIONS_AND_PRIOR_SETTLEMENTS_NO_CAUSAL_OR_REAL_COMMERCE_CLAIM'}


def connected_sequence(result,manifest):
    """Construct a post-audit *claim* from native events, never create a sale.

    Invoke only after the canonical source-bound independent native audit has
    accepted this complete result. Margin is order-level contribution and does
    not by itself isolate the investment's causal effect or complete host cost.
    """
    receipt=audit_history(result,manifest)
    orders=[o for o in result['orders'] if o['outcome']=='SETTLED' and o.get('collection_time') is not None]
    choices={d['time']:d for d in result['decisions'] if d.get('kind')=='opportunity_search'}
    chains=[]
    for investment in result['investments']:
        if investment['funding_receipt']['funding']!='EARNED' or investment['kind'] not in {'acquisition','capacity'}:continue
        t=investment['purchased_time'];prior=[o for o in orders if o['collection_time']<t]
        key='acquisition_source_plan_id' if investment['kind']=='acquisition' else 'capacity_source_plan_id'
        later=[o for o in orders if o['collection_time']>t and o.get(key)==investment['plan_id']]
        if not prior or not later:continue
        higher=[(a,b) for a in prior for b in later if a['offer']['service_id']!=b['offer']['service_id'] and b['price']-b['complete_cost']>a['price']-a['complete_cost']]
        if not higher:continue
        a,b=max(higher,key=lambda x:(x[1]['price']-x[1]['complete_cost'])-(x[0]['price']-x[0]['complete_cost']))
        decision=choices.get(t)
        if decision is None or decision['selected']!=('partner_access' if investment['kind']=='acquisition' else 'add_capacity'):continue
        chains.append({'prior_collection':{'order_id':a['id'],'service_id':a['offer']['service_id'],'collected_microUSD':a['price'],
                      'contribution_before_tax_microUSD':a['price']-a['complete_cost'],'time':a['collection_time']},
                      'constraint_change':{'kind':investment['kind'],'decision_id':decision['id'],'time':t,
                      'native_earned_cost_microUSD':investment['cost'],'source_plan_id':investment['plan_id']},
                      'next_opportunity':{'order_id':b['id'],'service_id':b['offer']['service_id'],'collected_microUSD':b['price'],
                      'contribution_before_tax_microUSD':b['price']-b['complete_cost'],'time':b['collection_time']},
                      'source_linked_later_settlements':len(later),
                      'complete_enterprise_modeled_profit_microUSD':result['summary']['profit'],
                      'scope':'SOURCE_LINKED_SYNTHETIC_VERSUS_EARLIER_LOWER_UNIT_CONTRIBUTION_NOT_CAUSAL_OR_REAL_MARKET_SUPERIORITY'})
    return {'schema':'agi-alpha/opportunity-sequence040/v1','scope':'NATIVE_AUDITED_SIMULATION_ONLY',
            'status':'CONNECTED_PROFITABLE_OPPORTUNITY_SEQUENCE' if chains and result['summary']['profit']>0 else 'NOT_ESTABLISHED',
            'chains':chains[:8], 'opportunity_audit':receipt,'actual_customers':0,'actual_collections_microUSD':0,
            'actual_profit_microUSD':None,'claimed_new_invention':False,'claimed_discovery_policy_advantage':False,
            'funding_authority':False, 'limitations':['Authored buyers/contract terms and estimated conversion; no calibrated real distribution.',
             'Source attribution does not alone establish causal marginal profit versus a matched no-investment control.',
             'Only canonical native audit can establish financial and customer acceptance facts. Host/model billing is unknown.']}
