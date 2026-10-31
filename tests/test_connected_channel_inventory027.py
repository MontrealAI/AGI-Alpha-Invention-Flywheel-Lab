"""Bounded equal synthetic inventory; no inference of market size or sales."""
import copy
from pathlib import Path
import tempfile
import unittest
from adaptive_enterprise.instruments import prepare_services,load_jobs
from connected_enterprise.engine import default_config,run_world
from connected_enterprise.capital_lifecycle import default_policy
ROOT=Path(__file__).resolve().parents[1]
class ChannelInventory(unittest.TestCase):
    def test_generation_bounds_before_effects(self):
        for n in (0,31,257,True):
            with self.assertRaises(ValueError):prepare_services(ROOT,'must-not-exist-inventory',jobs_per_service=n)
        self.assertFalse((ROOT/'must-not-exist-inventory').exists())
    def test_equal_extended_inventory_without_new_financial_engine(self):
        with tempfile.TemporaryDirectory(prefix='.inventory025-',dir=ROOT) as folder:
            relative=Path(folder).relative_to(ROOT)/'jobs'
            m=prepare_services(ROOT,str(relative),cohort_seed=2610311640,jobs_per_service=96)
            self.assertEqual(len(m['jobs']),296);self.assertEqual(len({j['id'] for j in m['jobs']}),296)
            self.assertEqual(m['cohort_provenance']['jobs_per_service'],96)
            self.assertEqual(len(load_jobs(ROOT,m)),296)
            self.assertNotIn('native_engine',m)  # Inventory expansion never opts into finance.
            changed=copy.deepcopy(m);changed['native_engine']='prospective-v1'
            self.assertEqual(len(load_jobs(ROOT,changed)),296)
            unknown=copy.deepcopy(m);unknown['native_engine']='unknown-engine'
            with self.assertRaisesRegex(ValueError,'DECLARED_NATIVE_ENGINE_REQUIRED'):load_jobs(ROOT,unknown)
            cfg=default_config()
            for manifest,config in [(changed,cfg),(m,{**cfg,'prospective_policy':default_policy()})]:
                output=Path(folder)/'rejected-account'
                with self.assertRaisesRegex(ValueError,'FRESH_POLICY_NATIVE_ENGINE_REGISTRATION_MISMATCH'):
                    run_world(ROOT,manifest,config,1,'competitive_growth',output)
                self.assertFalse((output/'account.sqlite').exists())
                self.assertFalse((output/'STATE.json').exists())
if __name__=='__main__':unittest.main()
