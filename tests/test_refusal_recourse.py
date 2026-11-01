"""Finite real-allocator public-response tests; no native market or sales claim."""
import copy,json,unittest
from portfolio25.pricing import SCENARIOS
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.strategic_commerce import select,allocate_actions,rederive_actions
from connected_enterprise.refusal_recourse import recourse,trace_digest,selective_decision,SELECTIVE_SCHEMA


def fixture(count=3,slots=3,cash=100000,prices=None,work=None,invest=False):
    obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':cash,'unrestrictedEarned':cash}}
    sc=copy.deepcopy(SCENARIOS[0]);sc.update(id='case',weight=1,repeat_horizon=0,cost_shock=1,accept_prob=1,collect_prob=1)
    policy={'schema':'connected-strategic-commerce/v1','public_basis':'Deterministic finite public engineering prior, not observed demand','price_bps':[5000],'rival_price_bps':[10000],'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':[sc],'demand_model':'connected_range','connected_beliefs':{'case':{'min_value_bps':20000,'max_value_bps':20000,'min_budget_microUSD':100000,'max_budget_microUSD':100000,'rival_available_bps':0}}}
    offer=next(o for o in offer_catalog(include_packet=True) if o['service_id']=='receivables_packet')
    ds=[]
    for i in range(count):
        price=prices[i] if prices else 1000
        pub={'anchor':price*2,'public_rival_price':price*2,'base_cost':100,'payment_bps':0,'payment_fixed':0,'available':cash,'reserve_buffer':0,'quote_cost':0,'native_state_digest':'a'*64,'profit_tax_bps':0}
        selection=select(policy,None,'job'+str(i),offer,None,pub)
        ds.append({'id':'quote'+str(i),'customer_id':'buyer'+str(i),'onboarding':0,'exclusive_group':'buyer'+str(i),'selection':selection,'requires':[],'capacity_units':3,'work_keys':work[i] if work else ['work'+str(i)]})
    risk={'scenarios':{'case':10000},'worst_loss_limit':100000,'downside_penalty_bps':0,'max_states':4096,'authorized_allocation':cash,'interactions':[]}
    investments=[]
    if invest:investments=[{'id':'retained-investment','kind':'capacity','upfront_cost':10,'later_liabilities':{'case':0},'future_net_cash':{'case':20},'benefit_ids':['disjoint-future'],'requires':[],'exclusive_group':None,'authorized':True,'evidence':'public-contract','execution':{'funding':'EARNED','contract':{'unit_price':10}}}]
    return allocate_actions(obs,ds,investments,risk,allow_seed=True,max_delivery_slots=slots)


def deliveries(record):return [o for o in record['decision']['selected_options'] if o['kind']=='delivery']
def response(option,accepted):return {'customer_id':option['execution']['customer_id'],'option_id':option['id'],'accepted':accepted}

