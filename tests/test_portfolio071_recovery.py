"""Matched native-policy and hostile-checkpoint tests on disposable dev accounts."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import _ADAPTIVE_ACCOUNT_CAPABILITY, digest
from commercial.single_writer import SingleWriterExchange
from connected_enterprise.finance import JournalAccount, audit_journal
from portfolio071.economics import World, execute_trajectory
from portfolio071.recovery import (
    RecoveryInterrupted, public_before_open, recover_trajectory, source_hashes,
)
from portfolio071.reproduce import stage_native_source
from portfolio071.verify_economics import audit_arm, daily_commitments, event_facts

REPO = Path(__file__).resolve().parents[1]


class NativeRecoverySemanticsTests(unittest.TestCase):
    def setUp(self):
        # Retained locally for diagnosis; never published with private authority.
        self.work = Path(tempfile.mkdtemp(prefix="portfolio071-recovery-tests-"))
        self.source, self.manifest = stage_native_source(
            self.work / "stage", REPO / "experiments/portfolio_20261102/evidence/r4/native_inputs")

    def recover(self, case, **kwargs):
        return recover_trajectory(self.source, self.manifest,
            self.work / case / "owned" / "account.sqlite",
            self.work / case / "recovered", development=True, **kwargs)

    def before(self, case):
        return public_before_open(self.work / case / "owned" / "account.sqlite")

    def independently_checked_cross_account_body(self, exported):
        """Compare financial semantics after checking each account's own hashes.

        Fresh development accounts have distinct local simulation signers. Their
        public HMACs and the two exact hashes that contain them are not expected
        to agree. No same-original-account recovery check uses this transform.
        """
        self.assertEqual(digest(exported["connected_journal"]), exported["connected_journal_sha256"])
        value = copy.deepcopy(exported)
        actions = exported["ledger"]["actions"]
        config = exported["ledger"]["config"]
        with tempfile.TemporaryDirectory(prefix="portfolio071-test-prefix-") as folder:
            with SingleWriterExchange(Path(folder) / "replay.sqlite", root=self.source,
                    manifest=self.manifest, opening=config["opening"], working=config["working"],
                    contract=config["contract"], durable=False,
                    _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY) as owner:
                cursor = 0
                for entry in value["connected_journal"]["entries"]:
                    target = entry["attempt"]["native_sequence"]
                    self.assertGreaterEqual(target, cursor)
                    while cursor < target:
                        row = actions[cursor]
                        after = owner._exchange.execute(row["op"], row["args"], row["day"])
                        self.assertEqual(after, row["after"])
                        cursor += 1
                    tape = owner.export()
                    reserved = {row["args"]["id"] for row in tape["actions"] if row["op"] == "reserve"}
                    finished = {row["args"]["id"] for row in tape["actions"] if row["op"] == "finish"}
                    before = {key: copy.deepcopy(item) for key, item in exported.items()
                              if key not in {"connected_journal", "connected_journal_sha256"}}
                    before["ledger"] = tape
                    before["action_proofs"] = {key: item for key, item in exported["action_proofs"].items() if key in reserved}
                    before["obligation_resolutions"] = {key: item for key, item in exported["obligation_resolutions"].items() if key in finished}
                    before["snapshot"] = {**copy.deepcopy(exported["snapshot"]),
                        "summary": tape["summary"], "sequence": len(tape["actions"]),
                        "actions_sha256": tape["actions_sha256"],
                        "state_digest": digest({"config": tape["config"],
                            "actions_sha256": tape["actions_sha256"], "summary": tape["summary"]})}
                    self.assertEqual(digest(before), entry["attempt"]["account_record_sha256"])
                    del entry["attempt"]["account_record_sha256"]
        for proof in value["action_proofs"].values():
            self.assertRegex(proof["signature"], r"^[0-9a-f]{64}$")
            del proof["signature"]
        del value["connected_journal_sha256"]
        return value

    def assert_same_economics(self, baseline, recovered, baseline_directory, case):
        # Every original output field is checked, except separately disclosed
        # engineering resource telemetry. The new provenance fields are extra.
        for key, value in baseline.items():
            if key in {"resource_measurement", "native_export_sha256", "drain_export_sha256"}:
                continue
            with self.subTest(field=key):
                self.assertEqual(value, recovered[key])
        for name in ("native-at-horizon.json", "native-after-drain.json"):
            left = json.loads((baseline_directory / name).read_text())
            right = json.loads((self.work / case / "recovered" / name).read_text())
            self.assertEqual(self.independently_checked_cross_account_body(left),
                             self.independently_checked_cross_account_body(right), name)
        hours = len(baseline["daily"]) * 24
        # Each unmodified export, including all original hashes, must pass the
        # frozen native and economic auditor before cross-account comparison.
        for directory in (baseline_directory, self.work / case / "recovered"):
            if hours >= 8760:
                self.assertTrue(audit_arm(self.source, directory, expected_hours=hours)["accepted"])
            else:
                # The unchanged full-year report auditor intentionally requires
                # a completed trailing year. Short development probes use its
                # exact native, event/tax and daily checks without inventing one.
                trajectory = json.loads((directory / "trajectory.json").read_text())
                native = json.loads((directory / "native-at-horizon.json").read_text())
                drained = json.loads((directory / "native-after-drain.json").read_text())
                for export in (native, drained):
                    self.assertTrue(audit_journal(export, root=self.source, manifest=self.manifest)["accepted"])
                self.assertEqual(daily_commitments(trajectory, native["ledger"]["actions"]), hours // 24)
                facts = event_facts(drained["ledger"]["actions"],
                    trajectory["capital_usd"] * 1000000, trajectory["world"]["tax_bps"])
                self.assertEqual(facts["tax_paid"], trajectory["total_tax_after_drain_microUSD"])
        self.assertTrue(recovered["opening_plus_flows_reconciles"])
        self.assertEqual(recovered["external_financing_received_usd"], 0)
        self.assertEqual(recovered["external_revenue_usd"], 0)

    def matched(self, case, parameters, stops):
        baseline_dir = self.work / case / "uninterrupted"
        baseline = execute_trajectory(self.source, self.manifest, baseline_dir, **parameters)
        previous = None
        for count in stops:
            with self.assertRaises(RecoveryInterrupted):
                self.recover(case, **parameters, stop_after_new_operations=count)
            current = self.before(case)
            if previous is not None:
                self.assertEqual(previous["native_actions"],
                                 current["native_actions"][:len(previous["native_actions"])])
                self.assertEqual(previous["connected_journal"]["entries"],
                    current["connected_journal"]["entries"][:len(previous["connected_journal"]["entries"])])
            previous = current
        recovered = self.recover(case, **parameters)
        self.assert_same_economics(baseline, recovered, baseline_dir, case)
        final = self.before(case)
        self.assertEqual(previous["native_actions"], final["native_actions"][:len(previous["native_actions"])])
        return recovered

    def test_initial_research_refusal_preserves_paid_cost(self):
        result = self.matched("unfunded", {"capital_usd": 25000, "horizon_days": 65}, [1])
        self.assertEqual(result["operating_endpoint"]["profit"], -15000 * 1000000)
        self.assertEqual(result["modeled_licenses"], 0)

    def test_repeated_mid_sale_recovery_through_k2_tax_and_renewal(self):
        result = self.matched("central390", {"capital_usd": 100000, "horizon_days": 390}, [12, 7])
        self.assertIsNotNone(result["K2_funding"])
        self.assertTrue(result["tax_settlements"])
        self.assertEqual(len(result["daily"]), 390)
        self.assertTrue(any(row.get("renewal_after_collected_prior_year") for row in result["decisions"]))

    def test_post_horizon_collection_and_escrow_cancellation(self):
        world = World(name="recovery-delayed-cancellation-development", collection_delay_days=180, default_every=2)
        result = self.matched("delayed", {"capital_usd": 1000000, "world": world, "horizon_days": 65}, [20])
        self.assertGreater(result["post_horizon_collected_licenses"], 0)
        self.assertTrue(any(row["post_horizon"] for row in result["tax_settlements"]))
        final = json.loads((self.work / "delayed/recovered/native-after-drain.json").read_text())
        self.assertTrue(any(row["state"] == "refunded" for row in final["ledger"]["orders"]))

    def test_abrupt_exit_with_pending_terms_and_no_sqlite_checkpoint(self):
        """Actual child exit before first terms operation, with intent fsynced."""
        case = "abrupt-pending"
        code = r'''
import json, os, sys
from pathlib import Path
from connected_enterprise.finance import JournalAccount
from portfolio071.recovery import recover_trajectory
source, manifest_path, original, output = map(Path, sys.argv[1:])
original_perform = JournalAccount._perform
def crash_before_terms(self, entry):
    request = entry['request']
    if entry['status'] == 'PENDING' and request['operation'] == 'execute' and request['op'] == 'register_terms':
        os._exit(73)
    return original_perform(self, entry)
JournalAccount._perform = crash_before_terms
recover_trajectory(source, json.loads(manifest_path.read_text()), original, output,
                   capital_usd=100000, horizon_days=65, development=True)
'''
        manifest_path = self.work / case / "manifest-input.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(self.manifest))
        original = self.work / case / "owned/account.sqlite"
        completed = subprocess.run([sys.executable, "-c", code, str(self.source),
            str(manifest_path), str(original), str(self.work / case / "recovered")],
            cwd=REPO, capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 73, completed.stderr)
        self.assertFalse(original.exists(), "abrupt exit must leave no clean-close SQLite checkpoint")
        before = self.before(case)
        entries = before["connected_journal"]["entries"]
        self.assertEqual([row["status"] for row in entries].count("PENDING"), 1)
        self.assertEqual(entries[-1]["request"]["op"], "register_terms")
        self.assertEqual(entries[-1]["attempt"]["native_sequence"], len(before["native_actions"]))
        baseline_dir = self.work / case / "uninterrupted"
        baseline = execute_trajectory(self.source, self.manifest, baseline_dir,
                                      capital_usd=100000, horizon_days=65)
        recovered = self.recover(case, capital_usd=100000, horizon_days=65)
        self.assert_same_economics(baseline, recovered, baseline_dir, case)
        final = self.before(case)
        self.assertEqual(before["native_actions"], final["native_actions"][:len(before["native_actions"])] )
        self.assertEqual(entries[:-1], final["connected_journal"]["entries"][:len(entries)-1])
        resolved = final["connected_journal"]["entries"][len(entries)-1]
        self.assertEqual(resolved["status"], "COMPLETE")
        for field in ("key", "request", "plan", "funding", "attempt", "obligation_receipt"):
            self.assertEqual(entries[-1][field], resolved[field])
        appended = final["native_actions"][len(before["native_actions"])]
        self.assertEqual(appended["op"], "register_terms")
        self.assertEqual(appended["args"], entries[-1]["request"]["args"])
        matching = [row for row in final["native_actions"]
                    if row["op"] == appended["op"] and row["args"] == appended["args"]]
        self.assertEqual(len(matching), 1)
        self.assertTrue(recovered["recovery_provenance"]["native_reopen"]["resolved_pending"])

    def test_interruption_after_profitable_collection_and_inside_maturity(self):
        case = "collection-maturity"
        parameters = {"capital_usd": 100000, "horizon_days": 200}
        baseline_dir = self.work / case / "uninterrupted"
        baseline = execute_trajectory(self.source, self.manifest, baseline_dir, **parameters)
        original_perform = JournalAccount._perform
        previous = None
        for boundary in ("profitable_release_before_tax", "first_maturity_inside_advance"):
            def interrupt_at_boundary(account, entry):
                result = original_perform(account, entry)
                request = entry["request"]
                if request["operation"] == "execute":
                    is_release = (request["op"] == "event" and request["args"].get("action") == "release"
                                  and account.snapshot()["summary"]["profit"] > 0)
                    is_maturity = request["op"] == "mature"
                    if (boundary == "profitable_release_before_tax" and is_release
                            or boundary == "first_maturity_inside_advance" and is_maturity):
                        # Native intent and result have persisted; controller's
                        # following tax/advance code has not run.
                        raise RecoveryInterrupted("TARGETED_DEVELOPMENT_" + boundary)
                return result
            with patch.object(JournalAccount, "_perform", interrupt_at_boundary):
                with self.assertRaisesRegex(RecoveryInterrupted, boundary):
                    self.recover(case, **parameters)
            current = self.before(case)
            last = current["native_actions"][-1]
            if boundary == "profitable_release_before_tax":
                self.assertEqual(last["op"], "event")
                self.assertEqual(last["args"]["action"], "release")
                self.assertGreater(last["after"]["profit"], 0)
            else:
                self.assertEqual(last["op"], "mature")
            if previous is not None:
                self.assertEqual(previous["native_actions"], current["native_actions"][:len(previous["native_actions"])])
            previous = current
        recovered = self.recover(case, **parameters)
        self.assert_same_economics(baseline, recovered, baseline_dir, case)
        final = self.before(case)
        self.assertEqual(previous["native_actions"], final["native_actions"][:len(previous["native_actions"])])

    def interrupted_small(self, case):
        with self.assertRaises(RecoveryInterrupted):
            self.recover(case, capital_usd=100000, horizon_days=65, stop_after_new_operations=1)
        return digest(self.before(case))

    def test_source_mismatch_rejected_before_account_mutation(self):
        before = self.interrupted_small("source")
        altered = source_hashes()
        altered["portfolio071/recovery.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "RECOVERY_SOURCE_CHANGED"):
            self.recover("source", capital_usd=100000, horizon_days=65, expected_source_hashes=altered)
        self.assertEqual(before, digest(self.before("source")))

    def test_changed_recipe_rejected_without_reset(self):
        before = self.interrupted_small("recipe")
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_RECOVERY_SOURCE_OR_RECIPE_CHANGED"):
            self.recover("recipe", capital_usd=100000, horizon_days=66)
        self.assertEqual(before, digest(self.before("recipe")))
        # A legitimate subsequent reopen must work: failed preflight released
        # the owned writer, and did not strand a lock or overwrite the state.
        result = self.recover("recipe", capital_usd=100000, horizon_days=65)
        self.assertTrue(result["opening_plus_flows_reconciles"])

    def test_tampered_signed_checkpoint_is_rejected_without_financial_change(self):
        before = self.interrupted_small("checkpoint")
        path = self.work / "checkpoint/recovered/PRIVATE_CONTROLLER_CHECKPOINT.json"
        original = path.read_bytes()
        value = json.loads(original)
        self.assertIn("signature", value)
        value["signature"] = "0" * 64
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        with self.assertRaises(ValueError):
            self.recover("checkpoint", capital_usd=100000, horizon_days=65)
        self.assertEqual(before, digest(self.before("checkpoint")))
        path.write_bytes(original)
        result = self.recover("checkpoint", capital_usd=100000, horizon_days=65)
        self.assertTrue(result["opening_plus_flows_reconciles"])


if __name__ == "__main__":
    unittest.main()
