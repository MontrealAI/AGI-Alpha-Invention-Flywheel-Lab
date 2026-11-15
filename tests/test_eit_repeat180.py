"""EIT180 frozen synthetic controls; real-source result is separate and never replaced."""
from io import BytesIO
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import h5py
import numpy as np
from research import eit_chest177 as p
from research import eit_real179 as earlier
from research import eit_repeat180 as m


def fixture(n=12, cols=3):
    # Each column has nonconstant even rows, so independent affine fits identify.
    x = np.arange(n*cols, dtype=float).reshape(n, cols)/5. + 1.
    c = np.ones_like(x)
    return c, x


def test_archive(x, y, currents=None, include_sidecars=False):
    if currents is None:
        currents = np.ones_like(x)
    def mat(v):
        memory = BytesIO()
        with h5py.File(memory, "w") as f:
            f.create_dataset("currents_matrix", data=currents)
            f.create_dataset("voltages_matrix", data=v)
            f.create_dataset("units_info", data=np.array([1]))
        return memory.getvalue()
    memory = BytesIO()
    with ZipFile(memory, "w") as z:
        z.writestr("AgarChestPhantom/Data/a_1.mat", mat(x))
        z.writestr("AgarChestPhantom/Data/a_2.mat", mat(y))
        if include_sidecars:
            z.writestr("__MACOSX/AgarChestPhantom/Data/._0_1.mat", b"Mac OS X")
            z.writestr("__MACOSX/AgarChestPhantom/Data/._0_2.mat", b"Mac OS X")
    return memory.getvalue()


