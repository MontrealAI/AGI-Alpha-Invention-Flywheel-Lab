import copy,sys,unittest
from pathlib import Path
from connected_enterprise.channels import ChannelBook
from connected_enterprise.sequence_channels import forecast_contract
from connected_enterprise.sequence_planning import sequence_options
class MultiChannelSequence(unittest.TestCase):
 def setUp(self):
  from connected_enterprise.engine import default_config
  self.cfg=default_config();self.buyers={f'c{i:02}':{'id':f'c{i:02}','onboarded':False,'active':True} for i in range(12)}
  self.book=ChannelBook(999,self.cfg['channels']);self.book.expose(0,list(self.buyers.values()))
 def forecast(self,contract='extended',future=3):return forecast_contract(self.cfg['channels'],self.book.export(),self.buyers,0,future,contract)
 def test_exact_extended_terms_not_pilot_prices(self):
  r=self.forecast();self.assertEqual(r['invoice_microUSD'],20500000);self.assertEqual(r['terms'],self.cfg['channels']['extended']);self.assertTrue(r['new_tranche_admissible'])
 def test_other_live_contract_allows_second_contract(self):
  self.book.purchase('pilot',0,'paid-pilot');self.assertTrue(self.forecast()['new_tranche_admissible'])
 def test_per_contract_tranche_guard(self):
  self.book.purchase('extended',0,'paid-e1');self.book.purchase('extended',0,'paid-e2');self.assertFalse(self.forecast()['new_tranche_admissible'])
 def test_expired_and_unactivated_new_window(self):
  self.assertFalse(self.forecast(future=2)['new_tranche_admissible']);self.assertFalse(self.forecast(future=25)['new_tranche_admissible'])
 def test_shared_fatigue_and_cooldown_are_actual_transitions(self):
  for ident in self.buyers:self.book.state['contacts'][ident]=[{'day':0,'source_plan_id':'prior','exposure_id':'x'}]*3
  r=self.forecast();self.assertTrue(all(x['candidate']['window_contacts']==0 for x in r['rows']))
 def test_owned_and_channel_customer_populations_are_disjoint(self):
  self.cfg['channels']['extended']['owned_audience_count']=0
  book=ChannelBook(999,self.cfg['channels']);book.expose(0,list(self.buyers.values()))
  r=forecast_contract(self.cfg['channels'],book.export(),self.buyers,0,3,'extended',owned_contact_count=8)
  self.assertEqual(len(r['owned_customer_ids']),4)
  for row in r['rows']:
   for arm in ('baseline','candidate'):self.assertFalse(set(row[arm]['window_customer_ids'])&set(r['owned_customer_ids']))
 def test_no_original_state_mutation_or_actual_future_seed(self):
  before=self.book.export();r=self.forecast();self.assertEqual(before,self.book.export())
  other=ChannelBook(123456,self.cfg['channels']);other.expose(0,list(self.buyers.values()))
  q=forecast_contract(self.cfg['channels'],other.export(),self.buyers,0,3,'extended');self.assertEqual(r['rows'],q['rows'])
 def test_stale_state_and_changed_terms_rejected(self):
  state=self.book.export();state['last_day']=-1
  with self.assertRaises(ValueError):forecast_contract(self.cfg['channels'],state,self.buyers,0,3,'extended')
  self.book.purchase('pilot',0,'paid');self.book.state['instances']['paid']['terms']['price_microUSD']=1
  with self.assertRaises(ValueError):self.forecast()
 def test_same_planner_carries_exact_contract_cost_and_shared_benefit(self):
  scripts=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(scripts))
  try:
   from run_sequence026 import config
   cfg=config('central','sequence');cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['extended','pilot'],'conversion_bps':4000}
   jobs={'j':{'job':{'id':'j','accepted':True,'service_id':'reconciliation'},'artifact':{'method':'canonical','outcome_scope':'complete_outcome'}}}
   obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':100000000,'unrestrictedEarned':100000000}}
   rows=sequence_options(cfg,0,obs,0,jobs,set(),[],self.buyers,{},set(),cfg['strategic_allocation_policy']['risk']['scenarios'],channel_state=self.book.export())
   acquisitions=[r for r in rows if r['kind']=='acquisition'];self.assertEqual({r['execution']['contract_id'] for r in acquisitions},{'pilot','extended'})
   for row in acquisitions:
    terms=cfg['channels'][row['execution']['contract_id']];self.assertEqual(row['upfront_cost'],terms['price_microUSD']+terms['support_microUSD']);self.assertEqual(row['execution']['funding'],'EARNED')
    f=row['execution']['forecast']['forecast'];samples=f['channel_forecast']['rows']
    for route in f['routes']:
     key='candidate' if route['channel'] else 'baseline'
     reserved=max(x[key]['attempted_slots_to_window']*cfg['exposure_cost']+x[key]['realized_contacts_to_window']*cfg['qualification_cost'] for x in samples)+len(f['channel_forecast']['owned_customer_ids'])*(cfg['exposure_cost']+cfg['qualification_cost'])*cfg['strategic_allocation_policy']['sequence']['window_delay_days']
     self.assertEqual(route['future_contact_reserve_microUSD'],reserved)
   self.assertEqual(len({tuple(r['benefit_ids']) for r in rows}),1)
   obs['summary']['unrestrictedEarned']=0
   self.assertEqual(sequence_options(cfg,0,obs,0,jobs,set(),[],self.buyers,{},set(),cfg['strategic_allocation_policy']['risk']['scenarios'],channel_state=self.book.export()),[])
  finally:sys.path.remove(str(scripts))
if __name__=='__main__':unittest.main()
