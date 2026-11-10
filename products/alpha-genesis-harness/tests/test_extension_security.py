# SPDX-License-Identifier: Apache-2.0
"""Independent adversarial checks of arbitrary-source foundry boundaries.

Construction and evaluation are injected protocol fixtures. These tests never
execute candidate Python outside a native sandbox or claim real model access.
"""
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
import bridge.workflows as workflow_module
from bridge.upgrade_foundry import UpgradeFoundryService
import test_upgrade_foundry as fixture


class FoundryAdversarialReview(unittest.TestCase):
    setUp = fixture.FoundryTests.setUp
    tearDown = fixture.FoundryTests.tearDown
    register = fixture.FoundryTests.register
    construct = fixture.FoundryTests.construct
    qualify = fixture.FoundryTests.qualify

    def test_untracked_special_file_cannot_enter_candidate_manifest(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("POSIX FIFO creation unavailable")
        exp = self.construct()
        directory = self.service.root / exp["candidate_relative"]
        os.mkfifo(directory / "untracked.fifo")
        with self.assertRaises(BridgeError) as raised:
            self.service._candidate_files(directory, exp["baseline_manifest"])
        self.assertEqual(raised.exception.code, "FOUNDRY_SCOPE")

    def test_cancellation_between_final_check_and_commit_prevents_qualification(self):
        exp = self.construct()
        original = self.service.lock
        service = self.service
        class LateCancellationLock:
            count = 0
            def __enter__(self):
                self.count += 1
                # Models the operator's cancel completing just before the final
                # qualification transaction acquires the shared lock.
                if self.count == 2:
                    service.active[exp["id"]]["cancel"].set()
                return original.__enter__()
            def __exit__(self, *args):
                return original.__exit__(*args)
        self.service.lock = LateCancellationLock()
        with self.assertRaises(BridgeError) as raised:
            self.service.qualify({"experiment_id": exp["id"], "authorize": True})
        self.assertEqual(raised.exception.code, "FOUNDRY_CANCELLED")
        state = self.service.status()
        self.assertIsNone(state["active_candidate"])
        self.assertNotEqual(next(e for e in state["experiments"] if e["id"] == exp["id"])["status"], "qualified")

    def test_retained_candidate_execution_can_be_cancelled_before_result_acceptance(self):
        exp = self.qualify()
        self.service.activate({"experiment_id": exp["id"], "authorize": True,
                               "expected_candidate_sha256": exp["candidate_sha256"]})
        started, release, cancel_done = threading.Event(), threading.Event(), threading.Event()
        original = self.evaluator.run
        results, errors, cancellation = [], [], []
        def blocked(directory, cases, *, cancel=None):
            started.set()
            release.wait(3)
            if cancel is not None and cancel.is_set():
                raise BridgeError("FOUNDRY_CANCELLED", "Synthetic cancellation")
            return original(directory, cases, cancel=cancel)
        self.evaluator.run = blocked
        case = self.evaluator.calls[-1][1][0]
        request = {k: case[k] for k in ("instrument", "inputs", "expected", "max_operations")}
        def run():
            try: results.append(self.service.evaluate_retained(request))
            except Exception as error: errors.append(error)
        def cancel():
            try: cancellation.append(self.service.cancel({"experiment_id": exp["id"]}))
            finally: cancel_done.set()
        worker = threading.Thread(target=run)
        stopper = threading.Thread(target=cancel)
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            stopper.start()
            self.assertTrue(cancel_done.wait(1), "Retained evaluation must not hold the service lock across external execution")
        finally:
            release.set()
            worker.join(3)
            if stopper.ident is not None: stopper.join(3)
        self.assertFalse(results, "A cancelled retained result must never be accepted")
        self.assertTrue(cancellation[0]["cancelled"])
        self.assertTrue(errors and isinstance(errors[0], BridgeError))

    def test_restarted_orphaned_attempt_becomes_inspectable_without_promotion(self):
        exp = self.register()
        with self.service.lock:
            state = self.service._load()
            row = next(e for e in state["experiments"] if e["id"] == exp["id"])
            row["status"] = "constructing"
            self.service._save(state)
        restored = UpgradeFoundryService(self.workflows, self.codex, evaluator=self.evaluator)
        row = next(e for e in restored.status()["experiments"] if e["id"] == exp["id"])
        self.assertNotIn(row["status"], {"constructing", "qualifying", "qualified"})
        self.assertIsNone(restored.status()["active_candidate"])
        self.assertEqual(restored.export({"experiment_id": exp["id"]})["experiment"]["id"], exp["id"])
        self.assertFalse(self.process_calls)

    def test_changed_loaded_verifier_dependency_prevents_candidate_qualification(self):
        exp = self.construct()
        with patch.object(workflow_module, "LOADED_SOURCE_SHA256", "0" * 64):
            with self.assertRaises(BridgeError):
                self.service.qualify({"experiment_id": exp["id"], "authorize": True})
        self.assertFalse(self.evaluator.calls)


if __name__ == "__main__":
    unittest.main()
