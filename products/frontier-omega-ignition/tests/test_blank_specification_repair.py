"""Blank-contract revisions through the normal controller with a synthetic local provider."""
import copy
import json
import tempfile
import unittest

from ignition import family_contracts
from ignition.controller import Controller
from ignition.provider import ProviderUnavailable
from ignition.store import Conflict, StateError, Store
from test_integrity_boundaries import CHALLENGE, DISCOVERY, body, confirmation, proposal, spec


class ScriptedProvider:
    def __init__(self, drafts, *, build=None, discovery=None):
        self.drafts = iter(drafts)
        self.discovery = copy.deepcopy(discovery or DISCOVERY)
        chosen = self.discovery["candidates"][0]
        family = family_contracts.catalog()[chosen["kind"]]
        chosen["mechanics"] = {k: family[k] for k in ("inputs", "operations", "outputs")}
        self.discovery["requested_output"] = family["outputs"][0]
        self.build = proposal() if build is None else build
        self.requests = []
        self.receipts = []

    def identity(self):
        return {"mode": "local", "provider": "synthetic unit test", "model": "scripted"}

    def propose(self, stage, packet):
        self.requests.append((stage, copy.deepcopy(packet)))
        if stage == "specification":
            result = next(self.drafts)
            if isinstance(result, Exception):
                raise result
            return result
        return {"discover": self.discovery, "challenge": CHALLENGE, "construct": self.build}[stage]


