"""Small regressions for financial feasibility and honest finite optimization."""
import copy
import unittest
from adaptive_enterprise.strategies import offer_catalog
from adaptive_enterprise.allocation import allocate
from connected_enterprise.mechanism_choice import MODES
from connected_enterprise.strategic_commerce import select, rederive, allocate_actions, rederive_actions, _belief_choice
from portfolio25.pricing import SCENARIOS

class StrategicChoice(unittest.TestCase):
    def setUp(self):
        self.scenarios=copy.deepcopy(list(SCENARIOS))
        for s in self.scenarios:s.update(repeat_horizon=0,cost_shock=1)
        self.policy={'schema':'connected-strategic-commerce/v1','public_basis':'Explicit uncalibrated public test beliefs',
            'price_bps':[3000,5000,8999,9000,11000],'rival_price_bps':[4000,6000,8000,10000],
            'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':self.scenarios,'demand_model':'connected_range',
            'connected_beliefs':{s['id']:{'min_value_bps':10000,'max_value_bps':20000,'min_budget_microUSD':0,'max_budget_microUSD':600000000,'rival_available_bps':10000} for s in self.scenarios}}
        base=dict(execution=500000,discovery=0,integration=0,verification=100000,maintenance=10000,retrieval=0,failed_attempts=0)
        costs={m:dict(base) for m in MODES if m!='hold'}
        costs['generated']['execution']=900000;costs['critic_retain'].update(discovery=1000000,integration=500000)
        self.methods={'mode':'optimize','costs':costs,'accept_collect_bps':9700,'future_equivalent_jobs':0,'public_basis':'Paid method envelopes'}
        self.offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='generated_schema')
        self.public={'anchor':25000000,'public_rival_price':22500000,'base_cost':2500000,'payment_bps':290,'payment_fixed':300000,'available':100000000,'reserve_buffer':1000000,'quote_cost':150000,'native_state_digest':'a'*64,'profit_tax_bps':2000}
        self.obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':100000000,'unrestrictedEarned':0}}
        self.risk={'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},'worst_loss_limit':50000000,'downside_penalty_bps':0,'max_states':4096,'authorized_allocation':100000000,'interactions':[]}
    def pick(self, public=None):return select(self.policy,self.methods,'j',self.offer,None,public or self.public)
    def delivery(self):return [{'id':'first','customer_id':'c','onboarding':0,'exclusive_group':'c','selection':self.pick(),'requires':[]}]
    def investment(self):return {'id':'channel','kind':'acquisition','upfront_cost':1000000,'later_liabilities':dict.fromkeys(self.risk['scenarios'],0),'future_net_cash':dict.fromkeys(self.risk['scenarios'],10000000),'benefit_ids':['future-leads'],'requires':[],'exclusive_group':None,'authorized':True,'evidence':'public-contract-forecast','execution':{'funding':'EARNED'}}
    def test_actual_alternative_ordering(self):
        r=self.pick();self.assertEqual(r['offer']['price_microUSD'],22497500);self.assertEqual(r['method_plan']['mode'],'conventional');rederive(r)
    def test_affordable_alternative_before_ranking(self):
        r=self.pick({**self.public,'available':13000000});self.assertEqual(r['offer']['price_microUSD'],7500000)
        self.assertIsNone(self.pick({**self.public,'available':1})['offer'])
    def test_hidden_and_changed_inputs_refused(self):
        with self.assertRaises(ValueError):self.pick({**self.public,'actual_future_draw':.5})
        r=self.pick();r['decision']['selected']['price']+=1
        with self.assertRaises(ValueError):rederive(r)
    def test_scenario_identity_and_weights(self):
        p=copy.deepcopy(self.policy);p['scenarios'][1]['id']=p['scenarios'][0]['id']
        with self.assertRaises(ValueError):select(p,self.methods,'j',self.offer,None,self.public)
        risk=copy.deepcopy(self.risk);risk['scenarios']['baseline']-=1;risk['scenarios']['ai_parity_price_war']+=1
        with self.assertRaises(ValueError):allocate_actions(self.obs,self.delivery(),[],risk)
    def test_seed_delivery_but_earned_expansion(self):
        r=allocate_actions(self.obs,self.delivery(),[self.investment()],self.risk)
        self.assertTrue(r['decision']['selected']);self.assertNotIn('channel',r['decision']['selected']);rederive_actions(r)
        self.obs['summary']['unrestrictedEarned']=100000000
        r=allocate_actions(self.obs,self.delivery(),[self.investment()],self.risk)
        self.assertIn('channel',r['decision']['selected'])
    def test_operating_costs_deduct_before_earned_expansion(self):
        self.obs['summary']['unrestrictedEarned']=1000000
        r=allocate_actions(self.obs,self.delivery(),[self.investment()],self.risk,earned_deduction=1)
        self.assertNotIn('channel',r['decision']['selected']);rederive_actions(r)
        self.assertEqual(r['observation']['summary']['unrestrictedEarned'],1000000)
    def test_current_capacity_and_neutral_principal(self):
        self.obs['summary']['unrestrictedEarned']=100000000
        r=allocate_actions(self.obs,self.delivery(),[self.investment()],self.risk,max_delivery_slots=0)
        self.assertEqual(r['decision']['selected'],['channel'])
        r=allocate_actions(self.obs,self.delivery(),[],self.risk)['decision']
        locks=sum(o['execution']['cash_lock'] for o in r['selected_options'])
        self.assertEqual(r['reserve_amount'],r['upfront_cost']+r['worst_later_reserve']+locks)
    def test_no_forced_sale_and_decline_tie(self):
        b=self.policy['connected_beliefs']['baseline'];b.update(min_value_bps=0,max_value_bps=0)
        self.assertEqual(_belief_choice(1,100,self.public,self.policy,self.scenarios[0]),(0,0))
        b.update(min_value_bps=10000,max_value_bps=10000,min_budget_microUSD=100000000,max_budget_microUSD=100000000)
        self.assertEqual(_belief_choice(25000000,25000000,self.public,self.policy,self.scenarios[0]),(.25,.25))
    def test_bounded_categorical_enumeration(self):
        options=[]
        for g in range(2):
            for n in range(20):
                o=self.investment();o.update(id=f'g{g}-{n}',kind='delivery',exclusive_group=f'g{g}',benefit_ids=[f'j{g}'])
                o['execution']={'job_id':f'j{g}','customer_id':f'c{g}','payment_bps':0,'payment_fixed_microUSD':0,'onboarding_microUSD':0,'funding':'SEED_OR_EARNED','cash_lock':1};options.append(o)
        for n in range(2):
            o=self.investment();o.update(id=f'i{n}',benefit_ids=[f'i{n}']);options.append(o)
        self.obs['summary']['unrestrictedEarned']=100000000
        r=allocate(self.obs,options,{**self.risk,'max_states':256},allow_seed=True,max_delivery_slots=1)
        self.assertEqual(r['states_evaluated'],164)
        r=allocate(self.obs,options,{**self.risk,'max_states':100},allow_seed=True,max_delivery_slots=1)
        self.assertEqual(r['optimality_scope'],'NONE');self.assertEqual(r['selected'],[])

if __name__=='__main__':unittest.main()
