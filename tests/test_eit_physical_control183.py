"""Frozen offline refusals for EIT183 ordinary physical paired-voltage control."""
import io
import unittest
import zipfile
import numpy as np
from research.eit_physical_control183.control import Refusal, SHAPE, paired_control, validate_zip, parse_member

class TestControl(unittest.TestCase):
    def setUp(self):
        self.i = np.zeros(SHAPE, dtype=float)
        self.v0 = np.full(SHAPE, 0.1)
        self.v1 = np.full(SHAPE, 0.11)

    def test_known_difference_and_epsilon(self):
        r = paired_control(self.i, self.v0, self.i.copy(), self.v1)
        self.assertAlmostEqual(r["ordinary_direct_difference_l2"], 0.01 * np.sqrt(79 * 16))
        self.assertAlmostEqual(r["hypothetical_per_reading_error_bound_strictly_below"], 0.005)
        self.assertEqual(len(r["all_16_column_rms_differences"]), 16)

    def test_mismatched_currents_refuse(self):
        j = self.i.copy(); j[0, 0] = 1
        with self.assertRaisesRegex(Refusal, "EXCITATIONS_NOT_IDENTICAL"):
            paired_control(self.i, self.v0, j, self.v1)

    def test_no_contrast_refuses(self):
        with self.assertRaisesRegex(Refusal, "NO_NONZERO_MEASURED_CONTRAST"):
            paired_control(self.i, self.v0, self.i, self.v0.copy())

    def test_nonfinite_refuses(self):
        altered = self.v1.copy(); altered[7, 2] = np.nan
        with self.assertRaisesRegex(Refusal, "NONFINITE"):
            paired_control(self.i, self.v0, self.i, altered)

    def test_zero_baseline_refuses(self):
        with self.assertRaisesRegex(Refusal, "NO_FINITE_BASELINE"):
            paired_control(self.i, self.i, self.i, self.v1)

    def test_invalid_mat_refuses(self):
        with self.assertRaisesRegex(Refusal, "NOT_BOUNDED_HDF5"):
            parse_member(b"not-a-matlab-hdf5")

    def test_zip_path_traversal_refuses(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("../bad", "unsafe")
        with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
            with self.assertRaisesRegex(Refusal, "UNSAFE_ARCHIVE_PATH"):
                validate_zip(z)

    def test_zip_case_duplicate_refuses(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("ABC", "a"); z.writestr("abc", "b")
        with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:
            with self.assertRaisesRegex(Refusal, "DUPLICATE_ARCHIVE_MEMBER"):
                validate_zip(z)

    def test_wrong_shape_refuses(self):
        with self.assertRaisesRegex(Refusal, "SHAPE"):
            paired_control(np.zeros((5, 4)), self.v0, self.i, self.v1)

if __name__ == "__main__":
    unittest.main()
