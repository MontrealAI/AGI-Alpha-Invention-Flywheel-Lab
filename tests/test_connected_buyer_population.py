"""Configured finite populations are not an authored universal market ceiling."""
import copy,tempfile,unittest
from pathlib import Path
from connected_enterprise.engine import default_config,validate_config,_buyers,run_world
from connected_enterprise.verify import _check_buyer_origins,audit
from connected_enterprise.channels import ChannelBook,audit_channel_history
from adaptive_enterprise.instruments import prepare_services
ROOT=Path(__file__).resolve().parents[1]
class BuyerPopulation(unittest.TestCase):
 def test_positive_integer_population_has_no_200_or_10000_ceiling(self):
  for n in (1,201,10001,10**12):
   cfg=default_config();cfg['customer_pool']=n
   self.assertEqual(validate_config(cfg)['customer_pool'],n)
  for bad in (0,-1,True,201.0,float('inf'),float('nan'),'201',None):
   cfg=default_config();cfg['customer_pool']=bad
   with self.assertRaises(ValueError):validate_config(cfg)
 def test_generation_identity_audit_and_channel_reach_above_200(self):
  cfg=default_config();cfg['customer_pool']=257;buyers=_buyers(cfg,2610312234)
  self.assertEqual(len(buyers),257);self.assertEqual(len({b['id'] for b in buyers}),257)
  self.assertEqual(sum(b['known'] for b in buyers),4)
  self.assertTrue(all(not b['onboarded'] and b['purchases']==0 for b in buyers))
  _check_buyer_origins(cfg,2610312234,buyers)
  terms=cfg['channels']['pilot'];terms.update(slots_per_day=257,activation_reliability_bps=10000,realization_bps=10000,overlap_bps=10000)
  book=ChannelBook(2610312234,cfg['channels']);book.purchase('pilot',0,'paid-channel-fixture')
  xs=book.expose(terms['lead_days'],buyers)
  self.assertTrue(any(int(x['customer_id'].rsplit('-',1)[1])>200 for x in xs))
  self.assertLessEqual(len(xs),257-terms['owned_audience_count'])
  audit_channel_history(book.export(),cfg['channels'],2610312234,buyers)
 def test_full_native_audit_with_257_configured_buyers(self):
  with tempfile.TemporaryDirectory(prefix='.buyer-population-',dir=ROOT) as folder:
   folder=Path(folder);manifest=prepare_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2610312234)
   cfg=default_config();cfg.update(customer_pool=257,horizon_days=1,arrival_bps=0)
   result=run_world(ROOT,manifest,cfg,2610312234,'baseline',folder/'world')
   checked=audit(ROOT,manifest,result)
   self.assertTrue(checked['accepted']);self.assertEqual(checked['buyers_checked'],257)
   self.assertEqual(result['orders'],[]);self.assertEqual(result['summary']['collections'],0)
if __name__=='__main__':unittest.main()
