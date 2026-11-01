"""Exposed native wiring and adversarial audit tests, not an economic confirmation."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from adaptive_enterprise.instruments import prepare_complete_offer_services
from connected_enterprise.engine import run_world
from connected_enterprise.verify import audit
from connected_enterprise.joint_planning import plan_actions
from test_connected_complete_offer import fixture
ROOT=Path(__file__).resolve().parents[1]
def policy(scenarios):
 return {'schema':'connected-finite-follower-regret/v1','public_basis':'Exposed engineering stress: hypothetical competitor captures a fraction of positive contribution; not executed rival dynamics.','max_response_states':1000000,'scenarios':{s:{'budget':0,'responses':[{'id':'unchanged','haircut_bps':{},'capture_bps':0,'cost':0},{'id':'compete','haircut_bps':{'delivery':100,'capacity':100,'acquisition':100},'capture_bps':5000,'cost':0}]} for s in scenarios}}
class JointGameOperating(unittest.TestCase):
 def test_native_prefix_public_information_quantity_and_effects(self):
  with tempfile.TemporaryDirectory(prefix='.joint-game-',dir=ROOT) as tmp:
   folder=Path(tmp);manifest=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2610312254,packet_jobs=24,packet_rows=12)
   cfg=fixture(manifest,'menu');cfg.update(horizon_days=16,setup_cost=1000000,maximum_slots=9,capacity_price=1000000)
   cfg['strategic_allocation_policy']['max_customers']=4
   cfg['strategic_allocation_policy']['capacity_menu']={'max_quantity':6,'opportunity_delay_hours':24,'retention_bps':7000}
   cfg['strategic_allocation_policy']['strategic_game']=policy(cfg['strategic_allocation_policy']['risk']['scenarios'])
   calls=[]
   def checked(state,jobs,candidates,*args,**kwargs):
    original=plan_actions(state,jobs,candidates,*args,**kwargs)
    altered=copy.deepcopy(state);cs=copy.deepcopy(candidates)
    for b in altered['buyers']+cs:
     b['remaining_budget']=10**40;b['initial_budget']=10**41
    same=plan_actions(altered,jobs,cs,*args,**kwargs)
    self.assertEqual(original,same,'Policy must not read hidden initial/remaining buyer budget')
    calls.append(original)
    return original
   with patch('connected_enterprise.joint_planning.plan_actions',checked):
    result=run_world(ROOT,manifest,cfg,2610312254,'competitive_growth',folder/'world')
   self.assertTrue(audit(ROOT,manifest,result)['accepted']);self.assertEqual(len(calls),16)
   investments=result['investments'];self.assertTrue(investments)
   self.assertTrue(any(i.get('capacity_units',0)>=3 for i in investments))
   from adaptive_enterprise.strategic_game import investment_expected_net
   for wrapper in result['joint_actions'].values():
    decision=wrapper['allocation']['decision']
    self.assertIn('strategic_game_certificate',decision)
    for option in decision['selected_options']:
     if option['kind']=='delivery':continue
     row=next(i for i in investments if i['id']==option['id'])
     self.assertEqual(row['predicted_net'],investment_expected_net(decision,option['id']))
   for mutate in [lambda r:next(iter(r['joint_actions'].values()))['allocation']['observation']['summary'].__setitem__('available',10**40),lambda r:next(iter(r['joint_actions'].values())).__setitem__('operating_envelope',0),lambda r:r['investments'][0].__setitem__('predicted_net',10**40)]:
    bad=copy.deepcopy(result);mutate(bad)
    with self.assertRaises(ValueError):audit(ROOT,manifest,bad)
   bad=copy.deepcopy(result)
   target=next(w for w in bad['joint_actions'].values() if w['allocation']['decision']['selected_options'])
   values=target['allocation']['decision']['strategic_game_certificate']['selected_option_expected_net_fraction']
   values[next(iter(values))]='100000000000000000000'
   with self.assertRaises(ValueError):audit(ROOT,manifest,bad)
   from connected_enterprise.strategic_commerce import cash_opportunity_diagnostic
   with self.assertRaisesRegex(ValueError,'STRATEGIC_GAME_CASH_DIAGNOSTIC_UNAVAILABLE'):
    cash_opportunity_diagnostic(target['allocation'],relaxed_available=10**20,declared_allocation_ceiling=10**20)
   print('EXPOSED_GAME_NATIVE',{'profit':result['summary']['profit'],'investments':len(investments),'planning_checks':len(calls)})
if __name__=='__main__':unittest.main()
