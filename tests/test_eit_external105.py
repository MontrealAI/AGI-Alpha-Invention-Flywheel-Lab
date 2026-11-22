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

    def test_documented_singleton_list_identifiers_are_explicitly_valid(self):
        payload = {"license": ["CC BY 4.0"],
                   "variableMeasured": [{"identifier": [key]}
                                        for key in p.FIELDS + p.VOLTAGES]}
        result = p.metadata(json.dumps(payload).encode())
        self.assertEqual(result["declared_fields"], 24)

    def test_ambiguous_multi_identifier_refused(self):
        payload = {"license": ["CC BY 4.0"],
                   "variableMeasured": [{"identifier": ["object", "material"]}]}
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_METADATA_IDENTIFIER"):
            p.metadata(json.dumps(payload).encode())

    def test_duplicate_identifier_refused(self):
        payload = {"license": ["CC BY 4.0"],
                   "variableMeasured": [{"identifier": "object"}, {"identifier": ["object"]}]}
        with self.assertRaisesRegex(ValueError, "DUPLICATE_METADATA_IDENTIFIER"):
            p.metadata(json.dumps(payload).encode())

    def masked_sample(self, changes):
        rows=list(csv.DictReader(io.StringIO(self.sample().decode())))
        rows[0].update(changes)
        out=io.StringIO()
        writer=csv.DictWriter(out,fieldnames=p.FIELDS+p.VOLTAGES)
        writer.writeheader()
        writer.writerows(rows)
        return out.getvalue().encode()

    def test_masked_inventory_preserves_real_missing_electrodes(self):
        s=self.masked_sample({"E_02":"NA", "E_09":"NA"})
        with self.assertRaisesRegex(ValueError, "INVALID_MEASUREMENT"):
            p.describe_csv(s)  # frozen original full-channel validator stays FAILED
        summary=p.describe_masked_csv(s)
        self.assertEqual(summary["measurement_rows"],1)
        self.assertEqual(summary["finite_channel_count_histogram"],{14:1})
        self.assertEqual(summary["missing_on_injection_electrodes"],1)
        self.assertEqual(summary["missing_on_other_electrodes"],1)
        self.assertEqual(summary["distinct_observed_missing_masks"],1)
        self.assertTrue(summary["no_imputation"])

    def test_masked_inventory_refuses_unknown_missing_codes(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_MISSING_TOKEN"):
            p.describe_masked_csv(self.masked_sample({"E_08":"missing"}))

    def test_masked_inventory_refuses_nonfinite_float(self):
        with self.assertRaisesRegex(ValueError, "NONFINITE_MEASUREMENT"):
            p.describe_masked_csv(self.masked_sample({"E_08":"inf"}))

    def test_masked_inventory_refuses_empty_voltage(self):
        with self.assertRaisesRegex(ValueError, "INVALID_OR_EMPTY_MEASUREMENT"):
            p.describe_masked_csv(self.masked_sample({"E_08":""}))

    def test_masked_inventory_refuses_fewer_than_eight_measured(self):
        insufficient={f"E_{j:02d}":"NA" for j in range(1,10)}
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_FINITE_CHANNELS"):
            p.describe_masked_csv(self.masked_sample(insufficient))

    def test_masked_inventory_refuses_invalid_injection(self):
        with self.assertRaisesRegex(ValueError, "INVALID_EXCITATION"):
            p.describe_masked_csv(self.masked_sample({"ex_mat_0":"1","ex_mat_1":"1"}))

    def test_masked_inventory_refuses_missing_header(self):
        s=self.masked_sample({"E_02":"NA"}).replace(b"E_16",b"OMITTED",1)
        with self.assertRaisesRegex(ValueError, "MISSING_ACQUISITION_FIELDS"):
            p.describe_masked_csv(s)

    def test_masked_inventory_refuses_ragged_rows(self):
        with self.assertRaisesRegex(ValueError, "RAGGED_CSV_ROW"):
            p.describe_masked_csv(self.sample()+b"bad,more,rows\\n")

    def test_missing_metadata_fields_refused(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_METADATA_SCHEMA_CHANGED"):
            p.metadata(json.dumps({"license": ["CC BY 4.0"],
                                    "variableMeasured": []}).encode())

if __name__ == "__main__":
    unittest.main()
