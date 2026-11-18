import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ignition.controller import Controller
from ignition.followup_specialist import PRESET
from ignition.store import Conflict, StateError, Store
from ignition.server import Service


class FollowupMission(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.work = Path(work.name)
        self.ctrl = Controller(Store(self.work / "workspace"))
        self.mission = json.loads(PRESET.read_bytes())["mission"]
        self.mission["beneficiary"] = "Private operator marker e202aaf309"
        self.number = 0

    def submit(self, rid=None, prior=None, sources=None):
        self.number += 1
        body = {"mission": self.mission, "request_id": f"followup-{self.number}", "sources": sources or []}
        if rid:
            body["version"] = prior
        rid, version = self.ctrl.create(body, rid)
        return rid, version, self.ctrl.advance(rid, version)

    def test_bounded_scope_export_and_history(self):
        rid, version, result = self.submit()
        self.assertEqual(result["status"], "verified", result["error"])
        plan = result["followup_result"]
        self.assertEqual(result["evaluation"]["verification"]["direct_objective"], plan["objective"])
        self.assertFalse(plan["dispatch_authorized"])
        self.assertEqual(self.ctrl.deliver(rid, version, {}, trial=True), plan)
        package = self.ctrl.deliver(rid, version)
        self.assertEqual(self.ctrl.deliver(rid, version), package)
        with ZipFile(io.BytesIO(package)) as archive:
            for name in archive.namelist():
                self.assertNotIn(self.mission["beneficiary"].encode(), archive.read(name))
                self.assertNotIn(rid.encode(), archive.read(name))
            archive.extractall(self.work / "delivery")
        def replay():
            return subprocess.run([sys.executable, "-IB", str(self.work / "delivery/review_followup.py")],
                                  capture_output=True, cwd=self.work)
        first = replay()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["plan"], plan)
        paper = self.work / "delivery/plan.json"
        paper.write_text(json.dumps(dict(plan, dispatch_authorized=0)))
        self.assertNotEqual(replay().returncode, 0)
        paper.write_text(json.dumps(dict(plan, dispatch_authorized=True)))
        self.assertNotEqual(replay().returncode, 0)
        paper.unlink()
        self.assertNotEqual(replay().returncode, 0)
        self.mission["resources"]["followup"]["max_slots"] = 0
        _, revision, changed = self.submit(rid, version)
        self.assertEqual(changed["status"], "verified", changed["error"])
        self.assertEqual(changed["followup_result"]["slots"], [])
        self.assertEqual(changed["followup_result"]["objective"], 0)
        self.assertNotEqual(changed["contract_sha256"], result["contract_sha256"])
        with self.assertRaises(Conflict):
            self.ctrl.deliver(rid, version)
        with self.assertRaises(StateError):
            self.ctrl.deliver(rid, revision, {"dispatch": True}, trial=True)
        restored = Controller(Store(self.work / "workspace"))
        self.assertEqual(restored.view(rid)["version"], revision)
        self.assertEqual(restored.store.history(rid)[0]["followup_result"], plan)

    def test_scope_and_current_source(self):
        for params in ({"visits_per_target": True, "max_slots": 1},
                       {"visits_per_target": 2, "max_slots": 7},
                       {"visits_per_target": 2, "max_slots": 1, "site": "private site"}):
            self.mission["resources"]["followup"] = params
            _, _, result = self.submit()
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["artifact"])
        self.mission["resources"]["followup"] = {"visits_per_target": 1, "max_slots": 2}
        self.mission["requirements"].append("Acquire real telescope time.")
        self.assertEqual(self.submit()[2]["status"], "blocked")
        self.mission["requirements"].pop()
        self.assertEqual(self.submit(sources=[{"note": "private source"}])[2]["status"], "blocked")
        self.mission["resources"]["endpoint_lab"] = {}
        with self.assertRaises(StateError):
            self.submit()
        self.mission["resources"].pop("endpoint_lab")
        rid, version, _ = self.submit()
        with patch("ignition.followup_specialist.identity", return_value="changed"):
            self.assertEqual(self.ctrl.view(rid)["status"], "stale")
            self.assertNotIn("followup_result", self.ctrl.view(rid))
            with self.assertRaises(Conflict):
                self.ctrl.deliver(rid, version)
        state = self.ctrl.store.get(rid)
        state["followup_result"]["objective"] += 1
        self.ctrl.store.save(state)
        with self.assertRaises(Conflict):
            self.ctrl.deliver(rid, version)

    def test_private_http_lifecycle(self):
        with Service(self.ctrl, 0) as service:
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{service.server_port}"
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

                def call(path, body=None, **headers):
                    if body is not None:
                        headers.update({"Content-Type": "application/json", "X-Ignition-Request": "1"})
                    request = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                                     headers=headers)
                    return opener.open(request, timeout=10)

                for route in ("/follow-up?lang=fr", "/followup.js"):
                    with call(route) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                        self.assertNotIn("sandbox allow-scripts", response.headers["Content-Security-Policy"])
                        self.assertNotIn(self.mission["beneficiary"].encode(), response.read())

                def publish(path, request_id, version=None):
                    body = {"mission": self.mission, "request_id": request_id}
                    if version is not None:
                        body["version"] = version
                    with call(path, body) as received:
                        self.assertEqual(received.status, 202)
                        rid = json.load(received)["id"]
                    run_path = "/api/runs/" + rid
                    deadline = time.monotonic() + 8  # finite HTTP regression poll
                    while time.monotonic() < deadline:
                        with call(run_path) as response:
                            data = json.load(response)
                        if data["status"] not in {"queued", "running"}:
                            break
                        time.sleep(0.03)
                    self.assertEqual(data["status"], "verified", data.get("error"))
                    return run_path, data

                path, first = publish("/api/runs", "followup-api-001")
                self.assertFalse(first["followup_result"]["dispatch_authorized"])
                with call(path + "/bundle?version=1") as response:
                    self.assertEqual(response.headers["Content-Type"], "application/zip")
                    with ZipFile(io.BytesIO(response.read())) as archive:
                        self.assertEqual(json.loads(archive.read("plan.json")), first["followup_result"])
                self.mission["resources"]["followup"]["max_slots"] = 0
                _, amended = publish(path + "/amend", "followup-api-002", 1)
                self.assertEqual(amended["followup_result"]["objective"], 0)
                with self.assertRaises(urllib.error.HTTPError) as refused:
                    call(path + "/bundle?version=1")
                self.assertEqual(refused.exception.code, 409)
                with self.assertRaises(urllib.error.HTTPError) as refused:
                    call(path, Origin="null")
                self.assertEqual(refused.exception.code, 403)
            finally:
                service.shutdown()
                thread.join()
