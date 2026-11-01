import copy,json,unittest,importlib.util
from pathlib import Path
from adaptive_enterprise.allocation import allocate
from adaptive_enterprise.strategic_game import rederive,investment_expected_net,select_game
import adaptive_enterprise.strategic_game as game_module
from unittest.mock import patch

_original_select=select_game
_full=[]
def capture_select(*args,**kwargs):
    result=_original_select(*args,**kwargs);_full.append(result);return result



def fixture():
    obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':10000,'unrestrictedEarned':10000}}
    risk={'scenarios':{'normal':5000,'rival':5000},'worst_loss_limit':1000,'downside_penalty_bps':0,'max_states':128,'authorized_allocation':10000,'interactions':[]}
    unchanged={'id':'hold','haircut_bps':{},'capture_bps':0,'cost':0}
    game={'schema':'connected-finite-follower-regret/v1','public_basis':'Declared public reduced-form stress, not real rival receipts','max_response_states':1000,'scenarios':{'normal':{'budget':0,'responses':[unchanged]},'rival':{'budget':100,'responses':[unchanged,{'id':'compete','haircut_bps':{'delivery':10000},'capture_bps':10000,'cost':1}]}}}
    def opt(id,kind,net):
        return {'id':id,'kind':kind,'upfront_cost':10,'later_liabilities':dict.fromkeys(risk['scenarios'],0),'future_net_cash':dict.fromkeys(risk['scenarios'],net+10),'benefit_ids':[id],'requires':[],'exclusive_group':'one','authorized':True,'evidence':'public','execution':{'funding':'EARNED' if kind=='capacity' else 'SEED_OR_EARNED','cash_lock':20,'job_id':id,'customer_id':'c','payment_bps':0,'payment_fixed_microUSD':0,'onboarding_microUSD':0}}
    return obs,risk,game,[opt('risky','delivery',100),opt('stable','capacity',60)]