class RefusalRecourse(unittest.TestCase):
    def test_refusal_exposes_new_quote_without_new_cash(self):
        original=fixture();before=copy.deepcopy(original);first=deliveries(original)[0]
        r=recourse(original,[response(first,False)])
        self.assertEqual(len(deliveries(r)),1)
        self.assertNotEqual(deliveries(r)[0]['execution']['customer_id'],first['execution']['customer_id'])
        self.assertEqual(r['observation'],original['observation']);self.assertEqual(original,before)
        rederive_actions(json.loads(json.dumps(r)))

    def test_accepted_exact_quote_and_investment_remain_mandatory(self):
        original=fixture(4,6,work=[['shared'],['b'],['shared'],['d']],invest=True)
        accepted,refused=deliveries(original)
        attempts=[response(accepted,True),response(refused,False)]
        r=recourse(original,attempts);selected=r['decision']['selected_options']
        self.assertIn(accepted,selected)
        self.assertIn(next(o for o in original['decision']['selected_options'] if o['kind']=='capacity'),selected)
        self.assertEqual(set(r['mandatory_ids']),{accepted['id'],'retained-investment'})
        self.assertLessEqual(sum(o['execution']['capacity_units'] for o in deliveries(r)),6)
        keys=[k for o in deliveries(r) for k in o['execution']['work_keys']]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(len(deliveries(r)),2)
        self.assertNotIn(refused['id'],r['decision']['selected'])

    def test_game_recourse_hold_means_preserve_existing_commitments(self):
        seed=fixture(3,6,invest=True)
        game={'schema':'connected-finite-follower-regret/v1','public_basis':'Explicit no-change response control','max_response_states':4096,'scenarios':{'case':{'budget':0,'responses':[{'id':'hold','haircut_bps':{},'capture_bps':0,'cost':0}]}}}
        original=allocate_actions(seed['observation'],seed['deliveries'],seed['investments'],seed['riskpolicy'],allow_seed=True,max_delivery_slots=6,strategic_game=game)
        accepted,refused=deliveries(original)
        r=recourse(original,[response(accepted,True),response(refused,False)])
        self.assertIn(accepted,r['decision']['selected_options'])
        self.assertIn('retained-investment',r['decision']['selected'])
        self.assertEqual(r['strategic_game'],game)
        rederive_actions(json.loads(json.dumps(r)))

    def test_all_refusals_eventually_hold(self):
        original=fixture();r=original;attempts=[]
        for _ in range(3):
            attempts.append(response(deliveries(r)[0],False));r=recourse(original,attempts)
        self.assertEqual(r['decision']['selected'],[])
        self.assertIsNone(r['decision']['authorized_digest'])
        self.assertEqual(len({a['customer_id'] for a in attempts}),3)

    def test_insufficient_cash_does_not_create_affordable_alternative(self):
        original=fixture(2,cash=1100,prices=[1000,1500]);first=deliveries(original)[0]
        r=recourse(original,[response(first,False)])
        self.assertEqual(r['decision']['selected'],[])
        self.assertEqual(r['observation']['summary']['available'],1100)

    def test_duplicate_unselected_and_malformed_attempts_rejected(self):
        original=fixture();first=deliveries(original)[0];decline=response(first,False)
        other=next(d for d in original['deliveries'] if d['customer_id']!=first['execution']['customer_id'])
        unselected={'customer_id':other['customer_id'],'option_id':other['id']+'-0','accepted':False}
        for attempts in ([decline,decline],[unselected],[response(first,True)],[dict(decline,accepted=0)],[dict(decline,private_budget=100)],[]):
            with self.subTest(attempts=attempts),self.assertRaises(ValueError):recourse(original,attempts)

    def test_original_and_recourse_tampering_rejected(self):
        original=fixture();attempts=[response(deliveries(original)[0],False)]
        bad=copy.deepcopy(original);bad['observation']['summary']['available']+=1
        with self.assertRaises(ValueError):recourse(bad,attempts)
        r=recourse(original,attempts);r['decision']['expected_net']+=1
        with self.assertRaises(ValueError):rederive_actions(r)
        self.assertNotEqual(trace_digest(original,attempts),trace_digest(original,[dict(attempts[0],accepted=True)]))

    def test_game_conditional_hold_retains_real_commitments(self):
        def policy(scenarios):
            return {'schema':'connected-finite-follower-regret/v1','public_basis':'Declared finite response engineering test','max_response_states':4096,'scenarios':{k:{'budget':0,'responses':[{'id':'hold','haircut_bps':{},'capture_bps':0,'cost':0},{'id':'stress','haircut_bps':{'delivery':100,'capacity':100},'capture_bps':5000,'cost':0}]} for k in scenarios}}
        original=fixture(3,6,invest=True)
        original=allocate_actions(original['observation'],original['deliveries'],original['investments'],original['riskpolicy'],max_delivery_slots=6,strategic_game=policy(original['riskpolicy']['scenarios']))
        accepted,refused=deliveries(original)
        r=recourse(original,[response(accepted,True),response(refused,False)])
        self.assertIn(accepted,r['decision']['selected_options'])
        self.assertIn('retained-investment',r['decision']['selected'])
        self.assertIn('strategic_game_certificate',r['decision'])
        rederive_actions(json.loads(json.dumps(r)))
        self.assertTrue(set(r['mandatory_ids'])<=set(r['decision']['selected']))

    def test_authored_interactions_rejected_explicitly(self):
        original=fixture();original['riskpolicy']['interactions']=[{'not':'supported'}]
        with self.assertRaisesRegex(ValueError,'RECOURSE_AUTHORED_INTERACTIONS_NOT_COMPOSED'):
            recourse(original,[response(deliveries(original)[0],False)])

    def test_explicit_empty_mandatory_default_byte_parity(self):
        original=fixture()
        r=allocate_actions(original['observation'],original['deliveries'],original['investments'],original['riskpolicy'],allow_seed=original['allow_seed'],max_delivery_slots=original['max_delivery_slots'],earned_deduction=original['earned_deduction'],mandatory_ids=[])
        self.assertEqual(json.dumps(original,sort_keys=True),json.dumps(r,sort_keys=True))
        self.assertNotIn('mandatory_ids',r)


