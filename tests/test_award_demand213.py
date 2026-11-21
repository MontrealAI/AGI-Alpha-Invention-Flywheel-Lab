"""AWARD-DEMAND213 deterministic offline tests. ALL rows here are synthetic."""
import csv
from datetime import datetime
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import award_demand213 as m


AS_OF = "2026-11-21T12:00:00Z"
HEADERS = [m.TITLE_EN, m.TITLE_FR, m.STATUS, m.SOLICITATION]


def award(title="Artificial Intelligence workflow", fr="", status="Active",
          ref="TEST-ARTIFICIAL-001"):
    return {m.TITLE_EN: title, m.TITLE_FR: fr,
            m.STATUS: status, m.SOLICITATION: ref}


def source(rows=None, headers=None):
    buf = StringIO()
    fieldnames = headers if headers is not None else HEADERS
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in ([award()] if rows is None else rows):
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


class SourceContracts(unittest.TestCase):
    def test_active_public_award_is_never_payment_or_bid_approval(self):
        receipt = m.assess(source(), AS_OF)
        self.assertEqual(receipt["distinct_matching_active_solicitation_refs"], 1)
        self.assertEqual(receipt["rows_total"], 1)
        self.assertIsNone(receipt["government_payments_proven"])
        self.assertIsNone(receipt["montreal_ai_cash_collected"])
        self.assertIsNone(receipt["complete_cost_profit"])
        self.assertIsNone(receipt["repeat_buyers_proven"])
        self.assertEqual(receipt["operating_action"], "NO_BID_NO_DEPLOY_NO_FINANCIAL_AUTHORIZATION")
        self.assertFalse(receipt["us_3b_trailing365_complete_cost_profit_qualified"])

    def test_french_whole_phrase_is_discovered(self):
        r = m.assess(source([award(title="Service informatique",
                                   fr="Projet intelligence artificielle")]), AS_OF)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 1)

    def test_generic_ai_substring_is_not_enough(self):
        r = m.assess(source([award(title="Canadian supplier")]), AS_OF)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 0)

    def test_machine_learning_and_genererative_ai(self):
        rows = [award(title="Machine learning maintenance", ref="s1"),
                award(title="Generative AI service", ref="s2")]
        r = m.assess(source(rows), AS_OF)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 2)

    def test_cancelled_or_unknown_status_is_not_award(self):
        rows = [award(status="Cancelled", ref="s1"),
                award(status="", ref="s2"), award(status="Open", ref="s3")]
        r = m.assess(source(rows), AS_OF)
        self.assertEqual(r["keyword_matching_nonactive_or_unverified_rows"], 3)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 0)

    def test_duplicate_solicitation_is_not_new_customer(self):
        rows = [award(ref="  S100  "), award(ref="s100")]
        r = m.assess(source(rows), AS_OF)
        self.assertEqual(r["keyword_matching_active_award_rows"], 2)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 1)

    def test_late_duplicate_revision_deterministic(self):
        a = award(ref="S100", title="Artificial Intelligence b")
        b = award(ref="S100", title="Artificial Intelligence a")
        self.assertEqual(m.assess(source([a,b]), AS_OF)["published_entries"],
                         m.assess(source([b,a]), AS_OF)["published_entries"])

    def test_ref_is_required(self):
        r = m.assess(source([award(ref="")]), AS_OF)
        self.assertEqual(r["active_rows_missing_solicitation_identity"], 1)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 0)

    def test_empty_file_with_header_is_truly_no_match(self):
        r = m.assess(source([]), AS_OF)
        self.assertEqual(r["rows_total"], 0)
        self.assertEqual(r["research_next_action"], "NO_QUALIFIED_MATCH_IN_FROZEN_SOURCE")

    def test_unknown_required_header_is_schema_refusal(self):
        raw = source([]).replace(m.STATUS.encode(), b"status-gibberish")
        with self.assertRaisesRegex(m.Refusal, "UNSUPPORTED_AWARD_SCHEMA"):
            m.assess(raw, AS_OF)

    def test_duplicate_header_is_schema_refusal(self):
        raw = source([]).replace(m.TITLE_FR.encode(), m.TITLE_EN.encode())
        with self.assertRaisesRegex(m.Refusal, "MISSING_OR_DUPLICATE_HEADERS"):
            m.assess(raw, AS_OF)

    def test_ragged_row_fails(self):
        with self.assertRaisesRegex(m.Refusal, "RAGGED_CSV_EXTRA_COLUMNS"):
            m.assess(source([]) + b"a,b,c,d,e\n", AS_OF)

    def test_invalid_utf8_nul_and_nonbytes(self):
        for raw in (b"\xff", source() + b"\x00", b"", b"q"*(m.MAX_BYTES + 1)):
            with self.assertRaises(m.Refusal):
                m.assess(raw, AS_OF)

    def test_invalid_observation_time(self):
        for stamp in ("2026-11-21", "2026-11-21T12:00:00", "tomorrow", "2026-13-00T00:00:00Z"):
            with self.assertRaises(m.Refusal):
                m.assess(source(), stamp)

    def test_formula_injected_identity_not_emitted(self):
        r = m.assess(source([award(ref="=HYPERLINK(1)", title="Artificial Intelligence")]), AS_OF)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 0)
        self.assertEqual(r["active_rows_missing_solicitation_identity"], 1)

    def test_formula_injected_title_not_emitted(self):
        r = m.assess(source([award(title="=Artificial Intelligence")]), AS_OF)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 0)

    def test_fixed_25_visible_but_complete_denominator(self):
        rows = [award(ref="S%03d"%i) for i in range(30)]
        r = m.assess(source(rows), AS_OF)
        self.assertEqual(r["distinct_matching_active_solicitation_refs"], 30)
        self.assertTrue(r["published_entries_truncated"])
        self.assertEqual(len(r["published_entries"]), 25)

    def test_canonical_unchanged_and_sha_binds_bytes(self):
        raw = source()
        a, b = m.assess(raw, AS_OF), m.assess(raw, AS_OF)
        self.assertEqual(m.canonical(a), m.canonical(b))
        self.assertEqual(a["source_sha256"], m.sha256(raw))
        self.assertNotEqual(m.assess(source([award(ref="S2")]), AS_OF)["source_sha256"], a["source_sha256"])

    def test_verify_rejects_source_and_receipt_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = source()
            receipt = m.assess(raw, AS_OF)
            (root / "SOURCE.csv").write_bytes(raw)
            (root / "RECEIPT.json").write_bytes(m.canonical(receipt))
            self.assertEqual(m.verify(root), receipt)
            (root / "SOURCE.csv").write_bytes(source([award(ref="changed")]))
            with self.assertRaisesRegex(m.Refusal, "SOURCE_OR_RECEIPT_CHANGED"):
                m.verify(root)
            (root / "SOURCE.csv").write_bytes(raw)
            (root / "RECEIPT.json").write_bytes(b'{"schema":"x"}')
            with self.assertRaisesRegex(m.Refusal, "BAD_RECEIPT_SCHEMA"):
                m.verify(root)

    def test_symlink_output_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SOURCE.csv").write_bytes(source())
            (root / "RECEIPT.json").symlink_to(root / "SOURCE.csv")
            with self.assertRaisesRegex(m.Refusal, "UNSAFE_OUTPUT_FILE"):
                m.verify(root)

    def test_no_redirect_in_fetch(self):
        handler = m.NoRedirect()
        with self.assertRaisesRegex(m.Refusal, "REDIRECT_REFUSED"):
            handler.redirect_request(None, None, 302, "found", {}, "https://another.example/")
        

if __name__ == "__main__":
    unittest.main()
