"""Pre-frozen 076 acceptance: no invented buyers, funding, or authority."""
import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("commercial076_admission", HERE / "admission.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
BASE = json.loads((HERE / "SSC_FACTS.json").read_text())

def run(document, today="2026-11-15"):
    return mod.evaluate(document, on_date=today)

def synthetic_ready(data):
    arrangement = data["arrangements"][0]
    for name in mod.REQUIRED:
        arrangement["criteria"][name] = {
            "status": "claimed_verified",
            "source": "https://example.invalid/synthetic-not-real",
            "checked_on": "2026-11-15",
            "independent": True,
        }
    arrangement["costs_cents"] = {k: 1000 for k in mod.COSTS}
    arrangement["current_available_cash_cents"] = 1000000
    arrangement["peak_cash_required_cents"] = 500000
    arrangement["proposed_price_cents"] = 1000000
    return arrangement

class PreregisteredAdmission076(unittest.TestCase):
    def test_01_actual_ssc_is_hold_for_three_routes(self):
        result = run(BASE)
        self.assertEqual([x["decision"] for x in result["arrangements"]],
                         ["HOLD_NO_BID"] * 3 + ["ADMISSIBLE_NO_DEPLOY"])
        self.assertTrue(all(x["hypothetical_margin_cents"] is None for x in result["arrangements"]))

    def test_02_max_award_is_not_collected_revenue(self):
        data = copy.deepcopy(BASE)
        data["arrangements"][0]["proposed_price_cents"] = 200000000
        result = run(data)
        self.assertEqual(result["arrangements"][0]["decision"], "HOLD_NO_BID")
        self.assertEqual(result["external_collections_cents"], 0)
        self.assertEqual(result["contract_awards_observed"], 0)
        self.assertIsNone(result["actual_profit_cents"])

    def test_03_rfi_never_counts_as_contract(self):
        data = copy.deepcopy(BASE)
        synthetic_ready(data)
        data["opportunity"]["kind"] = "RFI"
        result = run(data)
        self.assertIn("nonpurchase_request_for_information", result["arrangements"][0]["unresolved"])
        self.assertEqual(result["arrangements"][0]["decision"], "HOLD_NO_BID")

    def test_04_stale_source_refuses_progress(self):
        data = copy.deepcopy(BASE)
        synthetic_ready(data)
        data["opportunity"]["checked_on"] = "2026-10-31"
        result = run(data)
        self.assertIn("official_source_stale_or_closed", result["arrangements"][0]["unresolved"])
        self.assertEqual(result["arrangements"][0]["decision"], "HOLD_NO_BID")

    def test_05_missing_claim_and_cost_rejects_model_profit(self):
        data = copy.deepcopy(BASE)
        arrangement = synthetic_ready(data)
        arrangement["costs_cents"]["remaining_claims"] = None
        result = run(data)
        self.assertIn("complete_costs_unknown", result["arrangements"][0]["unresolved"])
        self.assertIsNone(result["arrangements"][0]["hypothetical_margin_cents"])

    def test_06_all_synthetic_conditions_are_review_only(self):
        data = copy.deepcopy(BASE)
        synthetic_ready(data)
        result = run(data)
        self.assertEqual(result["arrangements"][0]["decision"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertGreater(result["arrangements"][0]["hypothetical_margin_cents"], 0)
        self.assertFalse(result["authorized_to_bid"])
        self.assertFalse(result["authorized_to_deploy"])
        self.assertIsNone(result["actual_profit_cents"])
        self.assertFalse(result["operating_ledger_modified"])

    def test_07_failed_trl_blocks_favorable_hypothetical_margin(self):
        data = copy.deepcopy(BASE)
        arrangement = synthetic_ready(data)
        arrangement["criteria"]["trl_5_to_9"]["status"] = "failed"
        result = run(data)
        self.assertEqual(result["arrangements"][0]["decision"], "HOLD_NO_BID")
        self.assertIn("trl_5_to_9", result["arrangements"][0]["unresolved"])

    def test_08_no_deploy_is_always_admissible(self):
        self.assertEqual(run(BASE)["arrangements"][3], {
            "route": "no_deploy",
            "decision": "ADMISSIBLE_NO_DEPLOY",
            "unresolved": [],
            "hypothetical_margin_cents": None,
        })

    def test_09_repeat_is_deterministic_and_unmutating(self):
        data = copy.deepcopy(BASE)
        original = json.dumps(data, sort_keys=True)
        self.assertEqual(run(data), run(data))
        self.assertEqual(original, json.dumps(data, sort_keys=True))
        self.assertEqual(run(data)["input_sha256"], run(BASE)["input_sha256"])

    def test_10_negative_bool_cost_and_duplicate_json_rejected(self):
        for bad in (-1, True):
            data = copy.deepcopy(BASE)
            data["arrangements"][0]["costs_cents"]["repair"] = bad
            with self.assertRaises(ValueError):
                run(data)
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "bad.json"
            path.write_text('{"schema":1,"schema":2}')
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
                mod.load(path)

    def test_11_no_writer_path_from_evidence_url(self):
        data = copy.deepcopy(BASE)
        synthetic_ready(data)
        with patch("pathlib.Path.write_text", side_effect=AssertionError("MUST_NOT_WRITE")):
            result = run(data)
        self.assertEqual(result["arrangements"][0]["decision"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertEqual(result["scope"], "PUBLIC_SOLICITATION_AND_UNVERIFIED_RESEARCH_GATE_NOT_PURCHASER_ACCEPTANCE")

if __name__ == "__main__":
    unittest.main(verbosity=2)
