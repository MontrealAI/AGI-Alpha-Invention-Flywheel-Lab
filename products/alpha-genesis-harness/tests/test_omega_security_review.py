# SPDX-License-Identifier: Apache-2.0
"""Independent boundary regressions for the GENESIS NEXT integration.

These tests exercise public persistence and the emitted candidate's real
verification method. They are authored engineering tests, not live model runs.
"""
import copy
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.genesis_next import EvidenceIndex, GenesisNextService, construct_candidate, load_candidate
import bridge.genesis_next as genesis_module
from bridge.server import HarnessServer
from bridge.workflows import WorkflowService, digest, encoded


def instrument():
    return {"name": "Reviewer addition", "inputs": ["x", "y"],
            "outputs": {"total": {"op": "add", "args": [{"field": "x"}, {"field": "y"}]}},
            "conditions": "Exact integer arithmetic", "limitations": "No empirical claim"}


class CandidateVerificationReview(unittest.TestCase):
    def test_lazy_genesis_import_rejects_previously_loaded_stale_evaluator(self):
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp)
            package = product / "bridge"
            package.mkdir()
            for source in (genesis_module.PRODUCT / "bridge").glob("*.py"):
                shutil.copyfile(source, package / source.name)
            script = """from pathlib import Path
import bridge.workflows
from bridge.adapters import BridgeError
path = Path('bridge/instruments.py')
path.write_bytes(path.read_bytes() + b'\\n# later disk version before lazy GENESIS initialization\\n')
try:
    import bridge.genesis_next
except BridgeError as error:
    assert error.code == 'GENESIS_SOURCE_DRIFT', error.code
else:
    raise AssertionError('Old evaluator was bound to new disk source identity')
"""
            result = subprocess.run([sys.executable, "-c", script], cwd=product,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_checker_disk_drift_cannot_bind_old_loaded_code_to_new_identity(self):
        expected = genesis_module.source_identity()
        original = genesis_module.PRODUCT
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp)
            (product / "bridge").mkdir()
            for name in expected:
                if name.endswith(".py"):
                    (product / "bridge" / name).write_bytes((original / "bridge" / name).read_bytes())
            with patch.object(genesis_module, "PRODUCT", product):
                self.assertEqual(genesis_module.source_identity(), expected)
                path = product / "bridge" / "instruments.py"
                path.write_bytes(path.read_bytes() + b"\n# changed on disk while evaluator remains loaded\n")
                with self.assertRaises(BridgeError):
                    genesis_module.source_identity()

    def test_cache_cannot_turn_document_bytes_into_an_accepted_instrument(self):
        with tempfile.TemporaryDirectory() as temp:
            built = construct_candidate(Path(temp) / "candidate")
            cls = load_candidate(built["path"])
            candidate = object.__new__(cls)
            candidate.evidence_index = EvidenceIndex("reviewed-checker-v1")
            candidate.checker_dependencies = {"checker": "a" * 64}
            raw = encoded(instrument())
            candidate._read_artifact = lambda state, name: raw
            candidate._event = lambda *args: None
            spec = {"acceptance": [{"artifact": "addition.json", "kind": "instrument",
                "input": {"x": 7, "y": 11}, "expected": {"total": 18}}], "max_operations": 1000}
            state = {"spec": spec, "spec_hash": digest(spec), "artifacts": {
                "addition.json": {"kind": "instrument", "sha256": hashlib.sha256(raw).hexdigest()}}}
            candidate._verify(state)
            self.assertTrue(state["verification"]["passed"])
            changed = copy.deepcopy(state)
            changed["artifacts"]["addition.json"]["kind"] = "document"
            baseline = copy.deepcopy(changed)
            WorkflowService._verify(candidate, baseline)
            self.assertFalse(baseline["verification"]["passed"])
            candidate._verify(changed)
            self.assertFalse(changed["verification"]["passed"],
                "Cache reuse must preserve the baseline's artifact-type acceptance condition")

    def test_emitted_candidate_cannot_be_replaced_with_arbitrary_python(self):
        with tempfile.TemporaryDirectory() as temp:
            built = construct_candidate(Path(temp) / "candidate")
            built["path"].write_text("raise RuntimeError('should never execute')\n")
            with self.assertRaises(BridgeError) as raised:
                load_candidate(built["path"])
            self.assertEqual(raised.exception.code, "GENESIS_SOURCE")


class PersistentEvidenceReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workflows = WorkflowService(Runtime({"local_only": True}), Path(self.temp.name) / "private")
        self.service = GenesisNextService(self.workflows)

    def tearDown(self):
        self.workflows.close()
        self.temp.cleanup()

    def test_forged_persistent_capability_promotion_fails_authentication(self):
        wrapper = json.loads(self.service.path.read_text())
        wrapper["state"]["capabilities"][0]["status"] = "independently_verified"
        self.service.path.write_text(json.dumps(wrapper))
        with self.assertRaises(BridgeError) as raised:
            self.service.status()
        self.assertEqual(raised.exception.code, "GENESIS_INTEGRITY")

    def test_forged_persistent_cache_result_fails_authentication(self):
        request = {"instrument": instrument(), "inputs": {"x": 7, "y": 11}, "expected": {"total": 18}}
        first = self.service.verify_instrument(request)
        self.assertTrue(first["verification"]["accepted"])
        wrapper = json.loads(self.service.path.read_text())
        index = wrapper["state"]["evidence_index"]
        entry = next(iter(index["entries"].values()))
        entry["result"]["actual"]["total"] = 999
        entry["sha256"] = digest({k: v for k, v in entry.items() if k != "sha256"})
        index["sha256"] = digest({k: v for k, v in index.items() if k != "sha256"})
        self.service.path.write_text(json.dumps(wrapper))
        with self.assertRaises(BridgeError) as raised:
            self.service.verify_instrument(request)
        self.assertEqual(raised.exception.code, "GENESIS_INTEGRITY")

    def test_frontier_replay_reconsiders_without_promoting_a_capability(self):
        before = self.service.status()["capabilities"]
        result = self.service.replay({"title": "Operator claim", "url": "local:unverified-report",
            "observed_at": "2026-01-01T00:00:00+00:00", "content_sha256": "a" * 64,
            "capability_ids": ["dependency-evidence-reuse"], "evidence_status": "reproduced"})
        self.assertTrue(result["reactivated"])
        self.assertTrue(all(row["unlocked"] is False for row in result["reactivated"]))
        self.assertEqual(result["state"]["capabilities"], before)

    def test_unknown_import_method_cannot_grant_portable_evidence_authority(self):
        value = self.service.export()
        self.assertIn("Imports do not inherit authority", value["export_notice"])
        self.assertFalse(hasattr(self.service, "import_archive"))


class IntegrationAuthorizationReview(unittest.TestCase):
    def test_new_mutating_routes_require_same_origin_session_before_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "private"
            server = HarnessServer(("127.0.0.1", 0), Runtime({"local_only": True}),
                                   config={"local_only": True}, workspace=root)
            initial_connections = server._local_connections
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for route in ("/api/genesis-next/demo", "/api/genesis-next/opportunity",
                              "/api/genesis-next/verify", "/api/local-models/connect",
                              "/api/local-models/disconnect", "/api/local-models/discover"):
                    for headers in ({}, {"X-Harness-Token": server.token, "Origin": "https://foreign.example"}):
                        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                        connection.request("POST", route, "{}", {"Content-Type": "application/json", **headers})
                        response = connection.getresponse()
                        self.assertEqual(response.status, 403, route)
                        response.read()
                        connection.close()
                self.assertIsNone(server._genesis_next)
                self.assertIs(server._local_connections, initial_connections)
                self.assertFalse(root.exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(3)


if __name__ == "__main__":
    unittest.main()
