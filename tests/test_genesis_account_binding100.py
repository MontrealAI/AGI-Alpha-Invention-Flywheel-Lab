"""GENESIS100: source-bound registration vs real canonical native-account authority.

Protocol frozen at 9a5817b96a86068e1991811cebeabf0edad802be.
Simulation-only disposable accounts; no old account or signer is accessed.
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


class RegisteredAccountConfiguration100(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.output = self.base / "registered-business"
        self.protocol = json.loads(
            (ROOT / "campaign/genesis-enterprise-002/PROTOCOL.json").read_text(encoding="utf-8")
        )
        freeze = self.base / "protocol.json"
        freeze.write_bytes(canonical(self.protocol))
        native.register(ROOT, self.output, freeze)

    def _override_actual_native_authority(self, *, opening=None, working=None, contract=None):
        from flexibility063.native import BusinessAccount

        real_init = BusinessAccount.__init__
        created = []

        def create_different_native_account(account, root, manifest, path, *,
                                            opening, working, contract):
            changed = {
                "opening": opening,
                "working": working,
                "contract": contract,
            }
            if opening_override is not None:
                changed["opening"] = opening_override
            if working_override is not None:
                changed["working"] = working_override
            if contract_override is not None:
                changed["contract"] = contract_override
            created.append(changed.copy())
            return real_init(account, root, manifest, path, **changed)

        opening_override, working_override, contract_override = opening, working, contract
        with patch.object(BusinessAccount, "__init__", create_different_native_account):
            with self.assertRaisesRegex(
                ValueError, "REGISTERED_NATIVE_ACCOUNT_CONFIGURATION_CHANGED"
            ):
                native.operate(self.output)
        self.assertEqual(len(created), 1, "Actual native authority construction must occur exactly once")
        return created[0]

    def test_a_unmodified_registered_native_account_passes(self):
        receipt = native.operate(self.output)
        self.assertTrue(receipt["complete"])
        self.assertTrue(receipt["native_audit_accepted"])
        self.assertTrue(native.audit(self.output)["native_audit_accepted"])
        config = json.loads(
            (self.output / "public/native-export.json").read_text(encoding="utf-8")
        )["ledger"]["config"]
        self.assertEqual(
            {k: config[k] for k in ("opening", "working", "contract")},
            {
                "opening": self.protocol["opening"],
                "working": 0,
                "contract": json.loads(
                    (self.output / "REGISTRATION.json").read_text(encoding="utf-8")
                )["contract"],
            },
        )
        print("GENESIS100_A_NATIVE_REGISTRATION_ACCEPTED")

    def test_b_larger_actual_native_seed_must_be_rejected(self):
        actual = self._override_actual_native_authority(
            opening=self.protocol["opening"] + 100_000_000
        )
        self.assertEqual(actual["opening"], self.protocol["opening"] + 100_000_000)
        print("GENESIS100_B_INFLATED_CANONICAL_OPENING_REJECTED")

    def test_c_unregistered_native_working_capital_must_be_rejected(self):
        actual = self._override_actual_native_authority(working=1_000_000)
        self.assertEqual(actual["working"], 1_000_000)
        print("GENESIS100_C_UNREGISTERED_WORKING_CAPITAL_REJECTED")

    def test_d_wrong_real_native_contract_must_be_rejected(self):
        changed_contract = "genesis100-unregistered-simulation-contract"
        actual = self._override_actual_native_authority(contract=changed_contract)
        self.assertEqual(actual["contract"], changed_contract)
        print("GENESIS100_D_UNREGISTERED_NATIVE_CONTRACT_REJECTED")


if __name__ == "__main__":
    unittest.main()
