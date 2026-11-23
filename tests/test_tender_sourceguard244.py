"""Independent preregistered source/readiness/negative regressions for TENDER244."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location("tender244", ROOT / "tools/tender_sourceguard244.py")
mod = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(mod)
CASE = json.loads((ROOT / "research/tender-sourceguard244/CASE_30008508.json").read_text())


class TestSourceGuard(unittest.TestCase):
    def test_real_three_authorities_and_third_party_conflict(self):
        result = mod.reconcile(copy.deepcopy(CASE))
        self.assertEqual(result["observed_official_instant_utc"], "2026-11-23T19:00:00+00:00")
        self.assertEqual(result["schedule_status"], "INDETERMINATE")
        self.assertFalse(result["final_current_deadline_verified"])
        self.assertEqual(result["commercial_decision"], "HOLD_NO_BID")
        self.assertTrue(result["external_discrepancies"][0]["conflicts_with_known_official"])
        self.assertEqual(result["source_evidence_tier"], "MANUALLY_EXTRACTED_PUBLIC_URL_NOT_BYTE_VERIFIED")

    def test_missing_middle_addendum_is_explicitly_incomplete(self):
        x = copy.deepcopy(CASE)
        x["documents"] = [d for d in x["documents"] if d["sequence"] != 1]
        self.assertEqual(mod.reconcile(x)["missing_official_sequences"], [1])
        self.assertEqual(mod.reconcile(x)["observed_official_instant_utc"], None)

    def test_official_authority_conflict_blocks_single_instant(self):
        x = copy.deepcopy(CASE)
        x["documents"][2]["reading_local"] = "2026-11-24T14:00:00"
        result = mod.reconcile(x)
        self.assertEqual(result["schedule_status"], "CONFLICT")
        self.assertIsNone(result["observed_official_instant_utc"])

    def test_duplicate_authoritative_sequence_refused(self):
        x = copy.deepcopy(CASE)
        x["documents"].append({**x["documents"][2], "id": "other", "url": x["documents"][2]["url"]})
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OFFICIAL_SEQUENCE"):
            mod.reconcile(x)

    def test_ambiguous_eastern_time_refused(self):
        x = copy.deepcopy(CASE)
        x["documents"][0]["zone"] = "ET"
        with self.assertRaisesRegex(ValueError, "EXPLICIT_EST_EDT_OR_UTC_REQUIRED"):
            mod.reconcile(x)

    def test_false_dst_label_refused_on_november(self):
        x = copy.deepcopy(CASE)
        x["documents"][1]["zone"] = "EDT"
        with self.assertRaisesRegex(ValueError, "TIMEZONE_LABEL_CONFLICTS"):
            mod.reconcile(x)

    def test_winter_est_summer_edt(self):
        self.assertEqual(mod._datetime("2026-07-01T14:00:00", "EDT").isoformat(),
                         "2026-07-01T14:00:00-04:00")
        with self.assertRaisesRegex(ValueError, "TIMEZONE_LABEL_CONFLICTS"):
            mod._datetime("2026-07-01T14:00:00", "EST")

    def test_official_domain_masquerade_rejected(self):
        x = copy.deepcopy(CASE)
        x["documents"][1]["url"] = "https://canadabuys.canada.ca.evil.test/addendum.pdf"
        with self.assertRaisesRegex(ValueError, "OFFICIAL_DOMAIN"):
            mod.reconcile(x)

    def test_cross_solicitation_source_rejected(self):
        x = copy.deepcopy(CASE)
        x["documents"][2]["solicitation"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "CROSS_SOLICITATION"):
            mod.reconcile(x)

    def test_unknown_location_rejected(self):
        x = copy.deepcopy(CASE)
        x["documents"][1]["locator"] = ""
        with self.assertRaisesRegex(ValueError, "MISSING_PROVENANCE_LOCATOR"):
            mod.reconcile(x)

    def test_self_attested_closure_is_not_verified(self):
        x = copy.deepcopy(CASE)
        x["document_inventory_closed"] = True
        result = mod.reconcile(x)
        self.assertEqual(result["schedule_status"], "SELF_ATTESTED_CONSISTENT")
        self.assertFalse(result["final_current_deadline_verified"])

    def test_all_claimed_readiness_still_no_auto_bid(self):
        x = copy.deepcopy(CASE)
        x["commercial_readiness"] = {k: True for k in x["commercial_readiness"]}
        self.assertEqual(mod.reconcile(x)["commercial_decision"], "REVIEW_REQUIRED_NO_AUTO_BID")

    def test_readiness_false_and_unknown_block(self):
        x = copy.deepcopy(CASE)
        x["commercial_readiness"]["subcontract_permission"] = False
        self.assertIn("subcontract_permission", mod.reconcile(x)["unqualified_requirements"])
        self.assertEqual(mod.reconcile(x)["commercial_decision"], "HOLD_NO_BID")

    def test_duplicate_json_field_refused_by_cli(self):
        path = ROOT / "research/tender-sourceguard244/CASE_30008508.json"
        self.assertEqual(subprocess.run([sys.executable, str(ROOT / "tools/tender_sourceguard244.py"),
                                         "--input", str(path)], capture_output=True, text=True).returncode, 0)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
            json.loads('{"schema":1,"schema":2}', object_pairs_hook=mod._reject_duplicate_keys)

    def test_invalid_date_refused(self):
        x = copy.deepcopy(CASE)
        x["documents"][1]["reading_local"] = "2026-02-29T14:00:00"
        with self.assertRaisesRegex(ValueError, "INVALID_CANONICAL_LOCAL_DATETIME"):
            mod.reconcile(x)


if __name__ == "__main__":
    unittest.main()
