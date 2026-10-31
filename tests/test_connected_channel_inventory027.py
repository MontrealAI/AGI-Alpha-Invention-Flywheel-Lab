"""Bounded equal synthetic inventory; no inference of market size or sales."""
import copy
from pathlib import Path
import tempfile
import unittest
from adaptive_enterprise.instruments import prepare_services,load_jobs
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
            changed=copy.deepcopy(m);changed['native_engine']='prospective-v1'
            with self.assertRaises(ValueError):load_jobs(ROOT,changed)
if __name__=='__main__':unittest.main()
