"""Adversarial strongest-incumbent qualification tests; no paid agent execution."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import invent

class InventionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for name in ("reference.py", "candidate.py"):
            (self.root / name).write_text("def solve(payload): return payload\n")
        (self.root / "heldout.json").write_text("[]")
        (self.root / "acceptance.json").write_text("{}")
        (self.root / "frontier.json").write_text(json.dumps({"min_best_speedup": 1.2, "max_worst_regression": 1.05}))
        (self.root / "incumbents").mkdir()
        (self.root / "incumbents" / "best.py").write_text("def solve(payload): return payload\n")
        self.cases = [{"id":"correct","kind":"correctness","input":{}},
                      {"id":"perf1","kind":"performance","input":{}},
                      {"id":"perf2","kind":"performance","input":{}}]

    def scenario(self, reference=1000, candidate=100, incumbent=700, corrupt=False, gate="PASS"):
        def fake(source, cases, mode, name):
            filename = Path(source).name
            ns = reference if filename == "reference.py" else candidate if filename == "candidate.py" else incumbent
            return [{"id":c["id"],"median_ns":ns,
                     "response":"false" if filename == "best.py" and corrupt else "true"} for c in cases]
        with patch.object(invent.unlock, "read_project", return_value=(self.root, self.cases, {})), \
             patch.object(invent.unlock, "verify", return_value={"status":gate}), \
             patch.object(invent.unlock, "execute", side_effect=fake):
            return invent.evaluate(self.root, self.root / "candidate.py", "local")

    def test_pass_requires_fastest_correct_incumbent(self):
        report = self.scenario()
        self.assertEqual(report["status"], "PASS_LAB")
        self.assertEqual(report["performance"]["geomean_vs_fastest"], 7.0)
        self.assertEqual(report["economics"]["status"], "NO_BUYER_ECONOMIC_INPUT")

    def test_stronger_rival_invalidates_strawman_improvement(self):
        r = self.scenario(incumbent=50)
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("NO_QUALIFIED_ADVANTAGE", r["reason"])

    def test_incorrect_incumbent_fails_closed(self):
        r = self.scenario(corrupt=True)
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("INCUMBENT_ORACLE_MISMATCH", r["reason"])

    def test_candidate_not_good_enough(self):
        self.assertEqual(self.scenario(candidate=900, incumbent=500)["status"], "HOLD")

    def test_base_gate_failure_not_overridden(self):
        self.assertEqual(self.scenario(gate="HOLD")["status"], "HOLD")

    def test_missing_rival_is_not_a_frontier_win(self):
        (self.root / "incumbents" / "best.py").unlink()
        with patch.object(invent.unlock, "read_project", return_value=(self.root, self.cases, {})):
            with self.assertRaises(invent.FrontierError):
                invent.evaluate(self.root, self.root / "candidate.py", "local")

    def test_bad_economic_fields_fail_closed(self):
        for x in (True, "NaN", -1, None):
            c = {"min_best_speedup":1.2,"max_worst_regression":1.05,
                 "economics":{"annual_invocations":x,"compute_cost_per_hour":2,
                              "year_one_integration_cost":0,"annual_maintenance_cost":0}}
            (self.root / "frontier.json").write_text(json.dumps(c))
            with self.subTest(x=x), self.assertRaises(invent.FrontierError):
                invent.configuration(self.root)

    def test_no_duplicated_thresholds(self):
        (self.root / "frontier.json").write_text('{"min_best_speedup":1.2,"min_best_speedup":2,"max_worst_regression":1}')
        with self.assertRaises(invent.FrontierError):
            invent.configuration(self.root)

    def test_economic_scenario_is_not_revenue(self):
        c = {"min_best_speedup":1.2,"max_worst_regression":1.05,
             "economics":{"annual_invocations":1000000,"compute_cost_per_hour":1,
                          "year_one_integration_cost":5000,"annual_maintenance_cost":5000}}
        (self.root / "frontier.json").write_text(json.dumps(c))
        report = self.scenario()
        self.assertEqual(report["status"], "PASS_LAB")
        self.assertEqual(report["economics"]["status"], "HYPOTHETICAL_EQUAL_WEIGHT_NOT_REVENUE")
        self.assertLess(float(report["economics"]["buyer_year_one_net_scenario"]), 0)

if __name__ == "__main__":
    unittest.main()
