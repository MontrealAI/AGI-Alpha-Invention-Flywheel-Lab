"""Frozen gauge-invariance and physical acceptance controls for FRAMEFIX225."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWNER = ROOT / "research" / "frontier_qec_transfer"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(OWNER))
sys.path.insert(0, str(OWNER / "fixtures"))

from framefix import (
    pinned_blob_sha1, syndrome_anchor, fixed_ic_bras,
    build_canonical, apply_syndrome_gauge, fixed_unitary)
from noise_experiment import NoiseExperiment
from public_fixtures import pollatsek_ruskai_7, shor_9
from second_public_fixtures import pauli_hypotheses

PINS = {
    "recovery.py": "6c8092bf132f9f218ca4c1b074a6c9b93d9b2b69",
    "noise_experiment.py": "434278fa64d4d7e90cb6a3117f5afdfe8e5bc40b",
    "fixtures/public_fixtures.py": "75be45ee4581eba1991ac4e8b2e5690084796f45",
    "fixtures/second_public_fixtures.py": "866b170844f751731d66cc4f76bbdb427f8d53cc",
}
SEEDS = (1, 7, 257)
FIXTURES = (pollatsek_ruskai_7, shor_9)


class FrozenSource(unittest.TestCase):
    def test_actual_pinned_git_blobs(self):
        for relative, expected in PINS.items():
            with self.subTest(path=relative):
                self.assertEqual(pinned_blob_sha1(OWNER / relative), expected)

    def test_bad_shapes_and_invalid_gauge_rejected(self):
        with self.assertRaises(ValueError):
            syndrome_anchor(np.zeros((2, 2, 5), complex))
        with self.assertRaises(ValueError):
            fixed_ic_bras(0)
        with self.assertRaises(ValueError):
            fixed_ic_bras(129)
        with self.assertRaises(ValueError):
            build_canonical(np.ones((2, 2, 5)), np.zeros((2, 3, 3)))
        with self.assertRaises(ValueError):
            apply_syndrome_gauge(
                np.zeros((2, 2, 5)), np.zeros((1, 2, 2)), 2 * np.eye(2))


class FrozenFixtureComparisons(unittest.TestCase):
    def test_unchanged_owner_and_all_609_pairs(self):
        count = 0
        for factory, expected_h, expected_rank in zip(FIXTURES, (22, 28), (22, 22)):
            n, code = factory()
            exp = NoiseExperiment(n, code, pauli_hypotheses(n))
            self.assertEqual(exp.H, expected_h)
            self.assertEqual(exp.rank, expected_rank)
            f = build_canonical(exp._recovery, exp._syndrome_states)
            self.assertEqual(len(f.pair_distances()), expected_h * (expected_h - 1) // 2)
            self.assertEqual(f.response.shape, (exp.syndrome_rank**2, exp.H))
            self.assertLess(f.frame_residual, 2e-8)
            self.assertLess(f.physical_completeness_residual, 2e-8)
            self.assertLess(f.max_column_error, 2e-8)
            canonical_rank = np.linalg.matrix_rank(
                f.response, tol=32*np.finfo(float).eps*
                max(f.response.shape)*np.linalg.svd(f.response, compute_uv=False)[0])
            self.assertEqual(canonical_rank, expected_rank)
            count += len(f.pair_distances())
        self.assertEqual(count, 609)

    def test_fixed_three_complex_gauges_preserve_physical_measurement(self):
        original_can_vary = []
        for factory in FIXTURES:
            n, code = factory()
            exp = NoiseExperiment(n, code, pauli_hypotheses(n))
            baseline = build_canonical(exp._recovery, exp._syndrome_states)
            original = exp.response_matrix()
            for seed in SEEDS:
                with self.subTest(factory=factory.__name__, seed=seed):
                    Q = fixed_unitary(exp.syndrome_rank, seed)
                    rotated_R, rotated_S = apply_syndrome_gauge(
                        exp._recovery, exp._syndrome_states, Q)
                    rotated = build_canonical(rotated_R, rotated_S)
                    self.assertLess(float(np.max(np.abs(
                        rotated.response - baseline.response))), 2e-8)
                    self.assertLess(float(np.max(np.abs(
                        rotated.physical_operators -
                        baseline.physical_operators))), 2e-8)
                    tv0 = [v for _, v in baseline.pair_distances()]
                    tv1 = [v for _, v in rotated.pair_distances()]
                    self.assertEqual(len(tv0), len(tv1))
                    self.assertLess(max(abs(a-b) for a,b in zip(tv0,tv1)), 2e-8)
                    # Same original source-frame rows on changed syndrome gauge
                    # define a different PHYSICAL POVM. This control proves why
                    # source hashing alone cannot qualify that readout.
                    old_gauge_response = np.einsum(
                        "oi,hij,oj->oh",
                        exp._bras, rotated_S, exp._bras.conj(),
                        optimize=True).real
                    original_can_vary.append(
                        float(np.max(np.abs(original-old_gauge_response))))
        self.assertGreater(max(original_can_vary), 1e-4)

    def test_retained_logical_operation_and_erasure(self):
        n, code = pollatsek_ruskai_7()
        exp = NoiseExperiment(n, code, pauli_hypotheses(n))
        fixed = build_canonical(exp._recovery, exp._syndrome_states)
        # The physical effect of the complete outcome family is conserved,
        # including its explicit noncorrectable-space erasure complement.
        P = fixed.physical_operators.reshape(-1, exp.dimension)
        R = exp._recovery.reshape(-1, exp.dimension)
        self.assertLess(np.max(np.abs(
            P.conj().T @ P - R.conj().T @ R)), 2e-8)
        self.assertGreater(float(np.linalg.norm(
            np.eye(exp.dimension) - R.conj().T @ R)), 1e-5)

    def test_identity_consistency(self):
        for rank in (1,2,4,22):
            bras = fixed_ic_bras(rank)
            self.assertEqual(bras.shape, (rank*rank, rank))
            self.assertLess(np.max(np.abs(bras.conj().T @ bras-np.eye(rank))), 2e-8)


if __name__ == "__main__":
    unittest.main()
