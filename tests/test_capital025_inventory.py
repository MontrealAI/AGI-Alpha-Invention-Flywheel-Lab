"""Bounded equal synthetic inventory; no inference of market size or sales."""
import copy
from pathlib import Path
import tempfile
import unittest
from adaptive_enterprise.instruments import prepare_services,load_jobs
ROOT=Path(__file__).resolve().parents[1]
class CapitalInventory(unittest.TestCase):
    def test_generation_bounds_before_effects(self):
        with tempfile.TemporaryDirectory(prefix='.invalid-inventory-',dir=ROOT) as folder:
            target=Path(folder)/'jobs'
            relative=str(target.relative_to(ROOT))
            for n in (0,31,True):
                with self.assertRaises(ValueError):prepare_services(ROOT,relative,jobs_per_service=n)
                self.assertFalse(target.exists())
    def test_equal_extended_inventory_and_explicit_engine(self):
        with tempfile.TemporaryDirectory(prefix='.inventory025-',dir=ROOT) as folder:
            relative=Path(folder).relative_to(ROOT)/'jobs'
            m=prepare_services(ROOT,str(relative),cohort_seed=2610311640,jobs_per_service=257)
            self.assertEqual(len(m['jobs']),779);self.assertEqual(len({j['id'] for j in m['jobs']}),779)
            self.assertEqual(m['cohort_provenance']['jobs_per_service'],257)
            for name in ('legacy-permanent-v1','prospective-v1'):
                changed=copy.deepcopy(m);changed['native_engine']=name
                self.assertEqual(len(load_jobs(ROOT,changed)),779)
            changed=copy.deepcopy(m);changed['native_engine']='invented'
            with self.assertRaises(ValueError):load_jobs(ROOT,changed)
if __name__=='__main__':unittest.main()
