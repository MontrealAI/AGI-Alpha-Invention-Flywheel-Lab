"""Run all original recovery boundary tests against one-pass native replay."""
from unittest.mock import patch
import unittest
import json
import hashlib
import copy
from pathlib import Path
from experiments.public_portfolio_20261102 import recovery_fast, recovery_run
from experiments.public_portfolio_20261102.verification import test_recovery as original_tests


class FastRecoveryTests(original_tests.RecoveryTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adapter_patch = patch.object(recovery_run, "recover_case", recovery_fast.recover_case)
        cls.prefix_patch = patch.object(recovery_run, "PrefixRelay", recovery_fast.FastPrefixRelay)
        cls.adapter_patch.start()
        cls.prefix_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.prefix_patch.stop()
        cls.adapter_patch.stop()
        super().tearDownClass()

    def test_06_controller_prefix_mismatch_rejected_before_append(self):
        output = self._interrupt("prefix-mismatch", entry_number=6)
        tape = output / "private" / "interface-recovery-guard-fixture" / "account.sqlite.actions.jsonl"
        before = tape.read_bytes()
        altered = copy.deepcopy(self.protocol)
        altered["profiles_usd"]["interface"]["monthly_fixed_overhead"] += 1
        with self.assertRaisesRegex(ValueError, "FAST_RECOVERY_EXACT_REQUEST_PLAN_FUNDING_PREFIX_REQUIRED"):
            recovery_fast.recover_case(original_tests.ROOT, output, self.products, altered, "interface", self.scenario)
        self.assertEqual(tape.read_bytes(), before)

    def test_13_complete_result_read_only_closeout_without_economic_rerun(self):
        from experiments.public_portfolio_20261102 import economics
        protocol = json.loads((Path(__file__).resolve().parents[3] / economics.PROTOCOL).read_text())
        scenario = next(s for s in protocol["registered_scenarios"] if s["id"] == "rights-unresolved")
        plan = {"case_id": "purpose-rights-unresolved", "route": "purpose", "scenario": scenario}
        output = self.base / "completed-result-host-closeout"
        (output / "control").mkdir(parents=True)
        root = Path(__file__).resolve().parents[3]
        reference = economics._run_case(root, output, self.products, protocol, "purpose", scenario)
        folder = output / "public" / plan["case_id"]
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
        tape = output / "private" / plan["case_id"] / "account.sqlite.actions.jsonl"
        native_before = tape.read_bytes()
        with patch.object(economics, "_run_case", side_effect=AssertionError("Completed economics must never rerun")):
            state, receipt = recovery_fast.closeout_completed_result(root, output, self.products, protocol, plan)
        self.assertEqual(state, reference)
        self.assertFalse(receipt["economic_function_rerun"])
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()})
        self.assertEqual(native_before, tape.read_bytes())

    def test_14_corrupt_completed_result_closeout_rejected_read_only(self):
        from experiments.public_portfolio_20261102 import economics
        root = Path(__file__).resolve().parents[3]
        protocol = json.loads((root / economics.PROTOCOL).read_text())
        scenario = next(s for s in protocol["registered_scenarios"] if s["id"] == "non-entry")
        plan = {"case_id": "purpose-non-entry", "route": "purpose", "scenario": scenario}
        output = self.base / "corrupt-completed-result-host-closeout"
        (output / "control").mkdir(parents=True)
        economics._run_case(root, output, self.products, protocol, "purpose", scenario)
        path = output / "public" / plan["case_id"] / "RESULT.json"
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "EXACT_CANONICAL_PUBLIC_BYTES"):
            recovery_fast.closeout_completed_result(root, output, self.products, protocol, plan)
        self.assertEqual(path.read_bytes(), original + b" ")

    def test_15_two_explicit_host_interruptions_preserve_paid_original_prefix(self):
        output = self._interrupt("twice-host-interrupted", entry_number=2)
        tape = output / "private" / "interface-recovery-guard-fixture" / "account.sqlite.actions.jsonl"
        before = tape.read_bytes()
        actual_relay = recovery_fast.FastPrefixRelay
        class HostInterruptedRelay(actual_relay):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                original_execute = self._live.execute
                def host_interrupted_execute(*args, **kwargs):
                    result = original_execute(*args, **kwargs)
                    raise original_tests.InjectedInterruption("Second host fixture: first new original paid action committed, controller stack lost")
                self._live.execute = host_interrupted_execute
        with patch.object(recovery_fast, "FastPrefixRelay", HostInterruptedRelay):
            with self.assertRaises(original_tests.InjectedInterruption):
                recovery_fast.recover_case(original_tests.ROOT, output, self.products,
                                           self.protocol, "interface", self.scenario)
        advanced = tape.read_bytes()
        self.assertTrue(advanced.startswith(before))
        self.assertGreater(len(advanced), len(before))
        self._recover_and_compare(output)

    def test_16_review_of_another_candidate_cannot_register_recovery(self):
        from experiments.public_portfolio_20261102 import economics
        root = self.base / "stale-review-metadata-only"
        verification = root / economics.PREFIX / "verification"
        verification.mkdir(parents=True)
        current = {economics.PREFIX + "recovery_fast.py": "current-fast-source",
                   economics.PREFIX + "verification/FAST_RECOVERY_QUALIFICATION_003.json": "current-qualification",
                   economics.PREFIX + "recovery_run.py": "original-adapter-source"}
        (root / recovery_fast.AMENDMENT).write_text(json.dumps(
            {"unchanged_recovery_io_adapter_sha256": "original-adapter-source",
             "unchanged_native_source_sha256": recovery_run.EXPECTED_NATIVE_SOURCE}))
        (verification / "FAST_RECOVERY_QUALIFICATION_003.json").write_text(json.dumps(
            {"status": "PASS", "source_hashes": {economics.PREFIX + "recovery_fast.py": "current-fast-source"}}))
        (verification / "FAST_RECOVERY_REVIEW_002.json").write_text(json.dumps(
            {"status": "ACCEPTED_ENGINEERING_SCOPE", "fast_recovery_source_sha256": "old-fast-source",
             "qualification_receipt_sha256": "current-qualification"}))
        output = self.base / "stale-review-metadata-output"
        with patch.object(recovery_fast, "_source_hashes", return_value=current):
            with self.assertRaisesRegex(ValueError, "INDEPENDENT_REVIEW_OF_EXACT_TESTED_CANDIDATE"):
                recovery_fast.register(root, output, "1" * 40)
        self.assertFalse((output / "public" / recovery_fast.STAGE).exists())


if __name__ == "__main__":
    unittest.main()
