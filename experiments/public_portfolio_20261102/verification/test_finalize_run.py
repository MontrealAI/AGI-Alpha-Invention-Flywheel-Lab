"""Prevent incomplete or failed dispatch state being labeled complete."""
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from experiments.public_portfolio_20261102 import finalize_run, dispatch_case


class FinalizationAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="r2-finalization-admission-only-")
        self.output = Path(self.temporary.name)
        (self.output / "control/reservations").mkdir(parents=True)
        (self.output / "public").mkdir()
        (self.output / "public" / dispatch_case.STAGE).write_text(json.dumps({"publication_sha": "1" * 40}))
        self.plans = [{"case_id": "metadata-fixture-" + str(i)} for i in range(110)]
        self.load = patch.object(dispatch_case, "_load", return_value=({}, {}, {}, self.plans, []))
        self.stage = patch.object(dispatch_case, "_check_stage", return_value={})
        self.load.start();self.stage.start()

    def tearDown(self):
        self.stage.stop();self.load.stop();self.temporary.cleanup()

    def test_incomplete_110_denominator_never_writes_results(self):
        with self.assertRaisesRegex(ValueError, "ALL_ORIGINAL_110_ACCOUNTS_MUST_BE_COMPLETE"):
            finalize_run.finalize(Path.cwd(), self.output, "1" * 40)
        self.assertFalse((self.output / "public/RESULTS.json").exists())

    def test_existing_result_never_overwritten(self):
        path = self.output / "public/RESULTS.json"
        path.write_bytes(b"existing exact bytes")
        with self.assertRaisesRegex(ValueError, "IS_NOT_OVERWRITTEN"):
            finalize_run.finalize(Path.cwd(), self.output, "1" * 40)
        self.assertEqual(path.read_bytes(), b"existing exact bytes")

    def test_actual_failure_stop_never_finalized_complete(self):
        (self.output / "public" / dispatch_case.STOP).write_text("{}")
        with self.assertRaisesRegex(ValueError, "ACTUAL_FAILURE_STOP_PREVENTS"):
            finalize_run.finalize(Path.cwd(), self.output, "1" * 40)
        self.assertFalse((self.output / "public/RESULTS.json").exists())

    def test_reported_native_summary_cannot_differ_from_compacted_ledger(self):
        state = {"final_native_summary_microUSD": {"profit": 999}}
        record = {"ledger": {"summary": {"profit": -1}}}
        with self.assertRaisesRegex(ValueError, "REPORTED_SUMMARY_MUST_MATCH_EXACT_NATIVE_SUMMARY"):
            finalize_run._assert_state_native_consistency(state, record, {}, {})

    def test_stop_appearing_before_last_slot_release_is_rechecked(self):
        for plan in self.plans:
            (self.output / "control/reservations" / (plan["case_id"] + ".json")).write_text('{"status":"COMPLETE"}')
        @contextmanager
        def final_worker_released_with_failure(output):
            (output / "public" / dispatch_case.STOP).write_text("{}")
            yield
        with patch.object(finalize_run, "_all_slots_idle", final_worker_released_with_failure):
            with self.assertRaisesRegex(ValueError, "ACTUAL_FAILURE_STOP_PREVENTS"):
                finalize_run.finalize(Path.cwd(), self.output, "1" * 40)
        self.assertFalse((self.output / "public/RESULTS.json").exists())


if __name__ == "__main__":
    unittest.main()
