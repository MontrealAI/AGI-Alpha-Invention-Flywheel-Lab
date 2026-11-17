"""Development-only hypothesis instrumentation, isolated from frozen confirmation evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from ignition import construction, development, evaluation, routing
from ignition.controller import Controller
from ignition.store import Store

PRODUCT = Path(__file__).resolve().parents[1]


def fixture():
    def row(label, urgent):
        return {"location": label, "priority": urgent}

    def target(region, bin_id, urgent):
        return {"region": region, "bin_number": bin_id, "urgent": urgent}

    def case(name, source, expected):
        return {"name": name, "input": {"rows": [source]}, "expected": {"rows": [expected]}}

    purpose = "Route parcel location codes to the correct regional bin."
    definition = {"input_fields": ["location", "priority"], "extra_fields": "reject",
                  "targets": [{"name": "region", "type": "text"}, {"name": "bin_number", "type": "integer"},
                              {"name": "urgent", "type": "boolean"}],
                  "demonstrations": [{"input": {"rows": [row("X/NE/17", "true"), row("Y/SW/p/23", "false")]},
                                      "expected": {"rows": [target("NE", 17, True), target("SW", 23, False)]}}]}
    spec = {"purpose": purpose, "kind": "record_migration", "definition": definition,
            "cases": [case("UNSEEN-ONE", row("Z/WEST-SECRET/aa/bb/567", "false"), target("WEST-SECRET", 567, False)),
                      case("UNSEEN-TWO", row("W/EAST-SECRET/987", "true"), target("EAST-SECRET", 987, True))]}
    mission = {"purpose": purpose, "beneficiary": "Parcel sorter", "resources": {"direct_method": "specialist"},
               "construction_spec": spec}
    return {"request_id": "parcel-location-study", "mission": mission}


class DevelopmentRepairTests(unittest.TestCase):
    def test_new_schema_last_component_and_middle_component_with_receiver(self):
        body = fixture()
        with tempfile.TemporaryDirectory() as root:
            ctrl = Controller(Store(root))
            rid, rev = ctrl.create(body)
            state = ctrl.advance(rid, rev)
            self.assertEqual(state["status"], "verified", state.get("error"))
            self.assertEqual(state.get("attempts", 0), 0)
            ops = {c["target"]: c for c in state["artifact"]["program"]["columns"]}
            self.assertEqual(ops["bin_number"]["split"], {"separator": "/", "index": -1})
            self.assertEqual(ops["region"]["split"], {"separator": "/", "index": 1})
            self.assertEqual(ctrl.deliver(rid, rev, {"rows": [{"priority": "false", "location": "L/NORTH/p/q/3"}]},
                                          trial=True), {"rows": [{"region": "NORTH", "bin_number": 3, "urgent": False}]})
            self.assertTrue(ctrl.deliver(rid, rev).startswith(b"PK"))

    def test_observation_is_field_specific_even_when_candidate_raises_on_batch(self):
        spec = fixture()["mission"]["construction_spec"]
        contract = construction.freeze_contract(spec)
        program, error = development.learn(spec["definition"])
        self.assertIsNone(error)
        bin_column = next(x for x in program["columns"] if x["target"] == "bin_number")
        bin_column["split"]["separator"] = "."
        artifact = construction.build(contract, {"kind": "record_migration", "program": program})
        feedback = routing.diagnostic(contract, artifact, evaluation.evaluate(contract, artifact))
        detail = feedback["public_development"]["targets"]
        self.assertEqual([x["target"] for x in detail], ["bin_number"])
        self.assertEqual([x["observed"] for x in detail[0]["witnesses"]], [{"error": "invalid_value"}] * 2)
        self.assertEqual([x["expected"] for x in detail[0]["witnesses"]], [17, 23])
        self.assertEqual(detail[0]["fitting_columns"][0]["split"], {"separator": "/", "index": -1})
        serialized = json.dumps(feedback)
        for case in spec["cases"]:
            for private in [case["name"], case["input"]["rows"][0]["location"], construction.fingerprint(case["input"]),
                            case["expected"]["rows"][0]["region"], str(case["expected"]["rows"][0]["bin_number"])]:
                self.assertNotIn(private, serialized)
        # Replacing every held-out value without changing group counts cannot change the intervention.
        changed = copy.deepcopy(spec)
        for i, case in enumerate(changed["cases"]):
            case["name"] = "DIFFERENT-HOLDOUT-" + str(i)
            label = "DIFFERENT-REGION-" + str(i)
            case["input"]["rows"][0]["location"] = "B/" + label + "/99"
            case["expected"]["rows"][0].update(region=label, bin_number=99)
        new = construction.freeze_contract(changed)
        new_artifact = construction.build(new, {"kind": "record_migration", "program": program})
        self.assertEqual(routing.diagnostic(new, new_artifact, evaluation.evaluate(new, new_artifact)), feedback)

    def test_ambiguous_development_rows_require_abstention_without_authority(self):
        body = fixture()
        definition = body["mission"]["construction_spec"]["definition"]
        # With both records three components long, index 1 and -2 are indistinguishable.
        definition["demonstrations"][0]["input"]["rows"][1]["location"] = "Y/SW/23"
        with tempfile.TemporaryDirectory() as root:
            ctrl = Controller(Store(root))
            rid, ver = ctrl.create(body)
            state = ctrl.advance(rid, ver)
            self.assertEqual(state["status"], "deferred", state.get("error"))
            self.assertIn("equally simple", state["error"])
            self.assertIsNone(state["artifact"])
            self.assertEqual(state.get("attempts", 0), 0)

    def test_original_bad_repair_and_genuinely_ambiguous_development_evidence(self):
        historical = PRODUCT.parents[1] / "docs/frontier-omega-ignition/continuation/development-repair/rejected-proposal.json"
        proposal = json.loads(historical.read_bytes())
        self.assertEqual(construction.fingerprint(proposal),
                         "9353460cae209c5ee2e7aa43d9b45bcc93fa77136c8743391cb9ffa106e3ed2e")
        definition = json.loads((PRODUCT/"examples/migration.json").read_bytes())["mission"]["construction_spec"]
        contract = construction.freeze_contract(definition)
        artifact = construction.build(contract, proposal)
        receipt = evaluation.evaluate(contract, artifact)
        self.assertEqual((receipt["status"], sum(c["candidate_pass"] for c in receipt["cases"])), ("fail", 5))
        targets = routing.diagnostic(contract, artifact, receipt)["public_development"]["targets"]
        self.assertEqual([t["target"] for t in targets], ["area"])
        area = targets[0]
        self.assertEqual(area["fitting_hypothesis_count"], 2)
        self.assertEqual([(c["source"], c["split"]) for c in area["fitting_columns"]],
                         [("id", {"separator": "-", "index": 0}), ("name", {"separator": " ", "index": 1})])
        self.assertEqual(area["witnesses"][0]["expected"], "passive")
        self.assertEqual(area["witnesses"][0]["observed"]["value"], "passive-mechanical-function")
        self.assertIsNone(development.learn(definition["definition"])[0])