class SelectiveRecourse(unittest.TestCase):
    def test_exact_refusal_survives_a_rounded_certain_acceptance_display(self):
        from connected_enterprise.refusal_recourse import _refusal_probability
        exact='99999999999999999/100000000000000000'
        self.assertEqual(float(__import__('fractions').Fraction(exact)),1.0)
        self.assertGreater(_refusal_probability({'win_probability':1.0,'win_probability_fraction':exact}),0)
        self.assertEqual(_refusal_probability({'win_probability':1.0}),0)

    def uncertain(self,count=3,slots=3,cash=100000,invest=False):
        original=fixture(count,slots,cash,invest=invest)
        for delivery in original['deliveries']:
            p=delivery['selection']['problem']
            p['policy']['connected_beliefs']['case'].update(min_value_bps=0,max_value_bps=10000)
            delivery['selection']=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],p['public'])
        return allocate_actions(original['observation'],original['deliveries'],original['investments'],original['riskpolicy'],allow_seed=True,max_delivery_slots=slots)

    def choice(self,record,cost=100):
        return selective_decision(record,{'schema':SELECTIVE_SCHEMA,'daily_planning_cost':cost,'daily_evaluation_cost':1},['buyer'+str(i) for i in range(10)])

    def test_buy_only_positive_public_alternative_after_fee(self):
        record=self.uncertain();r=self.choice(record)
        self.assertTrue(r['purchase']);self.assertTrue(r['new_alternative_ids'])
        self.assertEqual(r['expected_increment_microUSD'],{'numerator':225,'denominator':1})
        self.assertFalse(self.choice(record,225)['purchase'])
        self.assertFalse(self.choice(record,226)['purchase'])

    def test_no_alternative_certain_acceptance_capacity_and_liquidity_hold(self):
        for record in (self.uncertain(1),fixture(),self.uncertain(slots=0),self.uncertain(cash=500),self.uncertain(count=2,slots=6)):
            with self.subTest(record=record['decision']['selected']):self.assertFalse(self.choice(record)['purchase'])

    def test_shared_scenario_refusal_and_alternative_value_not_independent(self):
        record=fixture();record['riskpolicy']['scenarios']={'bad':5000,'good':5000}
        for delivery in record['deliveries']:
            p=delivery['selection']['problem'];scenario=p['policy']['scenarios'][0]
            p['policy']['scenarios']=[dict(scenario,id=k,weight=.5) for k in ('bad','good')]
            belief=p['policy']['connected_beliefs']['case']
            p['policy']['connected_beliefs']={k:dict(belief,min_value_bps=v,max_value_bps=v) for k,v in [('bad',0),('good',20000)]}
            delivery['selection']=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],p['public'])
        record=allocate_actions(record['observation'],record['deliveries'],record['investments'],record['riskpolicy'],allow_seed=True,max_delivery_slots=3)
        decision=self.choice(record)
        self.assertTrue(decision['new_alternative_ids'])
        self.assertEqual(decision['expected_increment_microUSD'],{'numerator':0,'denominator':1})
        self.assertFalse(decision['purchase'])

    def test_tamper_duplicate_and_accepted_commitment_guards(self):
        record=self.uncertain(invest=True);before=copy.deepcopy(record)
        self.assertTrue(self.choice(record)['purchase']);self.assertEqual(record,before)
        bad=copy.deepcopy(record);bad['decision']['selected_options'][0]['upfront_cost']+=1
        with self.assertRaises(ValueError):self.choice(bad)
        with self.assertRaises(ValueError):selective_decision(record,{'schema':SELECTIVE_SCHEMA,'daily_planning_cost':100,'daily_evaluation_cost':1},['buyer0','buyer0'])
        selected=deliveries(record)[0]
        renewed=recourse(record,[response(selected,False)])
        self.assertIn('retained-investment',renewed['decision']['selected'])

if __name__=='__main__':unittest.main()
