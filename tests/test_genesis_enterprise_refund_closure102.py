"""GENESIS102 frozen selected-order refund closure tests on genuine native accounts.

Protocol: campaign/genesis-refund-closure102/PREREGISTRATION.md.
Disposable signed native finance is never edited, reset, or impersonated.
"""
from pathlib import Path
import tempfile
import unittest

from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import audit_journal
from flexibility063.native import BusinessAccount
from genesis_enterprise import native
from genesis_enterprise.policy import choose

ROOT = Path(__file__).resolve().parents[1]


class Genesis102SelectedOrderRefund(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="genesis102-")
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "operation"
        native.register(ROOT, self.output, ROOT / "campaign/genesis-enterprise-002/PROTOCOL.json")

    def _native_selected_without_production(self, *, settle):
        p, manifest, _, reg = native._bound(self.output)
        job = manifest["jobs"][0]
        ident, hour = job["id"], 24
        order = "g002-" + ident
        state = {"binding": reg["binding"], "index": 0, "phase": "refund",
                 "rows": [], "active": None}
        with BusinessAccount(
            self.output / "source", manifest, self.output / "private-disposable",
            opening=p["opening"], working=0, contract=reg["contract"],
        ) as account:
            if p["development"]:
                account.cost("genesis-development", p["development"], 0)
            account.advance(hour)
            if p["acquisition"]:
                account.cost("genesis-acquisition-" + ident, p["acquisition"], hour)
            if p["maintenance"]:
                account.cost("genesis-maintenance-" + ident, p["maintenance"], hour)
            summary = account.export()["ledger"]["summary"]
            observed = {k: summary[k] for k in ("available", "unrestrictedEarned")}
            decision = choose(
                p["offer"], p["tools"], available=summary["available"],
                earned=summary["unrestrictedEarned"],
                seed_allowed=p["first_delivery_may_use_seed"],
            )
            picked = decision["selected"]
            self.assertIsNotNone(picked)
            terms = prospective_terms(
                order, picked["price"], hour + 10, hour + 2,
                residual=p["offer"]["reserve"] - p["offer"]["fee"],
                fee=p["offer"]["fee"],
                counterparty_obligations=(
                    "Synthetic purchase of independently checked computational dispatch only. "
                    "No physical energy delivery or real customer money."
                ),
            )
            account.begin_order(
                ident, order, "buyer-" + order, picked["price"],
                p["offer"]["budget"], hour, hour + 3, terms,
            )
            row = {
                "job_id": ident, "decision": decision, "decision_state": observed,
                "accepted": False, "resource_receipt": None,
                "artifact_sha256": None, "ordinary_accepted": None,
                "construction_cpu_seconds": None,
            }
            if settle != "pending":
                if settle == "on_time":
                    account.refund(order, hour + 2)
                elif settle == "late":
                    account.refund(order, hour + 3)
                elif settle != "missing":
                    raise AssertionError(settle)
                native._tax(account, p, ident, hour + 3)
                state.update(index=1, phase="overhead", rows=[row], active=None)
            else:
                state["active"] = row
            exported = account.export()
            self.assertTrue(account.audit()["accepted"])
        native._save(self.output / "public/native-export.json", exported)
        native._save(self.output / "public/execution.json", state)
        self.assertTrue(audit_journal(
            exported, root=self.output / "source", manifest=manifest
        )["accepted"])
        return exported

    def test_C0_original_funded_pilot_and_resume_are_unaffected(self):
        verdict = native.operate(self.output)
        self.assertTrue(verdict["accepted"])
        self.assertTrue(verdict["complete"])
        self.assertTrue(verdict["conditional_self_funding"])
        snapshot = (self.output / "public/native-export.json").read_bytes()
        self.assertEqual(native.audit(self.output), verdict)
        self.assertEqual(native.operate(self.output), verdict)
        self.assertEqual((self.output / "public/native-export.json").read_bytes(), snapshot)

    def test_C1_selected_no_production_with_on_time_real_refund_passes(self):
        exported = self._native_selected_without_production(settle="on_time")
        self.assertEqual(exported["ledger"]["summary"]["collections"], 0)
        verdict = native.audit(self.output)
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["complete"])
        self.assertEqual(verdict["accepted_collected_deliveries"], 0)

    def test_C2_selected_no_production_without_refund_is_rejected(self):
        exported = self._native_selected_without_production(settle="missing")
        self.assertGreater(exported["ledger"]["summary"]["custodyReserve"], 0)
        with self.assertRaisesRegex(ValueError, "^REGISTERED_UNREFUNDED_SELECTED_ORDER$"):
            native.audit(self.output)

    def test_C3_selected_no_production_with_late_refund_is_rejected(self):
        self._native_selected_without_production(settle="late")
        with self.assertRaisesRegex(ValueError, "^REGISTERED_UNREFUNDED_SELECTED_ORDER$"):
            native.audit(self.output)

    def test_C4_active_unfinished_refund_phase_does_not_require_future_event(self):
        self._native_selected_without_production(settle="pending")
        verdict = native.audit(self.output)
        self.assertTrue(verdict["accepted"])
        self.assertFalse(verdict["complete"])


if __name__ == "__main__":
    unittest.main()
