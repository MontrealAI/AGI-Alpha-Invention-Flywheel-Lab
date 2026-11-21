"""Frozen CANADA-OPEN-NEED227 offline adversarial protocol.

Synthetic notice fixtures are NEVER government observations or paid demand.
"""
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import canada_open_need227 as n

AT = "2026-11-21T23:00:00+00:00"
FIELDS = (n.REFERENCE, n.TITLE, n.CLOSING, n.BUYER, n.CATEGORY)


def fixture(*items, fields=FIELDS):
    out = StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in items:
        writer.writerow(item)
    return out.getvalue().encode("utf-8")


def item(ref="CB-1", title="Software development services",
         closing="2026-12-01", buyer="Canadian public buyer", category="SRV"):
    return {n.REFERENCE: ref, n.TITLE: title, n.CLOSING: closing,
            n.BUYER: buyer, n.CATEGORY: category}


class FrozenAdversarialTests(unittest.TestCase):
    def summary(self, *rows, fields=FIELDS):
        return n.assess(fixture(*rows, fields=fields), AT)

    def test_01_source_identity_and_single_review(self):
        r = self.summary(item())
        self.assertEqual(r["review_candidates_total"], 1)
        self.assertEqual(r["review_candidates"][0]["reference"], "CB-1")
        self.assertEqual(r["decision"], "INVESTIGATE_ELIGIBILITY_ONLY")
        self.assertEqual(r["native_financial_account_touched"], False)
        self.assertIsNone(r["complete_cost_profit"])
        self.assertIsNone(r["buyer_willingness_to_pay_for_our_service"])

    def test_02_french_keyword_without_english_translation(self):
        r = self.summary(item(title="Services en intelligence artificielle"))
        self.assertEqual(r["review_candidates_total"], 1)

    def test_03_false_ai_token_and_description_not_searched(self):
        rows = (item(title="Canadian stationery service"),
                item(ref="CB-2", title="Office products"),
                item(ref="CB-3", title="Air conditioning equipment"))
        r = self.summary(*rows)
        self.assertEqual(r["review_candidates_total"], 0)
        self.assertEqual(r["counts"]["rows_all"], 3)

    def test_04_expired_and_same_day_not_recast_as_future(self):
        r = self.summary(item(closing="2026-11-21"),
                         item(ref="CB-2", closing="2026-11-20"))
        self.assertEqual(r["review_candidates_total"], 0)
        self.assertEqual(r["counts"]["expired_or_same_day"], 2)

    def test_05_unparseable_deadline_remains_in_denominator(self):
        r = self.summary(item(closing="11/30/2026"),
                         item(ref="CB-2", closing="2026-02-30"))
        self.assertEqual(r["review_candidates_total"], 0)
        self.assertEqual(r["counts"]["unparseable_or_missing_closing"], 2)

    def test_06_missing_or_unsafe_reference(self):
        r = self.summary(item(ref=""), item(ref="=2+2", closing="2026-12-02"))
        self.assertEqual(r["counts"]["missing_or_unsafe_identity_title"], 2)

    def test_07_identical_repeated_reference_not_two_buyers(self):
        r = self.summary(item(), item())
        self.assertEqual(r["counts"]["duplicate_identical_rows"], 1)
        self.assertEqual(r["review_candidates_total"], 1)

    def test_08_conflicting_reference_revisions_excluded(self):
        r = self.summary(item(), item(title="Machine learning integration"))
        self.assertEqual(r["review_candidates_total"], 0)
        self.assertEqual(r["counts"]["ambiguous_reference_groups"], 1)

    def test_09_missing_mandatory_header_rejected(self):
        raw = (n.REFERENCE + "," + n.TITLE + "\nCB-1,Software development\n").encode()
        with self.assertRaisesRegex(n.Refusal, "UNSUPPORTED_TENDER_SCHEMA"):
            n.assess(raw, AT)

    def test_10_duplicate_header_rejected(self):
        raw = (n.REFERENCE + "," + n.TITLE + "," + n.TITLE + "," + n.CLOSING + "\n").encode()
        with self.assertRaisesRegex(n.Refusal, "DUPLICATE_HEADERS"):
            n.assess(raw, AT)

    def test_11_embedded_nul_rejected(self):
        with self.assertRaisesRegex(n.Refusal, "NUL_IN_CSV"):
            n.assess(fixture(item()) + b"\x00", AT)

    def test_12_invalid_utf8_rejected(self):
        with self.assertRaisesRegex(n.Refusal, "NOT_UTF8"):
            n.assess(fixture(item()) + b"\xff", AT)

    def test_13_bom_is_permitted_and_bound_to_exact_bytes(self):
        original = fixture(item())
        r = n.assess(b"\xef\xbb\xbf" + original, AT)
        self.assertEqual(r["review_candidates_total"], 1)
        self.assertNotEqual(n.sha256(original), r["source_sha256"])

    def test_14_resource_bounds_not_silent_truncation(self):
        with patch.object(n, "MAX_BYTES", 20):
            with self.assertRaisesRegex(n.Refusal, "SOURCE_BYTES_BOUND"):
                n.assess(fixture(item()), AT)
        with patch.object(n, "MAX_ROWS", 1):
            with self.assertRaisesRegex(n.Refusal, "ROWS_BOUND"):
                n.assess(fixture(item(), item(ref="CB-2")), AT)

    def test_15_formula_title_cannot_be_exported(self):
        r = self.summary(item(title="=SUM(1,2) software development"))
        self.assertEqual(r["review_candidates_total"], 0)

    def test_16_receipt_full_replay_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "registered"
            root.mkdir()
            raw = fixture(item())
            (root / "SOURCE.csv").write_bytes(raw)
            (root / "RECEIPT.json").write_bytes(n.canonical(n.assess(raw, AT)))
            self.assertEqual(n.verify(root)["review_candidates_total"], 1)
            (root / "SOURCE.csv").write_bytes(raw + b"\n")
            with self.assertRaisesRegex(n.Refusal, "SOURCE_OR_RECEIPT_CHANGED"):
                n.verify(root)

    def test_17_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = fixture(item())
            (root / "SOURCE.csv").write_bytes(raw)
            (root / "RECEIPT.json").write_text('{"schema":"a","schema":"b"}')
            with self.assertRaisesRegex(n.Refusal, "DUPLICATE_JSON_KEY"):
                n.verify(root)

    def test_18_symlinked_output_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            target = root / "linked"
            target.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(n.Refusal, "UNSAFE_OUTPUT_DIRECTORY"):
                n.verify(target)

    def test_19_redirect_refused_without_following(self):
        handler = n.NoRedirect()
        with self.assertRaisesRegex(n.Refusal, "REDIRECT_REFUSED"):
            handler.redirect_request(None, None, 302, "Moved", {}, "https://other.example")

    def test_20_invalid_observation_time_is_not_treated_as_current(self):
        with self.assertRaisesRegex(n.Refusal, "INVALID_OBSERVED_AT"):
            n.assess(fixture(item()), "tomorrow")

    def test_21_source_lacks_buyer_does_not_fabricate_one(self):
        r = self.summary(item(buyer=""))
        self.assertIsNone(r["review_candidates"][0]["buyer_from_source"])
        self.assertIsNone(r["review_candidates"][0]["supplier_eligibility"])

    def test_22_no_automatic_commercial_action_or_prices(self):
        r = self.summary(item())
        self.assertEqual(r["actual_business_action"], "NO_BID_NO_DEPLOY_NO_SPENDING")
        self.assertEqual(len(r["competing_business_arrangements"]), 4)
        self.assertFalse(r["usd_3b_trailing365_complete_cost_profit_proven"])


if __name__ == "__main__":
    unittest.main()
