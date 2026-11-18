import base64
import hashlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from ignition.controller import Controller
from ignition import scroll_specialist as specialist
from ignition.store import Conflict, StateError, Store


def body_from(path):
    doc = json.loads(path.read_bytes())
    return {key: doc[key] for key in ("mission", "sources")}


class ScrollRecipient(unittest.TestCase):
    def test_real_package_revision_export_and_private_input(self):
        with tempfile.TemporaryDirectory() as folder:
            ctrl = Controller(Store(Path(folder) / "state"))
            body = body_from(specialist.PRESET)
            body.update(request_id="scroll-numerical-control")
            run_id, version = ctrl.create(body)
            state = ctrl.advance(run_id, version)
            self.assertEqual(state["status"], "verified", state.get("error"))
            self.assertEqual(state["evaluation"]["scope"], specialist.SCOPE)
            self.assertIsNone(state["scroll_result"]["beneficiary_acceptance"])
            self.assertIn(state["field_decision"]["disposition"], {"needs_evidence", "withhold"})
            data = ctrl.deliver(run_id, version)
            self.assertEqual(hashlib.sha256(data).hexdigest(), state["artifact"]["sha256"])
            with ZipFile(io.BytesIO(data)) as z:
                self.assertEqual(set(z.namelist()), set(specialist.MEMBERS))
                self.assertTrue(all(not n.endswith((".u8", ".f32", ".tif")) for n in z.namelist()))
            values = bytes([3, 3, 3, 3, 3])
            encoded = base64.b64encode(values).decode()
            with self.assertRaises(StateError):
                ctrl.deliver(run_id, version, {"pixels_base64": encoded}, trial=True)
            result = ctrl.deliver(run_id, version, {"pixels_base64": encoded, "rights_basis": "Self-authored test"},
                                  trial=True)
            self.assertEqual(base64.b64decode(result["output_base64"]), struct.pack("<5f", *([0] * 5)))
            body.update(version=version, request_id="scroll-next-revision")
            ctrl.create(body, run_id)
            with self.assertRaises(Conflict):
                ctrl.deliver(run_id, version)

    def test_research_requires_authority_and_reports_interrupted_trial(self):
        with tempfile.TemporaryDirectory() as folder:
            ctrl = Controller(Store(Path(folder) / "state"))
            body = body_from(specialist.PRESET.parent / "scroll_research.json")
            body["mission"]["authority"] = {}
            run_id, version = ctrl.create(dict(body, request_id="research-without-authority"))
            self.assertEqual(ctrl.advance(run_id, version)["status"], "blocked")
            body["mission"]["authority"] = {"public_sources": True}
            run_id, version = ctrl.create(dict(body, request_id="interrupted-research-trial"))
            s = ctrl.store.get(run_id)
            s["scroll_field_started"] = "2026-11-18T12:00:00Z"
            ctrl.store.save(s)
            recovered = ctrl.advance(run_id, version)
            self.assertEqual(recovered["field_decision"]["disposition"], "needs_evidence")
            self.assertIn("interrupted", recovered["scroll_field"]["error"])
            self.assertIsNone(recovered["scroll_field"]["receipt"])
            self.assertEqual(ctrl.advance(run_id, version)["scroll_field"], recovered["scroll_field"])

    def test_refuses_private_source_scope_and_stale_data(self):
        with tempfile.TemporaryDirectory() as folder:
            ctrl = Controller(Store(Path(folder) / "state"))
            body = body_from(specialist.PRESET)
            body.update(request_id="scroll-scope-boundary", sources=[{"text": "private scan canary"}])
            with self.assertRaises(StateError):
                ctrl.create(body)
            self.assertEqual(list(ctrl.store.inventory()), [])
            with self.assertRaises(StateError):
                ctrl.create(dict(body, request_id="two-scroll-specialists", mission={
                    **body["mission"], "resources": {**body["mission"]["resources"], "evidence_action": {}}}))


if __name__ == "__main__":
    unittest.main()
