"""Registered header-only diagnostic tests (no external data downloaded)."""
import unittest
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from scipy.io import savemat
from research.magnetic_rotor001 import gate, mat_format, schema


def build(member_override=None):
    mem = BytesIO()
    with ZipFile(mem, "w", ZIP_DEFLATED) as z:
        for i, name in enumerate(schema.EXPECTED_MEMBERS):
            p = BytesIO()
            savemat(p, {"repeated": np.array([[float(i)]])})
            body = member_override if i == 0 and member_override is not None else p.getvalue()
            z.writestr(name, body)
    return mem.getvalue()


class FormatDiagnosticTests(unittest.TestCase):
    def test_all_valid_metadata_is_still_only_diagnostic(self):
        r = mat_format.diagnostic(build(), require_original=False)
        self.assertEqual(r["member_count"], 10)
        self.assertEqual(r["reader_error_count"], 0)
        self.assertTrue(r["original_schema002_failure_preserved"])
        self.assertFalse(r["numeric_arrays_materialized"])
        self.assertFalse(r["physical_force_interpreted"])
        self.assertEqual(r["deployment"], "NO_DEPLOY")

    def test_exact_original_digest_cannot_be_inferred_from_another_archive(self):
        with self.assertRaisesRegex(gate.SourceGateError, "MD5_MISMATCH"):
            mat_format.diagnostic(build())

    def test_corrupt_first_member_is_a_counted_error_without_skipping_other_heights(self):
        r = mat_format.diagnostic(build(b"garbled-not-mat"), require_original=False)
        self.assertEqual(r["member_count"], 10)
        self.assertEqual(r["reader_error_count"], 1)
        self.assertEqual(r["records"][0]["reader_result"], "METADATA_ERROR")
        self.assertEqual(r["records"][1]["reader_result"], "METADATA_SUCCESS")
        self.assertEqual(r["status"], "MAT_FORMAT_DIAGNOSTIC_COMPLETE_SCHEMA002_STILL_FAILED")

    def test_signature_offset_512_is_recorded_without_numeric_read(self):
        p = b"x" * 512 + mat_format.HDF5_MAGIC + b"other-bytes"
        r = mat_format.diagnostic(build(p), require_original=False)
        self.assertTrue(r["records"][0]["hdf5_signature_at_offset512"])
        self.assertEqual(r["records"][0]["member_size"], len(p))
        self.assertEqual(r["reader_error_count"], 1)

    def test_missing_member_cannot_qualify_root_cause(self):
        p = BytesIO()
        with ZipFile(p, "w", ZIP_DEFLATED) as z:
            z.writestr(schema.EXPECTED_MEMBERS[0], b"x")
        with self.assertRaisesRegex(schema.SchemaError, "EXPECTED_MEMBER_COUNT"):
            mat_format.diagnostic(p.getvalue(), require_original=False)


if __name__ == "__main__":
    unittest.main()
