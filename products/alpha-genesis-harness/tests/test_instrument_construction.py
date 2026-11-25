# SPDX-License-Identifier: Apache-2.0
"""Qualification for the two malformed conditional programs observed in 1.2."""

from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bridge.instruments import evaluate, validate_instrument
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime


def recorded_conditional(name, inputs, outputs):
    return {
        "name": name,
        "inputs": inputs,
        "outputs": {key: {"op": "if", "args": [{"field": field} for field in inputs]} for key in outputs},
    }


def construct(name, spec):
    return {"tool": "construct_instrument", "name": name, "spec": spec}


def exercise(name, inputs):
    return {"tool": "run_instrument", "name": name, "input": inputs}


def propose(*actions, done=False):
    return {"summary": "Construct and check the scoped instrument.", "actions": list(actions), "done": done}


def payoff_instrument():
    cells = ("aa", "ab", "ba", "bb")
    weights = ("p * q", "p * (1 - q)", "(1 - p) * q", "(1 - p) * (1 - q)")
    return {
        "inputs": ["p", "q", "payoffs"],
        "numeric_mode": "exact-rational",
        "bindings": {cell: {"formula": weight} for cell, weight in zip(cells, weights)},
        "outputs": {
            label: {"op": "add", "args": [
                {"op": "mul", "args": [{"ref": cell}, {"field": f"payoffs.{cell}.{label}"}]}
                for cell in cells]}
            for label in ("row", "column")
        },
    }


def payoff_check(name, matrix, p, q):
    row_choices = [Fraction(p), 1 - Fraction(p)]
    column_choices = [Fraction(q), 1 - Fraction(q)]
    payoffs = {cell: dict(zip(("row", "column"), profile))
               for cell, profile in zip(("aa", "ab", "ba", "bb"), matrix[0] + matrix[1])}
    expected = {
        label: str(sum(row_prob * col_prob * matrix[i][j][index]
                       for i, row_prob in enumerate(row_choices)
                       for j, col_prob in enumerate(column_choices)))
        for index, label in enumerate(("row", "column"))
    }
    return {"kind": "instrument", "artifact": name, "input": {"p": p, "q": q, "payoffs": payoffs}, "expected": expected}


