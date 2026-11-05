"""GENESIS101: genuine canonical spend-before-delivery chronology regressions.

Frozen protocol: campaign/genesis-production-order101/PREREGISTRATION.md.
Every adversarial transaction uses a disposable real JournalAccount; no signed
tape or public financial export is rewritten. The public execution projection
is constructed from actual event receipts rather than a second money model.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from flexibility063.kernel import solve
from flexibility063.native import BusinessAccount
from flexibility063.verify import verify
from genesis_enterprise import native
from genesis_enterprise.policy import canonical, choose, digest

ROOT = Path(__file__).resolve().parents[1]


class Genesis101NativeChronology(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="genesis101-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.output = self.directory / "real-canonical-account"
        self.protocol = json.loads((ROOT / "campaign/genesis-enterprise-002/PROTOCOL.json").read_text())
        self.input = self.directory / "PROTOCOL.json"
        self.input.write_bytes(canonical(self.protocol))

    def register(self):
        native.register(ROOT, self.output, self.input)

    def _one_real_native_order(self, *, prepare_day, production_day):
        """An actual accepted job; only the *transaction order* is adversarial."""
        from commercial.terms_exact_v2 import prospective_terms

        self.register()
        manifest = native._read(self.output / "MANIFEST.json")
        reg = native._read(self.output / "REGISTRATION.json")
        job = manifest["jobs"][0]
        ident, hour = job["id"], 24
        order = "g002-" + ident
        with BusinessAccount(
            self.output / "source", manifest, self.output / "private/account",
            opening=self.protocol["opening"], working=0, contract=reg["contract"],
        ) as account:
            p = self.protocol
            if p["development"]:
                account.cost("genesis-development", p["development"], 0)
            account.advance(hour)
            if p["acquisition"]:
                account.cost("genesis-acquisition-" + ident, p["acquisition"], hour)
            if p["maintenance"]:
                account.cost("genesis-maintenance-" + ident, p["maintenance"], hour)
            before = account.export()["ledger"]["summary"]
            state = {key: before[key] for key in ("available", "unrestrictedEarned")}
            decision = choose(
                p["offer"], p["tools"], available=state["available"],
                earned=state["unrestrictedEarned"],
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
            artifact = solve(job["request"], picked["mode"])
            # The output is genuinely prepared before resource commitment.
            delivery = account.complete_order(order, ident, artifact, prepare_day)
            self.assertTrue(delivery["accepted"])
            if production_day > prepare_day:
                account.release(order, hour + 2)
            receipt = account.spend(
                "genesis-production-" + ident, "qualified-computational-delivery",
                picked["resource_cost"], production_day,
                {"binding": reg["binding"], "request_sha256": digest(job["request"]),
                 "executor": picked["tool"], "scope": "COMPUTATIONAL_ONLY"},
                expected_net=picked["contribution"],
                allow_seed=p["first_delivery_may_use_seed"],
            )
            self.assertIsNotNone(receipt)
            if production_day <= prepare_day:
                account.release(order, hour + 2)
            conventional = solve(job["request"], "conventional")
            native._save(self.output / "public/controls" / (ident + ".json"), conventional)
            native._tax(account, p, ident, hour + 3)
            row = {
                "job_id": ident, "decision": decision, "decision_state": state,
                "accepted": delivery["accepted"], "resource_receipt": receipt,
                "artifact_sha256": digest(artifact),
                "ordinary_accepted": verify(job["request"], conventional)["accepted"],
                "construction_cpu_seconds": 0.0,
            }
            native._save(self.output / "public/native-export.json", account.export())
            native._save(
                self.output / "public/execution.json",
                {"binding": reg["binding"], "index": 1, "phase": "overhead",
                 "rows": [row], "active": None},
            )
        # Independent oracle confirms a genuinely replayable native account.
        from connected_enterprise.finance import audit_journal
        exported = native._read(self.output / "public/native-export.json")
        self.assertTrue(audit_journal(exported, root=self.output / "source",
                                      manifest=manifest)["accepted"])
        acts = exported["ledger"]["actions"]
        prepares = [a for a in acts if a["op"] == "event" and
                    a["args"]["id"] == order and a["args"]["action"] == "prepare"]
        releases = [a for a in acts if a["op"] == "event" and
                    a["args"]["id"] == order and a["args"]["action"] == "release"]
        self.assertEqual(len(prepares), 1)
        self.assertEqual(len(releases), 1)
        self.assertLess(prepares[0]["seq"], receipt["native_event_sequence"])
        return receipt, prepares[0], releases[0]

    def test_C0_unchanged_real_pilot_is_accepted(self):
        self.register()
        result = native.operate(self.output)
        self.assertTrue(result["complete"])
        self.assertTrue(result["conditional_self_funding"])
        self.assertGreater(result["accepted_collected_deliveries"], 0)
        self.assertEqual(native.audit(self.output), result)

    def test_C1_delayed_spend_after_collection_is_rejected(self):
        receipt, prepare, release = self._one_real_native_order(
            prepare_day=25, production_day=26)
        self.assertEqual((receipt["day"], prepare["day"], release["day"]), (26, 25, 26))
        self.assertLess(release["seq"], receipt["native_event_sequence"])
        with self.assertRaisesRegex(ValueError, "REGISTERED_PRODUCTION_COMMITMENT_ORDER_CHANGED"):
            native.audit(self.output)

    def test_C2_same_hour_preparation_before_spend_is_rejected(self):
        receipt, prepare, release = self._one_real_native_order(
            prepare_day=24, production_day=24)
        self.assertEqual((receipt["day"], prepare["day"], release["day"]), (24, 24, 26))
        self.assertLess(prepare["seq"], receipt["native_event_sequence"])
        self.assertLess(receipt["native_event_sequence"], release["seq"])
        with self.assertRaisesRegex(ValueError, "REGISTERED_PRODUCTION_COMMITMENT_ORDER_CHANGED"):
            native.audit(self.output)

    def test_C3_real_funded_checkpoint_and_completed_resume_unchanged(self):
        self.register()
        partial = native.operate(self.output, max_steps=5)
        self.assertFalse(partial["complete"])
        completed = native.operate(self.output)
        self.assertTrue(completed["complete"])
        before = (self.output / "public/native-export.json").read_bytes()
        self.assertEqual(native.audit(self.output), completed)
        self.assertEqual(native.operate(self.output), completed)
        self.assertEqual((self.output / "public/native-export.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
