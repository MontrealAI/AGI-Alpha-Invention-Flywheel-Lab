"""Prospective EIT185 original-source MATLAB v5 compatibility tests after first failure."""
import io
import unittest

import numpy as np
from scipy.io import savemat
from scipy.sparse import csc_matrix

from research.eit_physical_control183.control import Refusal
from research.eit_jacobian185.original_source import dataset_inventory


def mat5(**values):
    buffer = io.BytesIO()
    savemat(buffer, values, do_compression=True)
    return buffer.getvalue()


class TestMat5FormatRepair(unittest.TestCase):
    def test_original_dense_numeric_matrix_inventory(self):
        rows = np.ones((1264, 2), dtype=np.float64)
        out = dataset_inventory(mat5(J=rows))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["shape"], [1264, 2])
        self.assertEqual(out[0]["container"], "MATLAB5")
        self.assertTrue(out[0]["has_1264_measurement_dimension"])
        self.assertIsNone(out[0]["sparse_nonzero_elements"])

    def test_original_sparse_matrix_no_densification(self):
        sparse = csc_matrix(np.eye(1264, 2, dtype=float))
        out = dataset_inventory(mat5(J=sparse))
        self.assertEqual(out[0]["shape"], [1264, 2])
        self.assertEqual(out[0]["sparse_nonzero_elements"], 2)

    def test_nonfinite_v5_rejected(self):
        data = np.ones((4, 5), dtype=float)
        data[0, 0] = np.inf
        with self.assertRaisesRegex(Refusal, "NONFINITE_MAT5_JACOBIAN"):
            dataset_inventory(mat5(J=data))

    def test_nested_matlab_struct_not_imagined_as_numeric_jacobian(self):
        with self.assertRaisesRegex(Refusal, "UNSUPPORTED_NESTED_MAT5_JACOBIAN"):
            dataset_inventory(mat5(J={"meta": np.ones((2, 2))}))

    def test_header_missing_rejected(self):
        with self.assertRaisesRegex(Refusal, "ORIGINAL_JACOBIAN_NOT_HDF5"):
            dataset_inventory(b"not a MATLAB source")

    def test_strict_bounds_on_v5_header_dimensions(self):
        from unittest.mock import patch
        with patch("scipy.io.whosmat", return_value=[("J", (20000000, 2), "double")]):
            with self.assertRaisesRegex(Refusal, "JACOBIAN_DATASET_TOO_LARGE"):
                dataset_inventory(mat5(J=np.ones((2, 2))))


if __name__ == "__main__":
    unittest.main()
