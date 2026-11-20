"""Schema002 preregistered MATLAB metadata checks; synthetic files only."""
from __future__ import annotations

from io import BytesIO
import unittest
from zipfile import ZipFile, ZIP_DEFLATED
import numpy as np
from scipy.io import savemat

from research.magnetic_rotor001 import schema


def files(fields_by_height=None, *, missing=None, extra=None, malformed=False):
    container = BytesIO()
    with ZipFile(container, "w", ZIP_DEFLATED) as z:
        for label in schema.HEIGHT_LABELS:
            if label == missing:
                continue
            fields = {"force": np.array([[1.0, 2.0]])}
            if fields_by_height and label in fields_by_height:
                fields = fields_by_height[label]
            buf = BytesIO()
            savemat(buf, fields)
            z.writestr(f"{schema.PREFIX}{label}.mat", b"wrong" if malformed else buf.getvalue())
        if extra:
            z.writestr(extra, b"EXTRA")
    return container.getvalue()


class MagneticSchemaTests(unittest.TestCase):
    def test_valid_ten_height_metadata_only(self):
        result = schema.inspect_mat_schema(files(), require_original=False)
        self.assertEqual(result["expected_member_count"], 10)
        self.assertEqual(result["observed_member_count"], 10)
        self.assertEqual(result["common_top_level_variable_names"], ["force"])
        self.assertFalse(result["numeric_arrays_materialized"])
        self.assertFalse(result["height_units_known"])
        self.assertFalse(result["physical_hold_slide_accepted"])
        self.assertEqual(result["actual_paid_customers"], 0)
        self.assertEqual(result["deployment"], "NO_DEPLOY")

    def test_no_manufactured_data_source_identity(self):
        with self.assertRaisesRegex(schema.SchemaError, "PINNED_ARCHIVE_SHA256_MISMATCH"):
            # Original MD5 is unavailable for synthetic file, but SHA remains independent.
            from unittest.mock import patch
            fixture_bytes = files()
            with patch.object(schema.gate, "EXPECTED_MD5", schema.gate.md5(fixture_bytes).hexdigest()):
                schema.inspect_mat_schema(fixture_bytes, require_original=True)

    def test_missing_height_fails(self):
        with self.assertRaisesRegex(schema.SchemaError, "TEN_FROZEN_HEIGHT"):
            schema.inspect_mat_schema(files(missing="2.0"), require_original=False)

    def test_extra_height_fails(self):
        with self.assertRaisesRegex(schema.SchemaError, "TEN_FROZEN_HEIGHT"):
            schema.inspect_mat_schema(files(extra="other.mat"), require_original=False)

    def test_non_mat_format_fails_closed(self):
        with self.assertRaisesRegex(schema.SchemaError, "MAT_DIRECTORY_PARSE"):
            schema.inspect_mat_schema(files(malformed=True), require_original=False)

    def test_no_common_variable_fails_closed(self):
        byheight = {h: {f"value_{h.replace('.', '_')}": np.array([3.0])} for h in schema.HEIGHT_LABELS}
        with self.assertRaisesRegex(schema.SchemaError, "NO_SHARED_VARIABLE"):
            schema.inspect_mat_schema(files(fields_by_height=byheight), require_original=False)

    def test_names_do_not_imply_physical_units(self):
        result = schema.inspect_mat_schema(files(), require_original=False)
        self.assertEqual([x["height_label_unverified_units"] for x in result["reported_mat_schemas"]],
            sorted(schema.HEIGHT_LABELS))
        self.assertFalse(result["physical_force_values_interpreted"])

    def test_whosmat_returns_classes_not_values(self):
        result = schema.inspect_mat_schema(files(), require_original=False)
        entry = result["reported_mat_schemas"][0]["top_level_variables"][0]
        self.assertEqual(entry["matlab_class"], "double")
        self.assertEqual(entry["shape"], [1, 2])
        self.assertNotIn("data", entry)


if __name__ == "__main__":
    unittest.main()
