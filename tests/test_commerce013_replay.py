"""Source manifest reconstruction and disjoint holdout replay checks."""
import json
from pathlib import Path
import unittest
from commerce013.replay import ROOT,restore_source,replay_seed
from commerce013.experiment import sha

class Replay013(unittest.TestCase):
    def test_original_service_manifest_is_bound_to_frozen_design(self):
        frozen=json.loads((ROOT/'campaign/commerce-013/FROZEN.json').read_text())
        m=json.loads((ROOT/'campaign/commerce-013/SERVICE_MANIFEST.json').read_text())
        self.assertEqual(sha(m),frozen['manifest_sha256'])
    def test_exact_original_manifest_has_semantically_checked_artifacts(self):
        m=json.loads((ROOT/'campaign/commerce-013/SERVICE_MANIFEST.json').read_text())
        self.assertEqual(len(m['jobs']),96)
        self.assertEqual(len(m['attempts']),3)
        self.assertTrue(all(j['accepted'] for j in m['jobs']))
    def test_replay_seed_must_be_a_frozen_confirm_seed(self):
        with self.assertRaisesRegex(ValueError,'FROZEN_CONFIRMATION_SEED'):
            replay_seed(ROOT,{},12002)
    def test_declared_protected_set_is_disjoint(self):
        from commerce013.experiment import DEV_SEEDS,CONFIRMATION_SEEDS
        self.assertFalse(set(DEV_SEEDS)&set(CONFIRMATION_SEEDS))

if __name__=='__main__':unittest.main()