class InstrumentConstructionTest(unittest.TestCase):
    def scope(self, ambition, acceptance=()):
        return {
            "ambition": ambition, "language": "en", "provider": "fixture", "model": "authored-constructor",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(),
            "max_turns": 5, "max_actions": 15, "max_output_tokens": 2048,
            "acceptance": list(acceptance),
        }

    def mission(self, ambition, responses, *, acceptance=()):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = FixtureRuntime(responses)
        service = UniversalMissionService(runtime, Path(temp.name) / "missions")
        self.addCleanup(service.close)
        view = service.submit(self.scope(ambition, acceptance))
        return service, runtime, view["id"]

    def assert_recorded_bytes(self, spec, fingerprint):
        raw = json.dumps(spec, sort_keys=True, indent=2).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), fingerprint)

    def test_owner_program_refused_before_write_then_exact_payoff_implementation_passes(self):
        bad = recorded_conditional("GameTheoryCalculator", ["player1_strategy", "player2_strategy"], ["payoff1", "payoff2"])
        self.assert_recorded_bytes(bad, "8e1dd35b53871bedbd85d94bfb18ed613171d26f7b9c012f8229d9b1716c5fde")
        name = "game_theory_calculator.json"
        prisoners = [[(3, 3), (0, 5)], [(5, 0), (1, 1)]]
        matching = [[(1, -1), (-1, 1)], [(-1, 1), (1, -1)]]
        battle = [[(2, 1), (0, 0)], [(0, 0), (1, 2)]]
        acceptance = [payoff_check(name, game, p, q) for game, p, q in (
            (prisoners, "1", "1"), (prisoners, "0", "1"),
            (matching, "1/2", "1/2"), (battle, "3/4", "1/3"), (battle, "1", "1"),
        )]
        failed_turn = propose(construct(name, bad), exercise(name, {"player1_strategy": [1, 0], "player2_strategy": [1, 0]}), done=True)
        repair = propose(construct(name, payoff_instrument()), exercise(name, acceptance[3]["input"]), done=True)
        ambition = "Build Frontier AI for Game Theory."
        service, runtime, ident = self.mission(ambition, [failed_turn, repair], acceptance=acceptance)

        refused = service.step(ident)
        self.assertEqual(refused["status"], "ready")
        self.assertEqual(refused["original_ambition"], ambition)
        self.assertEqual(service.export(ident)["files"], {})
        self.assertEqual(list((service._directory(ident) / ".objects").iterdir()), [])
        self.assertFalse(refused["verification"]["passed"])
        events = [entry["detail"] for entry in refused["events"] if entry["kind"] == "tool_refused"]
        self.assertEqual([event["code"] for event in events], ["INSTRUMENT_STRUCTURE", "INSTRUMENT_DEPENDENCY"])
        self.assertTrue(all(event["artifact"] == name for event in events))
        self.assertIn('$.outputs["payoff1"]', events[0]["reason"])
        self.assertIn('$.outputs["payoff2"]', events[0]["reason"])
        self.assertIn("[boolean condition, when_true, when_false]. Found 2", refused["feedback"])

        repaired = service.step(ident)
        self.assertEqual(repaired["status"], "needs_review")
        self.assertTrue(repaired["verification"]["passed"])
        self.assertEqual([check["actual"] for check in repaired["verification"]["checks"]],
                         [check["expected"] for check in acceptance])
        self.assertEqual(set(service.export(ident)["files"]), {name, "RUN_INSTRUMENT.py"})
        self.assertIn("Found 2", runtime.calls[1]["prompt"])
        self.assertEqual(service.capabilities()["capabilities"], [])

    def test_telemetry_refusal_does_not_replace_or_run_previous_bytes_and_can_repair_same_turn(self):
        bad = recorded_conditional("TelemetryClassifier", ["previous", "current"], ["classification"])
        self.assert_recorded_bytes(bad, "b6bdcf7b40194f35723d03000ab317969ea544920c9bb7ee493dfcf52967e724")
        corrected = {
            "inputs": ["previous", "current"],
            "outputs": {"classification": {"formula":
                "choose(current >= previous, 'normal', choose(previous >= 65000 and current <= 535, 'wrap', 'reset'))"}},
        }
        name = "telemetry_classifier.json"
        inputs = {"previous": 65000, "current": 535}
        base = propose(construct(name, corrected))
        unrelated = {"tool": "write_document", "name": "scope.md", "content": "A threshold rule for bounded counter records."}
        rejected = propose(construct(name, bad), exercise(name, inputs), unrelated, done=True)
        corrected_turn = propose(construct(name, bad), construct(name, corrected), exercise(name, inputs), done=True)
        service, _, ident = self.mission("Classify a 16-bit telemetry counter transition.", [base, rejected, corrected_turn])
        service.step(ident)
        original = service.export(ident)["files"][name]

        refused = service.step(ident)
        self.assertEqual(refused["status"], "ready")
        self.assertIn('$.outputs["classification"]', refused["feedback"])
        self.assertFalse(any(event["kind"] == "tool_completed" and event["detail"]["tool"] == "run_instrument"
                             for event in refused["events"]))
        files = service.export(ident)["files"]
        self.assertEqual(files[name], original)
        self.assertEqual(files["scope.md"], unrelated["content"])

        repaired = service.step(ident)
        self.assertEqual(repaired["status"], "needs_review")
        calculation = next(event["detail"]["outcome"] for event in repaired["events"]
                           if event["kind"] == "tool_completed" and event["detail"]["tool"] == "run_instrument")
        self.assertEqual(calculation["output"], {"classification": "wrap"})
        for previous, current in [(0, 0), (65535, 65535), (13, 1), (1, 13), (65000, 535), (64999, 535),
                                  (65000, 536), (65535, 0), (32768, 16), (42, 43), (65320, 535), (60000, 59999)]:
            ordinary = "normal"
            if current < previous:
                ordinary = "wrap" if previous >= 65000 and current <= 535 else "reset"
            output = evaluate(json.loads(files[name]), {"previous": previous, "current": current})
            self.assertEqual(output["output"]["classification"], ordinary)

    def test_static_walk_covers_lazy_branches_bindings_and_formula_syntax_without_fake_inputs(self):
        for branch, message in [
            ({"formula": "choose(flag, 1)"}, r"\.args\[2\]\.formula.*Found 2"),
            ({"op": "sum", "args": [[1], [2]]}, r"\.args\[2\].*sum needs one operand"),
            ({"field": "missing.value"}, "Input field root was not declared"),
            ({"formula": "round(1)"}, "unsupported expression or function"),
        ]:
            spec = {"inputs": ["flag"], "outputs": {"value": {"op": "if", "args": [True, 1, branch]}}}
            with self.subTest(branch=branch), self.assertRaisesRegex(ValueError, message):
                validate_instrument(spec)
        cycle = {"inputs": [], "outputs": {"value": 1}, "bindings": {"cycle": {"ref": "cycle"}}}
        with self.assertRaisesRegex(ValueError, r"bindings\.cycle.*cycle"):
            validate_instrument(cycle)
        unknown_branch = {"inputs": ["flag"], "outputs": {"value": {"formula": "choose(flag, 1, 1 / 0)"}}}
        validate_instrument(unknown_branch)
        self.assertEqual(evaluate(unknown_branch, {"flag": True})["output"], {"value": 1})
        with self.assertRaisesRegex(ValueError, "Division by zero"):
            evaluate(unknown_branch, {"flag": False})
        with self.assertRaisesRegex(ValueError, "if condition must be boolean"):
            validate_instrument({"inputs": [], "outputs": {"value": {"formula": "choose(1, 2, 3)"}}})

    def test_later_turn_cannot_execute_or_replay_stale_instrument_after_restart(self):
        name = "calibration.json"
        ambition = "Construct and refine a calibration check."
        run = exercise(name, {})
        initial = construct(name, {"inputs": [], "outputs": {"value": 1}})
        invalid = construct(name, {"inputs": [], "outputs": {"value": {"op": "if", "args": [True, 9]}}})
        corrected = construct(name, {"inputs": [], "outputs": {"value": {"op": "if", "args": [True, 9, 0]}}})
        service, _, ident = self.mission(ambition, [propose(initial, run), propose(invalid)])
        self.assertEqual(service.step(ident)["status"], "ready")
        refused = service.step(ident)
        self.assertEqual(refused["status"], "ready")
        self.assertEqual(service.pause(ident)["status"], "paused")
        root = service.root
        service.close()

        updated = UniversalMissionService(FixtureRuntime([propose(run, done=True), propose(corrected, run, done=True)]), root)
        self.addCleanup(updated.close)
        self.assertEqual(updated.get(ident)["status"], "paused")
        self.assertEqual(updated.resume(ident, background=False)["status"], "ready")
        stale = updated.step(ident)
        self.assertEqual(stale["status"], "ready")
        self.assertIn("Found 2", stale["feedback"])
        self.assertIn("INSTRUMENT_DEPENDENCY", [event["detail"].get("code") for event in stale["events"]])
        computations = [event["detail"]["outcome"] for event in stale["events"]
                        if event["kind"] == "tool_completed" and event["detail"]["tool"] == "run_instrument"]
        self.assertEqual([outcome["output"] for outcome in computations], [{"value": 1}])
        repaired = updated.step(ident)
        self.assertEqual(repaired["status"], "needs_review")
        computations = [event["detail"]["outcome"] for event in repaired["events"]
                        if event["kind"] == "tool_completed" and event["detail"]["tool"] == "run_instrument"]
        self.assertEqual([outcome["output"] for outcome in computations], [{"value": 1}, {"value": 9}])

    def test_archive_recovery_carries_refusal_to_new_scope_and_blocks_stale_verification(self):
        ambition = "Check the expected calibration value."
        name = "calibration.json"
        initial = construct(name, {"inputs": [], "outputs": {"value": 1}})
        invalid = construct(name, {"inputs": [], "outputs": {"value": {"formula": "choose(true, 9)"}}})
        corrected = construct(name, {"inputs": [], "outputs": {"value": {"formula": "choose(true, 9, 0)"}}})
        acceptance = [{"artifact": name, "kind": "instrument", "input": {}, "expected": {"value": 9}}]
        service, _, ident = self.mission(ambition, [
            propose(initial), propose(invalid), propose(exercise(name, {}), done=True),
            propose(corrected, exercise(name, {}), done=True),
        ], acceptance=acceptance)
        self.assertEqual(service.step(ident)["verification"]["checks"][0]["actual"], {"value": 1})
        rejected = service.step(ident)
        self.assertNotIn("actual", rejected["verification"]["checks"][0])
        archive = service.export(ident)
        imported = service.import_archive(archive, self.scope(ambition, acceptance))
        self.assertEqual(imported["status"], "paused")
        self.assertTrue(any(event["kind"] == "instrument_refusal_restored" for event in imported["events"]))
        self.assertEqual(service.export(imported["id"])["files"][name], archive["files"][name])
        service.resume(imported["id"], background=False)
        stale = service.step(imported["id"])
        self.assertEqual(stale["status"], "ready")
        self.assertIn("resubmit the corrected construction", stale["verification"]["checks"][0]["error"])
        self.assertFalse(any(event["kind"] == "tool_completed" for event in stale["events"]))
        resolved = service.step(imported["id"])
        self.assertEqual(resolved["status"], "needs_review")
        self.assertTrue(resolved["verification"]["passed"])
        self.assertEqual(resolved["verification"]["checks"][0]["actual"], {"value": 9})
