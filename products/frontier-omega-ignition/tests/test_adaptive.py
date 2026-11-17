"""Prospective process regressions. Unit doubles are not evidence of autonomous inference."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from ignition import construction, evaluation
from ignition.controller import Controller
from ignition.store import Conflict, StateError, Store, digest
from test_integrity_boundaries import body

PRODUCT = Path(__file__).resolve().parents[1]
ORIGINAL_RESPONSE = "9bef7cd8787ba4397137da29dce7e4b450f70c31eb26dacfa8910a6c38bf42b3"
ORIGINAL_CONTRACT = "9349cab7eed8ad480458c3f1655f659fc36455aaccb11b4e8fb56cb9094070a4"
ORIGINAL_ARTIFACT = "2997e2978470afe5818f42a697c5797436ea077e46e683fc2bb53890e550bae8"


def public_fixture(name):
    raw = json.loads((PRODUCT / "examples" / (name + ".json")).read_bytes())
    return {"mission": raw["mission"], "sources": raw["sources"], "request_id": "adaptive-experiment-" + name}


def recovered_rejection():
    expected = public_fixture("integrity")["mission"]["construction_spec"]["definition"]
    proposal = {"kind": "manifest_audit", "program": expected}
    expected["manifest"]["ignition.css"] = "23675657f7ffa6fbdbd0d085580ef56687f731e9066e28e1f6a5ad0c449b8668"
    if digest(proposal) != ORIGINAL_RESPONSE:
        raise AssertionError("Recovered proposal differs from the published Qwen receipt")
    return proposal


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.ctrl = Controller(Store(directory.name), assisted=("synthetic test exchange", "unit double"))

    def reply(self, run_id, version, stage, response):
        pending = self.ctrl.advance(run_id, version)
        self.assertEqual(pending["status"], "awaiting_model", pending.get("error"))
        self.assertEqual(pending["handoff"]["stage"], stage)
        self.ctrl.intervene(run_id, version, "respond", {"sha256": pending["handoff"]["sha256"], "response": response})
        return pending["handoff"]["prompt"]

    def test_reconstruct_exact_historical_rejection(self):
        spec = public_fixture("integrity")["mission"]["construction_spec"]
        contract = construction.freeze_contract(spec)
        self.assertEqual(contract["sha256"], ORIGINAL_CONTRACT)
        artifact = construction.build(contract, recovered_rejection())
        self.assertEqual(artifact["sha256"], ORIGINAL_ARTIFACT)
        receipt = evaluation.evaluate(contract, artifact)
        self.assertFalse(receipt["declared_program_conforms"])
        self.assertEqual(receipt["comparison"]["outcome"], "baseline_wins")
        self.assertEqual([c["name"] for c in receipt["cases"] if not c["candidate_pass"]],
                         ["Clean receipt for both real source blobs"])

    def test_exact_compilation_requires_no_model_or_public_network(self):
        fixture = public_fixture("integrity")
        fixture["mission"]["authority"] = {"public_sources": True}
        rid, rev = self.ctrl.create(fixture)
        with patch("ignition.research.discover_sources", side_effect=AssertionError("unexpected fetch")):
            state = self.ctrl.advance(rid, rev)
        self.assertEqual(state["status"], "verified")
        self.assertEqual(state["routing"]["method"], "specialist")
        self.assertEqual(state["research"]["candidates"], [])
        self.assertEqual(state.get("attempts", 0), 0)
        with ZipFile(io.BytesIO(self.ctrl.deliver(rid, rev))) as archive:
            context = json.loads(archive.read("context.json"))
            self.assertEqual(context["construction_attempts"][0]["checks"], 9)
            self.assertEqual(context["model_calls"], [])

    def test_explicit_free_form_migration_uses_only_builder_and_preserves_holdout(self):
        fixture = public_fixture("migration")
        fixture["mission"]["resources"]["direct_method"] = "model"
        spec = fixture["mission"]["construction_spec"]
        rid, rev = self.ctrl.create(fixture)
        example = PRODUCT.parents[1] / "docs/frontier-omega-ignition/qualification/89f2196d/direct-proposal.json"
        proposed = json.loads(example.read_bytes())
        prompt = self.reply(rid, rev, "construct", proposed)
        self.assertNotIn(spec["cases"][0]["name"], prompt)
        state = self.ctrl.advance(rid, rev)
        self.assertEqual((state["status"], state["routing"]["method"]), ("verified", "model"))
        self.assertEqual(state["attempts"], 1)
        self.assertEqual(state["construction_attempts"][0]["checks"], 9)

    def test_hash_bound_repair_keeps_frozen_evaluator_and_holds_out_cases(self):
        fixture = public_fixture("integrity")
        fixture["mission"]["resources"].update(direct_method="model", max_model_calls=2)
        rid, rev = self.ctrl.create(fixture)
        self.reply(rid, rev, "construct", recovered_rejection())
        pending = self.ctrl.advance(rid, rev)
        before = pending["construction_attempts"][0]
        self.assertEqual(before["status"], "rejected")
        self.assertEqual(before["artifact_sha256"], ORIGINAL_ARTIFACT)
        self.assertEqual(before["feedback"]["public_specification_mismatches"], ["ignition.css"])
        self.assertEqual(before["feedback"]["failed_check_counts"], {"confirmation": 1})
        with self.assertRaises(Conflict):
            self.ctrl.deliver(rid, rev)
        prompt = self.reply(rid, rev, "repair", {"kind": "manifest_audit", "program": {"use_frozen_manifest": True}})
        for case in fixture["mission"]["construction_spec"]["cases"]:
            self.assertNotIn(case["name"], prompt)
        self.assertNotIn('"expected"', prompt)
        state = self.ctrl.advance(rid, rev)
        self.assertEqual(state["status"], "verified", state.get("error"))
        attempts = state["construction_attempts"]
        self.assertEqual([i["status"] for i in attempts], ["rejected", "accepted"])
        self.assertEqual({i["contract_sha256"] for i in attempts}, {ORIGINAL_CONTRACT})
        self.assertEqual([i["passed_checks"] for i in attempts], [8, 9])
        self.assertEqual(state["attempts"], 2)
        self.assertEqual(state["evaluation"]["comparison"]["outcome"], "tie")

    def test_explicit_decline_and_budget_are_terminal_without_export(self):
        for options in ({"max_repairs": 0}, {"max_model_calls": 1}, {"max_repairs": 5}):
            fixture = public_fixture("integrity")
            fixture["request_id"] += str(next(iter(options.values()))) + next(iter(options))
            fixture["mission"]["resources"].update(direct_method="model", **options)
            rid, rev = self.ctrl.create(fixture)
            self.reply(rid, rev, "construct", recovered_rejection())
            if options.get("max_repairs") == 5:
                self.reply(rid, rev, "repair", recovered_rejection())
            self.assertEqual(self.ctrl.advance(rid, rev)["status"], "failed")
            with self.assertRaises(Conflict):
                self.ctrl.deliver(rid, rev)
        physical = public_fixture("unsupported")
        physical["mission"]["resources"].update(execution_strategy="direct")
        rid, rev = self.ctrl.create(physical)
        state = self.ctrl.advance(rid, rev)
        self.assertEqual((state["routing"]["route"], state["status"]), ("clarify", "deferred"))
        self.assertIsNone(state["artifact"])

    def test_research_marginal_cost_and_separate_fallback_verdicts(self):
        mission = {"purpose": "Reduce time spent verifying evidence for a research operator",
                   "beneficiary": "Evidence curator", "resources": {"research_economics":
                   {"unit": "CAD per decision", "decision_value": 20, "marginal_cost": 25}}}
        rid, rev = self.ctrl.create({"request_id": "cost-before-research", "mission": mission})
        state = self.ctrl.advance(rid, rev)
        self.assertEqual(state["routing"]["route"], "clarify")
        self.assertIsNone(state["artifact"])
        fixture = body()
        fixture["mission"]["resources"].update(execution_strategy="research", direct_after_research=True)
        rid, rev = self.ctrl.create(fixture)
        from test_integrity_boundaries import DISCOVERY, CHALLENGE, proposal
        self.reply(rid, rev, "discover", DISCOVERY)
        self.reply(rid, rev, "challenge", {**CHALLENGE, "decision": "defer", "selected": None})
        self.reply(rid, rev, "construct", proposal())
        state = self.ctrl.advance(rid, rev)
        self.assertEqual(state["research"]["decision"], "defer")
        self.assertEqual(state["routing"]["fallback"]["route"], "direct")
        self.assertEqual(state["status"], "verified")

    def test_unrelated_frozen_software_cannot_qualify_a_physical_action(self):
        fixture = public_fixture("integrity")
        mission = fixture["mission"]
        mission["requirements"].append("Measure actual force before and after wear using calibrated equipment.")
        rid, revision = self.ctrl.create(fixture)
        state = self.ctrl.advance(rid, revision)
        self.assertEqual((state["status"], state["routing"]["route"]), ("deferred", "clarify"))
        self.assertIn("force", state["routing"]["interpretation"]["obstruction"])
        self.assertIsNone(state["artifact"])

    def test_unusable_specification_and_invalid_policy_never_trigger_inference(self):
        for invalid in ({"max_model_calls": -1}, {"max_repairs": False}, {"direct_method": "deploy"},
                        {"execution_strategy": "unknown"}, {"direct_after_research": "yes"},
                        {"research_economics": {"unit": "CAD", "decision_value": 2, "marginal_cost": True}}):
            fixture = public_fixture("migration")
            fixture["mission"]["resources"].update(invalid)
            with self.assertRaises(StateError):
                self.ctrl.create(fixture)
        fixture = public_fixture("migration")
        fixture["mission"]["construction_spec"]["cases"] = []
        rid, rev = self.ctrl.create(fixture)
        state = self.ctrl.advance(rid, rev)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state.get("attempts", 0), 0)
