"""Frozen adversarial source-trace129 tests: no real buyers or procurement."""
import csv
import io
import tempfile
import unittest
from pathlib import Path

from scripts.trace_solicitations129 import (
    analyze, SourceRejected, safe_id, TITLE, SOLICITATION, REFERENCE,
)


def to_csv(headers, data, bom=False):
    f = io.StringIO(newline="")
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(data)
    result = f.getvalue().encode("utf-8")
    return b"\xef\xbb\xbf" + result if bom else result


class SourceTrace129Test(unittest.TestCase):
    def run_case(self, awards, tenders, a_blob=None, t_blob=None):
        ah = [TITLE, SOLICITATION, "contactInfoEmail", "description"]
        th = [SOLICITATION, REFERENCE, "supplierLegalName", "tenderDescription"]
        with tempfile.TemporaryDirectory() as d:
            a, t = Path(d) / "a.csv", Path(d) / "t.csv"
            a.write_bytes(to_csv(ah, awards) if a_blob is None else a_blob)
            t.write_bytes(to_csv(th, tenders) if t_blob is None else t_blob)
            return analyze(a, t)

    def test_one_exact_link_and_no_contacts(self):
        z = self.run_case(
            [["WCAG remediation", "WS5115894543", "PRIVATE_CONTACT", "PRIVATE_TEXT"]],
            [["WS5115894543", "WS5115894543-Doc50", "PRIVATE_SUPPLIER", "PRIVATE_MATERIAL"]],
        )
        self.assertEqual(z["counts"]["dispositions"]["matched_one_tender_row"], 1)
        self.assertEqual(z["leads"][0]["tender_references"][0]["reference_id"],
                         "WS5115894543-DOC50")
        for v in ("PRIVATE_CONTACT", "PRIVATE_TEXT", "PRIVATE_SUPPLIER", "PRIVATE_MATERIAL"):
            self.assertNotIn(v, str(z))

    def test_amendment_set_not_cherry_picked(self):
        z = self.run_case(
            [["Industrial inspection", "WS500000", "", ""]],
            [["WS500000", "WS500000-Doc1", "", ""],
             ["WS500000", "WS500000-Doc2", "", ""]],
        )
        self.assertEqual(z["leads"][0]["tender_row_count"], 2)
        self.assertEqual(z["leads"][0]["disposition"], "amendment_or_collision_set")

    def test_no_exact_match_does_not_infer_buyer(self):
        z = self.run_case([["Recycling", "WS200000", "", ""]],
                          [["WS300000", "WS300000-Doc1", "", ""]])
        self.assertEqual(z["leads"][0]["disposition"], "no_exact_tender_match")
        self.assertIsNone(z["unknown"]["future_demand_and_willingness_to_pay"])

    def test_missing_id_explicitly_unlinked(self):
        z = self.run_case([["Accessibility", "", "", ""]],
                          [["WS300000", "WS300000-Doc1", "", ""]])
        self.assertEqual(z["leads"][0]["disposition"], "missing_or_unsafe_solicitation_id")

    def test_unsafe_id_redacted(self):
        z = self.run_case([["Accessibility", "contact@example.test", "", ""]],
                          [["contact@example.test", "private@example.test", "", ""]])
        self.assertIsNone(z["leads"][0]["solicitation_id"])
        self.assertNotIn("@example", str(z))

    def test_unsafe_tender_reference_redacted(self):
        z = self.run_case([["Accessibility", "WS12345", "", ""]],
                          [["WS12345", "Actual Person", "", ""]])
        self.assertIsNone(z["leads"][0]["tender_references"][0]["reference_id"])
        self.assertEqual(z["counts"]["linked_rows_with_unsafe_tender_references"], 1)

    def test_overlap_is_one_row_not_three_customers(self):
        z = self.run_case([["WCAG metrology recycling", "WS1234", "", ""]],
                          [["WS1234", "WS1234-Doc1", "", ""]])
        self.assertEqual(z["counts"]["multi_family_award_rows"], 1)
        self.assertEqual(z["counts"]["matching_award_rows_not_buyers"], 1)
        self.assertEqual(sum(z["counts"]["family_rows_not_unique_buyers"].values()), 3)

    def test_bom_unicode_multiline_and_no_description_leak(self):
        a = to_csv([TITLE, SOLICITATION, "contactInfoEmail", "description"],
                   [["ACCESSIBILITY ＲＥＣＹＣＬＩＮＧ", "ws111111", "", "PRIVATE\nTHING"]], bom=True)
        z = self.run_case([], [["WS111111", "WS111111-Doc1", "", ""]], a_blob=a)
        self.assertEqual(z["counts"]["family_rows_not_unique_buyers"]["material_recovery"], 1)
        self.assertNotIn("PRIVATE", str(z))

    def test_new_source_hash_not_mislabeled_old(self):
        z = self.run_case([["Accessibility", "WS111111", "", ""]],
                          [["WS111111", "WS111111-Doc1", "", ""]])
        self.assertFalse(z["sources"]["same_award_bytes_as_PR333"])

    def test_duplicate_award_headers_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "DUPLICATE_HEADER"):
            self.run_case([], [["WS12345", "WS12345-Doc1", "", ""]],
                          a_blob=to_csv([TITLE, SOLICITATION, SOLICITATION],
                                        [["WCAG", "WS12345", "WS12345"]]))

    def test_missing_required_column_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "MISSING_OR_AMBIGUOUS"):
            self.run_case([], [["WS12345", "WS12345-Doc1", "", ""]],
                          a_blob=to_csv(["title", SOLICITATION], [["WCAG", "WS12345"]]))

    def test_row_width_mismatch_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "ROW_WIDTH_MISMATCH"):
            self.run_case([], [["WS12345", "WS12345-Doc1", "", ""]],
                          a_blob=(f"{TITLE},{SOLICITATION}\nWCAG,WS12345,EXTRA\n").encode())

    def test_invalid_utf8_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "INVALID_CSV_OR_UTF8"):
            self.run_case([], [["WS12345", "WS12345-Doc1", "", ""]],
                          a_blob=(f"{TITLE},{SOLICITATION}\n".encode() + b"\xff"))

    def test_empty_source_rejected(self):
        with self.assertRaisesRegex(SourceRejected, "EMPTY_SOURCE"):
            self.run_case([], [["WS12345", "WS12345-Doc1", "", ""]], a_blob=b"")

    def test_no_match_not_declared_no_demand(self):
        z = self.run_case([["Office chairs", "WS1111", "", ""]],
                          [["WS1111", "WS1111-Doc1", "", ""]])
        self.assertEqual(z["counts"]["matching_award_rows_not_buyers"], 0)
        self.assertIsNone(z["unknown"]["future_demand_and_willingness_to_pay"])

    def test_id_requires_number_and_no_whitespace(self):
        self.assertIsNone(safe_id("Mary Smith"))
        self.assertIsNone(safe_id("person@example.org"))
        self.assertEqual(safe_id("ws50000-doc1"), "WS50000-DOC1")


    def test_atomic_path_replacement_keeps_parsed_bytes_bound_to_digest(self):
        """A rename between open and parse may not misattribute a new record."""
        import hashlib
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            a, t, replacement = (Path(d) / name for name in ("a.csv", "t.csv", "replacement.csv"))
            original = to_csv([TITLE, SOLICITATION],
                              [["WCAG remediation", "WS100001"]])
            changed = to_csv([TITLE, SOLICITATION],
                             [["Recycling collection", "WS200002"]])
            a.write_bytes(original)
            replacement.write_bytes(changed)
            t.write_bytes(to_csv([SOLICITATION, REFERENCE],
                                 [["WS100001", "WS100001-Doc1"],
                                  ["WS200002", "WS200002-Doc1"]]))
            real_open = Path.open
            replaced = [False]

            def interleaved_open(p, *args, **kwargs):
                descriptor = real_open(p, *args, **kwargs)
                if p == a and not replaced[0]:
                    os.replace(replacement, a)
                    replaced[0] = True
                return descriptor

            with patch.object(Path, "open", interleaved_open):
                result = analyze(a, t)
            self.assertTrue(replaced[0], "injected swap must really occur")
            self.assertEqual(a.read_bytes(), changed)
            self.assertEqual(result["sources"]["awards"]["sha256"],
                             hashlib.sha256(original).hexdigest())
            self.assertEqual(result["sources"]["awards"]["bytes"], len(original))
            self.assertEqual(result["counts"]["family_rows_not_unique_buyers"]
                             ["accessible_publication"], 1)
            self.assertEqual(result["counts"]["family_rows_not_unique_buyers"]
                             ["material_recovery"], 0)
            self.assertEqual(result["leads"][0]["solicitation_id"], "WS100001")

    def test_in_place_modification_during_parse_rejected(self):
        """Active descriptor mutation is not an admissible successful snapshot."""
        from unittest.mock import patch
        from scripts.trace_solicitations129 import _HashingStream
        with tempfile.TemporaryDirectory() as d:
            a, t = Path(d) / "a.csv", Path(d) / "t.csv"
            a.write_bytes(to_csv([TITLE, SOLICITATION],
                                 [["WCAG remediation", "WS100001"]]))
            t.write_bytes(to_csv([SOLICITATION, REFERENCE],
                                 [["WS100001", "WS100001-Doc1"]]))
            real_readinto = _HashingStream.readinto
            real_open = Path.open
            mutated = [False]

            def interleaved_readinto(stream, buf):
                n = real_readinto(stream, buf)
                if stream.path == a and n and not mutated[0]:
                    with real_open(a, "ab") as f:
                        f.write(b"\n")
                    mutated[0] = True
                return n

            with patch.object(_HashingStream, "readinto", interleaved_readinto):
                with self.assertRaisesRegex(SourceRejected, "SOURCE_CHANGED_DURING_PARSE"):
                    analyze(a, t)
            self.assertTrue(mutated[0], "injected active-descriptor mutation must occur")



if __name__ == "__main__":
    unittest.main()
