"""Exposed source-bound integration, not fresh economic confirmation."""
import copy,json,tempfile,unittest
from pathlib import Path
from adaptive_enterprise.instruments import prepare_complete_offer_services
from connected_enterprise.engine import run_world
from connected_enterprise.verify import audit
from test_connected_complete_offer import fixture
ROOT=Path(__file__).resolve().parents[1]
class CapacityMenuOperating(unittest.TestCase):
 def test_costed_quantity_and_audited_declared_forecast(self):
  with tempfile.TemporaryDirectory(prefix='.capacity-menu-',dir=ROOT) as folder:
   folder=Path(folder);m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2610312254,packet_jobs=24,packet_rows=12)
   cfg=fixture(m,'menu');cfg.update(horizon_days=16,setup_cost=1_000_000,maximum_slots=9,capacity_price=1_000_000)
   cfg['strategic_allocation_policy']['max_customers']=4
   cfg['strategic_allocation_policy']['capacity_menu']={'max_quantity':6,'opportunity_delay_hours':24,'retention_bps':7000}
   result=run_world(ROOT,m,cfg,2610312254,'competitive_growth',folder/'world');verdict=audit(ROOT,m,result)
   self.assertTrue(verdict['accepted']);self.assertTrue(all('capacity_recourse' in w for w in result['joint_actions'].values()))
   rows=[i for i in result['investments'] if i['kind']=='capacity']
   print('EXPOSED_CAPACITY_RESULT',json.dumps({'profit':result['summary']['profit'],'paid':result['commercial_counters']['paid_jobs'] if 'commercial_counters' in result else None,'purchases':[(i['capacity_units'],i['cost']) for i in rows]}))
   # Receipt inspected through canonical audit; keep console output compact.
   self.assertTrue(rows,'Fixture must exercise actual native complementary purchase, not only planning')
   self.assertTrue(any(o.get('capacity_source_plan_ids') for o in result['orders'] if o['outcome']=='SETTLED'),'Exercise real useful delivery using purchased units')
   for i in rows:
    self.assertEqual(i['cost'],i['capacity_units']*cfg['capacity_price']);self.assertEqual(i['funding_receipt']['funding'],'EARNED')
   bad=copy.deepcopy(result);next(i for i in bad['investments'] if i['kind']=='capacity')['capacity_units']+=1
   with self.assertRaises(ValueError):audit(ROOT,m,bad)
   bad=copy.deepcopy(result);next(iter(bad['joint_actions'].values()))['capacity_recourse']['inputs']['retention_bps']=10000
   with self.assertRaises(ValueError):audit(ROOT,m,bad)
if __name__=='__main__':unittest.main()
