# SPDX-License-Identifier: Apache-2.0
"""Scoped software checks, not scientific confirmation or real opportunity discovery."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from lab import inspect, screen, sha

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "possibilities.json"


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.items = json.loads(EXAMPLE.read_text())

    def test_initial_three_distinct_domains(self):
        outcome = inspect(self.items)
        self.assertEqual(len(outcome["candidate_results"]), 3)
        self.assertEqual(outcome["admitted_cohorts"], 0)
        self.assertFalse(outcome["material_distinctness_verified"])

    def test_no_synthetic_profit_claim(self):
        self.assertEqual(inspect(self.items)["commercial_success"], "UNESTABLISHED")

    def test_no_human_or_frontier_foresight_claim(self):
        self.assertEqual(inspect(self.items)["forecast_superiority"], "UNMEASURED")

    def test_source_empty_not_treated_as_evidence(self):
        out = inspect(self.items)
        self.assertTrue(all(q["source_count"] == 0 for q in out["candidate_results"]))
        self.assertTrue(all(q["source_entries_are_unverified"] for q in out["candidate_results"]))

    def test_requires_three_candidates(self):
        with self.assertRaises(ValueError): inspect(self.items[:2])

    def test_duplicate_domain_refused(self):
        values = copy.deepcopy(self.items)
        values[1]["domain"] = values[0]["domain"]
        with self.assertRaises(ValueError): inspect(values)

    def test_duplicate_id_refused(self):
        values = copy.deepcopy(self.items)
        values[1]["id"] = values[0]["id"]
        with self.assertRaises(ValueError): inspect(values)

    def test_missing_falsifier_refused(self):
        values = copy.deepcopy(self.items)
        values[0]["falsifier"] = ""
        with self.assertRaises(ValueError): inspect(values)

    def test_extra_field_refused(self):
        values = copy.deepcopy(self.items)
        values[0]["profit"] = 1e9
        with self.assertRaises(ValueError): inspect(values)

    def test_bad_source_refused(self):
        values = copy.deepcopy(self.items)
        values[0]["evidence_sources"] = [{"url": "made up"}]
        with self.assertRaises(ValueError): inspect(values)

    def test_forged_cost_record_never_approves(self):
        values = copy.deepcopy(self.items)
        values[0]["known_complete_costs"] = {"baseline": "-100", "candidate": "+1000", "currency": "SIM", "horizon": "90 days", "source": "unverified"}
        self.assertEqual(inspect(values)["admitted_cohorts"], 0)

    def test_output_is_exclusive_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "screen"
            result = screen(EXAMPLE, output)
            self.assertEqual(result["input_sha256"], sha(self.items))
            self.assertTrue((output / "DECISION.md").is_file())
            self.assertEqual(json.loads((output / "SCREEN.json").read_text()), result)
            with self.assertRaises(FileExistsError): screen(EXAMPLE, output)

    def test_bad_json_refused_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            src, out = Path(folder) / "bad.json", Path(folder) / "out"
            src.write_text("not-json")
            with self.assertRaises(json.JSONDecodeError): screen(src, out)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
