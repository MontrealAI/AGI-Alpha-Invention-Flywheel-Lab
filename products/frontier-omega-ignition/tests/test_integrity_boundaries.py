"""Acceptance, replay and privacy regressions across the actual assisted entry point."""

import copy
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone

from ignition.construction import build, freeze_contract
from ignition.controller import Controller
from ignition.evaluation import evaluate
from ignition.store import Conflict, StateError, Store


PURPOSE = "Retain both item identifiers when migrating a records table."
REQUIREMENT = "Copy the supplier and customer identifiers to their separate output fields."
DEFINITION = {"columns": [{"source": "supplier", "target": "supplier_id", "type": "text"},
                          {"source": "customer", "target": "customer_id", "type": "text"}], "extra_fields": "reject"}


def confirmation(name, first, second):
    return {"name": name, "input": {"rows": [{"supplier": first, "customer": second}]},
            "expected": {"rows": [{"supplier_id": first, "customer_id": second}]}}


def spec(cases):
    return {"purpose": PURPOSE, "kind": "record_migration", "definition": copy.deepcopy(DEFINITION),
            "cases": copy.deepcopy(cases)}


def proposal():
    return {"kind": "record_migration", "program": copy.deepcopy(DEFINITION)}


def body(explicit=True):
    supplied = datetime.now(timezone.utc) - timedelta(days=1)
    mission = {"purpose": PURPOSE, "requirements": [REQUIREMENT], "authority": {"assisted_model": True}}
    if explicit:
        mission["construction_spec"] = spec([confirmation("Private confirmation", "CONFIRMATION-ONLY-1257", "PRIVATE-MAP-871")])
    return {"request_id": "integrity-test-create", "mission": mission, "sources": [
        {"title": "Test source for field mapping", "url": "https://example.org/document",
         "publisher": "Test fixture", "text": "The supplied record has two independently maintained identifier columns.",
         "retrieved_at": supplied.isoformat(), "event_at": supplied.date().isoformat(), "published_at": supplied.date().isoformat()}]}


DISCOVERY = {"favourite": "C1", "candidates": [{
    "title": "Verified records projection", "beneficiary": "catalogue editor", "outcome": "explicitly mapped records",
    "change": "proposed bounded construction", "obstruction": "unverified transformations",
    "route": "check a typed migration against operator examples", "value": "reduce review effort; unmeasured",
    "alternative": "handwritten Python", "scale": "one input record at a time", "kind": "record_migration",
    "test": "check every identifier against the supplied target", "sources": ["S1"]}]}
CHALLENGE = {"decision": "build", "selected": "C1", "reason": "Test source-field fidelity with independent records.",
             "objections": [], "fit": [{"requirement": REQUIREMENT, "status": "supported",
                                         "check": "compare both identifiers on confirmation inputs"}]}


