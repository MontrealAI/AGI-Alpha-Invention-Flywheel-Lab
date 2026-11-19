"""EIT189 fixed original-covariance inverse: offline analytic and adversarial tests."""
import io
import math
import unittest

import h5py
import numpy as np
from scipy.io import savemat
from scipy.linalg import cho_solve

from research.eit_physical_control183.control import Refusal
from research.eit_author_inverse189.reconstruct import (
    EXPECTED_NODES, NOISE_STD, all_folds, author_posterior,
    conditional_prediction_direct, conditional_prediction_from_precision,
    fixed_original_prior, original_inverse_nodes,
)


def fixture():
    nodes = np.array([[0., 0.], [3., 1.], [1., 4.]])
    j = np.array([
        [1, 0, .5], [0, 1, .3], [1, 1, .1],
        [0, 1, .8], [1, 0, .4], [1, -.5, 1.],
    ], dtype=np.float64) * .01
    base = np.arange(1., 7.).reshape(3, 2) * .01
    changed = base + np.array([
        [.7, -.3], [.2, .4], [-.1, .8],
    ]) * .001
    return j, nodes, base, changed


class OriginalAuthorsFullCovariance189Tests(unittest.TestCase):
    def test_literal_original_mesh_prior_is_symmetric_spd(self):
        _, nodes, _, _ = fixture()
        p = fixed_original_prior(nodes)
        self.assertEqual(p.shape, (3, 3))
        self.assertTrue(np.allclose(p, p.T))
        self.assertTrue(np.all(np.linalg.eigvalsh(p) > 0))
        self.assertAlmostEqual(p[0, 0], 6.25 * 1.01, places=12)

    def test_original_normal_equations_equal_dual_covariance(self):
        j, nodes, _, changed = fixture()
        prior = fixed_original_prior(nodes)
        H, fact, _ = author_posterior(j, prior)
        dy = changed.ravel(order="C")
        dual = prior @ j.T @ cho_solve(fact, dy)
        original = np.linalg.solve(
            j.T @ j / NOISE_STD**2 + np.linalg.inv(prior),
            j.T @ dy / NOISE_STD**2,
        )
        self.assertTrue(np.allclose(dual, original, rtol=1e-7, atol=1e-10))
        self.assertTrue(np.allclose(H, H.T, rtol=1e-10, atol=1e-12))

    def test_precision_conditional_matches_independent_training_only(self):
        j, nodes, _, changed = fixture()
        H, _, P = author_posterior(j, fixed_original_prior(nodes))
        y = changed.ravel(order="C")
        for idx in ([0, 2, 4], [1, 3, 5]):
            self.assertTrue(np.allclose(
                conditional_prediction_from_precision(P, y, idx),
                conditional_prediction_direct(H, y, idx),
                rtol=1e-7, atol=1e-9,
            ))

    def test_heldout_target_perturbation_does_not_change_prediction(self):
        j, nodes, _, changed = fixture()
        _, _, P = author_posterior(j, fixed_original_prior(nodes))
        y = changed.ravel(order="C")
        idx = np.array([0, 2, 4])
        prediction = conditional_prediction_from_precision(P, y, idx)
        altered = y.copy()
        altered[idx] += np.array([4., -9., 13.])
        prediction_changed = conditional_prediction_from_precision(P, altered, idx)
        self.assertTrue(np.allclose(prediction, prediction_changed,
                                    rtol=1e-7, atol=1e-8))
        self.assertFalse(np.array_equal(y[idx], altered[idx]))

    def test_finite_complete_column_controls_both_orientations(self):
        j, nodes, a, b = fixture()
        receipt = all_folds(j, nodes, a, b)
        self.assertEqual(receipt["heldout_column_count"], 2)
        self.assertEqual([x["raw_hdf5_vector_order_hypothesis"]
                          for x in receipt["all_methods"]], ["C", "F"])
        for arm in receipt["all_methods"]:
            self.assertEqual(arm["distinct_heldout_count"], 6)
            self.assertEqual(len(arm["all_column_folds"]), 2)
            self.assertAlmostEqual(
                arm["pooled_heldout_l2"]**2,
                sum(f["heldout_sse"] for f in arm["all_column_folds"]), places=8)
            self.assertTrue(math.isfinite(arm["pooled_heldout_rms"]))
        self.assertFalse(receipt["physical_property_truth_verified"])
        self.assertIsNone(receipt["revenue_collected_usd"])

    def test_mat5_inverse_mesh_has_exact_1197_nodes(self):
        points = np.column_stack(
            (np.linspace(0, 5, EXPECTED_NODES),
             np.linspace(4, 6, EXPECTED_NODES)))
        b = io.BytesIO()
        savemat(b, {"mesh": {"nodes": points}})
        actual = original_inverse_nodes(b.getvalue())
        self.assertTrue(np.array_equal(points, actual))

    def test_matlab_hdf5_reversed_axes_are_explicitly_recovered(self):
        points = np.column_stack(
            (np.linspace(0, 5, EXPECTED_NODES),
             np.linspace(4, 6, EXPECTED_NODES)))
        buffer = io.BytesIO()
        with h5py.File(buffer, "w") as h:
            mesh = h.create_group("mesh")
            mesh.create_dataset("nodes", data=points.T)
        actual = original_inverse_nodes(buffer.getvalue())
        self.assertTrue(np.array_equal(points, actual))

    def test_missing_mesh_nodes_and_bad_orientation_refused(self):
        buffer = io.BytesIO()
        with h5py.File(buffer, "w") as h:
            mesh = h.create_group("mesh")
            mesh.create_dataset("nodes", data=np.ones((2, 25)))
        with self.assertRaisesRegex(Refusal, "NODE_COUNT"):
            original_inverse_nodes(buffer.getvalue())
        buffer = io.BytesIO()
        with h5py.File(buffer, "w") as h:
            h.create_group("mesh")
        with self.assertRaisesRegex(Refusal, "NODES_MISSING"):
            original_inverse_nodes(buffer.getvalue())

    def test_unsupported_nonfinite_and_degenerate_data_fail_closed(self):
        j, nodes, a, b = fixture()
        with self.assertRaisesRegex(Refusal, "MESH_NODES_INCOMPATIBLE"):
            fixed_original_prior(np.array([[np.nan, 0.], [1., 2.]]))
        with self.assertRaisesRegex(Refusal, "J_OR_PRIOR_INVALID"):
            author_posterior(j.astype(complex), fixed_original_prior(nodes))
        with self.assertRaisesRegex(Refusal, "ARRAY_SHAPE_OR_FINITE_INVALID"):
            all_folds(j, nodes, a, np.full_like(b, np.nan))

    def test_bad_holdout_index_and_singular_precision_refused(self):
        j, nodes, _, changed = fixture()
        _, _, P = author_posterior(j, fixed_original_prior(nodes))
        y = changed.ravel(order="C")
        for idx in ([0, 0], [-1], list(range(6))):
            with self.assertRaisesRegex(Refusal, "INVALID_HELDOUT"):
                conditional_prediction_from_precision(P, y, idx)
        with self.assertRaisesRegex(Refusal, "HELDOUT_PRECISION_SINGULAR"):
            conditional_prediction_from_precision(np.zeros_like(P), y, [0])


if __name__ == "__main__":
    unittest.main()
