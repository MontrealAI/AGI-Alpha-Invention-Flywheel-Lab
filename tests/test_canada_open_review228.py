"""Offline follow-up: published source is exposed, not a fresh buyer observation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from tools import canada_open_review228 as r

BASE = {
    r.NOTICE: "Request for Proposal",
    r.BUYER: "Public Agency",
    r.BUYER_FR: "Agence publique",
    r.METHOD: "Competitive - Traditional",
    r.DESCRIPTION: "A request for a complete outcome.",
}

def row(**changes):
    return {**BASE, **changes}

class Review228Tests(unittest.TestCase):
    def test_01_actual_buyer_header(self):
        v = r.classify(row())
        self.assertEqual(v["buyer_as_published_en"], "Public Agency")
        self.assertEqual(v["buyer_as_published_fr"], "Agence publique")
        self.assertFalse(v["supplier_eligibility_verified"])
        self.assertFalse(v["qualified_sale_or_paid_customer"])

    def test_02_formula_and_control_injection(self):
        v = r.classify(row(**{r.BUYER: "=2+2", r.BUYER_FR: "Public\nAgency"}))
        self.assertIsNone(v["buyer_as_published_en"])
        self.assertIsNone(v["buyer_as_published_fr"])

    def test_03_rfi_not_purchase(self):
        v = r.classify(row(**{r.NOTICE: "Request for Information"}))
        self.assertEqual(v["notice_interpretation"], "RFI_INFORMATION_GATHERING_NOT_A_PAID_CONTRACT")
        self.assertFalse(v["application_or_bid_authorized"])

    def test_04_itq_publication_date_not_response_deadline(self):
        v = r.classify(row(**{r.NOTICE: "Invitation to Qualify", r.DESCRIPTION:
            "The publication closing date only and does not represent the ITQ response submission deadline."}))
        self.assertEqual(v["closing_date_interpretation"], "PUBLICATION_DATE_NOT_QUALIFICATION_RESPONSE_DEADLINE")

    def test_05_unknown_itq_dates_not_automatically_recategorized(self):
        v = r.classify(row(**{r.NOTICE: "Invitation to Qualify"}))
        self.assertFalse(v["source_text_flags"]["itq_publication_date_not_response_deadline"])
        self.assertEqual(v["notice_interpretation"], "QUALIFICATION_ONLY_NOT_AN_AWARDED_PURCHASE")

    def test_06_restricted_subscription_renewal(self):
        v = r.classify(row(**{r.DESCRIPTION:
            "Standard subscription renewal. Only suppliers who are pre-qualified are eligible."}))
        self.assertEqual(v["notice_interpretation"], "RESTRICTED_INCUMBENT_SUBSCRIPTION_RENEWAL")
        self.assertFalse(v["supplier_eligibility_verified"])

    def test_07_explicit_ai_tool_exclusion_only(self):
        self.assertFalse(r.classify(row())["source_text_flags"]["explicitly_excludes_new_ai_tool_development"])
        v = r.classify(row(**{r.DESCRIPTION: "Project does not involve developing a new AI tool."}))
        self.assertTrue(v["source_text_flags"]["explicitly_excludes_new_ai_tool_development"])

    def test_08_unknown_notice_type_remains_unknown(self):
        v = r.classify(row(**{r.NOTICE: "Other"}))
        self.assertEqual(v["notice_interpretation"], "UNKNOWN_NOTICE_TYPE_REQUIRES_MANUAL_REVIEW")
        self.assertFalse(v["qualified_sale_or_paid_customer"])

    def test_09_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(r.ReviewError, "DUPLICATE_JSON_KEY"):
            json.loads('{"a":1,"a":2}', object_pairs_hook=r.pairs_unique)

    def test_10_changed_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "SOURCE.csv").write_bytes(b"fake")
            (p / "RECEIPT.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(r.ReviewError, "REGISTERED_SOURCE_OR_RECEIPT_CHANGED"):
                r.read_source(p)

    def test_11_symlinked_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            target = p / "real"; target.mkdir()
            link = p / "link"; link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(r.ReviewError, "UNSAFE_SOURCE_DIR"):
                r.read_source(link)

    def test_12_no_network_dependency(self):
        source = Path(r.__file__).read_text()
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertEqual(len(r.SOURCE_SHA256), 64)

    def test_13_registered_artifact_exact_replay_when_provided(self):
        location = os.environ.get("NEED228_SOURCE_DIR")
        if not location:
            self.skipTest("historical external artifact not mounted, never silently retrieved")
        result = r.assess(location)
        self.assertEqual(result["source_rows"], 937)
        self.assertEqual(result["registered_matches"], 6)
        self.assertEqual(len(result["reviewed_rows"]), 6)
        self.assertTrue(all(item["buyer_as_published_en"] for item in result["reviewed_rows"]))
        self.assertFalse(result["financial_ledger_touched"])

if __name__ == "__main__":
    unittest.main()
