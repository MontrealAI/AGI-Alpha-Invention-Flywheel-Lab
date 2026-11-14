"""Transition163 frozen independent synthetic epoch exclusion checks.

No finance, HMAC, native queue, account, original checkpoint or real commerce.
"""
import json
import multiprocessing as mp
import os
import tempfile
import unittest
from pathlib import Path

from .gate import (
    Refusal, operate_once, prepare_once, OP_INTENT, OP_DONE,
)
from .test_gate import A

OLD = "a" * 64
AFTER = "c" * 64
OP = {"id": "old-operation", "expected_checkpoint_sha256": OLD}


def operation_worker(path, current, entered, release, results):
    def action(operation):
        entered.set()
        if not release.wait(15):
            raise AssertionError("FIXTURE_OPERATION_RELEASE_TIMEOUT")
        current["sha"] = AFTER
        return {"after_checkpoint_sha256": AFTER, "outcome": "synthetic-no-cash"}
    try:
        result = operate_once(path, OP,
                              observed_checkpoint=lambda: current["sha"],
                              operation_callback=action)
        results.put(("operation", "accepted", result))
    except Exception as exc:
        results.put(("operation", "refused", str(exc)))


def prepare_worker(path, current, attempted, done, results):
    attempted.set()
    try:
        result = prepare_once(
            path, A, observed_checkpoint=lambda: current["sha"],
            authorization_callback=lambda req: {"id": req["id"]},
        )
        results.put(("prepare", "accepted", result))
    except Exception as exc:
        results.put(("prepare", "refused", str(exc)))
    finally:
        done.set()


def crash_worker(path):
    def crash_after_intent(operation):
        os._exit(43)
    operate_once(path, OP, observed_checkpoint=lambda: OLD,
                 operation_callback=crash_after_intent)