class StrategicGame(unittest.TestCase):
    def setUp(self):
        self.patcher=patch.object(game_module,"select_game",side_effect=capture_select);self.patcher.start();self.addCleanup(self.patcher.stop)
    def test_exact_regret_changes_actual_basket_and_costs_preserved(self):
        obs,risk,g,opts=fixture();before=copy.deepcopy(opts)
        base=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3)
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertEqual(base['selected'],['risky']);self.assertEqual(r['selected'],['stable'])
        self.assertEqual(opts,before);self.assertEqual(r['reserve_amount'],30)
        self.assertEqual(investment_expected_net(r,'stable'),60)
        compact=r['strategic_game_certificate'];self.assertNotIn('alternatives',compact);self.assertLess(len(json.dumps(compact)),3000)
        cert=_full[-1];self.assertEqual(len(cert['alternatives']),3)
        self.assertEqual(cert['selected_option_expected_net_fraction'],{'stable':'60'})
        rederive(json.loads(json.dumps(cert)));cert['alternatives'][0]['expected_net']='1'
        with self.assertRaises(ValueError):rederive(cert)

    def test_budget_cost_and_tie_are_explicit(self):
        obs,risk,g,opts=fixture();g['scenarios']['rival']['budget']=0
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertEqual(r['selected'],['risky'])
        g['scenarios']['rival']['budget']=100;g['scenarios']['rival']['responses'][1]['cost']=100
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        row=next(x for x in _full[-1]['alternatives'] if x['selected']==['risky'])
        self.assertEqual(row['scenario_responses']['rival']['best_response_ties'],['compete','hold'])
        self.assertEqual(row['scenario_responses']['rival']['seller_net'],'0')

    def test_response_bound_no_false_optimum_or_authority(self):
        obs,risk,g,opts=fixture();g['max_response_states']=1
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertEqual(r['optimality_scope'],'NONE');self.assertEqual(r['selected'],[]);self.assertIsNone(r['authorized_digest'])

    def test_earned_option_must_remain_positive(self):
        obs,risk,g,opts=fixture()
        for sid in g['scenarios']:
            g['scenarios'][sid]={'budget':100,'responses':[{'id':'hold','haircut_bps':{},'capture_bps':0,'cost':0},{'id':'capture','haircut_bps':{'capacity':10000},'capture_bps':10000,'cost':0}]}
        r=allocate(obs,[opts[1]],risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertEqual(r['selected'],[])

    def test_native_capacity_cash_work_dependency_guards_remain(self):
        obs,risk,g,opts=fixture();opts[0]['execution'].update(capacity_units=3,work_keys=['shared'])
        opts[1]['exclusive_group']=None;opts[1]['execution'].update(recourse_work_keys=['shared'],earned_cash_lock=0,capacity_recourse_schema='connected-capacity-recourse/v1')
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=2,strategic_game=g)
        self.assertTrue(all('risky' not in row['selected'] for row in _full[-1]['alternatives']))
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertFalse(any(len(row['selected'])==2 for row in _full[-1]['alternatives']))
        obs['summary']['unrestrictedEarned']=0
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertTrue(all('stable' not in row['selected'] for row in _full[-1]['alternatives']))

    def test_unprofitable_earned_action_not_subsidized_by_delivery(self):
        obs,risk,g,opts=fixture()
        for o in opts:o['exclusive_group']=None
        for sid in g['scenarios']:
            g['scenarios'][sid]={'budget':100,'responses':[{'id':'hold','haircut_bps':{},'capture_bps':0,'cost':0},{'id':'capture','haircut_bps':{'capacity':10000},'capture_bps':10000,'cost':0}]}
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        row=next(x for x in _full[-1]['alternatives'] if len(x['selected'])==2)
        self.assertEqual(row['expected_net'],'100')
        self.assertEqual(row['option_expected_net_fraction']['stable'],'0')
        self.assertFalse(row['eligible_after_response'])
        self.assertEqual(r['selected'],['risky'])

    def test_sequence_first_investment_payload_preserved(self):
        obs,risk,g,opts=fixture();o=opts[1]
        o['execution']['first_investment']={'kind':'capacity','contract_id':'declared-unit','cost':10,'capacity_units':2}
        before=copy.deepcopy(o)
        r=allocate(obs,[o],risk,allow_seed=True,max_delivery_slots=3,strategic_game=g)
        self.assertEqual(r['selected_options'],[before]);self.assertEqual(o,before)
        self.assertEqual(investment_expected_net(r,'stable'),60)

    def test_large_enumeration_does_not_duplicate_table_into_native_plan(self):
        obs,risk,g,base=fixture();opts=[]
        risk['max_states']=4096;g['max_response_states']=10000
        for n in range(7):
            for template in base:
                o=copy.deepcopy(template);o['id']+=str(n);o['exclusive_group']='group'+str(n);o['benefit_ids']=[o['id']];o['execution']['job_id']=o['id'];opts.append(o)
        r=allocate(obs,opts,risk,allow_seed=True,max_delivery_slots=7,strategic_game=g)
        self.assertEqual(r['strategic_game_certificate']['feasible_basket_count'],2187)
        self.assertGreater(len(json.dumps(_full[-1])),2000000)
        self.assertLess(len(json.dumps(r)),100000)
        self.assertIsNotNone(r['authorized_digest'])

    def test_no_positive_bonus_and_big_rational_values(self):
        obs,risk,g,opts=fixture();g['scenarios']['rival']['responses'][1]['haircut_bps']['delivery']=-1
        with self.assertRaises(ValueError):allocate(obs,opts,risk,strategic_game=g)
        _,risk,g,_=fixture();n=2**80
        bs=[{'selected':[],'reserve_amount':0,'net':dict.fromkeys(risk['scenarios'],0),'positive_by_kind':dict.fromkeys(risk['scenarios'],{}),'options':[]}]
        for id,value in [('a',n),('b',n+1)]:
            bs.append({'selected':[id],'reserve_amount':10,'net':dict.fromkeys(risk['scenarios'],value),'positive_by_kind':{s:{'capacity':value} for s in risk['scenarios']},'options':[{'id':id,'kind':'capacity','funding':'EARNED','net':dict.fromkeys(risk['scenarios'],value)}]})
        c=select_game(bs,g,risk,'a'*64);self.assertEqual(c['selected_option_expected_net_fraction'],{'b':str(n+1)})

if __name__=='__main__':unittest.main()