class BlankSpecificationRepair(unittest.TestCase):
    def setUp(self):
        self.initial_case = confirmation("original illustration", "rejected-only-012", "rejected-only-023")
        self.invalid = {"spec": spec([self.initial_case, self.initial_case])}
        self.valid = {"spec": spec([confirmation("corrected illustration", "listed-003", "listed-014")])}
        self.heldout = confirmation("fresh operator data", "unseen-578", "unseen-632")

    def run_mission(self, drafts, *, resources=None, build=None, authorize=True, discovery=None, source_text=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.model = ScriptedProvider(drafts, build=build, discovery=discovery)
        self.ctrl = Controller(Store(folder.name), lambda: self.model)
        intake = body(explicit=False)
        intake["mission"]["authority"] = {"local_model": authorize}
        if source_text is not None:
            intake["sources"][0].update(text=source_text, rights="Public synthetic checksum fixture.")
        intake["mission"]["resources"].update(resources if resources is not None else {"max_repairs": 1, "max_model_calls": 8})
        self.rid, self.version = self.ctrl.create(intake)
        return self.ctrl.advance(self.rid, self.version)

    def approve(self, state, case):
        self.ctrl.intervene(self.rid, self.version, "approve",
                            {"confirmations": [case], "contract_sha256": state["contract_sha256"]})

    def test_fresh_approval_and_replay(self):
        state = self.run_mission([self.invalid, self.valid])
        self.assertEqual(state["status"], "awaiting_contract", state["error"])
        self.assertIsNone(state["contract"])
        self.assertIsNone(state["artifact"])
        self.assertEqual(len(state["specification_failures"]), 1)
        requests = [packet for stage, packet in self.model.requests if stage == "specification"]
        self.assertEqual(len(requests), 2)
        self.assertIn("family_contract", requests[0])
        self.assertIn("unique case names", requests[1]["validation_error"])
        self.assertEqual(requests[1]["selected"], requests[0]["selected"])
        self.assertEqual(requests[1]["mission"], requests[0]["mission"])
        self.assertNotIn("rejected-only-012", json.dumps(requests[1]))
        self.assertNotIn("unseen-578", json.dumps(self.model.requests))
        with self.assertRaisesRegex(StateError, "duplicates"):
            self.approve(state, self.initial_case)
        self.approve(state, self.heldout)
        done = self.ctrl.advance(self.rid, self.version)
        self.assertEqual(done["status"], "verified", done["error"])
        self.assertEqual(done["attempts"], 5)
        self.assertNotIn("unseen-578", json.dumps(self.model.requests))

    def test_no_new_draft_without_repair_grant_or_call_capacity(self):
        for resources in ({"max_model_calls": 8}, {"max_model_calls": 8, "max_repairs": 0},
                          {"max_repairs": 1}, {"max_model_calls": 3, "max_repairs": 1}):
            with self.subTest(resources=resources):
                state = self.run_mission([self.invalid], resources=resources)
                self.assertEqual(state["status"], "blocked")
                self.assertIn("unique case names", state["error"])
                self.assertEqual(state["attempts"], 3)
                self.assertEqual(len(state["specification_failures"]), 1)
        state = self.run_mission([], authorize=False)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(self.model.requests, [])

    def test_obstruction_or_second_invalid_draft_stops_with_original_trace(self):
        for drafts, rejected in [([{"obstruction": "Missing permission"}], 0),
                                 ([self.invalid, {"obstruction": "Missing permission"}], 1),
                                 ([self.invalid, self.invalid], 2)]:
            with self.subTest(rejected=rejected):
                state = self.run_mission(drafts, resources={"max_model_calls": 8, "max_repairs": 4})
                self.assertEqual(state["status"], "blocked")
                self.assertEqual(len(state.get("specification_failures", [])), rejected)
                stages = [stage for stage, _ in self.model.requests]
                self.assertEqual(stages.count("specification"), len(drafts))
                again = self.ctrl.advance(self.rid, self.version)
                self.assertEqual(state["attempts"], again["attempts"])
                self.assertEqual(len(self.model.requests), len(stages))

    def test_started_repair_cannot_be_reissued_after_provider_failure(self):
        state = self.run_mission([self.invalid, ProviderUnavailable("interrupted")])
        self.assertEqual(state["status"], "blocked")
        self.assertIn("interrupted", state["error"])
        again = self.ctrl.advance(self.rid, self.version)
        self.assertEqual(again["attempts"], 4)
        self.assertIn("without a reusable answer", again["error"])
        self.assertEqual(len(again["specification_failures"]), 1)
        self.assertEqual(len(again["unsuccessful_calls"]), 1)

    def test_completed_repair_survives_pause_at_the_call_checkpoint(self):
        original = ScriptedProvider.propose
        def respond_and_pause(provider, stage, packet):
            answer = original(provider, stage, packet)
            if stage == "specification" and "validation_error" in packet:
                self.ctrl.set_operation(self.rid, self.version, "pause")
            return answer
        from unittest.mock import patch
        with patch.object(ScriptedProvider, "propose", respond_and_pause), self.assertRaises(Conflict):
            self.run_mission([self.invalid, self.valid], resources={"max_repairs": 1, "max_model_calls": 4})
        self.ctrl.set_operation(self.rid, self.version, "resume")
        resumed = Controller(self.ctrl.store, lambda: self.model).advance(self.rid, self.version)
        self.assertEqual(resumed["status"], "awaiting_contract", resumed["error"])
        self.assertEqual(resumed["attempts"], 4)
        self.assertEqual(len(self.model.requests), 4)
        self.assertEqual(len(resumed["specification_failures"]), 1)

    def test_assisted_initial_response_does_not_grant_an_automatic_repair(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        ctrl = Controller(Store(folder.name), assisted=("test operator", "synthetic manual fixture"))
        intake = body(explicit=False)
        intake["mission"]["resources"].update(max_repairs=1, max_model_calls=8)
        intake["mission"]["authority"].update(local_model=True)
        rid, version = ctrl.create(intake)
        discovery = ScriptedProvider([]).discovery
        for stage, response in (("discover", discovery), ("challenge", CHALLENGE), ("specification", self.invalid)):
            current = ctrl.advance(rid, version)
            self.assertEqual(current["status"], "awaiting_model", current["error"])
            handoff = current["handoff"]
            self.assertEqual(handoff["stage"], stage)
            ctrl.intervene(rid, version, "respond", {"sha256": handoff["sha256"], "response": response})
        state = ctrl.advance(rid, version)
        self.assertEqual(state["status"], "blocked")
        self.assertIsNone(state["handoff"])
        self.assertEqual(state["attempts"], 3)

    def test_reproposal_spends_one_shared_repair_grant(self):
        state = self.run_mission([self.invalid, self.valid], build={"kind": "record_migration", "program": {}})
        self.approve(state, self.heldout)
        done = self.ctrl.advance(self.rid, self.version)
        self.assertEqual(done["status"], "failed", done["error"])
        self.assertEqual([stage for stage, _ in self.model.requests],
                         ["discover", "challenge", "specification", "specification", "construct"])
        self.assertEqual(len(done["construction_attempts"]), 1)

    def test_manifest_drafts_bind_original_supplied_inventory(self):
        from hashlib import sha256
        digest = sha256(b"public test content").hexdigest()
        discovery = copy.deepcopy(DISCOVERY)
        discovery["candidates"][0]["kind"] = "manifest_audit"
        none = self.run_mission([], discovery=discovery)
        self.assertEqual(none["status"], "deferred")
        self.assertIn("digests", none["research"]["decision_reason"])
        self.assertEqual([stage for stage, _ in self.model.requests], ["discover", "challenge"])
        manifest = {"public.txt": digest}
        case = {"name": "Empty directory", "input": {"files": {}},
                "expected": {"ok": False, "matched": [], "missing": ["public.txt"], "changed": [], "unexpected": []}}
        draft = {"spec": {"kind": "manifest_audit", "purpose": self.valid["spec"]["purpose"],
                          "definition": {"manifest": manifest}, "cases": [case]}}
        forged = copy.deepcopy(draft)
        forged["spec"]["definition"]["manifest"]["public.txt"] = "f" * 64
        state = self.run_mission([forged, draft], discovery=discovery, source_text=digest + "  public.txt")
        self.assertEqual(state["status"], "awaiting_contract", state["error"])
        self.assertEqual(state["proposed_contract"]["spec"]["definition"]["manifest"], manifest)
        self.assertEqual([p["trusted_manifest"] for s, p in self.model.requests if s == "specification"],
                         [manifest, manifest])
        self.assertIn("trusted_manifest", state["specification_failures"][0]["validation_error"])