class SyntheticEpoch163(unittest.TestCase):
    def test_01_two_real_processes_no_concurrent_prepare_and_operate(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = mp.get_context("spawn")
            with ctx.Manager() as manager:
                current = manager.dict(sha=OLD)
                entered, release, attempted, done = (
                    ctx.Event(), ctx.Event(), ctx.Event(), ctx.Event()
                )
                results = ctx.Queue()
                op = ctx.Process(target=operation_worker,
                                 args=(td, current, entered, release, results))
                op.start()
                self.assertTrue(entered.wait(10), "operation never entered")
                pr = ctx.Process(target=prepare_worker,
                                 args=(td, current, attempted, done, results))
                pr.start()
                self.assertTrue(attempted.wait(10), "prepare never attempted")
                # A prepare may not finish while an old-source callback owns the
                # same lease. This timeout is solely synchronization, not a
                # candidate score, CPU cap or sampling criterion.
                premature = done.wait(.25)
                release.set()
                for proc in (op, pr):
                    proc.join(12)
                    self.assertEqual(proc.exitcode, 0)
                values = [results.get(timeout=3) for _ in (op, pr)]
                self.assertFalse(premature, values)
                by_name = {item[0]: item for item in values}
                self.assertEqual(by_name["operation"][1], "accepted", values)
                self.assertEqual(by_name["prepare"][1], "refused", values)
                self.assertIn("STALE_PREPARE_CHECKPOINT_REFUSED",
                              by_name["prepare"][2])
                self.assertFalse((Path(td) / "PREPARE_INTENT.json").exists())
                self.assertTrue((Path(td) / OP_DONE).exists())

    def test_02_fresh_serial_prepare_after_completed_and_replay(self):
        with tempfile.TemporaryDirectory() as td:
            current = [OLD]
            calls = []
            def effect(operation):
                calls.append(operation["id"])
                current[0] = AFTER
                return {"after_checkpoint_sha256": AFTER, "outcome": "bounded"}
            kwargs = {"observed_checkpoint": lambda: current[0],
                      "operation_callback": effect}
            expected = {"after_checkpoint_sha256": AFTER, "outcome": "bounded"}
            self.assertEqual(operate_once(td, OP, **kwargs), expected)
            before = [(n, (Path(td) / n).read_bytes()) for n in (OP_INTENT, OP_DONE)]
            self.assertEqual(operate_once(td, OP, **kwargs), expected)
            self.assertEqual(calls, ["old-operation"])
            self.assertEqual(before, [(n, (Path(td) / n).read_bytes())
                                      for n in (OP_INTENT, OP_DONE)])
            req = {**A, "expected_checkpoint_sha256": AFTER}
            accepted = []
            self.assertEqual(
                prepare_once(td, req, observed_checkpoint=lambda: current[0],
                             authorization_callback=lambda r:
                             accepted.append(r["id"]) or {"id": r["id"]}),
                {"id": "writer-A"},
            )
            self.assertEqual(accepted, ["writer-A"])

    def test_03_crashed_operation_blocks_prepare_and_reexecution(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = mp.get_context("spawn")
            proc = ctx.Process(target=crash_worker, args=(td,))
            proc.start()
            proc.join(10)
            self.assertEqual(proc.exitcode, 43)
            self.assertTrue((Path(td) / OP_INTENT).exists())
            self.assertFalse((Path(td) / OP_DONE).exists())
            called = []
            with self.assertRaisesRegex(
                Refusal, "INCOMPLETE_OPERATION_REQUIRES_OWNER_RECOVERY"
            ):
                prepare_once(
                    td, A, observed_checkpoint=lambda: OLD,
                    authorization_callback=lambda req: called.append(req),
                )
            with self.assertRaisesRegex(
                Refusal, "INCOMPLETE_OPERATION_REQUIRES_OWNER_RECOVERY"
            ):
                operate_once(
                    td, OP, observed_checkpoint=lambda: OLD,
                    operation_callback=lambda op: called.append(op),
                )
            self.assertEqual(called, [])

    def test_04_pending_prepare_and_distinct_operation_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            calls = []
            prepare_once(td, A, observed_checkpoint=lambda: OLD,
                         authorization_callback=lambda req: {"id": req["id"]})
            with self.assertRaisesRegex(Refusal, "PENDING_PREPARE_REFUSES_OPERATION"):
                operate_once(
                    td, OP, observed_checkpoint=lambda: OLD,
                    operation_callback=lambda op: calls.append(op),
                )
            self.assertEqual(calls, [])
        with tempfile.TemporaryDirectory() as td:
            operate_once(td, OP, observed_checkpoint=lambda: OLD,
                         operation_callback=lambda op:
                         {"after_checkpoint_sha256": OLD, "outcome": "unchanged"})
            with self.assertRaisesRegex(Refusal, "DIFFERENT_OPERATION_REFUSED"):
                operate_once(
                    td, {**OP, "id": "other-operation"},
                    observed_checkpoint=lambda: OLD,
                    operation_callback=lambda op: calls.append(op),
                )
            self.assertEqual(calls, [])

    def test_05_stale_or_tampered_completion_refused(self):
        with tempfile.TemporaryDirectory() as td:
            current = [OLD]
            operate_once(td, OP, observed_checkpoint=lambda: current[0],
                         operation_callback=lambda op:
                         {"after_checkpoint_sha256": OLD, "outcome": "unchanged"})
            current[0] = AFTER
            with self.assertRaisesRegex(
                Refusal, "STALE_OPERATION_RESULT_CHECKPOINT_REFUSED"
            ):
                prepare_once(td, {**A, "expected_checkpoint_sha256": AFTER},
                             observed_checkpoint=lambda: current[0],
                             authorization_callback=lambda req: {"id": req["id"]})
        with tempfile.TemporaryDirectory() as td:
            operate_once(td, OP, observed_checkpoint=lambda: OLD,
                         operation_callback=lambda op:
                         {"after_checkpoint_sha256": OLD, "outcome": "unchanged"})
            raw = json.loads((Path(td) / OP_DONE).read_text())
            raw["receipt"]["outcome"] = "tampered"
            (Path(td) / OP_DONE).write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n"
            )
            with self.assertRaisesRegex(Refusal, "CORRUPT_OPERATION_RESULT_REFUSED"):
                prepare_once(td, A, observed_checkpoint=lambda: OLD,
                             authorization_callback=lambda req: {"id": req["id"]})


if __name__ == "__main__":
    unittest.main()
