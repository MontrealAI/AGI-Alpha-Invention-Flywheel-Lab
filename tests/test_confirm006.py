import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from verification.cycle006_confirm import axes, compare, frozen_sources, npz, ranking


class ConfirmationBoundaryTests(unittest.TestCase):
    def test_useful_threshold_and_zero_control_failure(self):
        passed = compare(np.full(12, .9), np.ones(12), ['A+B'] * 12)
        self.assertTrue(passed['practical_threshold_met'])
        failed = compare(np.ones(12), np.zeros(12), ['A+B'] * 12)
        self.assertFalse(failed['practical_threshold_met'])
        self.assertEqual(failed['zero_control_nonzero_candidate_cases'], 12)
        self.assertEqual(failed['per_pair_relative_rmse_gain'], [None] * 12)

    def test_source_identity_failure_precedes_application_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'SIDE_EFFECT'
            (root / 'untrusted.py').write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
            freeze = root / 'freeze.json'
            freeze.write_text(json.dumps({'sources': {'untrusted.py': '0' * 64}}))
            digest = hashlib.sha256(freeze.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'CONFIRMATION_SOURCE_IDENTITY_MISMATCH'):
                frozen_sources(root, freeze, digest)
            self.assertFalse(marker.exists())

    def test_undeclared_truth_field_and_changed_axes_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'payload.npz'
            np.savez_compressed(path, A=np.zeros((1, 1000)), AB=np.zeros((1, 1000)))
            with self.assertRaisesRegex(ValueError, 'NPZ_KEY_SCOPE'):
                npz(path, ['A'])
        features = {'A': np.zeros((1, 2)), 'pairs': np.asarray(['A+B']), 'genes': np.asarray(['G1', 'G2'])}
        output = {'prediction': np.zeros((1, 2)), 'pairs': np.asarray(['A+B']), 'genes': np.asarray(['G2', 'G1'])}
        with self.assertRaisesRegex(ValueError, 'PREDICTION_AXIS_IDENTITY_MISMATCH'):
            axes(output, features)

    def test_observed_zero_deviation_is_not_a_biological_interaction_label(self):
        zeros = np.zeros((1, 1000))
        features = {'A': zeros, 'B': zeros, 'ctrl': zeros, 'pairs': ['A+B'], 'genes': ['G%d' % i for i in range(1000)]}
        result = ranking(zeros, zeros, features, 'norman')
        self.assertEqual(result['defined_pairs'], 0)
        self.assertIsNone(result['mean_ndcg'])


if __name__ == '__main__':
    unittest.main()
