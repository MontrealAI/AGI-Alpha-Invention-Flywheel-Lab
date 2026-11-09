"""Synthetic refusal and H1-falsification tests; no public raw voltages embedded."""
import csv
import io
import unittest
from research.eit_schedule107.diagnose import (
    FIELDS, CHANNELS, classify_token, parse_pair, scan_csv, verify_source,
)


def row(*, a=0, b=1, obj="circle", absent=(0, 1, 2, 15), blank=(15,), measured=True):
    r = dict.fromkeys(FIELDS, "1.2")
    r.update({
        "value_desc": "measurement" if measured else "mean_empty_ground",
        "object": obj, "material": "petg", "r": "1", "phi": "0",
        "meas_num": "1", "ex_mat_0": str(a), "ex_mat_1": str(b)
    })
    for i, key in enumerate(CHANNELS):
        r[key] = "" if i in blank else ("NA" if i in absent else "1.2")
    return r


def render(rows, columns=FIELDS):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r[k] for k in columns})
    return buf.getvalue().encode()


class ScheduleTests(unittest.TestCase):
    def test_true_h1_is_representation_only(self):
        report = scan_csv(render([row(), row(obj="square")]))
        self.assertTrue(report["H1_supported_on_exact_exposed_file_only"])
        self.assertFalse(report["physical_acquisition_semantics_qualified"])
        self.assertEqual(report["per_pair_ternary_mask_count"], {"00-01": 1})
        self.assertEqual(report["token_totals_F_N_E"], {"E": 2, "F": 24, "N": 6})
        self.assertEqual(report["distinct_object_labels"], 2)

    def test_mask_depends_on_specimen_falsifies_h1(self):
        report = scan_csv(render([row(), row(obj="square", absent=(0, 1, 3, 15))]))
        self.assertEqual(report["H1_pair_only_mask_schedule"], "REJECT_PAIR_ONLY_PROJECTION")
        self.assertEqual(report["per_pair_ternary_mask_count"]["00-01"], 2)

    def test_numeric_on_injection_falsifies(self):
        report = scan_csv(render([row(absent=(1, 2, 3, 15))]))
        self.assertEqual(report["numeric_on_injection_cells"], 1)
        self.assertFalse(report["H1_supported_on_exact_exposed_file_only"])

    def test_incomplete_finite_falsifies(self):
        report = scan_csv(render([row(absent=(0, 1, 2, 3, 15))]))
        self.assertEqual(report["rows_not_exactly_12_finite"], 1)
        self.assertFalse(report["H1_supported_on_exact_exposed_file_only"])

    def test_empty_distinct_from_na(self):
        self.assertEqual(classify_token(""), "E")
        self.assertEqual(classify_token("NA"), "N")
        self.assertEqual(classify_token("-0.25"), "F")

    def test_invalid_nan_inf(self):
        for text in ("NaN", "inf", "-inf", " NA", "1.0 ", "  ", "not_number"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    classify_token(text)

    def test_missing_column_refused(self):
        with self.assertRaisesRegex(ValueError, "CSV_HEADER"):
            scan_csv(render([row()], columns=FIELDS[:-1]))

    def test_duplicate_header_refused(self):
        s = render([row()]).decode()
        s = s.replace("E_01,E_02", "E_01,E_01", 1)
        with self.assertRaisesRegex(ValueError, "CSV_HEADER"):
            scan_csv(s.encode())

    def test_ragged_refused(self):
        s = render([row()]).decode().splitlines()
        with self.assertRaisesRegex(ValueError, "RAGGED"):
            scan_csv((s[0] + "\n" + "a,b,c" + "\n").encode())

    def test_invalid_excitation_refused(self):
        for a, b in [(0, 0), (-1, 1), (0, 16)]:
            with self.subTest(pair=(a, b)):
                with self.assertRaisesRegex(ValueError, "INJECTION"):
                    scan_csv(render([row(a=a, b=b)]))

    def test_non_measurements_not_physical_observations(self):
        with self.assertRaisesRegex(ValueError, "NO_MEASUREMENT"):
            scan_csv(render([row(measured=False)]))

    def test_changed_source_refused(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_SIZE_CHANGED"):
            verify_source(b"synthetic\n")

    def test_nonfinite_raw_numeric_refused(self):
        r = row()
        r["E_03"] = "inf"
        with self.assertRaisesRegex(ValueError, "NONFINITE"):
            scan_csv(render([r]))

    def test_masked_row_no_fake_reconstruction(self):
        report = scan_csv(render([row()]))
        self.assertEqual(report["actual_finite_channel_histogram"], {12: 1})
        self.assertTrue(report["blank_E_kept_distinct_from_NA"])
        self.assertEqual(report["new_independent_physical_specimens"], 0)
        self.assertEqual(report["native_accounts_operated"], 0)

    def test_different_pairs_can_have_different_masks(self):
        second = row(a=1, b=2, absent=(1, 2, 3, 15))
        report = scan_csv(render([row(), second]))
        self.assertTrue(report["H1_supported_on_exact_exposed_file_only"])
        self.assertEqual(report["distinct_injection_pairs_not_acquisition_reduction"], 2)


if __name__ == "__main__":
    unittest.main()
