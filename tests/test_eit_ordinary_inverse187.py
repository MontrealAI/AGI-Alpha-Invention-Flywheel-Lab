"""No source acquisition in these tests; independent analytic and refusal checks."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import savemat

from research.eit_physical_control183.control import Refusal, SHAPE
from research.eit_ordinary_inverse187.compare import (
    DIFFERENCE_LINE_SHA256, EXPECTED_SCRIPT_DIFFERENCE_LINE, GAMMAS,
    difference_source_gate, fixed_ordinary_controls, load_original_J, main,
)


class OrdinaryInverse187Tests(unittest.TestCase):
    def test_frozen_matlab_colon_line_is_hash_anchored(self):
        difference_source_gate(EXPECTED_SCRIPT_DIFFERENCE_LINE)
        self.assertEqual(hashlib.sha256(EXPECTED_SCRIPT_DIFFERENCE_LINE.encode()).hexdigest(),
                         DIFFERENCE_LINE_SHA256)
        for changed in (
            EXPECTED_SCRIPT_DIFFERENCE_LINE.replace("(:)", "(:,:)", 1),
            EXPECTED_SCRIPT_DIFFERENCE_LINE.replace("m2", "m1", 1),
            EXPECTED_SCRIPT_DIFFERENCE_LINE + " ",
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(
                    Refusal, "MATLAB_DIFFERENCE_EXPRESSION_UNSUPPORTED"):
                difference_source_gate(changed)

    def test_mat5_J_single_named_variable(self):
        matrix = np.arange(6, dtype=float).reshape(3, 2)
        buf = io.BytesIO()
        savemat(buf, {"J": matrix})
        actual = load_original_J(buf.getvalue(), shape=(3, 2))
        self.assertTrue(np.array_equal(actual, matrix))
        with self.assertRaisesRegex(Refusal, "ORIGINAL_J_NONFINITE_SHAPE_OR_TYPE"):
            load_original_J(buf.getvalue(), shape=(2, 3))

    def test_missing_J_and_nonfinite_J_refused(self):
        buf = io.BytesIO()
        savemat(buf, {"X": np.ones((2, 2))})
        with self.assertRaisesRegex(Refusal, "ORIGINAL_J_VARIABLE_NOT_FOUND"):
            load_original_J(buf.getvalue(), shape=(2, 2))
        buf = io.BytesIO()
        savemat(buf, {"J": np.array([[float("nan")]])})
        with self.assertRaisesRegex(Refusal, "ORIGINAL_J_NONFINITE_SHAPE_OR_TYPE"):
            load_original_J(buf.getvalue(), shape=(1, 1))

    def test_unsupported_container_is_not_treated_as_a_source(self):
        with self.assertRaises(Refusal):
            load_original_J(b"unknown bytes", shape=(2, 2))

    def test_six_registered_arms_and_zero_control(self):
        J = np.zeros((1264, 1197), dtype=np.float64)
        J[0, 0] = 1.0
        raw_delta = np.zeros(SHAPE)
        raw_delta[0, 0] = 1.0
        observed = fixed_ordinary_controls(J, raw_delta)
        self.assertEqual([x["HDF5_raw_flatten_order_hypothesis"]
                          for x in observed["both_predeclared_order_arms"]], ["C", "F"])
        for arm in observed["both_predeclared_order_arms"]:
            self.assertEqual(arm["zero_solution_residual_l2"], 1.0)
            self.assertEqual([x["gamma"] for x in arm["all_fixed_regularizers"]], list(GAMMAS))
            for run in arm["all_fixed_regularizers"]:
                expected_x = 1 / (1 + run["lambda"])
                self.assertAlmostEqual(run["candidate_l2"], expected_x, places=7)
                self.assertAlmostEqual(run["residual_l2"], 1 - expected_x, places=7)
                self.assertFalse(run["solver_iteration_limit_reached"])
        self.assertFalse(observed["independent_original_J_row_correspondence_authenticated"])
        self.assertFalse(observed["property_truth_available"])
        self.assertIsNone(observed["commercial_collections_usd"])

    def test_orders_differ_when_input_has_asymmetric_location(self):
        J = np.zeros((1264, 1197), dtype=np.float64)
        J[1, 0] = 1.0
        raw_delta = np.zeros(SHAPE)
        raw_delta[0, 1] = 1.0  # C index 1; F index 79
        result = fixed_ordinary_controls(J, raw_delta)
        c, f = result["both_predeclared_order_arms"]
        self.assertLess(c["all_fixed_regularizers"][0]["residual_l2"],
                        f["all_fixed_regularizers"][0]["residual_l2"])
        self.assertEqual(f["all_fixed_regularizers"][0]["residual_l2"], 1.0)

    def test_invalid_inputs_refused(self):
        J = np.zeros((1264, 1197))
        delta = np.ones(SHAPE)
        with self.assertRaisesRegex(Refusal, "DEGENERATE_OR_UNBOUNDED_J"):
            fixed_ordinary_controls(J, delta)
        J[0, 0] = float("inf")
        with self.assertRaisesRegex(Refusal, "INCOMPATIBLE_J_OR_PHYSICAL_MATRIX"):
            fixed_ordinary_controls(J, delta)
        J[0, 0] = 1
        delta[0, 0] = float("nan")
        with self.assertRaisesRegex(Refusal, "INCOMPATIBLE_J_OR_PHYSICAL_MATRIX"):
            fixed_ordinary_controls(J, delta)

    def test_refuse_existing_output_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "receipt.json"
            output.write_text("retain")
            with patch("research.eit_ordinary_inverse187.compare.download_exact",
                       side_effect=AssertionError("must not download")):
                with self.assertRaisesRegex(Refusal, "OUTPUT_MUST_BE_FRESH"):
                    main(["--out", str(output)])
            self.assertEqual(output.read_text(), "retain")

    def test_no_public_archive_download_during_offline_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("research.eit_ordinary_inverse187.compare.download_exact",
                       side_effect=RuntimeError("offline")):
                with self.assertRaisesRegex(RuntimeError, "offline"):
                    main(["--out", str(Path(tmp)/"new.json")])


if __name__ == "__main__":
    unittest.main()
