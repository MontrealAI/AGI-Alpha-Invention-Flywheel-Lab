"""Finite channel menu admission and conservative shared-demand forecasts."""
import copy, unittest
from connected_enterprise.engine import default_config
from connected_enterprise.channels import validate_contracts,ChannelBook,audit_channel_history
from connected_enterprise.channel_menu import menu_options,validate_policy

class ChannelMenu(unittest.TestCase):
 def setUp(self):
  self.cfg=default_config();self.cfg['channels']=validate_contracts(self.cfg['channels']);self.cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['extended','pilot'],'conversion_bps':4000}
  self.buyers={f'c{i:03d}':{'id':f'c{i:03d}','onboarded':False,'active':True} for i in range(96)}
 def options(self,live=None,slots=1,day=1):return menu_options(self.cfg,'competitive_growth',day,self.buyers,{},live or [],[20000000],slots,{'central':10000})
 def test_both_contracts_are_costed_alternatives(self):
  rows=self.options();self.assertEqual([o['execution']['contract_id'] for o in rows],['extended','pilot'])
  self.assertEqual([o['upfront_cost'] for o in rows],[20500000,6250000]);self.assertEqual(rows[0]['benefit_ids'],rows[1]['benefit_ids'])
  self.assertTrue(all(o['execution']['funding']=='EARNED' for o in rows))
 def test_live_other_contract_does_not_blanket_block(self):
  rows=self.options([{'contract_id':'pilot','activation_day':3,'expiry_day':10}]);self.assertTrue(any(o['execution']['contract_id']=='extended' for o in rows))
 def test_contract_tranche_bound_and_zero_capacity(self):
  live=[{'contract_id':'pilot','activation_day':3,'expiry_day':24}]*2
  self.assertFalse(any(o['execution']['contract_id']=='pilot' for o in self.options(live)))
  self.assertEqual(self.options(slots=0),[])
 def test_disjoint_live_window_does_not_subtract_reach(self):
  rows=self.options([{'contract_id':'pilot','activation_day':100,'expiry_day':121}]);self.assertEqual(rows,self.options())
 def test_concurrent_actual_exposures_are_unique_and_replayable(self):
  book=ChannelBook(2610311750,self.cfg['channels']);book.purchase('pilot',0,'paid-pilot');book.purchase('extended',0,'paid-extended')
  buyers=list(self.buyers.values())
  for day in range(25):
   xs=book.expose(day,buyers);self.assertEqual(len(xs),len({x['customer_id'] for x in xs}))
  audit_channel_history(book.export(),self.cfg['channels'],2610311750,buyers)
 def test_shared_benefits_and_earned_funding_prevent_double_count(self):
  from adaptive_enterprise.allocation import allocate
  obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':100000000,'unrestrictedEarned':100000000}}
  risk={'scenarios':{'central':10000},'worst_loss_limit':0,'downside_penalty_bps':0,'max_states':32,'authorized_allocation':100000000,'interactions':[]}
  result=allocate(obs,self.options(),risk,allow_seed=True,max_delivery_slots=1)
  self.assertEqual(len(result['selected']),1)
  obs['summary']['unrestrictedEarned']=0
  self.assertEqual(allocate(obs,self.options(),risk,allow_seed=True,max_delivery_slots=1)['selected'],[])
 def test_owned_audience_matches_each_contract(self):
  for count in (0,4,6):
   self.cfg['channels']['extended']['owned_audience_count']=count
   self.cfg['channels']['pilot']['owned_audience_count']=6-count
   rows={r['execution']['contract_id']:r for r in self.options()}
   self.assertEqual(rows['extended']['execution']['forecast_inputs']['reachable'],96-count)
   self.assertEqual(rows['pilot']['execution']['forecast_inputs']['reachable'],96-(6-count))
 def test_unknown_contract_rejected(self):
  p=copy.deepcopy(self.cfg['channel_menu_policy']);p['contract_ids']=['free-audience']
  with self.assertRaises(ValueError):validate_policy(p,self.cfg['channels'])

if __name__=='__main__':unittest.main()
