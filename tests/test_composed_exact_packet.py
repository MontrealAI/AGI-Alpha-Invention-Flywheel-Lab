"""Composition wiring: current exact native finance with packet/game contracts."""
import copy,tempfile,unittest
from pathlib import Path
from adaptive_enterprise.instruments import prepare_complete_offer_services,load_jobs
from connected_enterprise.engine import fresh_account_config,run_world
from connected_enterprise.capital_lifecycle import default_policy
from connected_enterprise.verify import audit
from test_connected_complete_offer import fixture
from test_joint_game_operating import policy
ROOT=Path(__file__).resolve().parents[1]
class ExactPacketComposition(unittest.TestCase):
 def test_fresh_exact_permanent_and_prospective_packet_game(self):
  with tempfile.TemporaryDirectory(prefix='.exact-packet-',dir=ROOT) as tmp:
   folder=Path(tmp);m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2611010039,packet_jobs=8,packet_rows=12)
   for prospective in (False,True):
    terms=default_policy() if prospective else None
    if terms:terms.update(protection_hours=24,residual_microUSD=1000000,premium_microUSD=250000)
    native,registered=fresh_account_config(m,root=ROOT,prospective_policy=terms)
    cfg=fixture(registered,'menu');cfg['monetary_policy']=native['monetary_policy']
    if terms:cfg['prospective_policy']=terms
    cfg['strategic_allocation_policy']['strategic_game']=policy(cfg['strategic_allocation_policy']['risk']['scenarios'])
    load_jobs(ROOT,registered)
    r=run_world(ROOT,registered,cfg,2611010039,'competitive_growth',folder/('prospective' if prospective else 'permanent'))
    self.assertTrue(audit(ROOT,registered,r)['accepted']);self.assertTrue(r['orders'])
    self.assertTrue(any(o['offer']['service_id']=='receivables_packet' for o in r['orders']))
    self.assertEqual(registered['native_engine'],'exact-prospective-v2' if prospective else 'exact-permanent-v2')
    self.assertTrue(all(o['capacity_units']==3 for o in r['orders'] if o['offer']['service_id']=='receivables_packet'))
    bad=copy.deepcopy(registered);bad['native_engine']='prospective-v1' if prospective else 'legacy-permanent-v1'
    with self.assertRaisesRegex(ValueError,'FRESH_POLICY_NATIVE_ENGINE_REGISTRATION_MISMATCH'):
     run_world(ROOT,bad,cfg,2611010039,'competitive_growth',folder/('bad-prospective' if prospective else 'bad-permanent'))
if __name__=='__main__':unittest.main()
