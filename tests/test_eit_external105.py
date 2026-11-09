"""Synthetic-only adversarial checks; do not conflate with independent physics."""
import csv
from hashlib import md5
import io
import json
import unittest
from unittest.mock import patch

from research.eit_external105 import preflight as p

class ExternalPreflightTest(unittest.TestCase):
    def sample(self):
        out = io.StringIO()
        cols = p.FIELDS + p.VOLTAGES
        writer = csv.DictWriter(out, fieldnames=cols)
        writer.writeheader()
        for kind in ("measurement", "mean_empty_ground"):
            row = dict.fromkeys(cols, "0")
            row.update({"object": "circle", "material": "petg",
                        "value_desc": kind, "meas_num": "7",
                        "r": "20", "phi": "0", "ex_mat_0": "1",
                        "ex_mat_1": "2"})
            writer.writerow(row)
        return out.getvalue().encode()

    def test_source_can_only_use_frozen_names(self):
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_SOURCE"):
            p.check_source("unregistered.csv", b"x")

    def test_source_hash_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_CONTENT_CHANGED"):
            p.check_source("circle_petg.csv", b"fake CSV")

    def test_source_size_limit_fails(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SIZE"):
            p.check_source("data_description.JSON", b"x" * 200001)

    def test_source_valid_md5_records_independent_sha256(self):
        with patch.dict(p.SOURCES, {"small": (md5(b"ok").hexdigest(), 2)}):
            s = p.check_source("small", b"ok")
        self.assertEqual(s["bytes"], 2)
        self.assertEqual(len(s["sha256"]), 64)

    def test_required_fields_finite_and_grouped(self):
        d = p.describe_csv(self.sample())
        self.assertEqual(d["rows"], 2)
        self.assertEqual(d["distinct_excitation_pairs"], 1)
        self.assertEqual(d["measurement_rows"], 1)

    def test_missing_voltage_field_fails(self):
        with self.assertRaisesRegex(ValueError, "MISSING_ACQUISITION_FIELDS"):
            p.describe_csv(self.sample().replace(b"E_16", b"OTHER"))

    def test_nonfinite_measurement_refused(self):
        s = self.sample().replace(b",0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0",
                                  b",nan,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0", 1)
        with self.assertRaisesRegex(ValueError, "NONFINITE_VOLTAGE"):
            p.describe_csv(s)

    def test_invalid_injection_refused(self):
        s = self.sample().replace(b",1,2,", b",1,1,", 1)
        with self.assertRaisesRegex(ValueError, "INVALID_MEASUREMENT"):
            p.describe_csv(s)

    def test_ragged_data_refused(self):
        with self.assertRaisesRegex(ValueError, "RAGGED_CSV_ROW"):
            p.describe_csv(self.sample() + b",\n")

    def test_empty_data_refused(self):
        header = self.sample().splitlines()[0] + b"\n"
        with self.assertRaisesRegex(ValueError, "NO_PHYSICAL_MEASUREMENTS"):
            p.describe_csv(header)

    def test_unexpected_metadata_license_refused(self):
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_LICENSE"):
            p.metadata(json.dumps({"license": ["CC BY-NC"]}).encode())

    def test_missing_metadata_fields_refused(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_METADATA_SCHEMA_CHANGED"):
            p.metadata(json.dumps({"license": ["CC BY 4.0"],
                                    "variableMeasured": []}).encode())

if __name__ == "__main__":
    unittest.main()
