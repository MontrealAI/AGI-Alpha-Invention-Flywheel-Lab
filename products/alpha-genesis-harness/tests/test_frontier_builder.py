# SPDX-License-Identifier: Apache-2.0
"""Engineering fixtures for construction boundaries, not live invention evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge.adapters import BridgeError, Runtime
from bridge import frontier_builder as builder
from bridge.services import AccessRuntime


CONFIG = {"local_only": True, "allow_paid_requests": False, "providers": {"local": {
    "kind": "openai", "base_url": "http://127.0.0.1:12345/v1",
    "models": {"fixture": {"input_per_million": 0, "output_per_million": 0,
                           "max_output_tokens": 4096, "context_window": 32768,
                           "json_mode": True, "json_schema": True}},
}}}
ROUTE = {"provider": "local", "model": "fixture"}
CONTRACT = {
    "objective": "Return the distinct records in ascending order.",
    "acceptance": "Return a JSON array containing each distinct input integer exactly once, sorted.",
    "development": [{"input": [3, 1, 3], "expected": [1, 3]}],
    "qualification": [{"id": "WITHHELD_CASE_721638", "input": [9, -7, 9, 0], "expected": [-7, 0, 9]}],
}
CORRECT = "def solve(data): return sorted(set(data))"


class FrontierBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            builder.sandbox.execute("def solve(data): return 1", {})
        except builder.sandbox.SandboxError as error:
            if error.code == "SANDBOX_UNAVAILABLE":
                raise unittest.SkipTest(builder.sandbox.SUPPORT) from None
            raise

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.responses, self.prompts = [], []
        base = Runtime(CONFIG, sender=self.send)
        self.runtime = AccessRuntime(base, CONFIG, Path(self.workspace.name))
        self.addCleanup(self.runtime.close)

    def send(self, _url, _headers, body, **_kwargs):
        self.prompts.append(body["messages"][0]["content"])
        return {"choices": [{"message": {"content": self.responses.pop(0)}}],
                "usage": {"prompt_tokens": 170, "completion_tokens": 35}, "model": "fixture"}

    def respond(self, source):
        self.responses.append(json.dumps({"source": source, "rationale": "Engineering test fixture."}))

    def test_development_repair_and_frozen_hidden_qualification(self):
        self.respond("def solve(data): return sorted(data)")
        self.respond(CORRECT)
        checkpoints = []
        result = builder.construct(self.runtime, ROUTE, CONTRACT, on_checkpoint=checkpoints.append)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["attempts"][0]["status"], "development_failed")
        self.assertIn('"failures":', self.prompts[1])
        self.assertNotIn("WITHHELD_CASE_721638", "".join(self.prompts))
        self.assertNotIn("[-7,0,9]", "".join(self.prompts))
        frozen = next(row for row in checkpoints if row["status"] == "qualification_pending")
        self.assertIsNone(frozen["qualification"])
        self.assertEqual(frozen["frozen"]["source_sha256"], result["source_sha256"])
        self.assertEqual(result["qualification"]["passed_count"], 1)
        self.assertIsNone(result["totals"]["actual_complete_cost_usd"])
        self.assertEqual(result["attempts"][1]["usage"]["output_tokens"], 35)

    def test_qualification_failure_cannot_request_repair(self):
        self.respond("def solve(data): return [1, 3]")
        self.respond(CORRECT)
        result = builder.construct(self.runtime, ROUTE, CONTRACT, max_attempts=4)
        self.assertFalse(result["qualified"])
        self.assertEqual(result["status"], "qualification_failed")
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(len(self.responses), 1)
        self.assertIsNotNone(result["frozen"])

    def test_supplied_retained_source_requires_exact_identity(self):
        retained = {"source": CORRECT, "sha256": "0" * 64, "description": "Earlier sorting capability."}
        with self.assertRaises(BridgeError) as raised:
            builder.construct(self.runtime, ROUTE, CONTRACT, retained=retained)
        self.assertEqual(raised.exception.code, "FRONTIER_RETAINED")
        self.assertEqual(self.prompts, [])
        retained["sha256"] = hashlib.sha256(CORRECT.encode()).hexdigest()
        self.respond(CORRECT)
        result = builder.construct(self.runtime, ROUTE, CONTRACT, retained=retained)
        self.assertEqual(result["retained_sha256"], retained["sha256"])
        self.assertIn("Earlier sorting capability.", self.prompts[0])
        self.assertIn("rational_affine", self.prompts[0])

    def test_schema_failure_is_recorded_and_not_silently_retried(self):
        self.responses.append(json.dumps({"source": CORRECT}))
        result = builder.construct(self.runtime, ROUTE, CONTRACT)
        self.assertEqual(result["status"], "model_error")
        self.assertEqual(result["attempts"][0]["error"]["code"], "SCHEMA_RESPONSE")
        self.assertEqual(len(self.prompts), 1)
        self.assertIsNone(result["qualification"])
        self.assertIsNone(result["totals"]["actual_complete_cost_usd"])

    def test_constructor_rejects_remote_provider_before_dispatch(self):
        provider = self.runtime.provider("local")
        with patch.object(provider, "base", "https://example.com/v1"):
            with self.assertRaises(BridgeError) as raised:
                builder.construct(self.runtime, ROUTE, CONTRACT)
        self.assertEqual(raised.exception.code, "FRONTIER_MODEL")
        self.assertEqual(self.prompts, [])

    def test_contract_and_checkpoints_are_detached_from_external_mutation(self):
        contract = copy.deepcopy(CONTRACT)
        self.respond(CORRECT)
        def mutate(snapshot):
            snapshot["qualified"] = True
            if snapshot["status"] == "model_pending":
                contract["qualification"][0]["expected"] = "unwanted mutation"
        result = builder.construct(self.runtime, ROUTE, contract, on_checkpoint=mutate)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["qualification_sha256"], builder.digest(CONTRACT["qualification"]))

    def test_all_failed_development_attempts_are_counted(self):
        self.respond("def solve(data): return []")
        self.respond("def solve(data): return []")
        result = builder.construct(self.runtime, ROUTE, CONTRACT, max_attempts=2)
        self.assertEqual(result["status"], "development_failed")
        self.assertEqual(result["totals"]["model_calls"], 2)
        self.assertTrue(all(a["development"]["total"] == 1 for a in result["attempts"]))
        self.assertIsNone(result["qualification"])
        self.assertIsNone(result["frozen"])

    def test_conventional_runner_checks_types_and_refuses_io(self):
        false_equivalence = builder.run_candidate("def solve(data): return True", [{"input": {}, "expected": 1}])
        self.assertFalse(false_equivalence["passed"])
        refused = builder.run_candidate("def solve(data): return open('probe', 'w').write('x')",
                                        [{"input": {}, "expected": 1}])
        self.assertFalse(refused["passed"])
        self.assertEqual(refused["cases"][0]["error"]["code"], "SYSCALL_REFUSED")

    def test_empty_or_nonfinite_cohorts_are_not_evidence(self):
        for invalid in ([], [{"input": {}, "expected": float("nan")}], [{"input": {}}]):
            with self.assertRaises(BridgeError):
                builder.run_candidate(CORRECT, invalid)

    def test_exposed_examples_cannot_be_relabelled_withheld(self):
        contract = copy.deepcopy(CONTRACT)
        contract["qualification"] = copy.deepcopy(contract["development"])
        with self.assertRaises(BridgeError) as raised:
            builder.construct(self.runtime, ROUTE, contract)
        self.assertEqual(raised.exception.code, "FRONTIER_CONTRACT")
        self.assertEqual(self.prompts, [])

    def test_current_source_identity_binds_the_adopted_sandbox(self):
        self.assertEqual(builder.source_identity()["forge_sandbox.py"], builder.SANDBOX_ORIGIN["sha256"])
        with patch.object(builder, "_LOADED_SOURCE", {}):
            with self.assertRaises(BridgeError) as raised:
                builder.run_candidate(CORRECT, CONTRACT["development"])
        self.assertEqual(raised.exception.code, "FRONTIER_SOURCE_DRIFT")


if __name__ == "__main__":
    unittest.main()
