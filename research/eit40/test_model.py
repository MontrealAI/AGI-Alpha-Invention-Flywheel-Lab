"""Adversarial unit tests of the frozen EIT40 instrument; synthetic data only."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np
from scipy import linalg

from research.measurement_compiler.core import geometry
from research.eit40.model import compile_plan, development_gate, error
from research.eit40.run import run_confirm


def fixture():
    rng = np.random.default_rng(64040)
    n, patterns = 12, 24
    # Five independent physically charge-balanced current directions.
    A = np.zeros((n, 5))
    for i in range(5):
        A[i, i] = 1.0
        A[-1, i] = -1.0
    I = A @ rng.normal(size=(5, patterns))
    M = np.zeros((n, n-1))
    for j in range(n - 1):
        M[j, j] = 1.0
        M[-1, j] = -1.0
    _, _, C, _ = geometry(I, M)
    _, _, right = linalg.svd(C, full_matrices=True)
    known = right[:5]
    extra = right[5:9]
    def specimen(scale):
        return (rng.normal(size=(n-1,5)) @ known +
                scale * rng.normal(size=(n-1,4)) @ extra)
    U0 = specimen(0.8)
    calibrations = [specimen(0.8) for _ in range(4)]
    target = specimen(0.8)
    unknown = specimen(0.8) + 9.0 * np.outer(rng.normal(size=(n-1,)),right[10])
    return I, M, U0, calibrations, target, unknown


class EIT40Tests(unittest.TestCase):
    def setUp(self):
        self.I, self.M, self.ref, self.cal, self.target, self.unknown = fixture()
        self.plan = compile_plan(self.I, self.M, self.ref, self.cal, count=12)

    def test_measured_columns_are_preserved_exactly(self):
        acquired = self.target[:, self.plan.selected].copy()
        p = self.plan.predict(self.I, self.M, self.ref, self.cal, acquired)
        np.testing.assert_array_equal(p[:, self.plan.selected], acquired)
        self.assertLess(error(p, self.target), 1e-9)

    def test_unknown_untrained_response_is_not_silently_certified(self):
        p = self.plan.predict(self.I, self.M, self.ref, self.cal,
                              self.unknown[:, self.plan.selected])
        self.assertGreater(error(p, self.unknown), 0.01)

    def test_changed_reference_refuses(self):
        other = self.ref.copy()
        other[0, 0] += 1e-5
        with self.assertRaisesRegex(ValueError, "CALIBRATION_SOURCE_CHANGED"):
            self.plan.predict(self.I, self.M, other, self.cal,
                              self.target[:, self.plan.selected])

    def test_changed_calibration_refuses(self):
        c = [v.copy() for v in self.cal]
        c[2][0, 0] += 1e-5
        with self.assertRaisesRegex(ValueError, "CALIBRATION_SOURCE_CHANGED"):
            self.plan.predict(self.I, self.M, self.ref, c,
                              self.target[:, self.plan.selected])

    def test_changed_geometry_refuses(self):
        M = self.M.copy()
        M[0, 0] += 0.25
        M[-1, 0] -= 0.25
        with self.assertRaisesRegex(ValueError, "GEOMETRY_CHANGED"):
            self.plan.predict(self.I, M, self.ref, self.cal,
                              self.target[:, self.plan.selected])

    def test_bool_count_refuses(self):
        with self.assertRaisesRegex(ValueError, "INVALID_ACQUISITION_COUNT"):
            compile_plan(self.I, self.M, self.ref, self.cal, count=True)

    def test_nonfinite_input_refuses(self):
        with self.assertRaises(ValueError):
            compile_plan(self.I, self.M, self.ref, self.cal + [self.ref])
        changed = [v.copy() for v in self.cal]
        changed[1][0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "INVALID_CALIBRATION_DIMENSIONS"):
            compile_plan(self.I, self.M, self.ref, changed, count=12)

    def test_zero_residual_refuses(self):
        _, _, C, _ = geometry(self.I, self.M)
        zero = np.zeros_like(self.ref)
        # Entirely inside the identified current row space.
        zero[:] = np.ones((zero.shape[0], C.shape[0])) @ C
        with self.assertRaisesRegex(ValueError, "UNIDENTIFIABLE_REFERENCE_RESIDUAL"):
            compile_plan(self.I, self.M, zero, [zero]*4, count=12)

    def test_development_denominator_and_stop(self):
        self.assertTrue(development_gate([0.04]*4))
        self.assertFalse(development_gate([0.04, 0.04, 0.05001, 0.04]))
        with self.assertRaisesRegex(ValueError, "INVALID_FOLD_DENOMINATOR"):
            development_gate([0.0, 0.0, 0.0])
        with TemporaryDirectory() as td:
            frozen = Path(td) / "FAILED.json"
            frozen.write_text(json.dumps({
                "schema": "agi-alpha/eit40/v1", "stage": "DEVELOPMENT",
                "all_four_within_five_percent": False,
                "decision": "STOP_DEVELOPMENT_FAILED",
            }))
            with self.assertRaisesRegex(ValueError, "DEVELOPMENT_FAILED_NO_EVALUATION_PERMITTED"):
                # No archive present: failure must occur before any data fetch.
                run_confirm(Path(td) / "no-data", Path(td) / "out", frozen)

    def test_conventional_svd_has_equal_source_access(self):
        p = compile_plan(self.I, self.M, self.ref, self.cal,
                         mode="conventional_pca", count=12)
        self.assertEqual(p.calibration_specimens, 4)
        self.assertEqual(len(p.selected), 12)
        self.assertEqual(p.basis.shape[0], self.plan.basis.shape[0])

    def test_in_place_operator_corruption_must_fail_closed(self):
        # Compile once, then mutate only the supposedly frozen derived operator.
        acquired = self.target[:, self.plan.selected].copy()
        self.plan.operator[0, 0] += 10.0
        with self.assertRaisesRegex(ValueError, "OPERATOR_CHANGED"):
            self.plan.predict(self.I, self.M, self.ref, self.cal, acquired)

    def test_selected_column_substitution_must_fail_closed(self):
        # A frozen dataclass can still be reconstructed or changed by hostile
        # deserialization; acquired values cannot be silently relabeled.
        acquired = self.target[:, self.plan.selected].copy()
        object.__setattr__(self.plan, "selected", tuple(reversed(self.plan.selected)))
        with self.assertRaisesRegex(ValueError, "ACQUISITION_PLAN_CHANGED"):
            self.plan.predict(self.I, self.M, self.ref, self.cal, acquired)

    def test_rejected_malformed_acquired(self):
        with self.assertRaisesRegex(ValueError, "INVALID_ACQUIRED_OBSERVATIONS"):
            self.plan.predict(self.I, self.M, self.ref, self.cal, np.zeros((1, 12)))
        broken = self.target[:, self.plan.selected].copy()
        broken[0, 0] = np.inf
        with self.assertRaisesRegex(ValueError, "INVALID_ACQUIRED_OBSERVATIONS"):
            self.plan.predict(self.I, self.M, self.ref, self.cal, broken)


if __name__ == "__main__":
    unittest.main()
