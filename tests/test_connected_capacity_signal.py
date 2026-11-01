import copy
import unittest
from adaptive_enterprise.allocation import default_riskpolicy
from connected_enterprise.capacity_signal import capacity_only

def option(ident,units,net=100):
 return {'id':ident,'kind':'delivery','upfront_cost':10,'later_liabilities':{'central':0,'adverse':0},'future_net_cash':{'central':net+10,'adverse':net+10},'benefit_ids':[ident],'requires':[],'exclusive_group':ident,'authorized':True,'evidence':'fixture','execution':{'customer_id':ident,'capacity_units':units,'work_keys':[ident],'funding':'SEED_OR_EARNED','cash_lock':20}}

def record(chosen,slots=3):
 return {'decision':{'selected_options':chosen},'riskpolicy':default_riskpolicy(),'observation':{'summary':{'available':1000,'unrestrictedEarned':100}},'earned_deduction':0,'allow_seed':True,'max_delivery_slots':slots}

class CapacitySignal(unittest.TestCase):
 def test_packet_consumes_three_not_one(self):
  self.assertTrue(capacity_only(record([option('packet',3)]),option('other',1)))
  self.assertTrue(capacity_only(record([option('primitive',1)]),option('packet',3)))
  self.assertFalse(capacity_only(record([option('primitive',1)],4),option('packet',3)))
 def test_cash_and_earned_constraints_still_bind(self):
  r=record([option('packet',3)]);r['observation']['summary']['available']=59
  self.assertFalse(capacity_only(r,option('other',1)))
  r=record([option('packet',3)]);candidate=option('other',1);candidate['execution']['funding']='EARNED';r['earned_deduction']=71
  self.assertFalse(capacity_only(r,candidate))
 def test_native_stop_is_not_capacity_only(self):
  r=record([option('packet',3)]);r['observation']['summary']['investmentStopped']=True
  self.assertFalse(capacity_only(r,option('other',1)))
 def test_work_exclusivity_dependencies_and_value(self):
  for change in ('work','exclusive','dependency','unprofitable'):
   c=option('other',1)
   if change=='work':c['execution']['work_keys']=['packet']
   if change=='exclusive':c['exclusive_group']='packet'
   if change=='dependency':c['requires']=['missing']
   if change=='unprofitable':c['future_net_cash']={'central':0,'adverse':0}
   self.assertFalse(capacity_only(record([option('packet',3)]),c),change)
 def test_native_auditor_rejects_false_no_bid_reason(self):
  from pathlib import Path
  import tempfile
  from tests.test_connected_complete_offer import fixture
  from adaptive_enterprise.instruments import prepare_complete_offer_services
  from connected_enterprise.engine import run_world
  from connected_enterprise.verify import audit
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(prefix='.capacity-signal-',dir=root) as folder:
   folder=Path(folder)
   manifest=prepare_complete_offer_services(root,str(folder.relative_to(root)/'jobs'),cohort_seed=2610312145,packet_jobs=8,packet_rows=40)
   result=run_world(root,manifest,fixture(manifest,'menu'),2610312145,'competitive_growth',folder/'world')
   self.assertTrue(audit(root,manifest,result)['accepted'])
   declines=[d for d in result['decisions'] if d['kind']=='capacity_decline']
   self.assertTrue(declines)
   declines[0]['kind']='joint_no_bid'
   with self.assertRaises(ValueError):audit(root,manifest,result)
 def test_signal_has_no_mutation_or_authority(self):
  r=record([option('packet',3)]);c=option('other',1);before=copy.deepcopy((r,c))
  self.assertIs(capacity_only(r,c),True);self.assertEqual((r,c),before)
if __name__=='__main__':unittest.main()
