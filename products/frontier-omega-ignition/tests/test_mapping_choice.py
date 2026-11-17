"""Bounded model selection and source-bound operator clarification through the normal controller."""
from pathlib import Path
import json
import tempfile
import unittest

from ignition import development, model_schema
from ignition.controller import Controller
from ignition.provider import ProviderUnavailable
from ignition.store import Store, Conflict, StateError
from bridge.output_schema import validate_output, SchemaError

PRODUCT = Path(__file__).resolve().parents[1]


def mission(name, method, order="ascending"):
    path = (PRODUCT/"examples/migration.json" if name == "migration" else
            PRODUCT.parents[1]/"docs/frontier-omega-ignition/continuation/bounded-choice/parcel.json")
    data = json.loads(path.read_bytes())
    m = data["mission"]
    m["resources"].update(direct_method=method, execution_strategy="direct", choice_order=order)
    return {"mission": m, "sources": data.get("sources", []), "request_id": "-".join([name, method, order])}


class ChoiceModel:
    def __init__(self, respond):
        self.respond = respond
        self.receipts = []
        self.packets = []

    def identity(self):
        return {"mode": "local", "model": "synthetic-choice-regression"}

    def propose(self, stage, packet):
        assert stage == "choose_hypothesis"
        self.packets.append(packet)
        return self.respond(packet)


class MappingChoices(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.store = Store(root.name)

    def test_choice_ids_are_content_bound_and_independent_of_presentation_order(self):
        for dataset, required_text in (("migration", "first component of id"), ("parcel", "second component of routing_note")):
            found = []
            for order in ("ascending", "descending"):
                body = mission(dataset, "model_choice", order)
                model = ChoiceModel(lambda p: {"choice": next(x["id"] for x in p["candidates"]
                                                               if required_text in x["description"])})
                ctrl = Controller(self.store, lambda: model)
                rid, ver = ctrl.create(body)
                state = ctrl.advance(rid, ver)
                self.assertEqual(state["status"], "verified", state.get("error"))
                self.assertEqual(state["mapping_resolution"]["origin"], "model")
                self.assertEqual(len(model.packets), 1)
                packet = model.packets[0]
                candidates = [c["id"] for c in packet["candidates"]]
                found.append(candidates)
                self.assertEqual(set(packet), {"run_id", "revision", "mission_sha256", "instruction",
                                                "purpose", "requirements", "fixed_operations", "candidates"})
                for case in body["mission"]["construction_spec"]["cases"]:
                    self.assertNotIn(case["name"], json.dumps(packet))
                self.assertNotIn("definition", packet)
                self.assertNotIn("cases", packet)
                self.assertTrue(ctrl.deliver(rid, ver).startswith(b"PK"))
                validate_output({"choice": "abstain"}, model_schema.for_stage("choose_hypothesis", packet))
                with self.assertRaises(SchemaError):
                    validate_output({"choice": "unregistered"}, model_schema.for_stage("choose_hypothesis", packet))
            self.assertEqual(found[0], list(reversed(found[1])))

    def test_wrong_valid_choice_and_invalid_response_are_terminal(self):
        outcomes = ((lambda p: {"choice": next(x["id"] for x in p["candidates"] if "second component" in x["description"])}, "failed"),
                    (lambda p: {"choice": "abstain"}, "deferred"),
                    (lambda p: {"choice": ["new arbitrary operation"]}, "deferred"),
                    (lambda p: {"choice": "unregistered"}, "deferred"),
                    (lambda p: {"choice": p["candidates"][0]["id"], "program": {}}, "deferred"))
        for n, (answer, status) in enumerate(outcomes):
            model = ChoiceModel(answer)
            ctrl = Controller(self.store, lambda: model)
            body = mission("migration", "model_choice")
            body["request_id"] += str(n)
            rid, ver = ctrl.create(body)
            state = ctrl.advance(rid, ver)
            self.assertEqual(state["status"], status)
            ctrl.advance(rid, ver)
            self.assertEqual(len(model.packets), 1)
            with self.assertRaises(Conflict):
                ctrl.deliver(rid, ver)

    def test_operator_clarification_is_idempotent_and_bound_to_source_and_revision(self):
        body = mission("parcel", "operator_choice")
        body["mission"]["authority"] = {}
        ctrl = Controller(self.store)
        rid, ver = ctrl.create(body)
        state = ctrl.advance(rid, ver)
        self.assertEqual(state["status"], "awaiting_choice")
        menu = state["mapping_choice"]
        correct = next(c["id"] for c in menu["candidates"] if "second component" in c["description"])
        selected = {"choice": correct, "sha256": menu["sha256"]}
        with self.assertRaises(Conflict):
            ctrl.intervene(rid, ver, "choose", {**selected, "sha256": "0"*64})
        with self.assertRaises(StateError):
            ctrl.intervene(rid, ver, "choose", {**selected, "choice": "unlisted"})
        self.assertIsNone(ctrl.view(rid).get("mapping_resolution"))
        with self.assertRaises(Conflict):
            ctrl.deliver(rid, ver)
        ctrl.intervene(rid, ver, "choose", selected)
        ctrl.intervene(rid, ver, "choose", selected)
        accepted = ctrl.advance(rid, ver)
        self.assertEqual((accepted["status"], accepted["mapping_resolution"]["origin"]), ("verified", "operator"))
        changed = {**body, "request_id": body["request_id"]+"-revised", "version": ver}
        _, new_ver = ctrl.create(changed, rid)
        self.assertEqual(ctrl.advance(rid, new_ver)["status"], "awaiting_choice")
        with self.assertRaises(Conflict):
            ctrl.intervene(rid, new_ver, "choose", selected)

    def test_ambiguous_objective_or_inference_interruption_does_not_authorize_more_calls(self):
        def interrupted(_):
            raise ProviderUnavailable("Synthetic interrupted inference")
        model = ChoiceModel(interrupted)
        ctrl = Controller(self.store, lambda: model)
        body = mission("migration", "model_choice")
        rid, ver = ctrl.create(body)
        self.assertEqual(ctrl.advance(rid, ver)["status"], "deferred")
        ctrl.advance(rid, ver)
        self.assertEqual(len(model.packets), 1)
        body["request_id"] += "-ambiguous"
        m = body["mission"]
        m["purpose"] = m["construction_spec"]["purpose"] = "Prepare the editorial queue."
        m["requirements"] = ["The result must be useful."]
        rid, ver = ctrl.create(body)
        self.assertEqual(ctrl.advance(rid, ver)["status"], "deferred")
        self.assertEqual(len(model.packets), 1)

    def test_cues_distinguish_positions_even_when_the_source_is_shared(self):
        same_source = {"candidates": [{"operations": [{"column": {"source": "path_code", "target": "batch",
                          "split": {"separator": "/", "index": i}}}]} for i in (0, 1)]}
        self.assertTrue(development.has_distinguishing_evidence(
            {"purpose": "Take the second component from path_code.", "requirements": []}, same_source))
        self.assertFalse(development.has_distinguishing_evidence(
            {"purpose": "Take a component from path_code.", "requirements": []}, same_source))

    def test_excessive_combination_space_abstains_without_truncating_candidates(self):
        definition = {"input_fields": ["a", "b", "c"], "targets": [{"name": f"out{i}", "type": "text"} for i in range(4)],
                      "extra_fields": "drop", "demonstrations": [{"input": {"rows": [{"a":"v","b":"v","c":"v"}]},
                        "expected": {"rows": [{f"out{i}":"v" for i in range(4)}]}}]}
        menu, reason = development.menu(definition, "ascending")
        self.assertIsNone(menu)
        self.assertIn("more than", reason)
