import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from action_study import desk
from ignition.controller import Controller
from ignition.evidence_specialist import template
from ignition.store import Conflict, Store


class PrivateDecision(unittest.TestCase):
    def test_revision_delivery_and_active_grants(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ctrl = Controller(Store(folder / "store"))
            for profile in desk.PROFILES:
                task = desk.example(profile)
                m = template(task)
                m["beneficiary"] = "private-name-canary"
                rid, version = ctrl.create({"request_id":"initial-" + profile, "mission":m})
                state = ctrl.advance(rid, version)
                self.assertEqual(state["status"], "verified", state["error"])
                expected = ctrl.deliver(rid, version, {}, trial=True)
                pack = folder / profile
                with ZipFile(io.BytesIO(ctrl.deliver(rid, version))) as z:
                    self.assertTrue(all(b"private-name-canary" not in z.read(n) for n in z.namelist()))
                    z.extractall(pack)
                cmd = [sys.executable, "-IB", str(pack / "action_study/desk.py"), "verify", "decision.json",
                       "--mission", "mission.json", "--expect", expected["sha256"]]
                proc = subprocess.run(cmd, cwd=pack, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                (pack / "mission.json").write_text(json.dumps(dict(task, sources=[])))
                self.assertNotEqual(subprocess.run(cmd, cwd=pack, capture_output=True).returncode, 0)
                m = copy.deepcopy(m)
                m["resources"]["evidence_action"]["sources"] = []
                ctrl.create({"request_id":"amended-" + profile, "version":version, "mission":m}, rid)
                with self.assertRaises(Conflict):
                    ctrl.deliver(rid, version)
                current = ctrl.advance(rid, version+1)
                self.assertEqual(current["evidence_result"]["decision"]["state"], "unavailable")

    def test_reject_changed_purpose_and_private_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctrl = Controller(Store(Path(tmp)))
            task = desk.example("ztf-persistence")
            for flag in (False, True):
                m = template(task)
                if flag:
                    m["purpose"] = "Deploy a model now"
                rid, rev = ctrl.create({"request_id":"contract-" + str(flag), "mission":m,
                                        "sources":[] if flag else [{"text":"private"}]})
                self.assertEqual(ctrl.advance(rid, rev)["status"], "blocked")
                with self.assertRaises(Conflict):
                    ctrl.deliver(rid, rev)
