"""Dispatch, restart, and download checks; the model in this unit suite is synthetic."""
import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection

from ignition.controller import Controller
from ignition.dispatcher import Dispatcher
from ignition.server import Service
from ignition.store import Store
from test_controller import TestProvider
from test_integrity_boundaries import body


def wait_for(check):
    until = time.monotonic() + 15
    while time.monotonic() < until:
        result = check()
        if result:
            return result
        time.sleep(.02)
    raise AssertionError("Timed out waiting for recorded state")


class DispatchTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(temp.name)
        self.model = TestProvider()
        self.ctrl = Controller(self.store, lambda: self.model)
        self.input = body()
        self.input["mission"]["authority"] = {"local_model": True}

    def test_recover_after_unnotified_intake_and_retry_after_provider_recovery(self):
        self.model.fail_once = "challenge"
        run, rev = self.ctrl.create(self.input)
        waiting, v2 = self.ctrl.create(dict(self.input, request_id="stopped-before-boot"))
        self.ctrl.set_operation(waiting, v2, "stop")
        dispatch = Dispatcher(1)
        try:
            dispatch.recover(self.ctrl)
            wait_for(lambda: self.store.get(run)["status"] == "blocked")
        finally:
            dispatch.close()
        self.assertEqual(self.store.get(waiting)["calls"], {})
        restarted = Controller(Store(self.store.root), lambda: self.model)
        second = Dispatcher(1)
        self.addCleanup(second.close)
        second.recover(restarted)
        second.enqueue(restarted, run, rev, retry=True)
        wait_for(lambda: self.store.get(run)["status"] == "verified")
        self.assertEqual(self.model.stages, ["discover", "challenge", "challenge", "construct"])
        self.assertEqual(restarted.create(self.input), (run, rev))

    def test_bounded_execution_persists_waiting_work_and_completes_each_revision_once(self):
        entered, release = threading.Event(), threading.Event()

        def gate(stage, _):
            if stage == "discover":
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("Test did not release worker")

        self.model.before = gate
        dispatch = Dispatcher(1)
        self.addCleanup(dispatch.close)
        runs = []
        try:
            for i in range(5):
                runs.append(self.ctrl.create(dict(self.input, request_id=f"bounded-test-{i}")))
            dispatch.enqueue(self.ctrl, *runs[0])
            self.assertTrue(entered.wait(5))
            for run in runs:
                dispatch.enqueue(self.ctrl, *run)
            with dispatch.condition:
                self.assertEqual(len(dispatch.active), 1)
            with self.store.connection() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM dispatch_queue").fetchone()[0], 5)
        finally:
            release.set()
        wait_for(lambda: all(self.store.get(run)["status"] == "verified" for run, _ in runs))
        self.assertEqual(self.model.stages.count("construct"), 5)

    def test_real_http_inventory_and_evidence_export(self):
        with Service(self.ctrl, 0) as service:
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            def request(method, path, payload=None):
                conn = HTTPConnection("127.0.0.1", service.server_port, timeout=10)
                try:
                    headers = {"X-Ignition-Request": "1", "Content-Type": "application/json"}
                    conn.request(method, path, json.dumps(payload) if payload is not None else None, headers)
                    response = conn.getresponse()
                    return response.status, response.getheader("Content-Disposition"), json.loads(response.read())
                finally:
                    conn.close()
            try:
                status, _, state = request("POST", "/api/runs", self.input)
                self.assertEqual(status, 202)
                run = state["id"]
                wait_for(lambda: self.store.get(run)["status"] == "verified")
                self.assertEqual(request("GET", "/api/runs")[2]["runs"][0]["id"], run)
                status, disposition, receipt = request("GET", f"/api/runs/{run}/evidence?version=1")
                self.assertEqual(status, 200)
                self.assertIn("-v1-evidence.json", disposition)
                self.assertEqual(receipt["artifact"]["sha256"], self.store.get(run)["artifact"]["sha256"])
                self.assertNotIn("exchanges", receipt)
                self.assertEqual(request("GET", f"/api/runs/{run}/evidence?version=2")[0], 404)
            finally:
                service.shutdown()
                thread.join()
