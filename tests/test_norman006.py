import copy
import hashlib
from pathlib import Path
import unittest
import numpy as np
from experiments.norman006 import model

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = hashlib.sha256((ROOT / 'experiments/norman006/model.py').read_bytes()).hexdigest()


def data():
    rng = np.random.default_rng(17)
    a, b = rng.normal(size=(12, 5)), rng.normal(size=(12, 5))
    control = np.ones_like(a)
    return {'A': a + control, 'B': b + control, 'ctrl': control, 'AB': a + b + control + .2 * a * b,
            'pairs': np.array(['unit-%d' % i for i in range(12)]), 'genes': np.array(['g%d' % i for i in range(5)]),
            'fit_indices': np.arange(8), 'calibration_indices': np.arange(8, 12)}


def configuration():
    return {'language': model.LANGUAGE, 'expressions': ['a0', ['mul', 'a1', 'b1']], 'ridge': 1, 'symmetric': False, 'constraints': []}


class NormanModelTests(unittest.TestCase):
    def test_actual_generated_basis_is_confined_and_predictions_have_no_outcome_access(self):
        train = data()
        artifact = model.fit(train, configuration(), SOURCE_SHA)
        self.assertEqual(artifact['construction']['basis_receipt']['worker']['confinement'], 'linux-seccomp-default-deny')
        inputs = model.subset(train, np.arange(12), False)
        prediction = model.predict(artifact, inputs)['prediction']
        self.assertEqual(prediction.shape, (12, 5))
        self.assertTrue(np.isfinite(prediction).all())
        inputs['AB'] = train['AB']
        with self.assertRaisesRegex(ValueError, 'TRAINING_OR_PREDICTION_SCHEMA'):
            model.predict(artifact, inputs)

    def test_reproduced_constraint_changes_representation_generically(self):
        train = data()
        original = configuration()
        constraint = {'kind': 'exchange_symmetry', 'status': 'established', 'evidence_sha256': 'a' * 64}
        repaired = model.repair(original, [constraint])
        self.assertFalse(original['symmetric'])
        self.assertTrue(repaired['configuration']['symmetric'])
        artifact = model.fit(train, repaired['configuration'], SOURCE_SHA)
        inputs = model.subset(train, np.arange(12), False)
        first = model.predict(artifact, inputs)['prediction']
        inputs['A'], inputs['B'] = inputs['B'], inputs['A']
        second = model.predict(artifact, inputs)['prediction']
        self.assertLessEqual(float(np.max(np.abs(first - second))), 1e-10)
        bad = copy.deepcopy(constraint)
        bad['status'] = 'proposed'
        with self.assertRaisesRegex(ValueError, 'CONSTRAINT_SCHEMA'):
            model.repair(original, [bad])

    def test_invalid_source_artifact_and_gene_order_refuse(self):
        train = data()
        with self.assertRaisesRegex(ValueError, 'SOURCE_IDENTITY_MISMATCH'):
            model.fit(train, configuration(), '0' * 64)
        artifact = model.fit(train, configuration(), SOURCE_SHA)
        inputs = model.subset(train, np.arange(12), False)
        changed = copy.deepcopy(artifact)
        changed['coefficient'][0][0] += 1
        with self.assertRaisesRegex(ValueError, 'ARTIFACT_IDENTITY'):
            model.predict(changed, inputs)
        inputs['genes'] = inputs['genes'][::-1]
        with self.assertRaisesRegex(ValueError, 'GENE_AXIS_IDENTITY'):
            model.predict(artifact, inputs)

    def test_search_keeps_additive_stopping_and_original_failed_candidates(self):
        train = data()
        proposals = model.generate_configurations(9, 4)
        self.assertEqual(proposals['configurations'][0]['expressions'], [])
        invalid = configuration()
        invalid['expressions'] = [['eval', 'a0', 'b0']]
        result = model.search(train, proposals['configurations'] + [invalid], SOURCE_SHA)
        self.assertEqual(len(result['records']), 5)
        self.assertEqual(result['records'][-1]['status'], 'failed')
        self.assertEqual(result['status'], 'nominated-development-only')
        train['calibration_indices'] = train['fit_indices']
        with self.assertRaisesRegex(ValueError, 'DEVELOPMENT_SPLIT'):
            model.search(train, proposals['configurations'], SOURCE_SHA)


if __name__ == '__main__':
    unittest.main()
