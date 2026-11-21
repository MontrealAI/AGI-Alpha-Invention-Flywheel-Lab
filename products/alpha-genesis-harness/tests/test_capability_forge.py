# SPDX-License-Identifier: Apache-2.0
"""Engineering fixtures only. Live model evidence is recorded by the separate study."""
import http.client
import inspect
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from bridge.adapters import BridgeError, Runtime
from bridge.forge import ForgeWorkflow, development
from bridge import forge_sandbox as sandbox, forge_telemetry as telemetry
from bridge.server import HarnessServer
from bridge.services import AccessRuntime


CONFIG = {"local_only": True, "providers": {"local": {
    "kind": "openai", "base_url": "http://127.0.0.1:12345/v1",
    "models": {"test-model": {"input_per_million": 0, "output_per_million": 0}},
}}}
MISSION = {"objective": "Find the exact relation", "provider": "local", "model": "test-model"}
CASE = {"A": [[2, 0], [4, 0], [6, 0]], "y": [3, 6, 10], "target": [1, 0], "faults": 1}
FIXTURE = (
    "from fractions import Fraction\nfrom itertools import combinations\nfrom math import gcd\n"
    "def validate(data): return data['A'], data['y'], data['target'], data['faults']\n"
    + inspect.getsource(telemetry._elimination) + inspect.getsource(telemetry.verify)
    + "solve = verify\n"
)


class OracleTests(unittest.TestCase):
    def test_state_can_be_underdetermined_while_target_is_exact(self):
        self.assertEqual(telemetry.verify(CASE), {"status": "determined", "value": "3/2"})
        self.assertEqual(telemetry.verify({**CASE, "target": [1, 1]}), {"status": "ambiguous"})

    def test_competing_fault_explanations_and_impossibility(self):
        case = {"A": [[1], [1]], "y": [0, 1], "target": [1], "faults": 1}
        self.assertEqual(telemetry.verify(case), {"status": "ambiguous"})
        self.assertEqual(telemetry.verify({**case, "faults": 0}), {"status": "inconsistent"})
        self.assertEqual(telemetry.verify({**case, "faults": 2, "target": [0]}),
                         {"status": "determined", "value": "0"})

    def test_exact_format_requires_rationals_and_rejects_true_as_measurement(self):
        self.assertEqual(telemetry.normalize({"status": "determined", "value": "6/4"})["value"], "3/2")
        with self.assertRaises(ValueError):
            telemetry.normalize({"status": "determined", "value": 1.5})
        with self.assertRaises(ValueError):
            telemetry.validate({**CASE, "faults": True})


class IsolatedForgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            sandbox.execute("def solve(data): return 1", {})
        except sandbox.SandboxError as error:
            if error.code == "SANDBOX_UNAVAILABLE":
                raise unittest.SkipTest(sandbox.SUPPORT) from None
            raise

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.responses = []
        self.prompts = []
        runtime = Runtime(CONFIG, sender=self.send)
        self.access = AccessRuntime(runtime, CONFIG, self.root)
        self.addCleanup(self.access.close)
        self.service = ForgeWorkflow(self.access, self.root / "forge")
        self.addCleanup(self.service.close)

    def send(self, _url, _headers, body, **_):
        self.prompts.append(body["messages"][0]["content"])
        return {"choices": [{"message": {"content": self.responses.pop(0)}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 25}, "model": "fixture-model"}

    def respond_with(self, source, *, plain=False):
        response = ("# Exact test fixture\n" + source if plain else json.dumps({
            "summary": "Use an exact instrument", "actions": [
                {"tool": "write_document", "name": "candidate.txt", "content": source}], "done": True,
        }))
        self.responses.extend([
            "The target may live in the row space even when the state has free coordinates.",
            response,
        ])

    def test_kernel_filesystem_refusal_and_allowed_modules(self):
        with self.assertRaises(sandbox.SandboxError) as raised:
            sandbox.execute("def solve(data): return open('safe-probe.txt', 'w').write('probe')", {})
        self.assertEqual(raised.exception.code, "SYSCALL_REFUSED")
        with self.assertRaises(sandbox.SandboxError) as raised:
            sandbox.execute("import socket\ndef solve(data): return 1", {})
        self.assertEqual(raised.exception.code, "CANDIDATE_ERROR")
        self.assertEqual(sandbox.execute(
            "from fractions import Fraction\ndef solve(data): return str(Fraction(4, 6))", {})["answer"], "2/3")

    def test_development_overfit_stops_at_sealed_checks_without_retry(self):
        def key(data):
            return repr(tuple(data[name] for name in ("A", "y", "target", "faults")))
        memo = {key(case["input"]): telemetry.verify(case["input"]) for case in development()}
        self.respond_with(
            f"memo = {memo!r}\n"
            "def solve(data):\n"
            "    key = repr(tuple(data[name] for name in ('A', 'y', 'target', 'faults')))\n"
            "    return memo.get(key, {'status':'ambiguous'})\n"
        )
        created = self.service.create_mission(MISSION)
        ident = created["id"]
        self.assertNotIn("cohorts", created["forge"])
        self.service.step(ident)
        run = self.service.step(ident)
        self.assertEqual(run["status"], "needs_review")
        self.assertEqual(run["model_calls"], 2)
        self.assertEqual(len(run["forge"]["results"]["qualification"]), 24)
        self.assertEqual(self.service.capabilities()["capabilities"], [])
        for digest in run["forge"]["commitments"].values():
            self.assertTrue(all(digest not in prompt for prompt in self.prompts))
        with self.assertRaises(BridgeError):
            self.service.bundle(ident)

    def test_model_candidate_qualifies_exports_and_changes_successor_execution(self):
        self.respond_with(FIXTURE, plain=True)
        run = self.service.create_mission(MISSION)
        self.service.step(run["id"])
        run = self.service.step(run["id"])
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["model_calls"], 2)
        self.assertEqual(len(run["forge"]["results"]["transfer"]), 16)
        frozen = run["forge"]["frozen_artifact"]["sha256"]
        self.assertEqual(self.service.capabilities()["capabilities"][0]["version"], frozen)
        self.assertTrue(self.service.reuse(run["id"], CASE)["passed"])
        with zipfile.ZipFile(io.BytesIO(self.service.bundle(run["id"]))) as bundle:
            self.assertEqual(bundle.testzip(), None)
            self.assertEqual(json.loads(bundle.read("evidence.json"))["candidate_sha256"], frozen)
            self.assertIn("forge_sandbox.py", bundle.namelist())
        successor = self.service.create_mission({**MISSION, "objective": "Fresh data"})
        successor = self.service.step(successor["id"])
        self.assertEqual(successor["model_calls"], 0)
        self.assertEqual(successor["status"], "complete")
        self.assertEqual(successor["forge"]["frozen_artifact"]["sha256"], frozen)
        self.assertNotEqual(run["forge"]["commitments"], successor["forge"]["commitments"])
        self.service.retire(successor["id"])
        self.assertEqual(self.service.capabilities()["capabilities"][0]["id"], run["id"])
        with self.assertRaises(BridgeError):
            self.service.reuse(successor["id"], CASE)

    def test_sealed_interruption_resumes_without_another_model_call(self):
        self.respond_with(FIXTURE)
        ident = self.service.create_mission(MISSION)["id"]
        self.service.step(ident)
        original = telemetry.score
        calls = 0

        def interrupted(source, data):
            nonlocal calls
            calls += 1
            if calls == 10:  # Eight exposed checks plus one completed sealed check.
                raise OSError("interrupted outside the model request")
            return original(source, data)

        with patch("bridge.forge.telemetry.score", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.service.step(ident)
        saved = self.service.get(ident)
        self.assertEqual(saved["status"], "interrupted")
        self.assertEqual(len(saved["forge"]["results"]["qualification"]), 1)
        self.service.close()
        resumed_service = ForgeWorkflow(self.access, self.root / "forge")
        self.addCleanup(resumed_service.close)
        resumed_service.resume(ident, background=False)
        run = resumed_service.step(ident)
        self.assertEqual(run["status"], "complete")
        self.assertEqual(run["model_calls"], 2)
        self.assertEqual(run["forge"]["frozen_artifact"], saved["forge"]["frozen_artifact"])


class ForgeHTTPTests(unittest.TestCase):
    def test_paths_require_auth_and_do_not_expose_internal_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            server = HarnessServer(("127.0.0.1", 0), workspace=Path(directory) / "workspace")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def call(path, *, token=False, foreign=False):
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["X-Harness-Token"] = server.token
                if foreign:
                    headers["Origin"] = "https://elsewhere.example"
                conn.request("POST", path, "{}", headers)
                res = conn.getresponse()
                res.read()
                conn.close()
                return res.status

            try:
                for path in ("create", "start", "bundle", "reuse", "registry", "retire"):
                    self.assertEqual(call("/api/forge/" + path), 403)
                    self.assertEqual(call("/api/forge/" + path, token=True, foreign=True), 403)
                self.assertEqual(call("/api/forge/_load", token=True), 404)
                self.assertEqual(call("/api/forge/import_archive", token=True), 404)
                self.assertIsNone(server._forge)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(5)


if __name__ == "__main__":
    unittest.main()
