"""Tests of a separate structural MAT-v5 reader; no downloaded sensor values."""
import io
import unittest
import zipfile

import numpy as np
from scipy.io import savemat

from research.magnetic_rotor001 import gate, schema, v5_inventory as inv


def mat_bytes(mapping=None, *, compress=False):
    stream = io.BytesIO()
    savemat(stream, mapping or {"shared": np.arange(3, dtype=np.float64)},
            do_compression=compress)
    return stream.getvalue()


def archive(body=None, *, different_last=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, name in enumerate(schema.EXPECTED_MEMBERS):
            item = body if i == 0 and body is not None else mat_bytes(
                {"other": np.array([1.0])} if different_last and i == 9 else None)
            zf.writestr(name, item)
    return stream.getvalue()


class IndependentDirectory004(unittest.TestCase):
    def test_scipy_uncompressed_numeric_array_is_metadata_only(self):
        r = inv.inventory_mat_v5(mat_bytes())
        self.assertEqual([x["name"] for x in r], ["shared"])
        self.assertEqual(r[0]["shape"], [1, 3])
        self.assertEqual(r[0]["matrix_class_code"], 6)

    def test_scipy_compressed_numeric_array_is_metadata_only(self):
        r = inv.inventory_mat_v5(mat_bytes(compress=True))
        self.assertEqual(r[0]["name"], "shared")

    def test_empty_matrix_is_still_structural_metadata(self):
        r = inv.inventory_mat_v5(mat_bytes({"empty": np.array([[]])}))
        self.assertEqual(r[0]["name"], "empty")
        self.assertEqual(r[0]["shape"], [1, 0])

    def test_ten_source_shape_and_shared_field_can_pass_independently(self):
        r = inv.inspect_original_archive(archive(), require_original=False)
        self.assertEqual(r["inspected_member_count"], 10)
        self.assertEqual(r["failed_member_count"], 0)
        self.assertEqual(r["all_ten_common_names"], ["shared"])
        self.assertEqual(r["status"], "INDEPENDENT_DIRECTORY_PASS_PHYSICAL_HOLD")
        self.assertEqual(r["unmodified_scipy_schema002_status"], "FAILED")
        self.assertFalse(r["matlab_numeric_arrays_interpreted"])
        self.assertFalse(r["actual_physical_observations_interpreted"])
        self.assertEqual(r["deployment"], "NO_DEPLOY")

    def test_no_common_variable_preserves_all_denominators_and_fails(self):
        r = inv.inspect_original_archive(archive(different_last=True),
                                          require_original=False)
        self.assertEqual(r["inspected_member_count"], 10)
        self.assertEqual(r["failed_member_count"], 0)
        self.assertEqual(r["all_ten_common_names"], [])
        self.assertEqual(r["status"], "INDEPENDENT_DIRECTORY_FAILED")

    def test_malformed_first_file_fails_without_dropping_other_heights(self):
        r = inv.inspect_original_archive(archive(b"broken"), require_original=False)
        self.assertEqual(r["inspected_member_count"], 10)
        self.assertEqual(r["failed_member_count"], 1)
        self.assertEqual(r["records"][0]["metadata_status"], "ERROR")
        self.assertEqual(r["records"][1]["metadata_status"], "READABLE")

    def test_signed_original_digest_cannot_be_faked_with_synthetic_fixture(self):
        with self.assertRaisesRegex(gate.SourceGateError, "MD5_MISMATCH"):
            inv.inspect_original_archive(archive())

    def test_bad_version_is_rejected(self):
        original = bytearray(mat_bytes())
        original[124] = 42
        with self.assertRaisesRegex(inv.DirectoryError, "VERSION"):
            inv.inventory_mat_v5(bytes(original))

    def test_hdf5_is_rejected(self):
        with self.assertRaisesRegex(inv.DirectoryError, "NOT_V5"):
            inv.inventory_mat_v5(b"\x89HDF\r\n\x1a\n" + b"\0" * 256)

    def test_payload_length_overrun_is_rejected(self):
        original = bytearray(mat_bytes())
        original[132:136] = b"\xff\xff\xff\x7f"
        with self.assertRaisesRegex(inv.DirectoryError, "OUT_OF_BOUNDS"):
            inv.inventory_mat_v5(bytes(original))

    def test_duplicate_top_level_variable_is_rejected(self):
        original = mat_bytes()
        twice = original + original[128:]
        with self.assertRaisesRegex(inv.DirectoryError, "DUPLICATED"):
            inv.inventory_mat_v5(twice)

    def test_unknown_top_level_tag_rejected(self):
        original = bytearray(mat_bytes())
        original[128:132] = b"\x03\x00\x00\x00"
        with self.assertRaisesRegex(inv.DirectoryError, "UNSUPPORTED"):
            inv.inventory_mat_v5(bytes(original))

    def test_unbounded_decompression_fails_closed(self):
        import zlib
        with self.assertRaisesRegex(inv.DirectoryError, "UNBOUNDED"):
            inv._bounded_inflate(zlib.compress(b"x" * (inv.MAX_INFLATED + 1)))

    def test_wrong_number_of_archive_members_fails(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as zf:
            zf.writestr(schema.EXPECTED_MEMBERS[0], mat_bytes())
        with self.assertRaisesRegex(inv.DirectoryError, "TEN_MEMBERS"):
            inv.inspect_original_archive(stream.getvalue(), require_original=False)


if __name__ == "__main__":
    unittest.main()
