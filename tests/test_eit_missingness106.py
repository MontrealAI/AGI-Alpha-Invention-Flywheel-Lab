"""Synthetic-only EIT106 regressions: never substitute for physical evidence."""
import csv
import io
import unittest
from unittest.mock import patch

from research.eit_missingness106 import diagnose as d


def fixture(changes=None):
    out = io.StringIO()
    header = ("value_desc", "ex_mat_0", "ex_mat_1") + d.ELECTRODES
    writer = csv.DictWriter(out, fieldnames=header)
    writer.writeheader()
    row = {k: "0.5" for k in d.ELECTRODES}
    row.update({"value_desc": "measurement", "ex_mat_0": "0", "ex_mat_1": "1"})
    row.update(changes or {})
    writer.writerow(row)
    return out.getvalue().encode()


class IndependentTokenInventoryTests(unittest.TestCase):
    def test_registered_identity_refuses_changed_bytes(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_CHANGED"):
            d.verify_source(fixture())

    def test_register_size_limit(self):
        with patch.object(d, "MAX_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "SOURCE_SIZE"):
                d.verify_source(fixture())

    def test_each_token_class_explicit(self):
        expected = {
            "NA": "literal_na", "": "empty", " ": "whitespace_only",
            "  NA ": "padded_na", "2.1": "finite",
            " 2.1 ": "padded_finite", "NaN": "nonfinite",
            "-inf": "nonfinite", "bad": "other_text",
        }
        for token, category in expected.items():
            with self.subTest(token=token):
                self.assertEqual(d.classify(token), category)

    def test_whitespace_is_not_silently_numeric(self):
        self.assertEqual(d.classify("  "), "whitespace_only")
        self.assertNotEqual(d.classify("  "), "finite")

    def test_single_fixture_is_all_finite(self):
        s = d.diagnostic(fixture())
        self.assertEqual(s["measurement_rows"], 1)
        self.assertEqual(s["finite_per_row_min"], 16)
        self.assertEqual(s["invalid_or_unrepresented_rows"], 0)
        self.assertEqual(s["category_counts"]["finite"], 16)

    def test_anomalous_tokens_count_without_raw_values(self):
        s = d.diagnostic(fixture({
            "E_01": "NA", "E_02": " ", "E_03": "", "E_04": " 2 ",
            "E_05": "  NA ", "E_06": "inf", "E_07": "other",
        }))
        self.assertEqual(s["finite_per_row_min"], 9)
        self.assertEqual(s["category_counts"]["finite"], 9)
        self.assertEqual(s["category_counts"]["literal_na"], 1)
        self.assertEqual(s["category_counts"]["whitespace_only"], 1)
        self.assertEqual(s["category_counts"]["empty"], 1)
        self.assertEqual(s["category_counts"]["padded_finite"], 1)
        self.assertEqual(s["category_counts"]["padded_na"], 1)
        self.assertEqual(s["category_counts"]["nonfinite"], 1)
        self.assertEqual(s["category_counts"]["other_text"], 1)
        self.assertEqual(s["on_injection_category_counts"]["literal_na"], 1)
        self.assertEqual(s["on_injection_category_counts"]["whitespace_only"], 1)
        self.assertEqual(s["invalid_or_unrepresented_rows"], 1)
        self.assertFalse(s["unknown_tokens_accepted_as_voltage"])
        self.assertNotIn("other", str(s))

    def test_literal_na_count_separate_from_invalid(self):
        s = d.diagnostic(fixture({"E_16": "NA"}))
        self.assertEqual(s["rows_with_literal_NA"], 1)
        self.assertEqual(s["invalid_or_unrepresented_rows"], 0)

    def test_invalid_injection_indices_rejected(self):
        for pair in ({"ex_mat_0": "1", "ex_mat_1": "1"},
                     {"ex_mat_0": "-1"}, {"ex_mat_1": "16"}):
            with self.subTest(pair=pair):
                with self.assertRaisesRegex(ValueError, "INVALID_EXCITATION"):
                    d.diagnostic(fixture(pair))

    def test_invalid_injection_encoding_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_EXCITATION_INDEX"):
            d.diagnostic(fixture({"ex_mat_0": "1.5"}))

    def test_missing_or_duplicate_csv_columns_rejected(self):
        s = fixture()
        with self.assertRaisesRegex(ValueError, "SOURCE_REQUIRED_COLUMNS_ABSENT"):
            d.diagnostic(s.replace(b"E_16", b"ABSENT", 1))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_MISSING_CSV_HEADER"):
            d.diagnostic(s.replace(b"E_16", b"E_15", 1))

    def test_ragged_source_rejected(self):
        s = fixture() + b"measurement,0,1,1,2\n"
        with self.assertRaisesRegex(ValueError, "RAGGED_SOURCE_ROW"):
            d.diagnostic(s)

    def test_no_physical_measurements_rejected(self):
        s = fixture().replace(b"measurement,0,1", b"mean_empty_ground,0,1")
        with self.assertRaisesRegex(ValueError, "NO_MEASURED_ROWS"):
            d.diagnostic(s)

    def test_no_relaxation_after_seeing_result(self):
        s = d.diagnostic(fixture({"E_08": "unexpected"}))
        self.assertEqual(s["original_EIT105_strict_contract"], "FAILED_HISTORICAL")
        self.assertEqual(s["original_EIT105_masked_contract"], "FAILED_HISTORICAL")
        self.assertEqual(s["new_accepted_physical_outcomes"], 0)
        self.assertTrue(s["all_missing_values_left_unimputed"])

    def test_registered_row_bound(self):
        with patch.object(d, "MAX_ROWS", 0):
            with self.assertRaisesRegex(ValueError, "SOURCE_ROW_LIMIT"):
                d.diagnostic(fixture())


if __name__ == "__main__":
    unittest.main()