class EIT180RegisteredTests(unittest.TestCase):
    def test_01_identity_ties_ordinary_and_rejects_novelty(self):
        c, x = fixture()
        z = m.analyze_arrays(c, c, x, x)
        self.assertAlmostEqual(z["models"]["O0_identity"]["holdout"]["rms"], 0)
        self.assertEqual(z["decision"], "REJECT_INCREMENTAL_STRUCTURE")

    def test_02_global_gain_is_a_strong_ordinary_control(self):
        c, x = fixture()
        z = m.analyze_arrays(c, c, x, 1.7*x)
        self.assertAlmostEqual(z["models"]["O1_global_gain"]["holdout"]["rms"], 0, places=12)
        self.assertEqual(z["decision"], "REJECT_INCREMENTAL_STRUCTURE")

    def test_03_global_offset_affine_ordinary_can_win(self):
        c, x = fixture()
        z = m.analyze_arrays(c, c, x, 1.3*x + 7.)
        self.assertAlmostEqual(z["models"]["O2_global_affine"]["holdout"]["rms"], 0, places=12)
        self.assertEqual(z["decision"], "REJECT_INCREMENTAL_STRUCTURE")

    def test_04_channel_specific_affine_pattern_is_conditionally_detectable(self):
        c, x = fixture()
        y = x*np.array([0.5, 1.0, 1.7])[None,:] + np.array([3., -2., 5.])[None,:]
        z = m.analyze_arrays(c, c, x, y)
        self.assertEqual(z["ordinary_best_name"] in
                         ("O0_identity", "O1_global_gain", "O2_global_affine"), True)
        self.assertLess(z["models"]["C3_per_column_affine"]["holdout"]["rms"], 1.e-12)
        self.assertEqual(z["decision"], "CONDITIONAL_REPEAT_STRUCTURE_ONLY")
        self.assertEqual(z["models"]["C3_per_column_affine"]["trained_parameters"], 6)

    def test_05_train_only_does_not_use_heldout_target(self):
        c, x = fixture()
        y = 2*x + 1.
        z1 = m.analyze_arrays(c, c, x, y)
        corrupted = y.copy()
        corrupted[1::2] += 9.
        z2 = m.analyze_arrays(c, c, x, corrupted)
        self.assertEqual(z1["per_column_affine_parameters"],
                         z2["per_column_affine_parameters"])
        self.assertNotEqual(z1["models"]["C3_per_column_affine"]["holdout"]["rms"],
                            z2["models"]["C3_per_column_affine"]["holdout"]["rms"])

    def test_06_overfitting_even_rows_can_make_candidate_worse(self):
        c, x = fixture()
        y = x.copy()
        y[::2] = 3*x[::2]
        z = m.analyze_arrays(c, c, x, y)
        self.assertEqual(z["decision"], "REJECT_INCREMENTAL_STRUCTURE")
        self.assertGreater(z["models"]["C3_per_column_affine"]["holdout"]["rms"],
                           z["models"]["O0_identity"]["holdout"]["rms"])

    def test_07_constant_training_column_must_fail_closed(self):
        c, x = fixture()
        x[::2, 0] = 0.3
        with self.assertRaisesRegex(p.Refused, "RANK_DEFICIENT"):
            m.analyze_arrays(c, c, x, x+1.)

    def test_08_different_current_patterns_refuse_same_drive(self):
        c, x = fixture()
        other = c.copy()
        other[1, 0] += 0.0001
        with self.assertRaisesRegex(p.Refused, "CURRENT_PATTERNS_DIFFER"):
            m.analyze_arrays(c, other, x, x)

    def test_09_nonfinite_input_is_rejected(self):
        c, x = fixture()
        y = x.copy()
        y[2, 0] = float("nan")
        with self.assertRaisesRegex(p.Refused, "NONFINITE"):
            m.analyze_arrays(c, c, x, y)

    def test_10_dimension_mismatch_refuses_not_transposed(self):
        c, x = fixture()
        with self.assertRaisesRegex(p.Refused, "REPEAT_DIMENSIONS_CHANGED"):
            m.analyze_arrays(c, c, x, x.T)

    def test_11_row_bound_and_zero_variance_refuse(self):
        c, x = fixture(4)
        with self.assertRaisesRegex(p.Refused, "GEOMETRY"):
            m.analyze_arrays(c, c, x, x)
        with self.assertRaisesRegex(p.Refused, "RANK_DEFICIENT"):
            m._fit(np.array([1.,1.,1.]), np.array([2.,3.,4.]), intercept=True)

    def test_12_exact_parity_split_counts_holdout(self):
        c, x = fixture(13)
        z = m.analyze_arrays(c, c, x, 0.8*x+1.)
        self.assertEqual(z["development_rows"], [0,2,4,6,8,10,12])
        self.assertEqual(z["holdout_rows"], [1,3,5,7,9,11])
        self.assertTrue(z["current_matrix_exact_match"])

    def test_13_publisher_size_md5_sha_and_original_failure_are_bound(self):
        c, x = fixture()
        raw = test_archive(x, x+1., c, include_sidecars=True)
        with patch.object(p, "SIZE", len(raw)), patch.object(p, "MD5", hashlib.md5(raw).hexdigest()), patch.object(earlier, "PINNED_SHA256", hashlib.sha256(raw).hexdigest()):
            result = m.analyze_source(raw)
            self.assertEqual(result["original_eit177_source_run"], "FAILED")
            self.assertEqual(result["selected_true_data_stem"], "a")
            self.assertEqual(len(result["members"]), 2)
        with patch.object(p, "SIZE", len(raw)), patch.object(p, "MD5", hashlib.md5(raw).hexdigest()):
            with self.assertRaisesRegex(p.Refused, "SHA256_CHANGED"):
                m.analyze_source(raw)

    def test_14_create_only_receipt_prevents_second_get(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)/"already.json"
            dest.write_text("fixed")
            with patch.object(p, "download_once", side_effect=AssertionError("must not download")):
                with self.assertRaisesRegex(p.Refused, "CREATE_ONLY"):
                    m.run(dest)
            self.assertEqual(dest.read_text(), "fixed")


if __name__ == "__main__":
    unittest.main()
