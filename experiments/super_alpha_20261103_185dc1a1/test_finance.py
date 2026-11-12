import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount
from experiments.super_alpha_20261103_185dc1a1 import finance


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = finance.PREFIX + "TEST_PROTOCOL.json"


def protocol():
    amounts = (1200, 1800, 900, 400, 500, 200, 100, 365)
    hours = (0, 24, 48, 72, 96, 120, 144, 8759)
    return {"source_paths": [finance.MODULE], "finance": {
        "opening_microUSD": finance.OPENING, "operating_end_hour": 8760,
        "cost_basis": finance.COST_BASIS,
        "costs": [{"id": c, "category": c, "hour": h, "amount_microUSD": a * 1_000_000,
                   "basis": "Authored test envelope; not measured billing or labor."}
                  for c, h, a in zip(finance.CATEGORIES, hours, amounts)],
        "zero_cost_categories": {c: "Not applicable to the cost-only test account." for c in finance.ZERO_CATEGORIES}}}


class NativeDiscoveryFinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="super-alpha-finance-test-")
        self.root = Path(self.temp.name) / "source"
        self.output = Path(self.temp.name) / "account"
        p = protocol()
        paths = set(finance.required_paths(p, PROTOCOL_PATH)) - {PROTOCOL_PATH}
        finance._copy_source(ROOT, self.root, finance._source_hashes(ROOT, paths))
        finance._write(self.root / PROTOCOL_PATH, p)

    def tearDown(self):
        self.temp.cleanup()

    def run_account(self, **kwargs):
        return finance.run(self.root, PROTOCOL_PATH, self.output, **kwargs)

    def test_exact_capital_full_loss_no_sales_and_public_reproduction(self):
        r = self.run_account()
        self.assertTrue(r["complete"])
        self.assertEqual(r["costs_committed"], 8)
        s = r["financial_summary_microUSD"]
        self.assertEqual((s["profit"], s["cash"], s["available"]), (-5_465_000_000, 94_535_000_000, 94_535_000_000))
        self.assertEqual((s["revenue"], s["collections"], s["payables"], s["tailReserve"], s["unrestrictedEarned"]), (0, 0, 0, 0, 0))
        self.assertEqual(r["trailing_profit"]["trailing_365_day_profit_microUSD"], -5_465_000_000)
        self.assertIsNone(r["actual_model_host_billing_microUSD"])
        evidence = finance._read(self.output / "PUBLIC_EVIDENCE.json")
        self.assertEqual(evidence["native_export"]["ledger"]["orders"], [])
        self.assertEqual(len(evidence["manifest"]["jobs"]), 96)
        self.assertEqual(len(evidence["manifest"]["attempts"]), 3)
        self.assertTrue(finance.audit(self.root, self.output)["accepted"])
        exported_bytes = (self.output / "PUBLIC_EVIDENCE.json").read_bytes()
        for key_path in self.output.glob("*.adaptive-simulation-key"):
            self.assertNotIn(key_path.read_bytes().hex().encode(), exported_bytes)

    def test_resume_same_account_preserves_history_without_duplicate_expenses(self):
        first = self.run_account(max_new_costs=3)
        self.assertFalse(first["complete"])
        self.assertIsNone(first["trailing_profit"]["trailing_365_day_profit_microUSD"])
        original_contract = first["account_contract"]
        partial = finance._read(self.output / "PUBLIC_EVIDENCE.json")["native_export"]["ledger"]["actions"]
        completed = self.run_account()
        original = (self.output / "PUBLIC_EVIDENCE.json").read_bytes()
        self.assertEqual(completed["account_contract"], original_contract)
        full = finance._read(self.output / "PUBLIC_EVIDENCE.json")["native_export"]["ledger"]["actions"]
        self.assertEqual(full[:len(partial)], partial)
        self.assertEqual(len(full), 8)
        self.assertEqual(self.run_account(), completed)
        self.assertEqual((self.output / "PUBLIC_EVIDENCE.json").read_bytes(), original)

    def test_commit_before_checkpoint_recovers_without_reseed_or_double_charge(self):
        original = JournalAccount.spend
        def crash_after_commit(account, *args, **kwargs):
            original(account, *args, **kwargs)
            raise InterruptedError("after native spend before driver checkpoint")
        with patch.object(JournalAccount, "spend", crash_after_commit), self.assertRaises(InterruptedError):
            self.run_account()
        r = self.run_account()
        self.assertEqual(r["costs_committed"], 8)
        self.assertEqual(r["financial_summary_microUSD"]["expenses"], 5_465_000_000)
        self.assertTrue(finance.audit(self.root, self.output)["accepted"])

    def test_changed_registered_costs_or_source_cannot_resume(self):
        self.run_account(max_new_costs=2)
        p = finance._read(self.root / PROTOCOL_PATH)
        p["finance"]["costs"][0]["amount_microUSD"] += 1
        finance._write(self.root / PROTOCOL_PATH, p)
        with self.assertRaisesRegex(ValueError, "SOURCE_CHANGED"):
            self.run_account()

    def test_public_report_or_cost_work_tampering_rejected(self):
        self.run_account()
        evidence = finance._read(self.output / "PUBLIC_EVIDENCE.json")
        changed = copy.deepcopy(evidence)
        changed["report"]["financial_summary_microUSD"]["profit"] += 1
        with self.assertRaisesRegex(ValueError, "REPORT_CHANGED"):
            finance.audit_public(self.root, changed)
        changed = copy.deepcopy(evidence)
        changed["native_export"]["connected_journal"]["entries"][0]["request"]["work"]["protocol_sha256"] = "0" * 64
        changed["native_export"]["connected_journal_sha256"] = digest(changed["native_export"]["connected_journal"])
        with self.assertRaises(ValueError):
            finance.audit_public(self.root, changed)

    def test_empty_checkpoint_does_not_claim_year_or_create_revenue(self):
        r = self.run_account(max_new_costs=0)
        self.assertEqual(r["financial_summary_microUSD"]["cash"], finance.OPENING)
        self.assertFalse(r["complete"])
        self.assertIsNone(r["trailing_profit"]["trailing_365_day_profit_microUSD"])
        self.assertEqual(self.run_account()["costs_committed"], 8)

    def test_exact_capital_cost_types_horizon_and_complete_categories_enforced(self):
        for field, value in [("opening_microUSD", finance.OPENING + 1), ("operating_end_hour", 8759)]:
            p = protocol(); p["finance"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                finance.validate_protocol(p)
        p = protocol(); p["finance"]["costs"][0]["amount_microUSD"] = True
        with self.assertRaises(ValueError):
            finance.validate_protocol(p)
        p = protocol(); del p["finance"]["zero_cost_categories"]["tax"]
        with self.assertRaises(ValueError):
            finance.validate_protocol(p)

    def test_positive_profit_without_available_cash_defers_without_erasure(self):
        manifest = finance.prepare_services(self.root, "liquidity_control_fixtures")
        path = Path(self.temp.name) / "separate_liquidity_control.sqlite"
        with JournalAccount(self.root, manifest, path, opening=1_000_000_000, working=0,
                            contract="standalone-native-liquidity-control-not-research-product") as account:
            job = next(j for j in manifest["jobs"] if j["service_id"] == "reconciliation" and j["accepted"])
            account.execute("wallet", {"buyer": "control-buyer", "amount": 100_000_000}, 0)
            account.execute("offer", {"id": "control-order", "buyer": "control-buyer", "price": 100_000_000,
                                      "job_id": job["id"], "deadline": 100}, 0)
            for action in ("consent", "fund", "prepare", "release"):
                account.execute("event", {"id": "control-order", "action": action, "event_id": "control-" + action}, 0)
            account.cost("baseline-control-complete-cost", 10_000_000, 0)
            before = account.export()
            summary = before["ledger"]["summary"]
            self.assertEqual(summary["profit"], 90_000_000)
            requested = summary["available"] + 1
            receipt = account.spend("illiquid-positive-profit-control", "standalone_financial_regression", requested,
                                    1, {"scope": "Existing baseline financial control only; no confidential-capability product sale."},
                                    1, allow_seed=True)
            self.assertIsNone(receipt)
            self.assertEqual(account.export(), before)
            after = account.snapshot()["summary"]
            self.assertEqual(after["profit"], 90_000_000)
            self.assertEqual(after["available"], summary["available"])
            self.assertTrue(account.audit()["accepted"])


if __name__ == "__main__":
    unittest.main()