class IntegrityBoundaries(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(self.directory.name)
        self.controller = Controller(self.store, assisted=("Manual test provider", "manual-test-model"))
        self.prompts = []

    def respond(self, rid, revision, stage, response):
        current = self.controller.advance(rid, revision)
        self.assertEqual(current["status"], "awaiting_model", current.get("error"))
        pending = current["handoff"]
        self.assertEqual(pending["stage"], stage)
        self.prompts.append(pending["prompt"])
        self.controller.intervene(rid, revision, "respond", {"sha256": pending["sha256"], "response": response})

    def test_exact_mapping_when_witness_values_coincide(self):
        frozen = freeze_contract(spec([confirmation("same sources", "100", "100")]))
        wrong = proposal()
        wrong["program"]["columns"][0]["source"] = "customer"
        wrong["program"]["columns"][1]["source"] = "supplier"
        result = evaluate(frozen, build(frozen, wrong))
        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["declared_program_conforms"])
        self.assertTrue(all(case["candidate_pass"] for case in result["cases"]))
        self.assertEqual(result["comparison"]["outcome"], "baseline_wins")
        equivalent = proposal()
        equivalent["program"]["columns"].reverse()
        equivalent["program"]["input_fields"] = ["customer", "supplier"]
        self.assertEqual(evaluate(frozen, build(frozen, equivalent))["status"], "pass")

    def test_assisted_prompts_holdout_and_current_export(self):
        supplied = body()
        rid, rev = self.controller.create(supplied)
        for stage, response in (("discover", DISCOVERY), ("challenge", CHALLENGE), ("construct", proposal())):
            self.respond(rid, rev, stage, response)
        result = self.controller.advance(rid, rev)
        self.assertEqual(result["status"], "verified", result.get("error"))
        for prompt in self.prompts:
            for marker in ("CONFIRMATION-ONLY-1257", "PRIVATE-MAP-871", "Private confirmation"):
                self.assertNotIn(marker, prompt)
        report = json.loads(zipfile.ZipFile(io.BytesIO(self.controller.deliver(rid,rev))).read("context.json"))
        self.assertEqual(report["model_calls"][-1]["receipt"][0]["application_model_calls"], 0)
        self.assertNotIn("response", report["model_calls"][-1])
        revised = copy.deepcopy(supplied)
        revised.update(version=rev, request_id="amend-secret-confirmation")
        revised["mission"]["authority"]["assisted_model"] = False
        _, new_rev = self.controller.create(revised, rid)
        self.assertEqual(new_rev, rev + 1)
        with self.assertRaises(Conflict):
            self.controller.deliver(rid,rev)
        with self.assertRaises(Conflict):
            self.controller.deliver(rid,new_rev,{"rows":[]},trial=True)
        self.assertEqual(self.store.history(rid)[0]["evaluation"]["status"], "pass")
        self.assertIsNone(self.controller.view(rid)["evaluation"])

    def test_amendment_obeys_the_same_lock_as_export(self):
        supplied = body()
        rid, rev = self.controller.create(supplied)
        revised = {**supplied, "version": rev, "request_id": "simultaneous-amendment"}
        with self.store.work_lock(rid), self.assertRaises(Conflict):
            self.controller.create(revised,rid)
        self.assertEqual(self.store.get(rid)["version"], rev)
        self.assertEqual(self.controller.create(revised,rid), (rid, rev + 1))

    def test_model_authored_checks_cannot_be_reused_as_private_confirmation(self):
        rid, rev = self.controller.create(body(explicit=False))
        self.respond(rid, rev, "discover", DISCOVERY)
        self.respond(rid, rev, "challenge", CHALLENGE)
        draft_cases = [confirmation("Model-authored development", "PUBLIC-SUPPLIER", "PUBLIC-CUSTOMER")]
        self.respond(rid, rev, "specification", {"spec": spec(draft_cases)})
        result = self.controller.advance(rid, rev)
        self.assertEqual(result["status"], "awaiting_contract", result.get("error"))
        approve = {"contract_sha256": result["contract_sha256"]}
        with self.assertRaises((StateError,ValueError)):
            self.controller.intervene(rid, rev, "approve", approve)
        copied = confirmation("Renamed model witness", "PUBLIC-SUPPLIER", "PUBLIC-CUSTOMER")
        with self.assertRaises((StateError,ValueError)):
            self.controller.intervene(rid, rev, "approve", {**approve, "confirmations": [copied]})
        fresh = confirmation("Human-provided witness", "PRIVATE-FRESH-A", "PRIVATE-FRESH-B")
        self.controller.intervene(rid, rev, "approve", {**approve, "confirmations": [fresh]})
        self.respond(rid, rev, "construct", proposal())
        self.assertNotIn("PRIVATE-FRESH-A", self.prompts[-1])
        self.assertNotIn("PRIVATE-FRESH-B", self.prompts[-1])
        self.assertEqual(self.controller.advance(rid,rev)["status"], "verified")
