# SPDX-License-Identifier: Apache-2.0
"""State, permission and sequestered-acceptance regressions for economic missions."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge.adapters import BridgeError, Runtime
from bridge.economic_mission import ARTIFACT
from bridge.services import AccessRuntime
from bridge.workflows import WorkflowService, digest
from scripts.qualify_economic_mission import replay


def sources():
    result = {}
    for ident in ("measurement", "archives", "capacity"):
        body = f"Official record for the {ident} experimental workflow."
        result[ident] = {"label": ident, "url": f"https://example.com/{ident}",
                         "snapshot": {"body": body, "sha256": hashlib.sha256(body.encode()).hexdigest()}}
    return result


def specification(*, bad_holdout=False):
    route = {"provider": "local", "model": "fixture"}

    def case(x, y):
        return {"input": {"x": x}, "expected": {"result": y}}

    return {
        "objective": "Find a useful way to use our authorized evidence.", "roles": {"researcher": route, "builder": route},
        "tool_permissions": ["construct_instrument"], "max_iterations": 2, "max_actions": 2,
        "economic_mission": {"beneficiary": "Test", "sources": sources(),
                             "contracts": {"measurement": {"source": "measurement", "goal": "Double x for this test.",
                                "development": [case(3, 6)],
                                "qualification": [case(717123, 1434246), case(-11, 19 if bad_holdout else -22)]}}},
    }


def proposal(*, wrong_source=False):
    opportunities = [
        {"title": label, "outcome": "Outcome for " + label, "constraint": "Missing measured outcome",
         "alternative": "Conventional computation", "experiment": "Independent comparison",
         "capture": "Investigate repeat use", "source": label, "quote": f"the {label} experimental workflow",
         "contract": "measurement" if index == 0 else None}
        for index, label in enumerate(sources())
    ]
    if wrong_source:
        opportunities[0].update(source="archives", quote="the archives experimental workflow")
    return {"opportunities": opportunities, "selection": 0, "rationale": "Use the registered experiment first."}


def candidate(name=ARTIFACT):
    return {"summary": "Construct a general equation", "done": True, "actions": [
        {"tool": "construct_instrument", "name": name,
         "spec": {"name": "instrument", "inputs": ["x"], "outputs": {"result": {"formula": "2*x"}}}}]}


class EconomicMissionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "workflows"
        self.replies = []
        self.requests = []
        self.service = self.open_service()
        self.addCleanup(lambda: self.service.close())

    def open_service(self, *, remote=False):
        host = "https://example.com" if remote else "http://127.0.0.1:8123"
        config = {"providers": {"local": {"kind": "openai", "base_url": host + "/v1",
                  "models": {"fixture": {"input_per_million": 0, "output_per_million": 0}}}}}

        def call(url, headers, body, timeout):
            self.requests.append(body)
            return {"model": "fixture", "choices": [{"message": {"content": json.dumps(self.replies.pop(0))}}],
                    "usage": {"prompt_tokens": 42, "completion_tokens": 11}}

        return WorkflowService(AccessRuntime(Runtime(config, sender=call), config), self.root)

    def collect(self, spec):
        ident = self.service.create(spec)["id"]
        for _ in spec["economic_mission"]["sources"]:
            self.assertEqual(self.service.step(ident)["status"], "ready")
        return ident

    def test_source_binding_portable_retention_and_hidden_qualification(self):
        ident = self.collect(specification())
        self.assertEqual(len(self.requests), 0)
        initial = self.service.get(ident)
        self.assertNotIn("qualification", initial["spec"]["economic_mission"]["contracts"]["measurement"])
        with self.assertRaisesRegex(BridgeError, "once execution ends"):
            self.service.export(ident)
        self.replies.extend([proposal(), candidate()])
        self.assertEqual(self.service.step(ident)["phase"], "builder")
        final = self.service.step(ident)
        self.assertEqual(final["status"], "complete")
        self.assertEqual(final["verdicts"]["INDEPENDENT_ACCEPTANCE"], "demonstrated")
        self.assertEqual(final["verdicts"]["REAL_VALUE_CAPTURE"], "not_established")
        self.assertNotIn("717123", json.dumps(self.requests))
        self.assertEqual(final["economic_mission"]["operating_assessment"]["commercial_validation"], "NOT_ESTABLISHED")
        self.assertEqual(self.service.reuse(ident, {"x": 14})["outputs"][ARTIFACT]["output"], {"result": 28})
        archive = self.service.export(ident)
        self.assertEqual(final["economic_mission"]["frozen"]["sha256"],
                         hashlib.sha256(archive["files"][ARTIFACT].encode()).hexdigest())
        events = final["events"]
        self.assertLess(next(e["index"] for e in events if e["kind"] == "economic_candidate_frozen"),
                        next(e["index"] for e in events if e["kind"] == "verification" and e["detail"]["stage"] == "qualification"))
        self.assertEqual(len(final["request_costs"]), 2)
        with self.assertRaisesRegex(BridgeError, "audit records"):
            self.service.import_archive(archive)
        path = self.root.parent / "archive.json"
        path.write_text(json.dumps(archive), encoding="utf-8")
        self.assertEqual(replay(path)["passed"], 2)

    def test_no_build_on_abstention_wrong_source_or_bad_model_response(self):
        abstention = {**proposal(), "selection": None}
        for response, reason in [(abstention, "model_abstained"),
                                 (proposal(wrong_source=True), "selected_opportunity_lacks_source_or_registered_test"),
                                 ({"unexpected": True}, None)]:
            with self.subTest(response=response):
                ident = self.collect(specification())
                self.replies.append(response)
                result = self.service.step(ident)
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["model_calls"], 1)
                self.assertEqual(result["artifacts"], {})
                decision = result["economic_mission"]["decision"]
                self.assertEqual(decision and decision["disposition"], reason)

    def test_a_failed_fresh_case_is_terminal_and_unretained(self):
        ident = self.collect(specification(bad_holdout=True))
        self.replies.extend([proposal(), candidate()])
        self.service.step(ident)
        result = self.service.step(ident)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["verdicts"]["INDEPENDENT_ACCEPTANCE"], "rejected")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.service.capabilities()["capabilities"], [])

    def test_model_can_confirm_evidence_once_for_the_same_hypotheses(self):
        spec = specification()
        spec["economic_mission"]["confirm_citations"] = True
        ident = self.collect(spec)
        decision = proposal(wrong_source=True)
        confirmation = {"selection": 0, "rationale": "The first hypothesis uses the verified measurement.",
                        "citations": [
                            {"source": label, "excerpt_index": 0, "contract": None}
                            for label in sources()
                        ]}
        formula = {"summary": "Double x", "inputs": ["x"], "bindings": {"twice": "2*x"},
                   "outputs": {"result": "twice"}}
        self.replies.extend([decision, confirmation, formula])
        first = self.service.step(ident)
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["phase"], "researcher")
        self.assertIsNone(first["economic_mission"]["decision"]["selected"])
        fixed = self.service.step(ident)
        self.assertEqual(fixed["phase"], "builder")
        resolved = fixed["economic_mission"]["decision"]["opportunities"][0]
        self.assertEqual(resolved["outcome"], decision["opportunities"][0]["outcome"])
        self.assertTrue(resolved["quote_verified"])
        self.assertEqual(resolved["contract"], "measurement")
        self.assertEqual(fixed["economic_mission"]["decision"]["experiment_routed_by"],
                         "unique_registered_contract_for_confirmed_source")
        self.assertEqual(self.service.step(ident)["status"], "complete")

    def test_resume_after_freezing_does_not_call_model_again(self):
        ident = self.collect(specification())
        self.replies.extend([proposal(), candidate()])
        self.service.step(ident)
        real_verify = self.service._verify

        def interrupt(state, *, final=False):
            if final:
                raise RuntimeError("test interruption after seal")
            return real_verify(state)

        with patch.object(self.service, "_verify", side_effect=interrupt):
            with self.assertRaisesRegex(RuntimeError, "after seal"):
                self.service.step(ident)
        self.assertEqual(self.service.get(ident)["status"], "interrupted")
        self.service.close()
        self.service = self.open_service()
        self.service.resume(ident, background=False)
        final = self.service.step(ident)
        self.assertEqual(final["status"], "complete")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(sum(e["kind"] == "economic_candidate_frozen" for e in final["events"]), 1)

    def test_live_retrieval_consent_and_source_failure_are_durable(self):
        spec = specification()
        row = spec["economic_mission"]["sources"]["measurement"]
        row.pop("snapshot")
        with self.assertRaisesRegex(BridgeError, "offline source snapshots"):
            self.service.create(spec)
        spec["local_only"] = False
        with patch("bridge.adapters.retrieve_source", side_effect=BridgeError("SOURCE_CONNECTION", "Unavailable")) as get:
            ident = self.collect(spec)
        get.assert_called_once_with(row["url"], self.service.runtime.source_hosts)
        receipt = self.service.get(ident)["economic_mission"]["observations"]["measurement"]
        self.assertEqual(receipt["code"], "SOURCE_CONNECTION")
        self.replies.append(proposal())
        self.assertEqual(self.service.step(ident)["status"], "needs_review")

    def test_record_integrity_and_no_remote_inference_even_with_live_source_consent(self):
        spec = specification()
        originals = spec["economic_mission"]["sources"]["measurement"]["snapshot"]
        originals["sha256"] = digest("tampered")
        with self.assertRaisesRegex(BridgeError, "SHA-256"):
            self.service.create(spec)
        self.service.close()
        self.service = self.open_service(remote=True)
        spec = {**specification(), "local_only": False}
        with self.assertRaisesRegex(BridgeError, "refuses nonlocal"):
            self.service.create(spec)
        self.assertEqual(self.requests, [])

    def test_numeric_round_trip_does_not_create_a_fresh_input(self):
        spec = specification()
        original = spec["economic_mission"]["contracts"]["measurement"]
        original["qualification"][0]["input"]["x"] = 3.0
        with self.assertRaisesRegex(BridgeError, "input repeats"):
            self.service.create(spec)


if __name__ == "__main__":
    unittest.main()
