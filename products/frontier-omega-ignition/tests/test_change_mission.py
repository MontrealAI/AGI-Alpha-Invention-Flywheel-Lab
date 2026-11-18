import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ignition.change_specialist import PRESET
from ignition.controller import Controller
from ignition.server import Service
from ignition.store import Conflict, StateError, Store


class DatedQueue(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.ctrl = Controller(Store(self.root / "state"))
        self.base = json.loads(PRESET.read_bytes())["mission"]
        self.base["beneficiary"] = "Private quarterly review marker"
        self.count = 0

    def submit(self, *, rid=None, version=None, scope=None, mission=None, sources=None):
        m = copy.deepcopy(self.base if mission is None else mission)
        if scope is not None:
            m["resources"]["change_desk"] = scope
        self.count += 1
        body = {"request_id": f"change-desk-{self.count}", "mission": m, "sources": sources or []}
        if rid:
            body["version"] = version
        run_id, rev = self.ctrl.create(body, rid)
        return run_id, rev, self.ctrl.advance(run_id, rev)

    def test_selected_arm_as_of_export_and_amendment(self):
        rid, first, s = self.submit()
        self.assertEqual(s["status"], "verified", s["error"])
        bucket, = s["change_result"]["cohorts"]
        self.assertEqual(bucket["id"], "early_warm")
        self.assertEqual({a["band"] for a in bucket["alerts"]}, {"g", "r"})
        self.assertTrue(all(a["status"] == "awaiting_repeat" and a["followup"] is None for a in bucket["alerts"]))
        self.assertEqual(self.ctrl.deliver(rid, first, {}, trial=True), s["change_result"])
        data = self.ctrl.deliver(rid, first)
        self.assertEqual(data, self.ctrl.deliver(rid, first))
        checks = s["evaluation"]["verification"]
        with ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                self.assertNotIn(self.base["beneficiary"].encode(), z.read(member))
                self.assertNotIn(rid.encode(), z.read(member))
            z.extractall(self.root / "archive")
        kit = self.root / "archive"
        def receive(sha=checks["queue_sha256"]):
            return subprocess.run([sys.executable, "-IB", str(kit / "review_change.py"), "--expect-queue", sha],
                                  cwd=self.root, capture_output=True)
        original = receive()
        self.assertEqual(original.returncode, 0, original.stderr)
        self.assertEqual(json.loads(original.stdout), checks)
        self.assertNotEqual(receive("0" * 64).returncode, 0)
        for name, replacement in (("worklist.csv", b"forged\n"), ("queue.json", b'{"cohorts":[]}'),
                                  ("scope.json", b'{"as_of_utc":"2026-10-29T00:00:00Z","arm":"early_warm"}'),
                                  ("verification.json", b"{}"),
                                  ("invention/early_survey/sources/objects-1.json.gz", b"removed")):
            path = kit / name
            old = path.read_bytes()
            path.write_bytes(replacement)
            self.assertNotEqual(receive().returncode, 0, name)
            path.write_bytes(old)
        changed = {"arm": "early_warm", "as_of_utc": "2026-10-29T00:00:00Z"}
        _, second, at_deadline = self.submit(rid=rid, version=first, scope=changed)
        self.assertEqual(at_deadline["status"], "verified", at_deadline["error"])
        statuses = [a["status"] for a in at_deadline["change_result"]["cohorts"][0]["alerts"]]
        self.assertCountEqual(statuses, ["coverage_gap", "coverage_gap"])
        with self.assertRaises(Conflict):
            self.ctrl.deliver(rid, first)
        _, third, cold = self.submit(rid=rid, version=second, scope=dict(changed, arm="early_cold"))
        self.assertEqual(cold["status"], "verified", cold["error"])
        self.assertEqual(cold["change_result"]["cohorts"][0]["alerts"], [])
        self.assertEqual(len(self.ctrl.store.history(rid)), 3)
        self.assertEqual(Controller(Store(self.root / "state")).view(rid)["version"], third)
        with self.assertRaises(StateError):
            self.ctrl.deliver(rid, third, {"dispatch": True}, trial=True)

    def test_alternate_archive_requires_consent_an_issued_notice_and_a_later_witness(self):
        rid, first, disabled = self.submit()
        off = self.ctrl.deliver(rid, first)
        with ZipFile(io.BytesIO(off)) as package:
            self.assertNotIn("archive-recheck.csv", package.namelist())
            self.assertFalse(any("/exposures/" in path for path in package.namelist()))
        self.assertNotIn("archive_recheck", disabled["change_result"])
        scope = {"as_of_utc": "2026-10-26T00:00:00Z", "arm": "early_warm", "check_other_archive": True}
        _, second, at_issue = self.submit(rid=rid, version=first, scope=scope)
        self.assertEqual(at_issue["status"], "verified", at_issue["error"])
        by_band = at_issue["change_result"]["archive_recheck"]
        self.assertEqual(set(by_band), {"g", "r"})
        before = list(by_band.values())
        self.assertTrue(all(x["witness"] is None and x["status"] == "awaiting_repeat" for x in before))
        intermediate = dict(scope, as_of_utc="2026-10-28T07:00:00Z")
        _, _, single_visit = self.submit(scope=intermediate)
        self.assertEqual(single_visit["status"], "verified", single_visit["error"])
        one = single_visit["change_result"]["archive_recheck"]
        self.assertEqual(one["g"]["status"], "persisted")
        self.assertIsNotNone(one["g"]["witness"])
        self.assertEqual(one["r"]["status"], "awaiting_repeat")
        self.assertIsNone(one["r"]["witness"])
        later = dict(scope, as_of_utc="2026-10-29T00:00:00Z")
        _, third, complete = self.submit(rid=rid, version=second, scope=later)
        self.assertEqual(complete["status"], "verified", complete["error"])
        original, = complete["change_result"]["cohorts"]
        self.assertEqual([a["status"] for a in original["alerts"]], ["coverage_gap", "coverage_gap"])
        evidence = complete["change_result"]["archive_recheck"]
        self.assertEqual(set(evidence), {"g", "r"})
        self.assertTrue(all(x["witness"] and x["fink_status"] == "coverage_gap" and x["status"] == "persisted"
                            for x in evidence.values()))
        self.assertIsNone(evidence["r"]["forced_photometry"])
        _, _, november = self.submit(scope=dict(scope, as_of_utc="2026-11-04T00:00:00Z"))
        self.assertEqual(november["status"], "verified", november["error"])
        late = november["change_result"]["archive_recheck"]["r"]["forced_photometry"]
        self.assertEqual(late["status"], "persisted")
        self.assertTrue(late["carrier_utc"].startswith("2026-11-03T"))
        checked = complete["evaluation"]["verification"]
        with ZipFile(io.BytesIO(self.ctrl.deliver(rid, third))) as package:
            self.assertIn("archive-recheck.csv", package.namelist())
            self.assertTrue(any("/exposures/" in name for name in package.namelist()))
            self.assertFalse(any(name.endswith("/RESULT.json") for name in package.namelist()))
            package.extractall(self.root / "extra")
        def verify():
            return subprocess.run([sys.executable, "-IB", str(self.root / "extra/review_change.py"),
                                   "--expect-queue", checked["queue_sha256"]], capture_output=True)
        replay = verify()
        self.assertEqual(replay.returncode, 0, replay.stderr)
        (self.root / "extra/archive-recheck.csv").write_bytes(b"altered")
        self.assertNotEqual(verify().returncode, 0)
        _, _, cold = self.submit(rid=rid, version=third, scope=dict(later, arm="early_cold"))
        self.assertEqual(cold["status"], "verified", cold["error"])
        self.assertEqual(cold["change_result"]["archive_recheck"], {})

    def test_scope_is_private_http_only(self):
        with Service(self.ctrl, 0) as service:
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{service.server_port}"
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for url in ("/change-desk?lang=fr", "/change-desk.js"):
                    with opener.open(base + url) as resp:
                        self.assertEqual(resp.headers["Cache-Control"], "no-store")
                        self.assertIn("connect-src 'self'", resp.headers["Content-Security-Policy"])
                        self.assertIn("frame-ancestors 'none'", resp.headers["Content-Security-Policy"])
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        opener.open(urllib.request.Request(base + url, headers={"Origin": "null", "Sec-Fetch-Site": "cross-site"}))
                    self.assertEqual(rejected.exception.code, 403)
            finally:
                service.shutdown()
                thread.join()

    def test_reject_wrong_scope_and_stale_or_tampered_state(self):
        valid = self.base["resources"]["change_desk"]
        for bad in (dict(valid, check_other_archive=1), dict(valid, arm=True), dict(valid, artifact="path"), dict(valid, as_of_utc="2026-10-27"),
                    dict(valid, as_of_utc="2026-10-29T00:00:00-04:00"), dict(valid, as_of_utc="2026-10-01T00:00:00Z")):
            self.assertEqual(self.submit(scope=bad)[2]["status"], "blocked")
        self.assertEqual(self.submit(sources=[{"text": "a private observation"}])[2]["status"], "blocked")
        m = copy.deepcopy(self.base)
        m["requirements"].append("Dispatch a telescope observation.")
        self.assertEqual(self.submit(mission=m)[2]["status"], "blocked")
        m["resources"]["followup"] = {}
        with self.assertRaises(StateError):
            self.submit(mission=m)
        rid, revision, _ = self.submit()
        with patch("ignition.change_specialist.identity", return_value="different"):
            view = self.ctrl.view(rid)
            self.assertEqual(view["status"], "stale")
            self.assertNotIn("change_result", view)
            with self.assertRaises(Conflict):
                self.ctrl.deliver(rid, revision)
        state = self.ctrl.store.get(rid)
        state["change_result"]["cohorts"][0]["coverage"][0]["comparisons"] += 1
        self.ctrl.store.save(state)
        with self.assertRaises(Conflict):
            self.ctrl.deliver(rid, revision)


if __name__ == "__main__":
    unittest.main()
