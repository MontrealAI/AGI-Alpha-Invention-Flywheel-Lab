# SPDX-License-Identifier: Apache-2.0
"""Independent synthetic regressions for instrument versus outcome claims.

The arithmetic fixture has no clinical, inventory, supply or routing validity.
These tests exercise claim boundaries without network requests or real services.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge.adapters import BridgeError, Runtime
from bridge.services import AccessRuntime
from bridge.workflows import WorkflowService, digest, portable_digest
from scripts.qualify_economic_mission import replay


ECONOMIC_CLAIMS = (
    "AUTONOMOUS_DISCOVERY", "EXECUTABLE_INVENTION", "INDEPENDENT_ACCEPTANCE",
    "CAPABILITY_ADVANTAGE", "FRONTIER_PARITY", "ECONOMIC_FEASIBILITY",
    "PRODUCTIVE_ASSET", "REAL_VALUE_CAPTURE", "FRESH_SUCCESSOR_BENEFIT",
    "INVENTOR_IMPROVEMENT", "AFTER_COST_COMPOUNDING",
)


def source_catalogue():
    result = {}
    for name in ("arithmetic", "records", "capacity"):
        body = f"Synthetic {name} evidence for a finite engineering regression only."
        result[name] = {
            "label": name,
            "url": f"https://example.com/outcome-boundary/{name}",
            "snapshot": {
                "body": body,
                "sha256": hashlib.sha256(body.encode()).hexdigest(),
            },
        }
    return result


def mission_spec(*, instrument=False, failing=False, confirm=False, goal=None):
    route = {"provider": "local", "model": "boundary-fixture"}
    mission = {
        "beneficiary": "Synthetic regression beneficiary",
        "sources": source_catalogue(),
        "contracts": {
            "arithmetic": {
                "source": "arithmetic",
                "goal": goal or "Calculate exactly twice the supplied x.",
                "development": [{"input": {"x": 3}, "expected": {"result": 6}}],
                "qualification": [
                    {"input": {"x": 87301}, "expected": {"result": 174602}},
                    {"input": {"x": -5}, "expected": {"result": -9 if failing else -10}},
                ],
            },
        },
    }
    if instrument:
        mission["qualification_scope"] = "registered_instrument"
    if confirm:
        mission["confirm_citations"] = True
    return {
        "objective": "Investigate whether a claimed beneficiary outcome is actually tested.",
        "roles": {"researcher": route, "builder": route},
        "tool_permissions": ["construct_instrument"],
        "max_iterations": 2,
        "max_actions": 2,
        "economic_mission": mission,
    }


def nomination(outcome="Improve a synthetic clinic inventory decision", *, title=None):
    rows = []
    for index, name in enumerate(source_catalogue()):
        rows.append({
            "title": title if index == 0 and title else f"Synthetic {name} proposal",
            "outcome": outcome if index == 0 else f"Different synthetic {name} outcome",
            "constraint": "No independently established beneficiary outcome",
            "alternative": "Competent conventional workflow",
            "experiment": "Compare the complete beneficiary outcome",
            "capture": "Unverified repeat use",
            "source": name,
            "quote": f"Synthetic {name} evidence",
            "contract": "arithmetic" if index == 0 else None,
        })
    return {
        "opportunities": rows,
        "selection": 0,
        "rationale": "The model asserts that the arithmetic contract tests the outcome.",
    }


def confirmation():
    return {
        "citations": [
            {"source": name, "excerpt_index": 0, "contract": "arithmetic" if index == 0 else None}
            for index, name in enumerate(source_catalogue())
        ],
        "selection": 0,
        "rationale": "The model again asserts that the contract approves the nominated outcome.",
    }


def arithmetic_candidate():
    return {
        "summary": "Construct a finite arithmetic instrument",
        "done": True,
        "actions": [{
            "tool": "construct_instrument",
            "name": "asset.json",
            "spec": {
                "name": "boundary-arithmetic",
                "inputs": ["x"],
                "outputs": {"result": {"formula": "2*x"}},
            },
        }],
    }


class EconomicOutcomeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name) / "workflows"
        self.responses = []
        self.requests = []
        no_retrieval = patch(
            "bridge.adapters.retrieve_source",
            side_effect=AssertionError("Synthetic regressions must not retrieve remote sources."),
        )
        no_retrieval.start()
        self.addCleanup(no_retrieval.stop)
        self.service = self.open_service()
        self.addCleanup(lambda: self.service.close())

    def open_service(self):
        config = {
            "providers": {
                "local": {
                    "kind": "openai",
                    "base_url": "http://127.0.0.1:8123/v1",
                    "models": {
                        "boundary-fixture": {"input_per_million": 0, "output_per_million": 0},
                    },
                },
            },
        }

        def sender(url, headers, body, timeout):
            self.assertTrue(url.startswith("http://127.0.0.1:8123/"))
            self.requests.append(copy.deepcopy(body))
            self.assertTrue(self.responses, "Unexpected model request.")
            return {
                "model": "boundary-fixture",
                "choices": [{"message": {"content": json.dumps(self.responses.pop(0))}}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 13},
            }

        return WorkflowService(AccessRuntime(Runtime(config, sender=sender), config), self.workspace)

    def collect(self, spec):
        ident = self.service.create(spec)["id"]
        for _ in spec["economic_mission"]["sources"]:
            self.assertEqual(self.service.step(ident)["status"], "ready")
        return ident

    def assert_no_economic_claims(self, verdicts):
        for name in ECONOMIC_CLAIMS:
            with self.subTest(claim=name):
                self.assertEqual(verdicts[name], "not_established")

    def assert_instrument_scope(self, receipt):
        scope = receipt["qualification_scope"]
        self.assertEqual(scope["kind"], "registered_instrument_cases")
        self.assertEqual(scope["outcome_linkage"], "not_established")

    def finish_instrument(self, *, failing=False):
        ident = self.collect(mission_spec(instrument=True, failing=failing))
        self.responses.extend([nomination(), arithmetic_candidate()])
        admitted = self.service.step(ident)
        self.assertEqual(admitted["phase"], "builder")
        self.assertEqual(
            admitted["economic_mission"]["decision"]["disposition"],
            "admitted_to_instrument_test",
        )
        return ident, self.service.step(ident)

    def test_default_scope_refuses_arithmetic_as_unrelated_outcome_evidence(self):
        outcomes = (
            "Improve a synthetic clinic decision",
            "Avoid stockouts in a synthetic inventory workflow",
            "Coordinate a synthetic supply network",
            "Reduce distance in a synthetic routing workflow",
        )
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                before = len(self.requests)
                ident = self.collect(mission_spec())
                self.responses.append(nomination(outcome))
                receipt = self.service.step(ident)
                self.assertEqual(receipt["status"], "needs_review")
                self.assertEqual(receipt["artifacts"], {})
                decision = receipt["economic_mission"]["decision"]
                self.assertIsNone(decision["selected"])
                self.assertEqual(decision["disposition"], "outcome_contract_linkage_unverified")
                self.assertTrue(decision["opportunities"][0]["quote_verified"])
                self.assertEqual(len(self.requests) - before, 1)
                self.assert_no_economic_claims(receipt["verdicts"])
        self.assertEqual(self.service.capabilities()["capabilities"], [])

    def test_copied_service_title_and_goal_do_not_authorize_outcome_claims(self):
        copied = "Synthetic clinic supply routing service"
        spec = mission_spec(goal=copied)
        spec["objective"] = copied
        spec["economic_mission"]["sources"]["arithmetic"]["label"] = copied
        ident = self.collect(spec)
        self.responses.append(nomination(copied, title=copied))
        receipt = self.service.step(ident)
        self.assertEqual(receipt["status"], "needs_review")
        self.assertEqual(receipt["artifacts"], {})
        self.assertEqual(
            receipt["economic_mission"]["decision"]["disposition"],
            "outcome_contract_linkage_unverified",
        )
        self.assert_no_economic_claims(receipt["verdicts"])

    def test_model_citation_confirmation_cannot_upgrade_default_scope(self):
        ident = self.collect(mission_spec(confirm=True))
        self.responses.extend([nomination(), confirmation()])
        first = self.service.step(ident)
        self.assertEqual(first["phase"], "researcher")
        self.assertIsNone(first["economic_mission"]["decision"]["selected"])
        receipt = self.service.step(ident)
        self.assertEqual(receipt["status"], "needs_review")
        self.assertEqual(receipt["artifacts"], {})
        self.assertEqual(
            receipt["economic_mission"]["decision"]["disposition"],
            "outcome_contract_linkage_unverified",
        )
        self.assert_no_economic_claims(receipt["verdicts"])
        self.assertEqual(len(self.requests), 2)

    def test_blind_discovery_keeps_the_same_outcome_unqualified_after_matching(self):
        spec = mission_spec(confirm=True)
        spec["economic_mission"]["blind_discovery"] = True
        ident = self.collect(spec)
        hypothesis = nomination()
        for row in hypothesis["opportunities"]:
            row["contract"] = None
        self.responses.extend([hypothesis, confirmation()])
        first = self.service.step(ident)
        self.assertEqual(first["phase"], "researcher")
        self.assertNotIn("Calculate exactly twice", json.dumps(self.requests[0]))
        result = self.service.step(ident)
        decision = result["economic_mission"]["decision"]
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(decision["disposition"], "outcome_contract_linkage_unverified")
        self.assertIsNone(decision["selected"])
        self.assertEqual(decision["opportunities"][0]["outcome"], hypothesis["opportunities"][0]["outcome"])
        self.assertEqual(result["artifacts"], {})
        self.assertEqual(len(self.requests), 2)
        self.assertNotIn("174602", json.dumps(self.requests))

    def test_operator_scope_accepts_only_the_explicit_supported_string(self):
        for invalid in (None, True, False, 1, "", "beneficiary_outcome", "approved",
                        ["registered_instrument"], {"kind": "registered_instrument"}):
            with self.subTest(scope=invalid):
                spec = mission_spec()
                spec["economic_mission"]["qualification_scope"] = invalid
                with self.assertRaises(BridgeError):
                    self.service.create(spec)
        self.assertEqual(self.requests, [])

    def test_fake_operator_approval_fields_are_not_an_authority_channel(self):
        for key in ("approved", "outcome_approved", "outcome_linkage", "approved_outcomes"):
            with self.subTest(field=key):
                spec = mission_spec()
                spec["economic_mission"][key] = True
                with self.assertRaises(BridgeError):
                    self.service.create(spec)
        spec = mission_spec()
        spec["economic_mission"]["contracts"]["arithmetic"]["outcome_approved"] = True
        with self.assertRaises(BridgeError):
            self.service.create(spec)
        self.assertEqual(self.requests, [])

    def test_model_cannot_add_scope_or_approval_to_its_nomination(self):
        for field in ("qualification_scope", "outcome_approved"):
            with self.subTest(field=field):
                ident = self.collect(mission_spec())
                response = nomination()
                response[field] = "registered_instrument" if field == "qualification_scope" else True
                self.responses.append(response)
                receipt = self.service.step(ident)
                self.assertEqual(receipt["status"], "needs_review")
                self.assertEqual(receipt["artifacts"], {})
                self.assertIsNone(receipt["economic_mission"]["decision"])
                self.assert_no_economic_claims(receipt["verdicts"])

    def test_extra_model_confirmation_approval_is_rejected(self):
        ident = self.collect(mission_spec(confirm=True))
        invalid = confirmation()
        invalid["citations"][0]["outcome_approved"] = True
        self.responses.extend([nomination(), invalid])
        self.service.step(ident)
        receipt = self.service.step(ident)
        self.assertEqual(receipt["status"], "needs_review")
        self.assertEqual(receipt["artifacts"], {})
        self.assertIsNone(receipt["economic_mission"]["decision"]["selected"])
        self.assert_no_economic_claims(receipt["verdicts"])

    def test_explicit_instrument_pass_has_only_technical_demonstration(self):
        ident, receipt = self.finish_instrument()
        self.assertEqual(receipt["status"], "complete")
        self.assert_no_economic_claims(receipt["verdicts"])
        self.assertEqual(receipt["verdicts"]["INSTRUMENT_CONSTRUCTION"], "demonstrated")
        self.assertEqual(receipt["verdicts"]["REGISTERED_INSTRUMENT_ACCEPTANCE"], "demonstrated")
        self.assert_instrument_scope(receipt)
        self.assert_instrument_scope(self.service.get(ident))
        self.assertEqual(receipt["objective"], "Registered instrument: arithmetic")
        self.assertEqual(receipt["mission_objective"], mission_spec()["objective"])

    def test_failing_instrument_has_rejected_technical_acceptance_and_no_retention(self):
        ident, receipt = self.finish_instrument(failing=True)
        self.assertEqual(receipt["status"], "needs_review")
        self.assert_no_economic_claims(receipt["verdicts"])
        self.assertEqual(receipt["verdicts"]["INSTRUMENT_CONSTRUCTION"], "demonstrated")
        self.assertEqual(receipt["verdicts"]["REGISTERED_INSTRUMENT_ACCEPTANCE"], "rejected")
        self.assert_instrument_scope(receipt)
        self.assertEqual(self.service.capabilities()["capabilities"], [])
        with self.assertRaises(BridgeError):
            self.service.reuse(ident, {"x": 4})

    def test_instrument_scope_survives_restart_export_retention_reuse_and_replay(self):
        ident, receipt = self.finish_instrument()
        model_calls = len(self.requests)
        self.service.close()
        self.service = self.open_service()
        restarted = self.service.get(ident)
        self.assertEqual(restarted["status"], "complete")
        self.assert_instrument_scope(restarted)
        self.assert_no_economic_claims(restarted["verdicts"])

        capabilities = self.service.capabilities()["capabilities"]
        self.assertEqual(len(capabilities), 1)
        self.assertEqual(capabilities[0]["id"], ident)
        self.assert_instrument_scope(capabilities[0])
        self.assertEqual(capabilities[0]["objective"], "Registered instrument: arithmetic")

        reused = self.service.reuse(ident, {"x": 13})
        self.assertEqual(reused["outputs"]["asset.json"]["output"], {"result": 26})
        self.assertEqual(reused["verification"], "EXECUTED_NOT_SUCCESSOR_ACCEPTED")
        self.assert_instrument_scope(reused)

        archive = self.service.export(ident)
        self.assert_instrument_scope(archive["state"])
        self.assert_no_economic_claims(archive["state"]["verdicts"])
        path = Path(self.temporary.name) / "technical-export.json"
        path.write_text(json.dumps(archive), encoding="utf-8")
        replayed = replay(path)
        self.assertEqual(replayed["qualification"], "passed")
        self.assertEqual((replayed["passed"], replayed["total"]), (2, 2))
        self.assert_instrument_scope(replayed)
        self.assertEqual(len(self.requests), model_calls)

    def test_listing_and_inheritance_preserve_source_scope_without_acceptance(self):
        ident, _ = self.finish_instrument()
        listing = self.service.list()["runs"]
        self.assertEqual(len(listing), 1)
        self.assert_instrument_scope(listing[0])
        self.assert_no_economic_claims(listing[0]["verdicts"])
        child = self.service.create({
            "objective": "Check reuse on one new arithmetic input",
            "roles": {"builder": {"provider": "local", "model": "boundary-fixture"}},
            "tool_permissions": ["construct_instrument"],
            "inherited_capability": ident,
            "acceptance": [{"kind": "instrument", "artifact": "asset.json",
                            "input": {"x": 7}, "expected": {"result": 14}}],
        })
        inherited = next(event["detail"] for event in child["events"] if event["kind"] == "inherited")
        self.assertFalse(inherited["prior_verification_inherited"])
        self.assertEqual(inherited["source_qualification_scope"]["kind"], "registered_instrument_cases")
        self.assertEqual(inherited["source_qualification_scope"]["outcome_linkage"], "not_established")

    def test_legacy_shaped_replay_is_narrow_and_does_not_rewrite_the_archive(self):
        ident, _ = self.finish_instrument()
        archive = self.service.export(ident)
        state = archive["state"]
        # Synthetic compatibility fixture, not a rewrite of any historical receipt.
        state["spec"]["economic_mission"].pop("qualification_scope")
        state["spec_hash"] = digest(state["spec"])
        state.pop("qualification_scope")
        state["verification"].pop("qualification_scope")
        state["verdicts"] = {"INDEPENDENT_ACCEPTANCE": "demonstrated"}
        archive["sha256"] = portable_digest({key: value for key, value in archive.items() if key != "sha256"})
        path = Path(self.temporary.name) / "legacy-shaped.json"
        path.write_text(json.dumps(archive), encoding="utf-8")
        before = path.read_bytes()
        result = replay(path)
        self.assertEqual(result["qualification"], "passed")
        self.assert_instrument_scope(result)
        self.assertNotIn("INDEPENDENT_ACCEPTANCE", result)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
