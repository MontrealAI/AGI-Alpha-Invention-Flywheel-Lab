"""Admission tests only; mocks never represent a simulated business result."""
from pathlib import Path
import fcntl
import json
import tempfile
import unittest
from unittest.mock import patch

from experiments.public_portfolio_20261102 import dispatch_case as subject, qualification_run

ROOT = Path(__file__).resolve().parents[3]


class DispatchAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="r2-dispatch-admission-fixture-")
        self.output = Path(self.temporary.name)
        (self.output / "control/reservations").mkdir(parents=True)
        (self.output / "public").mkdir()
        self.plans = [{"case_id": "guard-case-" + str(i), "index": i,
                       "route": "purpose", "scenario": {"id": "guard"}} for i in range(2)]
        amendment = {"expected_registration_state": {"completed": 0, "interrupted_case_ids": [], "not_started": 2},
                     "unchanged_financial_source_sha256": "guard-fixture-source"}
        self.load = patch.object(subject, "_load", return_value=(amendment, {}, {}, self.plans, []))
        self.load.start()
        self.sha = "1" * 40
        subject.register(ROOT, self.output, self.sha)

    def tearDown(self):
        self.load.stop()
        self.temporary.cleanup()

    def successful_stub(self, root, output, products, protocol, amendment, plan):
        reservation = self.output / "control/reservations" / (plan["case_id"] + ".json")
        row = json.loads(reservation.read_text())
        self.assertEqual(row["status"], "RESERVED")
        folder = self.output / "public" / plan["case_id"]
        folder.mkdir()
        (folder / "RESULT.json").write_text('{"TEST_ADMISSION_STUB_ONLY":true}\n')
        qualification_run._replace(reservation, {**row, "status": "COMPLETE"})
        return {"ok": True, "case_id": plan["case_id"]}

    def test_01_fresh_worker_once_and_complete_case_not_reentered(self):
        with patch.object(subject.qualification_run, "_worker", side_effect=self.successful_stub) as worker:
            result = subject.dispatch(ROOT, self.output, "guard-case-0", self.sha)
            self.assertTrue(result["ok"])
            with self.assertRaisesRegex(ValueError, "MUST_NEVER_HAVE_STARTED"):
                subject.dispatch(ROOT, self.output, "guard-case-0", self.sha)
            self.assertEqual(worker.call_count, 1)

    def test_02_actual_failure_stops_later_admission(self):
        with patch.object(subject.qualification_run, "_worker", return_value={"ok": False, "error": "guard fixture failure"}) as worker:
            with self.assertRaisesRegex(ValueError, "ORIGINAL_WORKER_FAILED"):
                subject.dispatch(ROOT, self.output, "guard-case-0", self.sha)
            with self.assertRaisesRegex(ValueError, "STOPS_NEW_DISPATCH"):
                subject.dispatch(ROOT, self.output, "guard-case-1", self.sha)
            self.assertEqual(worker.call_count, 1)

    def test_03_four_kernel_slots_prevent_fifth_reservation(self):
        streams = []
        try:
            for i in range(4):
                stream = (self.output / "control" / ("financial-worker-slot-" + str(i) + ".lock")).open("a+b")
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                streams.append(stream)
            with self.assertRaisesRegex(BlockingIOError, "FOUR_FINANCIAL_WORKER_SLOTS"):
                subject.dispatch(ROOT, self.output, "guard-case-0", self.sha)
            self.assertFalse((self.output / "control/reservations/guard-case-0.json").exists())
        finally:
            for stream in streams:
                stream.close()

    def test_04_source_change_rejected_before_reservation(self):
        with patch.object(subject, "_source_hashes", return_value={"changed": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "EXACT_PROSPECTIVE_DISPATCH_SOURCE"):
                subject.dispatch(ROOT, self.output, "guard-case-0", self.sha)
        self.assertFalse((self.output / "control/reservations/guard-case-0.json").exists())

    def test_05_full_native_source_mismatch_refused_before_admission(self):
        with patch.object(subject.service, "prepare_manifest", return_value={}), \
             patch.object(subject, "source_identity", return_value={"sha256": "changed-source"}):
            with self.assertRaisesRegex(ValueError, "COMPLETE_NATIVE_SOURCE_REQUIRED_BEFORE_ADMISSION"):
                subject._assert_native_source(ROOT, [], {"unchanged_financial_source_sha256": "original-source"})
        self.assertFalse((self.output / "control/reservations/guard-case-0.json").exists())

    def test_06_publication_identifier_must_be_exact_hex(self):
        with self.assertRaisesRegex(ValueError, "PUBLICATION_COMMIT_HEX"):
            subject.dispatch(ROOT, self.output, "guard-case-0", "unverified")


if __name__ == "__main__":
    unittest.main()
