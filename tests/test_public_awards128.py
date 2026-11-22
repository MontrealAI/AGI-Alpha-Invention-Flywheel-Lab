"""Frozen development fixtures for public-evidence128; not observed buyers."""
import csv
import io
import unittest

from scripts.scan_public_awards128 import SourceRejected, analyze


def csv_bytes(headers, rows, bom=False):
    sink = io.StringIO(newline="")
    w = csv.writer(sink)
    w.writerow(headers)
    w.writerows(rows)
    payload = sink.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" if bom else b"") + payload


class AwardEvidence128Tests(unittest.TestCase):
    def test_bom_rfc4180_multiline_and_no_description_leak(self):
        source = csv_bytes(
            ["referenceNumber", "title-titre-eng", "contactEmail", "description-eng"],
            [["one", "Accessible Document Conversion", "private@example.test",
              "person@example.test\nrecycling text must not be classified"]],
            bom=True,
        )
        o = analyze(source)
        self.assertEqual(o["results"]["source_rows"], 1)
        self.assertEqual(o["results"]["family_matched_rows_not_unique_buyers"]
                         ["accessible_publication"], 1)
        self.assertEqual(o["results"]["family_matched_rows_not_unique_buyers"]
                         ["material_recovery"], 0)
        self.assertNotIn("private@example.test", str(o))
        self.assertNotIn("person@example.test", str(o))
        self.assertEqual(o["source"]["title_column"], "title-titre-eng")

    def test_casefold_and_canonical_unicode(self):
        o = analyze(csv_bytes(["title-titre-eng"],
                    [["INDUSTRIAL INSPECTION, METROLOGY AND ＲＥＣＹＣＬＩＮＧ"]]))
        counts = o["results"]["family_matched_rows_not_unique_buyers"]
        self.assertEqual(counts["physical_measurement"], 1)
        self.assertEqual(counts["material_recovery"], 1)

    def test_overlap_one_row_three_not_three_buyers(self):
        o = analyze(csv_bytes(["title-titre-eng"],
                    [["WCAG industrial inspection recycling"]]))
        self.assertEqual(o["results"]["any_family_matched_rows"], 1)
        self.assertEqual(o["results"]["overlapping_rows"]["all_three"], 1)
        self.assertEqual(sum(o["results"]["family_matched_rows_not_unique_buyers"].values()), 3)

    def test_no_match_retained_not_reported_as_no_demand(self):
        o = analyze(csv_bytes(["title"], [["catering"], ["office chairs"]]))
        self.assertEqual(o["results"]["source_rows"], 2)
        self.assertEqual(o["results"]["any_family_matched_rows"], 0)
        self.assertEqual(o["classification"], "WEAK_TITLE_LEVEL_PUBLIC_RECORD_SIGNAL_ONLY")
        self.assertIsNone(o["unknown"]["future_demand"])
        self.assertEqual(o["decision"], "NO_BID_NO_DEPLOY")

    def test_duplicate_headers_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "DUPLICATE_HEADERS"):
            analyze(csv_bytes(["title", "TITLE"], [["a", "b"]]))

    def test_invalid_utf8_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "INVALID_UTF8"):
            analyze(b"title\n\xff\n")

    def test_missing_title_rejected_not_description_proxy(self):
        with self.assertRaisesRegex(SourceRejected, "TITLE_COLUMN_MISSING"):
            analyze(csv_bytes(["description-eng"], [["WCAG remediation"]]))

    def test_multiple_english_title_columns_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "AMBIGUOUS"):
            analyze(csv_bytes(["title-titre-eng", "title-service-eng"],
                              [["accessibility", "recycling"]]))

    def test_extra_row_fields_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "MALFORMED_ROW"):
            analyze(b"title\nwcag,unexpected\n")

    def test_truncated_quoted_csv_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "CSV_MALFORMED"):
            analyze(b'title\n"wcag\n')

    def test_empty_source_and_header_only_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "EMPTY_SOURCE"):
            analyze(b"")
        with self.assertRaisesRegex(SourceRejected, "NO_DATA_ROWS"):
            analyze(b"title-titre-eng\n")

    def test_buyer_counts_and_prices_remain_unknown(self):
        o = analyze(csv_bytes(["title-titre-eng", "contractAmount", "contactName"],
                    [["Recycling", "3000000000", "Actual Person"]]))
        self.assertIsNone(o["unknown"]["native_trailing365_profit"])
        self.assertIsNone(o["unknown"]["supplier_prices_or_complete_costs"])
        self.assertNotIn("Actual Person", str(o))
        self.assertNotIn("3000000000", str(o))


if __name__ == "__main__":
    unittest.main()
