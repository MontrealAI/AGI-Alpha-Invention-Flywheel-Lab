"""Operating enterprise with isolated public learning and persistent market actors.

Every monetary mutation uses Account and the inherited protected exchange. Market
preferences and timing are disclosed simulation assumptions, not observed demand.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
from adaptive_enterprise.account import Account
from adaptive_enterprise.allocation import allocate, default_riskpolicy
from adaptive_enterprise.learning import Policy, OFFER_FIELDS, validate_public
from adaptive_enterprise.strategies import offer_catalog,adjudicate_and_adapt
from adaptive_enterprise.instruments import load_jobs, execute_offer, infer_plan, retain_failure, compare_methods
from commercial.ledger import canonical, digest, read_bound

MICRO = 1_000_000
SERVICES = ('reconciliation', 'kpi_variance', 'evidence_matrix')


def usd(value):
    return int(round(value * MICRO))


def keyed(seed, cycle, actor, purpose):
    return int.from_bytes(hashlib.sha256(canonical(['adaptive012', seed, cycle, actor, purpose])).digest()[:8], 'big') / 2**64


def default_policy():
    return {'schema': 'agi-alpha/adaptive012-operating-policy/v1', 'scope': 'SIMULATED', 'currency': 'simulated-microUSD',
        'max_cycles': 24, 'decision_slots': 3, 'cycle_days': 7, 'opening': usd(5000), 'working': usd(100), 'setup_cost': usd(75),
        'learning_budget_per_decision': usd(.05), 'quote_cost': usd(.20), 'onboarding_once': usd(.50), 'base_production_cost': usd(1.5),
        'payment_bps': 290, 'payment_fixed': usd(.30), 'profit_tax_bps': 2000, 'payment_deadline_days': 35,
        'instrument_cost': usd(8), 'channel_cost': usd(6), 'capacity_cost': usd(8), 'supplier_diversity_cost': usd(5),
        'maintenance_per_cycle': usd(.10), 'upfront_cost_multiplier': 1., 'supplier_initial_capacity': 2, 'reachable_channel_capacity': 12, 'discount_per_cycle': .03,
        'human_comparator': {'reconciliation': {'hours': .65, 'loaded_usd_hour': 34.75}, 'kpi_variance': {'hours': .65, 'loaded_usd_hour': 60}, 'evidence_matrix': {'hours': .8, 'loaded_usd_hour': 55}, 'operations_bundle': {'hours':1.9,'loaded_usd_hour':50.58552631578947}},
        'thresholds': {'minimum_customers': 3, 'minimum_settled_jobs': 12, 'minimum_repeat_customers': 2, 'minimum_profitable_earned_continuations': 2, 'region_success_fraction': .75, 'downside_cvar_limit': usd(750)},
        'risk': {**default_riskpolicy(), 'worst_loss_limit': usd(30), 'authorized_allocation': usd(100)},
        'arms': ['full_adaptive', 'strategic_011_public_priors', 'strong_fixed', 'ordinary_adaptive', 'no_memory', 'no_opponent', 'no_diagnosis', 'no_instrument', 'no_capital_adaptation'],
        'cost_evidence': 'AUTHORED_RESOURCE_ENVELOPES_NOT_MODEL_BILLS. Setup covers construction, search, qualification of all source packets, integration and failures. Actual deterministic production, generated intake search and separate checker execute. Bid, learning, onboarding, production, supplier, correction/support, maintenance, experiments, fees, taxes and failed work are charged. No hypothetical human staff or CPU-to-human-time conversion. Billing unavailable; scope is conditional simulation.',
        'human_evidence': 'Matched small synthetic packets:12invoices/10metrics/8requirements; first-order0.65/0.65/0.80human-hour scenarios with0.10h onboarding deducted from repeat outside alternatives, broad loadedcompensation proxies, plus2USDtools. Authored times and SLA waiting scenarios, not measurements, selling prices or wages for a specific customer.',
        'hard_constraints': ['Synthetic authorized input only', 'Native money conservation and obligations', 'Mandatory owned Account on local POSIX filesystem', 'No private actor state in policy observation', 'No fabricated technical acceptance', 'No future receipts funding current commitments'],
        'revisable_policies': ['Price range and allocation shortlist', 'Channel, segment, capacity and method selection', 'Exploration and diagnostic cadence', 'Withdrawal or profitable expansion'],
        'simulation_limits': ['Buyer utilities, rival reactions, supplier terms, demand arrival, reputation and payment timing are scenario assumptions.', 'Competitors share a competent complete-outcome specification; only our actual delivered artifacts are directly executed and independently checked.', 'Finite public-information heuristics and a finite allocation shortlist; no equilibrium, general optimality, live demand or autonomous invention-superiority claim.', 'Native principal-plus-fee reserves remain restricted; initial capital may back reserves while earnings finance subsequent delivery.']}


def validate_policy(policy):
    template = default_policy()
    if not isinstance(policy, dict) or set(policy) != set(template) or policy['schema'] != template['schema'] or policy['scope'] != 'SIMULATED' or policy['currency'] != template['currency']:
        raise ValueError('EXACT_ADAPTIVE_OPERATING_POLICY_REQUIRED')
    for key in ['max_cycles','decision_slots','cycle_days','supplier_initial_capacity','payment_deadline_days','reachable_channel_capacity']:
        if type(policy[key]) is not int or not 1 <= policy[key] <= 1000:
            raise ValueError('BOUNDED_OPERATING_HORIZON_AND_CAPACITY_REQUIRED')
    for key in ['opening','working','setup_cost','learning_budget_per_decision','quote_cost','onboarding_once','base_production_cost','payment_fixed','instrument_cost','channel_cost','capacity_cost','supplier_diversity_cost','maintenance_per_cycle']:
        if type(policy[key]) is not int or not 0 <= policy[key] <= 10**12:
            raise ValueError('INTEGER_MICROUSD_RESOURCE_BUDGET_REQUIRED')
    if policy['arms'] != template['arms'] or type(policy['upfront_cost_multiplier']) not in {int,float} or not 0 < policy['upfront_cost_multiplier'] <= 20 or not math.isfinite(policy['upfront_cost_multiplier']):
        raise ValueError('DECLARED_ARMS_AND_FINITE_COST_MULTIPLIER_REQUIRED')
    if type(policy['discount_per_cycle']) not in {int,float} or not math.isfinite(policy['discount_per_cycle']) or policy['discount_per_cycle']<=0:raise ValueError('POSITIVE_DECLARED_FORECAST_DISCOUNT_REQUIRED')
    for key in ['payment_bps','profit_tax_bps']:
        if type(policy[key]) is not int or not 0 <= policy[key] <= 10000:
            raise ValueError('BASIS_POINT_TARIFF_REQUIRED')
    if set(policy['human_comparator']) != set(SERVICES)|{'operations_bundle'}:
        raise ValueError('MATCHED_COMPLETE_HUMAN_COMPARATORS_REQUIRED')
    for record in policy['human_comparator'].values():
        if not isinstance(record,dict) or set(record) != {'hours','loaded_usd_hour'} or any(type(v) not in {int,float} or not math.isfinite(v) or v<=0 for v in record.values()):
            raise ValueError('POSITIVE_FINITE_HUMAN_WORKLOAD_REQUIRED')
    if set(policy['thresholds']) != set(template['thresholds']) or any(type(v) not in {int,float} or not math.isfinite(v) or v <= 0 for v in policy['thresholds'].values()) or policy['thresholds']['region_success_fraction'] > 1:
        raise ValueError('PREDECLARED_ECONOMIC_AND_RISK_THRESHOLDS_REQUIRED')
    return policy


def world_specs():
    base = {'arrival': .94, 'retention': .97, 'value_scale': 1., 'premium_fraction': .45, 'rival_response_delay': 2, 'rival_observation_delay': 1, 'rival_initial_price_ratio': .9, 'rival_private_cost_ratio': .2, 'rival_capacity': 2, 'supplier_base_quote': usd(.25), 'supplier_observation_delay': 1, 'supplier_outage_start': -1, 'supplier_outage_length': 0, 'payment_delay_days': 7, 'payment_default_probability': .02, 'feedback_delay_cycles': 1, 'demand_shift_cycle': -1, 'demand_shift_factor': 1., 'imitation_cycle': -1, 'rival_fast_hours': 24.}
    changes = [
        ('recurring_complete_service', {}),
        ('unseen_responsive_rival', {'rival_initial_price_ratio': .75, 'rival_response_delay': 1, 'rival_private_cost_ratio': .12}),
        ('demand_shift', {'demand_shift_cycle': 10, 'demand_shift_factor': .55}),
        ('competent_imitation', {'imitation_cycle': 10, 'rival_fast_hours': 4., 'rival_initial_price_ratio': .85}),
        ('supplier_interruption', {'supplier_outage_start': 8, 'supplier_outage_length': 3, 'supplier_base_quote': usd(.45)}),
        ('delayed_payments', {'payment_delay_days': 23, 'feedback_delay_cycles': 2, 'payment_default_probability': .04}),
        ('premium_need_mix', {'premium_fraction': .8, 'rival_capacity': 1}),
        ('joint_adverse', {'arrival': .60, 'retention': .85, 'demand_shift_cycle': 8, 'demand_shift_factor': .6, 'supplier_outage_start': 9, 'supplier_outage_length': 3, 'payment_default_probability': .12, 'rival_initial_price_ratio': .55})]
    return [{'id': name, **base, **change} for name, change in changes]


def _world(world):
    fields = set(world_specs()[0])
    if not isinstance(world,dict) or set(world) != fields:
        raise ValueError('EXACT_PRIVATE_EVALUATION_WORLD_REQUIRED')
    for key,value in world.items():
        if key=='id':
            if not isinstance(value,str) or not value: raise ValueError('EVALUATOR_WORLD_ID_REQUIRED')
        elif type(value) not in {int,float} or not math.isfinite(value):
            raise ValueError('FINITE_PRIVATE_EVALUATION_ASSUMPTION_REQUIRED')
    for key in ['arrival','retention','payment_default_probability','premium_fraction']:
        if not 0 <= world[key] <= 1: raise ValueError('PRIVATE_WORLD_PROBABILITY_REQUIRED')
    return copy.deepcopy(world)


class MarketActors:
    """Private environment; only public_view outputs may reach Policy.act."""
    def __init__(self, policy, world, seed):
        self.spec, self.seed = _world(world), seed
        self.human = copy.deepcopy(policy['human_comparator'])
        self.buyers = []
        for i in range(policy['reachable_channel_capacity']):
            premium = keyed(seed,-1,i,'segment') < world['premium_fraction']
            self.buyers.append({'id':f'SIM-customer-{i:02d}','segment':'premium' if premium else 'standard','budget':usd(450+900*keyed(seed,-1,i,'budget')),'value_factor':1.4+2.2*keyed(seed,-1,i,'value'),'urgency':1. if premium else .45,'active':True,'visible':i<4,'purchases':0,'onboarded':False,'last_outcome':'NEW','trust':.95,'next_service':i%3,'last_cycle':-1})
        for buyer in self.buyers:
            buyer.update(initial_budget=buyer['budget'],commitments={},outside_spend=0,our_settled_spend=0)
        self.rival_cash=usd(500);self.rival_initial_cash=self.rival_cash;self.rival_collections=0;self.rival_expenses=0
        self.supplier_cash=usd(100);self.supplier_initial_cash=self.supplier_cash;self.supplier_collections=0;self.supplier_expenses=0
        self.rival_prices={s: int((policy['human_comparator'][s]['hours']*policy['human_comparator'][s]['loaded_usd_hour']+2)*MICRO*world['rival_initial_price_ratio']) for s in policy['human_comparator']}
        self.rival_history=[];self.rival_observations=[];self.ad_queue=[];self.visible_ads=[]
        self.supplier_quote=world['supplier_base_quote'];self.supplier_history=[];self.supplier_queue=[]
        self.capacity_extension=0;self.diversified=False;self.cycle=-1;self.actual_capacity=0;self.leads=[];self.pending_leads=[]
        self.instrument=False;self.retained=None;self.source_obstacles=[];self.market_events=[];self.pending_retention=[];self.retention_attempted=set();self.imitated=False;self.rival_remaining_capacity=0;self.rival_modeled_contribution=0;self.capacity_sources=[];self.diversity_source=None;self.instrument_source=None;self.actual_outage=False

    def advance(self, cycle, policy):
        self.cycle=cycle
        for event in list(self.pending_leads):
            if event['cycle']<=cycle:
                for buyer in self.buyers[event['start']:event['stop']]:buyer['visible']=True;buyer['active']=True;buyer['acquisition_plan_id']=event['plan_id']
                self.pending_leads.remove(event);self.market_events.append({'cycle':cycle,'kind':'PAID_CHANNEL_LEADS_ACTIVATED','count':event['stop']-event['start']})
        for renewal in list(self.pending_retention):
            if renewal['cycle']<=cycle:
                buyer=next(b for b in self.buyers if b['id']==renewal['customer_id']);responded=keyed(self.seed,cycle,buyer['id'],'paid-renewal-response')<.6
                if responded:buyer['active']=True;buyer['retention_plan_id']=renewal['plan_id']
                self.market_events.append({'cycle':cycle,'kind':'COSTED_RETENTION_RESPONSE','customer_id':buyer['id'],'responded':responded,'source_plan':renewal['plan_id'],'scope':'Simulated paid customer-context service reminder; response probability.6 is an explicit scenario assumption, not guaranteed new demand.'});self.pending_retention.remove(renewal)
        self.rival_remaining_capacity=int(self.spec['rival_capacity'])
        visible_rival_history=[r for r in self.rival_observations if r['visible_cycle']<=cycle]
        if not self.imitated and self.spec['imitation_cycle']>=0 and cycle>=self.spec['imitation_cycle'] and visible_rival_history:
            adopted=next((r for r in reversed(visible_rival_history) if r['offered_method']=='generated_schema'),visible_rival_history[-1]);self.imitated=True;self.rival_modeled_contribution-=usd(8);self.rival_cash-=usd(8);self.rival_expenses+=usd(8)
            self.market_events.append({'cycle':cycle,'kind':'COMPETITOR_COPIED_OBSERVED_EXECUTABLE_METHOD','source_action_id':adopted['action_id'],'adopted_pipeline_method':adopted['offered_method'],'qualification':'Competent use of the same public deterministic production/verification tools is a scenario assumption; copied method has8USD modeled acquisition cost and declared fast supplier scheduling, not a free trust/quality multiplier.'})
        if cycle and cycle % max(1,int(self.spec['rival_response_delay'])) == 0:
            observed=[r for r in self.rival_observations if r['visible_cycle']<=cycle]
            for service in self.rival_prices:
                records=[r for r in observed[-18:] if r['service_id']==service]
                if records:
                    own_prices=[r['our_price'] for r in records]
                    win_fraction=sum(r['rival_chosen'] for r in records)/len(records)
                    private_floor=int((policy['human_comparator'][service]['hours']*policy['human_comparator'][service]['loaded_usd_hour']+2)*MICRO*self.spec['rival_private_cost_ratio'])
                    target=int(sum(own_prices)/len(own_prices)*(.88 if win_fraction<.4 else 1.02))
                    previous=self.rival_prices[service]
                    self.rival_prices[service]=max(private_floor,int(.65*previous+.35*target))
                    self.market_events.append({'cycle':cycle,'kind':'RIVAL_DELAYED_HISTORY_RESPONSE','service_id':service,'observed_action_ids':[r['action_id'] for r in records],'previous_public_price':previous,'new_public_price':self.rival_prices[service],'information':'Rival sees delayed offered prices and own won/lost decisions, never buyer private reservation values.'})
        if self.supplier_queue and self.supplier_queue[0]['visible_cycle']<=cycle:
            observed=self.supplier_queue.pop(0)
            utilization=observed['used']/max(1,observed['capacity'])
            previous=self.supplier_quote
            self.supplier_quote=max(usd(.05),int(self.supplier_quote*(1.08 if utilization>.8 else .96)))
            self.market_events.append({'cycle':cycle,'kind':'SUPPLIER_DELAYED_UTILIZATION_RESPONSE','source_cycle':observed['source_cycle'],'quoted_unit_cost':self.supplier_quote,'previous_quote':previous})
        outage=self.spec['supplier_outage_start']<=cycle<self.spec['supplier_outage_start']+self.spec['supplier_outage_length']
        self.actual_outage=outage
        physical_capacity=(1 if self.diversified else 0) if outage else policy['supplier_initial_capacity']+self.capacity_extension
        affordable_units=max(0,(self.supplier_cash-usd(.02))//max(1,int(self.supplier_quote*.6)))
        self.actual_capacity=min(physical_capacity,affordable_units)
        for service,price in self.rival_prices.items():
            hours=self.spec['rival_fast_hours'] if self.imitated else 24.
            self.ad_queue.append({'available_cycle':cycle+int(self.spec['rival_observation_delay']),'ad':{'rival_id':'SIM-rival','service_id':service,'advertised_price_microUSD':price,'advertised_delivery_hours':hours,'observed_cycle':cycle+int(self.spec['rival_observation_delay']),'evidence_level':'COMPLETE_OUTCOME_ADVERTISEMENT_ASSUMPTION'}})
        for item in list(self.ad_queue):
            if item['available_cycle']<=cycle:self.visible_ads.append(item['ad']);self.ad_queue.remove(item)
        self.visible_ads=self.visible_ads[-18:]
        self.leads=[]
        for buyer in self.buyers:
            if not buyer['visible']:continue
            if buyer['purchases'] and keyed(self.seed,cycle,buyer['id'],'retention')>self.spec['retention']:buyer['active']=False
            if not buyer['active'] or keyed(self.seed,cycle,buyer['id'],'arrival')>self.spec['arrival']:continue
            service=SERVICES[(buyer['next_service']+cycle//3)%3]
            requested=list(SERVICES)+['operations_bundle'] if buyer['segment']=='premium' and cycle%4==2 else [service]
            self.leads.append({'id':buyer['id'],'segment':buyer['segment'],'requested_services':requested,'deadline_hours':12. if buyer['segment']=='premium' else 36.,'onboarded':buyer['onboarded'],'settled_jobs':buyer['purchases'],'last_outcome':buyer['last_outcome']})
        return {'quoted_unit_cost_microUSD':self.supplier_quote,'available_capacity_units':self.actual_capacity,'announced_latency_hours':2. if self.actual_capacity else 48.}

    def choose(self, customer_id, offer, price, cycle, action_id, delivery_hours):
        buyer=next(b for b in self.buyers if b['id']==customer_id)
        service=offer['service_id'];anchor=offer['human_anchor_microUSD']
        shift=self.spec['demand_shift_factor'] if self.spec['demand_shift_cycle']>=0 and cycle>=self.spec['demand_shift_cycle'] else 1.
        value=anchor*buyer['value_factor']*self.spec['value_scale']*shift
        friction=0 if buyer['onboarded'] else usd(.5)
        ours=value*buyer['trust']-price-friction-usd(delivery_hours*buyer['urgency'])
        rival_hours=self.spec['rival_fast_hours'] if self.imitated else 24.
        rival=value*.95-self.rival_prices[service]-usd(rival_hours*buyer['urgency'])
        matched_human=max(0,anchor-(usd(.1*self.human[service]['loaded_usd_hour']) if buyer['onboarded'] else 0))
        human=value*.96-matched_human-usd(48*buyer['urgency'])
        self_service=value*.95-int(matched_human*.85)-usd(16*buyer['urgency'])
        rival_cost=int(anchor*self.spec['rival_private_cost_ratio'])
        if self.rival_remaining_capacity<offer['capacity_units'] or self.rival_cash<rival_cost or self.rival_prices[service]<rival_cost:rival=-10**18
        available_budget=buyer['budget']-sum(buyer['commitments'].values())
        choices=[ours,rival,human,self_service,0.]
        # Bounded idiosyncratic choice variation is private and cannot enter the seller observation.
        choices=[utility+usd((keyed(self.seed,cycle,customer_id,'choice-'+str(i))-.5)*2) for i,utility in enumerate(choices)]
        option_costs=[price,self.rival_prices[service],matched_human,int(matched_human*.85),0]
        choices=[utility if option_costs[i]<=available_budget else -10**18 for i,utility in enumerate(choices)]
        option=max(range(5),key=lambda i:(choices[i],-i))
        participates=option==0 and ours>=0 and available_budget>=price
        if option==1:
            self.rival_remaining_capacity-=offer['capacity_units'];self.rival_modeled_contribution+=self.rival_prices[service]-rival_cost;self.rival_collections+=self.rival_prices[service];self.rival_expenses+=rival_cost;self.rival_cash+=self.rival_prices[service]-rival_cost
        if option in {1,2,3}:
            buyer['budget']-=option_costs[option];buyer['outside_spend']+=option_costs[option]
            self.market_events.append({'cycle':cycle,'kind':'BUYER_OUTSIDE_PURCHASE','customer_id':customer_id,'provider':['our','rival','human','self'][option],'paid_microUSD':option_costs[option],'our_revenue_microUSD':0})
        self.assert_buyer_budgets()
        self.rival_observations.append({'visible_cycle':cycle+int(self.spec['rival_response_delay']),'action_id':action_id,'service_id':service,'our_price':price,'rival_chosen':option==1,'offered_method':offer['method'],'advertised_delivery_hours':delivery_hours})
        self.rival_history.append({'cycle':cycle,'action_id':action_id,'service_id':service,'buyer_choice':option,'rival_price':self.rival_prices[service],'rival_remaining_capacity':self.rival_remaining_capacity,'rival_modeled_contribution':self.rival_modeled_contribution})
        return participates, {'buyer_choice':option,'buyer_utility_private':ours,'rival_utility_private':rival,'budget_private_after_choice':buyer['budget'],'available_budget_before_choice':available_budget,'matched_human_complete_cost_microUSD':matched_human}

    def commit_buyer(self,buyer_id,order_id,price):
        buyer=next(b for b in self.buyers if b['id']==buyer_id)
        if order_id in buyer['commitments']:
            if buyer['commitments'][order_id]!=price:raise ValueError('BUYER_COMMITMENT_CHANGED')
            return
        if buyer['budget']-sum(buyer['commitments'].values())<price:raise ValueError('BUYER_UNCOMMITTED_BUDGET_EXHAUSTED')
        buyer['commitments'][order_id]=price;self.assert_buyer_budgets()

    def assert_buyer_budgets(self):
        for buyer in self.buyers:
            if buyer['initial_budget']!=buyer['budget']+buyer['outside_spend']+buyer['our_settled_spend'] or buyer['budget']<sum(buyer['commitments'].values()) or buyer['budget']<0:
                raise ValueError('BUYER_BUDGET_CONSERVATION_FAILURE')
        if self.rival_cash!=self.rival_initial_cash+self.rival_collections-self.rival_expenses or self.rival_cash<0:
            raise ValueError('RIVAL_CASH_CONSERVATION_FAILURE')

    def delivered(self, buyer_id, *, settled, price, cycle, order_id):
        buyer=next(b for b in self.buyers if b['id']==buyer_id)
        if buyer['commitments'].pop(order_id,None)!=price:raise ValueError('ORDER_BOUND_BUYER_COMMITMENT_REQUIRED')
        if settled:
            buyer['purchases']+=1;buyer['budget']-=price;buyer['our_settled_spend']+=price;buyer['last_outcome']='SETTLED';buyer['trust']=min(.99,buyer['trust']+.002);buyer['last_cycle']=cycle
        else:buyer['last_outcome']='REFUNDED';buyer['trust']=max(.5,buyer['trust']-.02)
        self.assert_buyer_budgets()


def _joint_price(policy,offer,artifact,public_ads,public_supplier,segment):
    from enterprise.pricing import optimize_bundle
    components=artifact['components'];anchors=[]
    for component in components:
        service=component['artifact']['service_id'];human=policy['human_comparator'][service];anchors.append(human['hours']*human['loaded_usd_hour']+2)
    ratio=offer['human_anchor_microUSD']/MICRO/sum(anchors);publics=[];quotes=[]
    for index,(component,anchor) in enumerate(zip(components,anchors)):
        service=component['artifact']['service_id'];observed=[ad for ad in public_ads if ad['service_id']==service]
        rival_price=min((ad['advertised_price_microUSD']/MICRO for ad in observed),default=anchor*.9)
        publics.append({'anchor_usd':anchor*ratio,'autonomous_cost_usd':offer['production_cost_microUSD']/MICRO/3+public_supplier['quoted_unit_cost_microUSD']/MICRO,'onboarding_cost_usd':offer['onboarding_cost_microUSD']/MICRO if index==0 else 0.,'friction_usd':.5 if index==0 else 0.,'trust':.95,'rival_trust':.95,'urgency_value_hour':1. if segment=='premium' else .45,'repeat_probability':.75,'payment_fraction':offer['payment_fee_bps']/10000,'payment_fixed_usd':offer['payment_fixed_microUSD']/MICRO/3})
        quotes.append({'price':anchor*ratio*.95,'rival':{'price':rival_price}})
    common={'our_hours':offer['delivery_hours']+public_supplier['announced_latency_hours'],'rival_hours':min((ad['advertised_delivery_hours'] for ad in public_ads),default=24.),'self_complete_cost_ratio':.85,'temperature_ratio':.10,'collection_probability':.95,'refund_probability':.03,'quote_cost_usd':offer['quote_cost_microUSD']/MICRO/3,'arrival_probability':1.,'qualification_probability':1.,'supplier_outage_probability':0.}
    result=optimize_bundle(publics,quotes,common,'logit',strategic=True,coordination_cost_usd=0.)
    return usd(result['total_price']) if result['total_price'] is not None else offer['human_anchor_microUSD'],{'call_path':'enterprise.pricing.optimize_bundle','public_component_priors':publics,'public_component_quotes':quotes,'common_public_priors':common,'result':result,'scope':'Actual source-bound joint contract, context/onboarding deduplicated, common declared priors and delayed advertisements only; no hidden evaluator state.'}


def _offers(policy,jobs,consumed,owned_assets,arm,public_ads,public_supplier):
    core={};public=[]
    for base in offer_catalog():
        if base['method'] in {'generated_schema','staged_readiness'} and (not owned_assets['instrument'] or arm=='no_instrument'):continue
        applicable=[]
        for ident,entry in jobs.items():
            artifact=entry['artifact'];keys=entry['job']['work_keys']
            if ident in consumed or set(keys)&consumed or entry['job']['service_id']!=base['service_id'] or artifact['method']!=base['method'] or artifact['outcome_scope']!=base['scope']:continue
            if base['service_id']=='operations_bundle' and any(component['artifact']['method']!='canonical' for component in artifact['components']) and (not owned_assets['instrument'] or arm=='no_instrument'):continue
            applicable.append(ident)
        if not applicable:continue
        for segment in ['standard','premium']:
            offer=copy.deepcopy(base);offer['id']=base['id']+'|'+segment;offer['segment']=segment
            human=policy['human_comparator'][base['service_id']];anchor=usd(human['hours']*human['loaded_usd_hour']+2)
            if base['scope']=='intake_readiness':anchor=int(anchor*.45)
            offer.update(human_anchor_microUSD=anchor,production_cost_microUSD=int(policy['base_production_cost']*policy['upfront_cost_multiplier'])*base['capacity_units']+(usd(.3) if base['method']!='canonical' else 0),quote_cost_microUSD=policy['quote_cost'],onboarding_cost_microUSD=policy['onboarding_once'],payment_fee_bps=policy['payment_bps'],payment_fixed_microUSD=policy['payment_fixed'],applicable_job_ids=applicable[:5],delivery_hours=.25*base['capacity_units'] if base['method']=='canonical' else .5*base['capacity_units'],evidence_level='SOURCE_BOUND_INDEPENDENT_ACCEPTANCE_CONTRACT')
            for channel in ['qualified_inbound','authorized_repeat']:
                variant=copy.deepcopy(offer);variant['id']+='|'+channel;variant['channel']=channel;variant['quote_cost_microUSD']=policy['quote_cost'] if channel=='qualified_inbound' else policy['quote_cost']//4
                if base['service_id']=='operations_bundle':
                    price,pricing=_joint_price(policy,variant,jobs[applicable[0]]['artifact'],copy.deepcopy(public_ads),copy.deepcopy(public_supplier),segment);variant['price_microUSD']=price
                    variant['evidence']=variant['evidence']+['Joint solver receipt:'+digest(pricing)]
                    owned_assets.setdefault('joint_price_receipts',{})[variant['id']]=pricing
                core[variant['id']]=variant;public.append({key:copy.deepcopy(variant[key]) for key in OFFER_FIELDS})
    return core,public


def _feedback(action, outcome, cost, collected, cycle):
    return {'event_id':action['action_id']+'-'+outcome,'action_id':action['action_id'],'offer_id':action['offer_id'],'customer_id':action['customer_id'],'observed_cycle':cycle,'offered_price_microUSD':action['price_microUSD'],'outcome':outcome,'complete_cost_microUSD':cost,'collected_microUSD':collected,'delivery_hours':action.get('actual_delivery_hours',0.)}


def _option(ident,kind,cost,central,adverse,evidence,execution,later=0):
    return {'id':ident,'kind':kind,'upfront_cost':cost,'later_liabilities':{'central':later,'adverse':later},'future_net_cash':{'central':central,'adverse':adverse},'benefit_ids':[ident+'-benefit'],'requires':[],'exclusive_group':None,'authorized':True,'evidence':evidence,'execution':execution}


def validate_growth_snapshot(snapshot):
    fields={'cycle','remaining_authorized_cycles','instrument_enabled','capacity_extension','supplier_diversified','current_supplier_capacity','decision_slot_limit','visible_customer_ids','current_lead_ids','pending_channel_activation','disclosed_channel_capacity','retention_attempted_ids','supplier_history','source_contracts','own_transactions'}
    if not isinstance(snapshot,dict) or set(snapshot)!=fields:
        raise ValueError('EXACT_PUBLIC_GROWTH_SNAPSHOT_REQUIRED')
    if any(key in snapshot for key in ['seed','world','regime','private_value','private_cost']):
        raise ValueError('PRIVATE_GROWTH_INFORMATION_REFUSED')
    for key in ['cycle','remaining_authorized_cycles','capacity_extension','current_supplier_capacity','decision_slot_limit','disclosed_channel_capacity']:
        if type(snapshot[key])is not int or snapshot[key]<0:raise ValueError('PUBLIC_GROWTH_INTEGER_REQUIRED')
    for key in ['instrument_enabled','supplier_diversified','pending_channel_activation']:
        if type(snapshot[key])is not bool:raise ValueError('PUBLIC_OWNED_ASSET_BOOLEAN_REQUIRED')
    schemas={'supplier_history':{'cycle','used','capacity'},'source_contracts':{'id','method'},'own_transactions':{'action_id','customer_id','cycle','outcome','collected','complete_cost'}}
    for name,fields_ in schemas.items():
        if not isinstance(snapshot[name],list) or any(not isinstance(row,dict) or set(row)!=fields_ for row in snapshot[name]):raise ValueError('PUBLIC_GROWTH_HISTORY_SCHEMA_REQUIRED')
    return copy.deepcopy(snapshot)


def _growth_options(policy,public_snapshot):
    public=validate_growth_snapshot(public_snapshot);recorded=public['own_transactions'];cycle=public['cycle']
    settled=[row for row in recorded if row['outcome']=='SETTLED']
    if len(settled)<3:return []
    margin=max(0,int(sum(row['collected']-row['complete_cost'] for row in settled[-8:])/min(8,len(settled))))
    counts={customer:sum(row['customer_id']==customer for row in settled) for customer in {row['customer_id'] for row in settled}}
    repeat_fraction=(1+sum(count>1 for count in counts.values()))/(2+len(counts))
    terminal=[row for row in recorded if row['outcome'] in {'SETTLED','REFUNDED'}]
    collection=(1+len(settled))/(2+len(terminal))
    rate=repeat_fraction*collection/(1+policy['discount_per_cycle'])
    remaining=public['remaining_authorized_cycles']
    renewal_units=sum(rate**step for step in range(1,remaining+1))
    source=digest(public);options=[];support=usd(.5)
    def add(kind,cost,units,execution,adverse_ratio=.25):
        central=int(margin*min(max(0,units),renewal_units))-support
        adverse=int(margin*min(max(0,units),renewal_units)*adverse_ratio)-support
        option=_option(kind+'-'+str(cycle),kind,cost,central,adverse,source,execution,later=support)
        option['benefit_ids']=['future-delivery-cohort-'+source]
        option['execution'].update({'forecast_source_history':source,'observed_repeat_fraction':repeat_fraction,'observed_collection_fraction':collection,'discount_per_cycle':policy['discount_per_cycle'],'remaining_authorized_cycles':remaining,'expected_discounted_renewal_units':renewal_units,'forecast_scope':'Marginal alternative hypotheses over the same finite future delivery cohort; shared-benefit ID prevents adding their gross returns. No forecast receipt enters current cash.'})
        options.append(option)
    if not public['instrument_enabled'] and any(row['method'] in {'generated_schema','staged_readiness'} for row in public['source_contracts']):
        add('instrument',int(policy['instrument_cost']*policy['upfront_cost_multiplier']),sum(row['method'] in {'generated_schema','staged_readiness'} for row in public['source_contracts']),{'kind':'instrument'})
    visible=len(public['visible_customer_ids'])
    if visible<public['disclosed_channel_capacity'] and not public['pending_channel_activation']:
        add('acquisition',int(policy['channel_cost']*policy['upfront_cost_multiplier']),min(2,public['disclosed_channel_capacity']-visible)*renewal_units,{'kind':'acquisition','start':visible,'stop':min(public['disclosed_channel_capacity'],visible+2)})
    stale=sorted({row['customer_id'] for row in settled if row['cycle']<cycle-3 and row['customer_id'] not in public['current_lead_ids'] and row['customer_id'] not in public['retention_attempted_ids']})
    if stale:add('retention',int(usd(2)*policy['upfront_cost_multiplier']),renewal_units*.6,{'kind':'retention','customer_id':stale[0]},adverse_ratio=0.)
    if public['current_supplier_capacity']<public['decision_slot_limit'] and len(public['current_lead_ids'])>public['current_supplier_capacity']:
        add('capacity',int(policy['capacity_cost']*policy['upfront_cost_multiplier']),remaining,{'kind':'capacity'})
    if not public['supplier_diversified'] and public['supplier_history'] and any(row['capacity']==0 for row in public['supplier_history']):
        outage_frequency=(1+sum(row['capacity']==0 for row in public['supplier_history']))/(2+len(public['supplier_history']))
        add('supplier_diversity',int(policy['supplier_diversity_cost']*policy['upfront_cost_multiplier']),remaining*outage_frequency,{'kind':'supplier_diversity'})
    return options


def run_world(root,manifest,policy,seed,world,arm='full_adaptive',output=None,persist=True):
    validate_policy(policy);world=_world(world)
    if type(seed)is not int or seed<0 or arm not in policy['arms']:raise ValueError('DECLARED_ADAPTIVE_WORLD_AND_CONTROL_REQUIRED')
    root=Path(root).absolute();jobs=load_jobs(root,manifest);actors=MarketActors(policy,world,seed);controller=Policy(arm)
    temporary=tempfile.TemporaryDirectory(prefix='adaptive012-operating-') if output is None else None
    destination=Path(temporary.name) if temporary else Path(output)
    if output is not None:destination.mkdir(parents=True,exist_ok=False)
    account=Account(root,manifest,destination/'account.sqlite',opening=policy['opening'],working=policy['working'],contract='adaptive012/'+digest({'policy':policy,'manifest':manifest,'seed':seed,'world':world,'arm':arm}))
    observations=[];decisions=[];costs=[];records=[];pending=[];feedback_queue=[];visible_feedback=[];consumed=set();investments=[];instrument_receipts=[];cycle_records=[]
    cumulative_tax=0;prior_taxable=0;stop=None;start_cpu=time.process_time();start_wall=time.monotonic()
    def charge(ident,amount,day,category):
        if amount:account.cost(ident,amount,day);costs.append({'id':ident,'amount':amount,'category':category,'currency':policy['currency'],'evidence':'AUTHORED_RESOURCE_ENVELOPE'})
    def settle_through(day,cycle):
        for payment in sorted(list(pending),key=lambda x:x['event_day']):
            if payment['event_day']>day:continue
            row=payment['record'];action='refund' if payment['default'] else 'release'
            account.execute('event',{'id':payment['order_id'],'event_id':payment['order_id']+'-'+action,'action':action},payment['event_day'])
            settled=not payment['default'];row['outcome']='SETTLED' if settled else 'REFUNDED';row['collected']=row['price'] if settled else 0
            actors.delivered(row['customer_id'],settled=settled,price=row['price'],cycle=cycle,order_id=payment['order_id'])
            feedback_queue.append({'available_cycle':cycle+int(world['feedback_delay_cycles']),'feedback':_feedback(row['decision'],row['outcome'],row['complete_cost'],row['collected'],cycle+int(world['feedback_delay_cycles']))})
            pending.remove(payment)
    def finish_plan(plan,spent,work_hash,day,delivery=None):
        selected=plan['selected_options'];upfront=sum(o['upfront_cost'] for o in selected);growth=[];delivery_receipts=[]
        later_incurred=0
        for option in selected:
            if option['kind']=='delivery':
                if delivery is None:raise ValueError('EXECUTED_DELIVERY_OBLIGATION_RECEIPT_REQUIRED')
                payment_fee=delivery.get('payment_fee',0);onboard=delivery.get('onboarding_cost',0);later_incurred+=payment_fee+onboard
                delivery_receipts.append({'option_id':option['id'],'job_id':delivery['job_id'],'order_id':delivery.get('order_id'),'artifact_sha256':delivery['service_receipt'].get('artifact_sha256',jobs[delivery['job_id']]['job']['artifact_sha256']),'customer_id':delivery['customer_id'],'outcome':'NATIVE_ACCEPTED' if delivery.get('order_id') else 'NO_ORDER','payment_fee_microUSD':payment_fee,'onboarding_microUSD':onboard})
            else:
                support=max(option['later_liabilities'].values());later_incurred+=support
                growth.append({'option_id':option['id'],'execution_sha256':digest(option['execution']),'prepaid_support_microUSD':support})
        if upfront+later_incurred!=spent:raise ValueError('EXECUTED_RESOURCE_INVOICE_DOES_NOT_RECONCILE')
        receipt={'schema':'agi-alpha/adaptive012-obligation-resolution/v1','plan_id':plan['plan_id'],'resolved_at_day':day,'native_actions_sha256':account.snapshot()['actions_sha256'],'work_artifact_sha256':work_hash,'upfront_incurred_microUSD':upfront,'later_incurred_microUSD':later_incurred,'unused_reserve_microUSD':plan['reserve_amount']-spent,'deliveries':delivery_receipts,'growth':growth}
        account.finish(plan['plan_id'],spent,work_hash,day,obligation_receipt=receipt)
        return receipt
    try:
        charge('adaptive012-complete-setup',int(policy['setup_cost']*policy['upfront_cost_multiplier']),0,'all_construction_prequalification_integration')
        for cycle in range(policy['max_cycles']):
            day=cycle*policy['cycle_days']+1
            settle_through(day,cycle)
            supplier=actors.advance(cycle,policy);remaining_capacity=supplier['available_capacity_units'];served=set();before=account.snapshot()['summary'];cycle_actions=[]
            for item in list(feedback_queue):
                if item['available_cycle']<=cycle:visible_feedback.append(item['feedback']);feedback_queue.remove(item)
            charge('maintenance-'+str(cycle),int(policy['maintenance_per_cycle']*policy['upfront_cost_multiplier']),day,'learning_and_instrument_maintenance')
            for slot in range(policy['decision_slots']):
                owned_assets={'instrument':actors.instrument,'joint_price_receipts':{}};core,offers=_offers(policy,jobs,consumed,owned_assets,arm,actors.visible_ads,supplier)
                snap=account.snapshot();public={'schema':'agi-alpha/adaptive012-public/v1','cycle':cycle,'account':{'state_digest':snap['state_digest'],'available_microUSD':snap['summary']['available'],'earned_microUSD':snap['summary']['unrestrictedEarned'],'cash_microUSD':snap['summary']['cash'],'pending_payment_count':len(pending),'learning_budget_microUSD':policy['learning_budget_per_decision']},'supplier':{**supplier,'available_capacity_units':remaining_capacity},'offers':offers,'customers':[copy.deepcopy(c) for c in actors.leads if c['id'] not in served],'feedback':copy.deepcopy(visible_feedback),'competitor_ads':copy.deepcopy(actors.visible_ads),'history_digest':digest({'observed_feedback':visible_feedback,'public_prior_decisions':decisions})}
                public=validate_public(public);decision=controller.act(copy.deepcopy(public));observations.append(public);decisions.append(copy.deepcopy(decision));cycle_actions.append(decision['action_id'])
                if decision['action']=='WITHDRAW':
                    charge(decision['action_id']+'-learning',decision['learning_cost_microUSD'],day,'costed_policy_withdrawal')
                    break
                offer=copy.deepcopy(core[decision['offer_id']]);offer['price_microUSD']=decision['price_microUSD'];job_id=offer['applicable_job_ids'][0];job=jobs[job_id]['job'];customer=next(b for b in actors.buyers if b['id']==decision['customer_id'])
                fee=(decision['price_microUSD']*policy['payment_bps']+9999)//10000+policy['payment_fixed'];onboarding=0 if customer['onboarded'] else policy['onboarding_once'];base=offer['production_cost_microUSD']+supplier['quoted_unit_cost_microUSD']*decision['capacity_units']+offer['quote_cost_microUSD']+decision['learning_cost_microUSD'];later=fee+onboarding
                option=_option('delivery-'+decision['action_id'],'delivery',base,max(0,decision['expected_net_microUSD']+base),-later,digest(public),{'kind':'delivery','job_id':job_id,'action_id':decision['action_id'],'customer_id':decision['customer_id'],'payment_bps':policy['payment_bps'],'payment_fixed_microUSD':policy['payment_fixed'],'onboarding_microUSD':onboarding},later=later)
                growth_snapshot={'cycle':cycle,'remaining_authorized_cycles':policy['max_cycles']-cycle-1,'instrument_enabled':actors.instrument,'capacity_extension':actors.capacity_extension,'supplier_diversified':actors.diversified,'current_supplier_capacity':supplier['available_capacity_units'],'decision_slot_limit':policy['decision_slots'],'visible_customer_ids':[b['id'] for b in actors.buyers if b['visible']],'current_lead_ids':[lead['id'] for lead in actors.leads],'pending_channel_activation':bool(actors.pending_leads),'disclosed_channel_capacity':policy['reachable_channel_capacity'],'retention_attempted_ids':sorted(actors.retention_attempted),'supplier_history':copy.deepcopy(actors.supplier_history),'source_contracts':[{'id':ident,'method':entry['artifact']['method']} for ident,entry in jobs.items() if ident not in consumed and not set(entry['job']['work_keys'])&consumed],'own_transactions':[{k:r[k] for k in ['action_id','customer_id','cycle','outcome','collected','complete_cost']} for r in records if r['outcome'] in {'PENDING','SETTLED','REFUNDED'} or r['action_id'] in {event['action_id'] for event in visible_feedback}]};growth_snapshot=validate_growth_snapshot(growth_snapshot)
                growth=_growth_options(policy,copy.deepcopy(growth_snapshot)) if slot==0 and arm!='no_capital_adaptation' else []
                if arm=='no_instrument':growth=[option for option in growth if option['kind']!='instrument']
                plan=allocate(account.snapshot(),[option,*growth],policy['risk']);funded=option['id'] in plan['selected'];selected_growth=[o for o in plan['selected_options'] if o['kind']!='delivery'];plan_before=account.snapshot()['summary'];actual_growth_cost=0
                if plan['selected']:
                    account.reserve(plan,expected_state_digest=plan['expected_state_digest'],authorized_digest=plan['authorized_digest'],amount=plan['reserve_amount'],expected_net=plan['expected_net'],day=day)
                    for growth_option in selected_growth:
                        kind=growth_option['kind'];spent=growth_option['upfront_cost']+max(growth_option['later_liabilities'].values());actual_growth_cost+=spent
                        if kind=='instrument':
                            probe=next((entry for ident,entry in jobs.items() if ident not in consumed and entry['artifact']['method']=='generated_schema'),None)
                            if probe:
                                raw=read_bound(root,probe['job']['input'],probe['job']['input_sha256']);canonical_offer=next(o for o in offer_catalog() if o['service_id']==probe['job']['service_id'] and o['method']=='canonical');chain=adjudicate_and_adapt(raw,canonical_offer,probe['artifact'],instrument_budget_microUSD=policy['instrument_cost']);failed=chain['adjudication']['rejection_receipt'];memory=retain_failure(raw,chain['adjudication']);generated=infer_plan(raw,memory,mode='retained');comparison=compare_methods(raw,memory);actors.instrument=generated['status']=='READY';actors.retained=memory;actors.instrument_source=plan['plan_id'] if actors.instrument else None
                                instrument_receipts.append({'plan_id':plan['plan_id'],'source_job_id':probe['job']['id'],'source_sha256':digest(raw),'generated_plan':generated,'verified_failure_receipt':failed,'adjudicated_repair_chain':chain,'retained_constraints':memory,'matched_methods':comparison,'origin':'Bounded developer-authored search generates an executable typed mapping. Ordinary equal-content reuse may tie; no invention superiority inferred.'})
                        elif kind=='acquisition':actors.pending_leads.append({'cycle':cycle+1,'start':growth_option['execution']['start'],'stop':growth_option['execution']['stop'],'plan_id':plan['plan_id']})
                        elif kind=='retention':
                            target=growth_option['execution']['customer_id'];actors.retention_attempted.add(target);actors.pending_retention.append({'cycle':cycle+1,'customer_id':target,'plan_id':plan['plan_id']})
                        elif kind=='capacity':actors.capacity_extension+=1;actors.capacity_sources.append(plan['plan_id']);actors.supplier_cash+=growth_option['upfront_cost'];actors.supplier_collections+=growth_option['upfront_cost']
                        elif kind=='supplier_diversity':actors.diversified=True;actors.diversity_source=plan['plan_id']
                if not funded:
                    if account.snapshot()['summary']['available']<base+later:
                        if plan['selected']:
                            finish_plan(plan,actual_growth_cost,digest(selected_growth),day);costs.append({'id':plan['plan_id'],'amount':actual_growth_cost,'category':'earned_funded_growth','currency':policy['currency'],'evidence':'AUTHORED_RESOURCE_ENVELOPE'})
                        stop='PROTECTED_LIQUIDITY_BEFORE_ATTEMPT';break
                    charge(decision['action_id']+'-seed-prepaid-attempt',base,day,'seed_backed_prepaid_production_acquisition_learning')
                receipt=execute_offer(root,manifest,offer,job_id,context={'retained':actors.retained} if actors.retained else None);consumed.add(job_id);consumed.update(job['work_keys']);remaining_capacity-=decision['capacity_units'];served.add(customer['id'])
                decision['actual_delivery_hours']=offer['delivery_hours']+supplier['announced_latency_hours'];participants,private_audit=actors.choose(customer['id'],offer,decision['price_microUSD'],cycle,decision['action_id'],decision['actual_delivery_hours'])
                accepted=participants and receipt.get('accepted') is True and decision['actual_delivery_hours']<=next(c['deadline_hours'] for c in actors.leads if c['id']==customer['id'])
                actual_later=0;order_id=None
                row={'action_id':decision['action_id'],'decision':copy.deepcopy(decision),'offer':offer,'job_id':job_id,'work_keys':list(job['work_keys']),'joint_pricing_receipt':owned_assets['joint_price_receipts'].get(offer['id']),'customer_id':customer['id'],'service_id':offer['service_id'],'outcome_scope':offer['scope'],'cycle':cycle,'price':decision['price_microUSD'],'outcome':'NO_PURCHASE','collected':0,'complete_cost':base,'funding':'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS' if funded else 'SEED_BACKED_PREPAID_ATTEMPT','plan_id':plan['plan_id'] if funded else None,'before':plan_before,'service_receipt':receipt,'private_evaluator_only':private_audit}
                executed_slot=supplier['available_capacity_units']-remaining_capacity-1
                row['capacity_source_plan_id']=actors.capacity_sources[executed_slot-policy['supplier_initial_capacity']] if not actors.actual_outage and executed_slot>=policy['supplier_initial_capacity'] and executed_slot-policy['supplier_initial_capacity']<len(actors.capacity_sources) else None
                row['supplier_diversity_source_plan_id']=actors.diversity_source if actors.actual_outage and actors.diversified else None
                row['instrument_source_plan_id']=actors.instrument_source if offer['method']!='canonical' else None
                row['acquisition_source_plan_id']=customer.get('acquisition_plan_id')
                row['retention_source_plan_id']=customer.get('retention_plan_id')
                if accepted:
                    order_id='adaptive012-order-'+str(len(records));wallet=order_id+'-buyer-wallet';account.execute('wallet',{'buyer':wallet,'amount':decision['price_microUSD']},day);account.execute('offer',{'id':order_id,'buyer':wallet,'price':decision['price_microUSD'],'job_id':job_id,'deadline':day+policy['payment_deadline_days']},day)
                    for action in ['consent','fund','prepare']:account.execute('event',{'id':order_id,'event_id':order_id+'-'+action,'action':action},day)
                    actors.commit_buyer(customer['id'],order_id,decision['price_microUSD'])
                    actual_later=fee+onboarding;customer['onboarded']=True;row['complete_cost']+=actual_later;row['outcome']='PENDING';row['order_id']=order_id
                    modeled_delay=int(world['payment_delay_days'])+int(keyed(seed,cycle,customer['id'],'payment-jitter')*3);default=keyed(seed,cycle,customer['id'],'collection-default')<world['payment_default_probability'] or modeled_delay>policy['payment_deadline_days'];delay=policy['payment_deadline_days'] if default else modeled_delay;pending.append({'event_day':day+delay,'default':default,'order_id':order_id,'record':row,'contract_due_day':day+policy['payment_deadline_days']})
                    feedback_queue.append({'available_cycle':cycle+int(world['feedback_delay_cycles']),'feedback':_feedback(decision,'ACCEPTED',row['complete_cost'],0,cycle+int(world['feedback_delay_cycles']))});feedback_queue.append({'available_cycle':cycle+int(world['feedback_delay_cycles']),'feedback':_feedback(decision,'PENDING',row['complete_cost'],0,cycle+int(world['feedback_delay_cycles']))})
                else:
                    outcome='NO_PURCHASE' if receipt.get('accepted') else 'REJECTED_QUALITY';row['outcome']=outcome
                    feedback_queue.append({'available_cycle':cycle+int(world['feedback_delay_cycles']),'feedback':_feedback(decision,outcome,base,0,cycle+int(world['feedback_delay_cycles']))})
                if plan['selected']:
                    spent=actual_growth_cost+(base+actual_later if funded else 0);row['payment_fee']=fee if order_id else 0;row['onboarding_cost']=onboarding if order_id else 0;work_hash=digest({'selected':plan['selected'],'job_id':job_id,'artifact_sha256':receipt.get('artifact_sha256'),'accepted':receipt.get('accepted'),'growth':[{k:r.get(k) for k in ['plan_id','source_job_id','source_sha256','generated_plan']} for r in instrument_receipts if r['plan_id']==plan['plan_id']]});resolution=finish_plan(plan,spent,work_hash,day,row if funded else None);costs.append({'id':plan['plan_id'],'amount':spent,'category':'earned_funded_actual_delivery_and_growth','currency':policy['currency'],'evidence':'AUTHORED_RESOURCE_ENVELOPE'})
                    investments.append({'plan':plan,'public_growth_snapshot':growth_snapshot,'cycle':cycle,'before':plan_before,'actual_spend':spent,'executed_job_id':job_id if funded else None,'order_id':order_id if funded else None,'selected_growth_kinds':[o['kind'] for o in selected_growth],'actual_growth_spend':actual_growth_cost,'obligation_resolution':resolution,'forecast_and_cash_scope':'Signed net forecasts are hypotheses only. Native reservation uses prior unrestricted earned cash and covers upfront/later costs. Unused cap released only after actual immediate obligations are charged; native principal refund tails remain restricted.'})
                if not funded and actual_later:charge(decision['action_id']+'-onboarding-fees',actual_later,day,'once_onboarding_and_nonrefundable_payment_fees')
                row['after']=account.snapshot()['summary'];records.append(row)
            supplier_receipt=(supplier['available_capacity_units']-remaining_capacity)*supplier['quoted_unit_cost_microUSD'];supplier_cost=int(supplier_receipt*.6)+(usd(.02) if actors.supplier_cash>=usd(.02) else 0);actors.supplier_collections+=supplier_receipt;actors.supplier_expenses+=supplier_cost;actors.supplier_cash+=supplier_receipt-supplier_cost
            actors.supplier_history.append({'cycle':cycle,'used':supplier['available_capacity_units']-remaining_capacity,'capacity':supplier['available_capacity_units']});actors.supplier_queue.append({'visible_cycle':cycle+int(world['supplier_observation_delay']),'source_cycle':cycle,'used':supplier['available_capacity_units']-remaining_capacity,'capacity':supplier['available_capacity_units']})
            taxable=max(0,account.snapshot()['summary']['profit']+cumulative_tax);tax=max(0,taxable-prior_taxable)*policy['profit_tax_bps']//10000
            if tax:charge('tax-provision-'+str(cycle),tax,day,'conditional_positive_profit_tax_provision')
            cumulative_tax+=tax;prior_taxable=max(prior_taxable,taxable);cycle_records.append({'cycle':cycle,'before':before,'after':account.snapshot()['summary'],'action_ids':cycle_actions,'public_supplier':supplier,'active_offers':len(offers),'remaining_capacity':remaining_capacity})
            if stop:break
        terminal_day=(policy['max_cycles']+1)*policy['cycle_days']+policy['payment_deadline_days'];settle_through(terminal_day,policy['max_cycles'])
        terminal_taxable=max(0,account.snapshot()['summary']['profit']+cumulative_tax);terminal_tax=max(0,terminal_taxable-prior_taxable)*policy['profit_tax_bps']//10000
        if terminal_tax:charge('tax-provision-terminal',terminal_tax,terminal_day,'conditional_final_collection_profit_tax_provision')
        cumulative_tax+=terminal_tax;prior_taxable=max(prior_taxable,terminal_taxable)
        for item in feedback_queue:visible_feedback.append(item['feedback'])
        final_feedback_cycle=max([policy['max_cycles'],*[r['observed_cycle'] for r in visible_feedback]])
        owned_assets={'instrument':actors.instrument,'joint_price_receipts':{}};core,offers=_offers(policy,jobs,consumed,owned_assets,arm,actors.visible_ads,supplier);snap=account.snapshot();last_public={'schema':'agi-alpha/adaptive012-public/v1','cycle':final_feedback_cycle,'account':{'state_digest':snap['state_digest'],'available_microUSD':snap['summary']['available'],'earned_microUSD':snap['summary']['unrestrictedEarned'],'cash_microUSD':snap['summary']['cash'],'pending_payment_count':len(pending),'learning_budget_microUSD':0},'supplier':{'quoted_unit_cost_microUSD':actors.supplier_quote,'available_capacity_units':0,'announced_latency_hours':0},'offers':offers,'customers':[],'feedback':visible_feedback,'competitor_ads':actors.visible_ads,'history_digest':digest(visible_feedback)};controller.act(last_public)
        audited=account.audit();exported=account.export();summary=audited['summary']
    finally:
        account.close()
        if temporary:temporary.cleanup()
    settled=[r for r in records if r['outcome']=='SETTLED'];customers={r['customer_id'] for r in settled};repeat=sum(sum(r['customer_id']==customer for r in settled)>1 for customer in customers)
    growth_cost_by_plan={i['plan']['plan_id']:i['actual_growth_spend'] for i in investments}
    earned=[r for r in settled if r['funding']=='PRIOR_UNRESTRICTED_SIMULATED_EARNINGS' and r['collected']>r['complete_cost']+growth_cost_by_plan.get(r['plan_id'],0)]
    protected=summary['payables']==0 and not summary['investmentStopped'] and summary['cash']>=summary['tailReserve']+summary['workingCapital']+summary['custodyReserve']
    thresholds=policy['thresholds'];go=len(customers)>=thresholds['minimum_customers'] and len(settled)>=thresholds['minimum_settled_jobs'] and repeat>=thresholds['minimum_repeat_customers'] and len(earned)>=thresholds['minimum_profitable_earned_continuations'] and summary['profit']>0 and summary['unrestrictedEarned']>0 and protected
    for investment in investments:
        linked=[r for r in records if r['plan_id']==investment['plan']['plan_id']];investment['realized_delivery_collections']=sum(r['collected'] for r in linked);investment['realized_delivery_cost']=sum(r['complete_cost'] for r in linked);investment['realized_scoped_net_cash']=investment['realized_delivery_collections']-investment['actual_spend'];investment['growth_future_receipts_booked']=0;investment['pending_delivery_orders']=sum(r['outcome']=='PENDING' for r in linked)
    expansion_evidence=[]
    for investment in investments:
        for kind in investment['selected_growth_kinds']:
            source_field={'instrument':'instrument_source_plan_id','acquisition':'acquisition_source_plan_id','capacity':'capacity_source_plan_id','supplier_diversity':'supplier_diversity_source_plan_id','retention':'retention_source_plan_id'}.get(kind)
            used=[row['job_id'] for row in settled if source_field and row.get(source_field)==investment['plan']['plan_id']]
            expansion_evidence.append({'plan_id':investment['plan']['plan_id'],'kind':kind,'later_settled_job_ids':sorted(set(used)),'scope':'Actual subsequent use within this trajectory. Causal incremental profit versus matched no-investment control remains separate.'})
    result={'schema':'agi-alpha/adaptive012-world/v1','scope':'SIMULATED','evaluator_world_id':world['id'],'evaluator_world':world,'seed':seed,'arm':arm,'policy_sha256':digest(policy),'manifest_sha256':digest(manifest),'conditional_simulated_go':go,'accepted_jobs':sum(r['outcome'] in {'PENDING','SETTLED','REFUNDED'} for r in records),'paid_jobs':len(settled),'customers':len(customers),'repeat_buyers':repeat,'profitable_earned_continuations':len(earned),'earned_funded_cycles':len({r['cycle'] for r in earned}),'summary':summary,'cash_survival':protected,'stop':stop,'operated_cycles':len(cycle_records),'economic_completion_requires_all_cycles':False,'inventory_completion_required':False,'public_observations':observations,'decisions':decisions,'cycles':cycle_records,'service_records':records,'delayed_public_feedback':visible_feedback,'private_actor_event_audit':actors.market_events,'rival_history_evaluator_only':actors.rival_history,'supplier_history':actors.supplier_history,'private_buyer_budget_audit':[{'id':b['id'],'initial_budget':b['initial_budget'],'remaining_budget':b['budget'],'pending_commitments':b['commitments'],'outside_spend':b['outside_spend'],'our_settled_spend':b['our_settled_spend']} for b in actors.buyers],'counterparty_cash_audit':{'rival':{'initial':actors.rival_initial_cash,'cash':actors.rival_cash,'collections':actors.rival_collections,'expenses':actors.rival_expenses},'supplier':{'initial':actors.supplier_initial_cash,'cash':actors.supplier_cash,'collections':actors.supplier_collections,'expenses':actors.supplier_expenses},'scope':'Private simulated counterparty resource balances; never enterprise receipts or seller-policy inputs.'},'learning':controller.export(),'allocations':investments,'instrument_receipts':instrument_receipts,'productive_expansion_evidence':expansion_evidence,'cost_receipts':costs,'owned_account':exported,'ledger':exported['ledger'],'available_earned_surplus':summary['unrestrictedEarned'],'seed_backing_reserves':summary['equityProtectionBacking'],'actual_customers':0,'actual_collections':0,'actual_profit':None,'cost_evidence':policy['cost_evidence'],'human_comparator':policy['human_comparator'],'human_evidence':policy['human_evidence'],'verdicts':{'executed_service_capability':'EXECUTED_AND_INDEPENDENTLY_CHECKED' if settled else 'NO_SETTLED_SERVICE','conditional_simulated_commercial_flywheel':'SUCCEEDED' if go else 'NOT_ESTABLISHED','actual_commercial_operation':'NOT_AUTHORIZED_OR_EXECUTED','competitive_adaptation':'EXECUTED_PUBLIC_LEARNING_REQUIRES_MATCHED_CONTROL_COMPARISON','invention':'GENERATED_MAPPING_EXECUTED_NO_SUPERIORITY_CLAIM' if instrument_receipts else 'NOT_EXECUTED_IN_THIS_TRAJECTORY','productive_expansion':'CONSTRUCTED_AND_USED_ON_SUBSEQUENT_SETTLED_WORK' if any(e['later_settled_job_ids'] for e in expansion_evidence) else 'CONSTRUCTED_WITHOUT_SETTLED_USE' if expansion_evidence else 'NOT_EXECUTED'},'resource_receipt':{'process_cpu_seconds':time.process_time()-start_cpu,'wall_seconds':time.monotonic()-start_wall,'model_calls_in_service_executor':0,'model_billing':'UNAVAILABLE'},'limits':policy['simulation_limits']}
    if output is not None:(destination/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


def aggregate(results):
    if not results:raise ValueError('NONEMPTY_ADAPTIVE_TRAJECTORY_COHORT_REQUIRED')
    profits=sorted(r['summary']['profit'] for r in results);n=len(results);success=sum(r['conditional_simulated_go'] for r in results);tail=profits[:max(1,math.ceil(n*.2))]
    return {'runs':n,'go_runs':success,'go_fraction':success/n,'mean_complete_profit':sum(profits)/n,'profit_range':[profits[0],profits[-1]],'downside_cvar20':sum(tail)/len(tail),'cash_survival_fraction':sum(r['cash_survival'] for r in results)/n,'mean_paid_jobs':sum(r['paid_jobs'] for r in results)/n,'mean_customers':sum(r['customers'] for r in results)/n,'mean_profitable_earned_continuations':sum(r['profitable_earned_continuations'] for r in results)/n,'mean_available_earned':sum(r['summary']['unrestrictedEarned'] for r in results)/n,'scope':'Prespecified conditional finite seeded scenarios, not observed real-market demand or revenue probability. Hard protected balances never relaxed; tail loss and chosen region-success tolerance are reported separately.'}


def stable_projection(result):
    timings={'process_cpu_seconds','cpu_seconds','wall_seconds','production_cpu_seconds','production_wall_seconds','worker_cpu_seconds','worker_wall_seconds'}
    def stable(value,path=()):
        if isinstance(value,dict):
            return {key:stable(item,path+(key,)) for key,item in value.items()
                    if key not in timings and not (key=='signature' and 'action_proofs' in path)
                    and not (key=='filesystem' and 'owned_account' in path)}
        if isinstance(value,list):return [stable(item,path) for item in value]
        return value
    return stable(result)
