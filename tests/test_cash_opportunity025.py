"""Diagnostic cash relaxation is non-executable and capacity/funding constrained."""
import copy
from fractions import Fraction
import unittest
from portfolio25.pricing import SCENARIOS
from connected_enterprise.strategic_commerce import select,allocate_actions,cash_opportunity_diagnostic

class CashOpportunity(unittest.TestCase):
    def fixture(self, slots=1, max_states=4096):
        scenarios=copy.deepcopy(list(SCENARIOS))
        for s in scenarios:s.update(repeat_horizon=0,cost_shock=1)
        policy={'schema':'connected-strategic-commerce/v1','public_basis':'Declared diagnostic test only',
            'price_bps':[5000,8999],'rival_price_bps':[9000],'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,'demand_model':'connected_range',
            'connected_beliefs':{s['id']:{'min_value_bps':10000,'max_value_bps':20000,'min_budget_microUSD':100000000,'max_budget_microUSD':100000000,'rival_available_bps':10000} for s in scenarios}}
        obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':1,'unrestrictedEarned':0}}
        public={'anchor':25000000,'public_rival_price':22500000,'base_cost':2500000,'payment_bps':290,'payment_fixed':300000,'available':1,'reserve_buffer':1000000,'quote_cost':150000,'native_state_digest':'a'*64,'profit_tax_bps':2000}
        selection=select(policy,None,'job',{'service_id':'other','method':'default'},None,public)
        ds=[{'id':'first','customer_id':'c','onboarding':0,'exclusive_group':'c','selection':selection,'requires':[]}]
        risk={'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},'worst_loss_limit':50000000,'downside_penalty_bps':0,'max_states':max_states,'authorized_allocation':1,'interactions':[]}
        return allocate_actions(obs,ds,[],risk,max_delivery_slots=slots)
    def diagnose(self,r):return cash_opportunity_diagnostic(r,relaxed_available=100000000,declared_allocation_ceiling=100000000)
    def test_cash_gain_without_native_mutation_or_authority(self):
        r=self.fixture();before=copy.deepcopy(r);d=self.diagnose(r)
        self.assertEqual(r,before);self.assertEqual(d['actual']['delivery_count'],0)
        self.assertEqual(d['counterfactual']['selected_work'][0]['job_id'],'job')
        self.assertEqual(d['counterfactual']['selected_work'][0]['mode'],'default')
        self.assertEqual(d['counterfactual']['delivery_count'],1);self.assertGreater(Fraction(d['predicted_objective_gain']),0)
        self.assertIsNone(d['authorized_digest']);self.assertIsNone(d['counterfactual']['authorized_digest'])
        for key in ['selected_options','action_id','plan_id','reserve_amount','execution']:
            self.assertNotIn(key,d['counterfactual'])
    def test_zero_slots_no_gain(self):
        d=self.diagnose(self.fixture(slots=0));self.assertEqual(d['counterfactual']['delivery_count'],0);self.assertEqual(d['predicted_objective_gain'],'0')
    def test_bound_is_unresolved(self):
        d=self.diagnose(self.fixture(max_states=1));self.assertFalse(d['resolved']);self.assertIsNone(d['predicted_objective_gain'])
    def test_declared_ceiling_binding(self):
        r=self.fixture();r['riskpolicy']['authorized_allocation']=2
        with self.assertRaises(ValueError):self.diagnose(r)
    def test_earned_only_investment_stays_unfunded(self):
        r=self.fixture();sc=r['riskpolicy']['scenarios']
        investment={'id':'channel','kind':'acquisition','upfront_cost':100,'later_liabilities':dict.fromkeys(sc,0),'future_net_cash':dict.fromkeys(sc,10000000),'benefit_ids':['new-demand'],'requires':[],'exclusive_group':None,'authorized':True,'evidence':'declared-test','execution':{'funding':'EARNED'}}
        r=allocate_actions(r['observation'],r['deliveries'],[investment],r['riskpolicy'],max_delivery_slots=0)
        d=self.diagnose(r);self.assertEqual(d['counterfactual']['selected_ids'],[])
        self.assertEqual(d['predicted_objective_gain'],'0')
    def test_default_replay_identical(self):
        r=self.fixture();self.diagnose(r)
        again=allocate_actions(r['observation'],r['deliveries'],r['investments'],r['riskpolicy'],max_delivery_slots=r['max_delivery_slots'])
        self.assertEqual(r,again)

if __name__=='__main__':unittest.main()
