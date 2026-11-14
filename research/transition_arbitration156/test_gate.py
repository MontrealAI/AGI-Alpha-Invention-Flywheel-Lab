"""Adversarial tests for an isolated NON-FINANCIAL reference arbitration kernel."""
import multiprocessing as mp
import os
import tempfile
import time
import unittest
from pathlib import Path

from .gate import Refusal, prepare_once, INTENT, PREPARED

A = {"id": "writer-A", "expected_checkpoint_sha256": "a" * 64,
     "target_source_sha256": "b" * 64}
B = {**A, "id": "writer-B"}


def _crash_worker(path):
    def kill_after_intent(request):
        os._exit(37)
    prepare_once(path, A, observed_checkpoint=lambda: "a" * 64,
                 authorization_callback=kill_after_intent)


def _run_worker(path, request, start, results):
    start.wait()
    try:
        value = prepare_once(path, request,
                             observed_checkpoint=lambda: "a" * 64,
                             authorization_callback=lambda req: (time.sleep(.05) or {"id": req["id"]}))
        results.put(("accepted", value["id"]))
    except Exception as exc:
        results.put(("refused", str(exc)))


class PrepareGateReference156(unittest.TestCase):
    def test_first_and_same_request_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            signed = []
            def authorize(req):
                signed.append(req["id"])
                return {"id": req["id"], "not_a_signature": True}
            kwargs = {"observed_checkpoint": lambda: "a" * 64,
                      "authorization_callback": authorize}
            self.assertEqual(prepare_once(td, A, **kwargs), {"id":"writer-A", "not_a_signature": True})
            old_intent = (Path(td) / INTENT).read_bytes()
            old_prepared = (Path(td) / PREPARED).read_bytes()
            self.assertEqual(prepare_once(td, A, **kwargs), {"id":"writer-A", "not_a_signature": True})
            self.assertEqual(signed, ["writer-A"])
            self.assertEqual(old_intent, (Path(td) / INTENT).read_bytes())
            self.assertEqual(old_prepared, (Path(td) / PREPARED).read_bytes())

    def test_serial_distinct_pending_fails_before_signing(self):
        with tempfile.TemporaryDirectory() as td:
            signed = []
            kwargs = {"observed_checkpoint": lambda: "a" * 64,
                      "authorization_callback": lambda r: signed.append(r["id"]) or {"id":r["id"]}}
            prepare_once(td, A, **kwargs)
            before = [(name, (Path(td) / name).read_bytes()) for name in (INTENT, PREPARED)]
            with self.assertRaisesRegex(Refusal, "DIFFERENT_PENDING_REQUEST_REFUSED"):
                prepare_once(td, B, **kwargs)
            self.assertEqual(signed, ["writer-A"])
            self.assertEqual(before, [(name, (Path(td) / name).read_bytes()) for name in (INTENT, PREPARED)])

    def test_true_cross_process_race_at_most_one_success(self):
        with tempfile.TemporaryDirectory() as td:
            ctx=mp.get_context("spawn")
            event=ctx.Event(); q=ctx.Queue()
            ps=[ctx.Process(target=_run_worker,args=(td,r,event,q)) for r in (A,B)]
            for p in ps:p.start()
            event.set()
            for p in ps:
                p.join(10)
                self.assertEqual(p.exitcode, 0)
            values=[q.get(timeout=2) for _ in ps]
            self.assertEqual(sum(s=="accepted" for s,_ in values),1,values)
            self.assertEqual(sum(s=="refused" for s,_ in values),1,values)
            self.assertTrue(any("DIFFERENT_PENDING_REQUEST_REFUSED" in v for s,v in values if s=="refused"),values)

    def test_authorizer_crash_freezes_intent_not_automatically_resigned(self):
        with tempfile.TemporaryDirectory() as td:
            calls=[]
            def crash(r):
                calls.append(r["id"])
                raise RuntimeError("synthetic interruption")
            with self.assertRaisesRegex(RuntimeError,"synthetic interruption"):
                prepare_once(td,A,observed_checkpoint=lambda:"a"*64,authorization_callback=crash)
            self.assertTrue((Path(td)/INTENT).exists())
            self.assertFalse((Path(td)/PREPARED).exists())
            for request in (A,B):
                with self.assertRaises(Refusal):
                    prepare_once(td,request,observed_checkpoint=lambda:"a"*64,
                                 authorization_callback=crash)
            self.assertEqual(calls,["writer-A"])

    def test_real_process_death_during_authorization_freezes_intent(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = mp.get_context("spawn")
            proc = ctx.Process(target=_crash_worker, args=(td,))
            proc.start();proc.join(10)
            self.assertEqual(proc.exitcode, 37)
            self.assertTrue((Path(td) / INTENT).exists())
            self.assertFalse((Path(td) / PREPARED).exists())
            with self.assertRaisesRegex(Refusal,"INCOMPLETE_PREPARE_REQUIRES_OWNER_RECOVERY"):
                prepare_once(td,A,observed_checkpoint=lambda:"a"*64,
                             authorization_callback=lambda r: {"id": r["id"]})

    def test_stale_digest_and_noncanonical_record_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            calls=[]
            with self.assertRaisesRegex(Refusal,"STALE_PREPARE_CHECKPOINT_REFUSED"):
                prepare_once(td,A,observed_checkpoint=lambda:"c"*64,
                             authorization_callback=lambda r:calls.append(r))
            self.assertEqual(calls,[])
            (Path(td)/INTENT).write_text('{"schema":"forged"}\n')
            with self.assertRaises(Refusal):
                prepare_once(td,A,observed_checkpoint=lambda:"a"*64,
                             authorization_callback=lambda r:calls.append(r))
            self.assertEqual(calls,[])

    def test_157_identical_replay_after_checkpoint_advance_refused(self):
        with tempfile.TemporaryDirectory() as td:
            current = ["a" * 64]
            signed = []
            def authorize(request):
                signed.append(request["id"])
                return {"id": request["id"]}
            kwargs = {"observed_checkpoint": lambda: current[0],
                      "authorization_callback": authorize}
            self.assertEqual(prepare_once(td, A, **kwargs), {"id": "writer-A"})
            before = [(name, (Path(td) / name).read_bytes()) for name in (INTENT, PREPARED)]
            current[0] = "c" * 64
            with self.assertRaisesRegex(Refusal, "STALE_PREPARE_CHECKPOINT_REFUSED"):
                prepare_once(td, A, **kwargs)
            self.assertEqual(signed, ["writer-A"])
            self.assertEqual(before, [(name, (Path(td) / name).read_bytes()) for name in (INTENT, PREPARED)])

    def test_symlink_intent_does_not_get_followed(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/INTENT).symlink_to(Path(td)/"outside.json")
            with self.assertRaises(Refusal):
                prepare_once(td,A,observed_checkpoint=lambda:"a"*64,
                             authorization_callback=lambda r:{"id":r["id"]})

if __name__ == "__main__":
    unittest.main()
