"""Source-bound GENESIS099 canonical cost-chronology repair qualification.

Frozen before implementation: campaign/genesis-chronology099/PREREGISTRATION.md
at ae4bec21d6e1e497c17308a0f04d345d2dbfc0fa. Not a new
commercial experiment, not a replacement for GENESIS098 historical C1.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from genesis_enterprise import native
from genesis_enterprise.policy import canonical

ROOT = Path(__file__).resolve().parents[1]


class CanonicalOverheadChronology099(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.output = self.path / "case"
        self.protocol = json.loads(
            (ROOT / "campaign/genesis-enterprise-002/PROTOCOL.json").read_text()
        )

    def register(self):
        frozen = self.path / "protocol.json"
        frozen.write_bytes(canonical(self.protocol))
        native.register(ROOT, self.output, frozen)

    def cost_rows(self):
        export = json.loads((self.output / "public/native-export.json").read_text())
        return [a for a in export["ledger"]["actions"] if a["op"] == "cost"]

    def test_a_registered_unmodified_operating_costs_audit(self):
        self.register()
        result = native.operate(self.output)
        self.assertTrue(result["complete"])
        self.assertTrue(result["native_audit_accepted"])
        jobs = json.loads((self.output / "MANIFEST.json").read_text())["jobs"]
        actions = self.cost_rows()
        for index, job in enumerate(jobs):
            for kind in ("acquisition", "maintenance"):
                ident = f"genesis-{kind}-{job['id']}"
                matches = [r for r in actions if r["args"]["id"] == ident]
                self.assertEqual(len(matches), 1, ident)
                self.assertEqual(matches[0]["day"], 24 * (index + 1))
                self.assertEqual(matches[0]["args"]["amount"], self.protocol[kind])
        self.assertTrue(native.audit(self.output)["native_audit_accepted"])
        print("GENESIS099_A_CANONICAL_ACCEPT_CORRECT_HOURS_AND_AMOUNT")

    def test_b_real_native_early_acquisition_must_fail_canonical_audit(self):
        from flexibility063.native import BusinessAccount
        self.register()
        original = BusinessAccount.cost
        observed = []
        def early_first(account, ident, amount, hour):
            if ident.startswith("genesis-acquisition-") and not observed:
                self.assertEqual(hour, 24)
                observed.append((ident, hour, hour - 1))
                return original(account, ident, amount, hour - 1)
            return original(account, ident, amount, hour)
        with patch.object(BusinessAccount, "cost", early_first):
            with self.assertRaisesRegex(ValueError, "REGISTERED_FIXED_COST_CHANGED"):
                native.operate(self.output)
        self.assertEqual(len(observed), 1)
        print("GENESIS099_B_CANONICAL_REJECTS_EARLY_NATIVE_COST")

    def test_c_missing_native_maintenance_must_fail_canonical_audit(self):
        from flexibility063.native import BusinessAccount
        self.register()
        original = BusinessAccount.cost
        omitted = []
        def omit_first(account, ident, amount, hour):
            if ident.startswith("genesis-maintenance-") and not omitted:
                self.assertEqual(hour, 24)
                omitted.append(ident)
                return None
            return original(account, ident, amount, hour)
        with patch.object(BusinessAccount, "cost", omit_first):
            with self.assertRaisesRegex(ValueError, "REGISTERED_FIXED_COST_CHANGED"):
                native.operate(self.output)
        self.assertEqual(len(omitted), 1)
        print("GENESIS099_C_CANONICAL_REJECTS_MISSING_NATIVE_COST")

    def test_d_refusal_keeps_registered_costs_and_zero_revenue(self):
        self.protocol["offer"]["value"] = 0
        self.register()
        result = native.operate(self.output)
        self.assertTrue(result["complete"])
        self.assertTrue(result["native_audit_accepted"])
        self.assertEqual(result["accepted_collected_deliveries"], 0)
        self.assertEqual(result["actual_revenue"], 0)
        jobs = json.loads((self.output / "MANIFEST.json").read_text())["jobs"]
        actions = self.cost_rows()
        for i, job in enumerate(jobs):
            for kind in ("acquisition", "maintenance"):
                ident = f"genesis-{kind}-{job['id']}"
                costs = [a for a in actions if a["args"]["id"] == ident]
                self.assertEqual(len(costs), 1)
                self.assertEqual(costs[0]["day"], 24 * (i + 1))
                self.assertEqual(costs[0]["args"]["amount"], self.protocol[kind])
        self.assertTrue(native.audit(self.output)["native_audit_accepted"])
        print("GENESIS099_D_REFUSAL_CHARGED_CORRECTLY_NO_ACTUAL_REVENUE")


if __name__ == "__main__":
    unittest.main()
