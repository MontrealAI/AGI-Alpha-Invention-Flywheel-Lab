"""Private-workspace regressions for automatic selection and CLI intervention."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ignition import development
from ignition.controller import Controller
from ignition.store import Store
from test_adaptive import public_fixture
from test_development_repair import fixture as unique_fixture

PRODUCT = Path(__file__).resolve().parents[1]


class AdaptiveMappingTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.ctrl = Controller(Store(self.root / "state"), assisted=("test transport", "unit double"))

    def run_body(self, body):
        rid, version = self.ctrl.create(body)
        return self.ctrl.advance(rid, version)

    def test_materially_different_mappings_select_the_least_authorized_route(self):
        unique = unique_fixture()
        unique["mission"]["resources"] = {"max_model_calls": 0}
        accepted = self.run_body(unique)
        self.assertEqual((accepted["routing"]["method"], accepted["status"]), ("specialist", "verified"))
        self.assertEqual(accepted.get("attempts", 0), 0)

        fixture = public_fixture("reading-catalog")
        pending = self.run_body(fixture)
        self.assertEqual((pending["routing"]["method"], pending["handoff"]["stage"]), ("model_choice", "choose_hypothesis"))
        self.assertEqual(len(pending["mapping_choice"]["candidates"]), 3)
        self.assertNotIn("Parallel editions named separately", pending["handoff"]["prompt"])

        for suffix in ("unclear", "no-grant", "zero-calls"):
            fixture = public_fixture("reading-catalog")
            fixture["request_id"] += suffix
            m = fixture["mission"]
            if suffix == "unclear":
                m["purpose"] = m["construction_spec"]["purpose"] = "Prepare a multilingual catalog file."
            elif suffix == "no-grant":
                m["authority"]["assisted_model"] = False
            else:
                m["resources"]["max_model_calls"] = 0
            state = self.run_body(fixture)
            self.assertEqual((state["routing"]["method"], state["status"]), ("operator_choice", "awaiting_choice"))
            self.assertEqual(state.get("attempts", 0), 0)

    def test_default_route_preserves_intended_split_when_a_copy_fits(self):
        path = PRODUCT.parents[1] / "docs/frontier-omega-ignition/continuation/bounded-choice/parcel.json"
        for by_model in (False, True):
            m = json.loads(path.read_bytes())["mission"]
            m["resources"] = {}
            m["authority"] = {"assisted_model": by_model}
            spec = m["construction_spec"]
            definition = spec["definition"]
            definition["input_fields"].append("reported_mark")
            for demo in definition["demonstrations"]:
                for source, target in zip(demo["input"]["rows"], demo["expected"]["rows"]):
                    source["reported_mark"] = target["sorting_mark"]
            for case in spec["cases"]:
                for source in case["input"]["rows"]:
                    source["reported_mark"] = "incorrect"
            rid, revision = self.ctrl.create({"request_id": f"adaptive-incidental-copy-{by_model}", "mission": m})
            state = self.ctrl.advance(rid, revision)
            self.assertEqual(state["routing"]["method"], "model_choice" if by_model else "operator_choice")
            menu = state["mapping_choice"]
            choices = {item["description"]: item["id"] for item in menu["candidates"]}
            self.assertTrue(any("copy reported_mark" in desc for desc in choices))
            selected = next(identifier for desc, identifier in choices.items() if "second component of routing_note" in desc)
            if by_model:
                self.assertEqual(state["handoff"]["stage"], "choose_hypothesis")
                self.ctrl.intervene(rid, revision, "respond", {"sha256": state["handoff"]["sha256"],
                                                              "response": {"choice": selected}})
            else:
                self.ctrl.intervene(rid, revision, "choose", {"sha256": menu["sha256"], "choice": selected})
            state = self.ctrl.advance(rid, revision)
            self.assertEqual(state["status"], "verified", state.get("error"))
            self.assertEqual(state["construction_attempts"][0]["passed_checks"], 9)
            self.assertEqual(state.get("attempts", 0), int(by_model))

    def test_unrepresentable_join_and_oversized_space(self):
        fixture = public_fixture("reading-catalog")
        definition = fixture["mission"]["construction_spec"]["definition"]
        for row in definition["demonstrations"][0]["expected"]["rows"]:
            row["publication"] += " " + row["reading_language"]
        state = self.run_body(fixture)
        self.assertEqual((state["routing"]["method"], state["handoff"]["stage"]), ("model", "construct"))
        fixture["request_id"] += "-unavailable"
        fixture["mission"]["authority"] = {}
        self.assertEqual(self.run_body(fixture)["routing"]["route"], "clarify")

        fixture = public_fixture("reading-catalog")
        fixture["request_id"] += "-excess"
        definition = fixture["mission"]["construction_spec"]["definition"]
        for extra in ("one", "two"):
            definition["targets"].append({"name": extra, "type": "text"})
            for demo in definition["demonstrations"]:
                for row in demo["expected"]["rows"]:
                    row[extra] = row["reading_language"]
            for case in fixture["mission"]["construction_spec"]["cases"]:
                for row in case.get("expected", {}).get("rows", []):
                    row[extra] = row["reading_language"]
        state = self.run_body(fixture)
        self.assertEqual((state["routing"]["route"], state["status"]), ("clarify", "deferred"))
        self.assertIn("more than", state["routing"]["reason"])
        self.assertEqual(state.get("attempts", 0), 0)

    def test_partial_or_conflicting_evidence_does_not_disambiguate(self):
        ops = [("left", 0), ("left", 1), ("right", 0)]
        menu = {"candidates": [{"operations": [{"column": {"source": field, "target": "unit",
                          "split": {"separator": "/", "index": index}}}]} for field, index in ops]}
        for text in ("Use left.", "Use first.", "Use first or second from left.",
                     "Use first from left. Use second from left."):
            self.assertFalse(development.has_distinguishing_evidence({"purpose": text, "requirements": []}, menu))
        self.assertTrue(development.has_distinguishing_evidence({"purpose": "Use first from left.", "requirements": []}, menu))

    def test_cli_can_resolve_or_abstain_without_a_model(self):
        fixture = public_fixture("reading-catalog")
        fixture["mission"]["authority"] = {}
        source = self.root / "mission.json"
        source.write_text(json.dumps(fixture))
        command = [sys.executable, "-B", "-m", "ignition", "--state", str(self.root / "operator")]

        def run(*args, check=True):
            return subprocess.run([*command, *args], cwd=PRODUCT, capture_output=True, text=True, check=check)

        for accept in (False, True):
            state = json.loads(run("start", str(source)).stdout)
            self.assertEqual(state["status"], "awaiting_choice")
            menu = state["mapping_choice"]
            chosen = next(c["id"] for c in menu["candidates"] if "copy edition_language" in c["description"])
            args = ["choose", state["id"], chosen if accept else "abstain", "--version", str(state["version"]), "--sha256"]
            self.assertNotEqual(run(*args, "0" * 64, check=False).returncode, 0)
            for _ in range(2):
                final = json.loads(run(*args, menu["sha256"]).stdout)
                self.assertEqual(final["status"], "verified" if accept else "deferred")
                self.assertEqual(final.get("attempts", 0), 0)
