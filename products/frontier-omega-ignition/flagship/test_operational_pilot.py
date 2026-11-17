"""Synthetic adverse-case qualification. All amounts and observations here are test fixtures."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import operational_pilot as op
from pairing_lab import ROOT, digest
from pilot import canonical


class OperationalPilot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d = Path(self.temp.name)
        self.data = (ROOT / "runs.csv").read_bytes()
        self.source = self.put(b"synthetic source observation")
        configs = ["qwen/agentless", "glm/acr", "current_agent", "direct_tool", "human_conventional"]
        self.spec = {"tasks": {"new-issue": self.put(b"fixture requirement")}, "currency": "CAD",
                     "authority": {k: self.put(k.encode()) for k in op.AUTHORITIES},
                     "configurations": {k: self.put(k.encode()) for k in configs}}
        for stage in ("gate", "acceptance"):
            self.spec["authority"][stage + "_qualification"] = self.put(canonical({
                "procedure": self.spec["authority"][stage + "_procedure"],
                "controls": [{"artifact": self.put(f"control-{v}".encode()), "expected": v, "observed": v,
                              "source_sha256": self.source} for v in (False, True)]}))
        self.plan = op.register(self.spec, self.d, self.data)
        self.logs = {}
        self.first = self.put(b"candidate A")
        self.other = self.put(b"candidate B")
        for arm, slots in self.plan["routes"].items():
            cell = {}
            for i, slot in enumerate(slots):
                row = {"run_id": f"{arm}-{i}", "tokens": 10,
                       "artifact": self.other if i else self.first, "gate_pass": True}
                base = {"type": "selection", "task_contract": self.spec["tasks"]["new-issue"],
                        "arm": arm, "configuration": self.spec["configurations"][slot],
                        "grader": self.spec["authority"]["gate_procedure"]}
                row["receipt"] = self.doc({**base, **row})
                cell[slot] = [row]
            self.logs["new-issue:" + arm] = cell

    def put(self, raw):
        ref = digest(raw)
        (self.d / ref).write_bytes(raw)
        return ref

    def doc(self, obj):
        return self.put(canonical({**obj, "source_sha256": self.source}))

    def select(self):
        return op.select(self.plan, self.logs, self.d)

    def finals(self, deliveries, unknown=False):
        finals = {}
        for arm in op.ARMS:
            key = "new-issue:" + arm
            base = {"task_contract": self.spec["tasks"]["new-issue"], "arm": arm,
                    "delivery_sha256": digest(canonical(deliveries))}
            obs = {"delivered": deliveries["cells"][key]["selected"],
                   "accepted": arm in ("direct_tool", "human_conventional")}
            obs["decision_receipt"] = self.doc({**base, **obs, "type": "acceptance",
                                                "grader": self.spec["authority"]["acceptance_procedure"]})
            meters = {"human_ms": 3, "delivery_ms": 8, "cost_micros": {k: 5 for k in op.COSTS}}
            if unknown and arm == "historical_pair":
                meters["cost_micros"]["verification"] = None
            obs.update(meters)
            obs["meter_receipt"] = self.doc({**base, **meters, "type": "costs", "currency": "CAD"})
            finals[key] = obs
        return finals

    def test_commitments_and_configuration_evidence(self):
        raw = canonical(self.plan)
        self.assertEqual(self.plan, op.read_plan(raw, digest(raw), self.d, self.data))
        with self.assertRaises(ValueError):
            op.read_plan(raw + b" ", digest(raw), self.d, self.data)
        (self.d / self.spec["authority"]["rights_and_distribution"]).unlink()
        with self.assertRaises(OSError):
            op.read_plan(raw, digest(raw), self.d, self.data)

    def test_ambiguous_or_empty_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, "repeated JSON keys"):
            op.read_json(b'{"accepted": true, "accepted": false}')
        with self.assertRaisesRegex(ValueError, "empty evidence"):
            op.evidence(self.d, self.put(b""))

    def test_unqualified_acceptance_procedure_is_rejected(self):
        ref = self.spec["authority"]["acceptance_qualification"]
        controls = json.loads((self.d / ref).read_bytes())
        controls["controls"][0]["observed"] = True
        self.spec["authority"]["acceptance_qualification"] = self.put(canonical(controls))
        with self.assertRaisesRegex(ValueError, "failed or repeated"):
            op.register(self.spec, self.d, self.data)

    def test_complete_matched_comparison_can_lose_to_incumbents(self):
        deliveries = self.select()
        report = op.score(self.plan, deliveries, self.finals(deliveries), self.d)
        pair = report["arms"]["historical_pair"]
        self.assertEqual((pair["accepted"], pair["attempts"], pair["tokens"], pair["total_cost_micros"]),
                         (0, 2, 20, 30))
        self.assertEqual(report["pair_minus_alternative"]["direct_tool"]["additional_accepted"], -1)
        self.assertEqual(report["arms"]["human_conventional"]["accepted"], 1)

    def test_failed_gate_still_charged_and_frozen_priority_prevents_oracle(self):
        key = "new-issue:historical_pair"
        row = self.logs[key]["qwen/agentless"][0]
        selected = self.select()
        self.assertEqual(selected["cells"][key]["selected"], self.first)
        obs = self.finals(selected)
        obs[key]["delivered"] = self.other
        with self.assertRaisesRegex(ValueError, "chosen before"):
            op.score(self.plan, selected, obs, self.d)
        raw = json.loads((self.d / row["receipt"]).read_bytes())
        row.update(gate_pass=False, artifact=None, receipt=self.doc({**raw, "gate_pass": False, "artifact": None}))
        self.assertEqual(self.select()["cells"][key], {"selected": self.other, "tokens": 20, "attempts": 2})

    def test_missing_control_duplicate_run_and_tampered_grade(self):
        key = "new-issue:human_conventional"
        saved = self.logs.pop(key)
        with self.assertRaises(ValueError):
            self.select()
        self.logs[key] = saved
        rows = saved["human_conventional"]
        rows.append(rows[0])
        with self.assertRaisesRegex(ValueError, "own run ID"):
            self.select()
        rows.pop()
        rows[0]["gate_pass"] = False
        with self.assertRaisesRegex(ValueError, "receipt"):
            self.select()

    def test_unknown_cost_blocks_difference_and_meter_mutation_fails(self):
        selected = self.select()
        finals = self.finals(selected, unknown=True)
        report = op.score(self.plan, selected, finals, self.d)
        self.assertIsNone(report["arms"]["historical_pair"]["total_cost_micros"])
        self.assertIsNone(report["pair_minus_alternative"]["current_agent"]["additional_cost_micros"])
        finals["new-issue:direct_tool"]["cost_micros"]["human_labor"] = 0
        with self.assertRaisesRegex(ValueError, "receipt"):
            op.score(self.plan, selected, finals, self.d)

    def test_cli_two_phase_round_trip_and_output_is_exclusive(self):
        def file(name, obj):
            path = self.d / name
            path.write_bytes(canonical(obj))
            return path

        def run(action, outfile, *args, ok=True):
            result = subprocess.run([sys.executable, ROOT / "operational_pilot.py", action,
                                     "--evidence", self.d, "--out", self.d / outfile, *args],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0 if ok else 2, result.stderr)
            return result.stdout.strip()

        spec = file("spec.json", self.spec)
        plan_sha = run("register", "plan.json", "--spec", spec)
        run("register", "plan.json", "--spec", spec, ok=False)
        attempts = file("attempts.json", self.logs)
        shared = ("--plan", self.d / "plan.json", "--plan-sha", plan_sha, "--attempts", attempts)
        selection_sha = run("select", "delivery.json", *shared)
        deliveries = json.loads((self.d / "delivery.json").read_bytes())
        finals = file("finals.json", self.finals(deliveries))
        tail = ("--deliveries", self.d / "delivery.json", "--finals", finals)
        run("score", "fail.json", *shared, *tail, "--delivery-sha", "0" * 64, ok=False)
        self.assertFalse((self.d / "fail.json").exists())
        run("score", "result.json", *shared, *tail, "--delivery-sha", selection_sha)


if __name__ == "__main__":
    unittest.main()
