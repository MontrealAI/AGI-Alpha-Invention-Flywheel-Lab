"""Fixed-target mathematical, input-integrity and publication checks (stdlib only).

Each criticism addresses the same prespecified material-defect proposition;
these tests cannot establish coverage of mixed true/false allegation batches.
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import check_study
import study


ROOT = Path(__file__).resolve().parent


class ExactChallengeAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
        cls.reference = cls.protocol["scenarios"][0]["parameters"]
        cls.temporary = tempfile.TemporaryDirectory(prefix="missing-move-audit-")
        cls.output = Path(cls.temporary.name) / "evidence"
        cls.generated = study.generate(output=cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_all_published_results_match_separate_branch_calculation(self):
        checked = check_study.check_publication(evidence=self.output)
        self.assertEqual(checked["status"], "PASS")
        self.assertEqual(checked["named_profiles_checked"], 11)
        self.assertEqual(checked["grid_points_checked"], 2304)
        self.assertEqual(checked["successful_cash_paths_checked"], 2)
        paths = [(["-60", "-30", "120"], "90"), (["40", "-60", "-30", "80"], "50")]
        for flows, minimum in paths:
            produced = study.successful_cash_path(flows)
            self.assertEqual(produced, check_study.check_cash_prefixes(flows))
            self.assertEqual(produced["minimum_starting_cash"], minimum)
            self.assertEqual(produced["net_contribution"], "30")

    def test_reproduction_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as destination:
            other = Path(destination)
            study.generate(output=other)
            for filename in ("results.json", "results.csv", "results_table.tex"):
                self.assertEqual((self.output / filename).read_bytes(), (other / filename).read_bytes())

    def test_checked_in_publication_is_current(self):
        for filename in ("results.json", "results.csv", "results_table.tex"):
            self.assertEqual((ROOT / "evidence" / filename).read_bytes(), (self.output / filename).read_bytes())

    def test_probability_mass_and_impossible_acceptance(self):
        _, branches = check_study.enumerate_branches(self.reference)
        self.assertEqual(len(branches), 8)
        self.assertEqual(sum(Fraction(row["probability"]) for row in branches), 1)
        for row in branches:
            if row["A"] and not row["D"]:
                self.assertEqual(Fraction(row["probability"]), 0)

    def test_boundary_worlds_do_not_earn_imaginary_repairs(self):
        cases = [
            ({"pi": "0", "f": "0"}, Fraction(-8)),
            ({"pi": "0", "f": "1", "b": "1"}, Fraction(-38)),
            ({"pi": "1", "d": "1", "a": "1"}, Fraction(92)),
            ({"pi": "1", "d": "0", "a": "1"}, Fraction(-8)),
        ]
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                parameters = {**self.reference, **overrides}
                exact = study.evaluate(parameters)
                enumerated, _ = check_study.enumerate_branches(parameters)
                self.assertEqual(exact, enumerated)
                self.assertEqual(Fraction(exact["delta"]), expected)

    def test_invalid_probabilities_are_rejected_by_both_paths(self):
        for key in ("pi", "d", "a", "f", "b"):
            for value in ("-1/100", "101/100"):
                for implementation in (study.evaluate, check_study.enumerate_branches):
                    with self.subTest(key=key, value=value, implementation=implementation.__name__):
                        with self.assertRaises(ValueError):
                            implementation({**self.reference, key: value})

    def test_floating_point_boolean_and_nonfinite_inputs_are_rejected(self):
        for value in (0.25, True, float("nan"), "NaN", "Infinity", "1/0", None):
            for implementation in (study.evaluate, check_study.enumerate_branches):
                with self.subTest(value=value, implementation=implementation.__name__):
                    with self.assertRaises(ValueError):
                        implementation({**self.reference, "pi": value})

    def test_unknown_and_missing_parameters_are_rejected(self):
        missing = dict(self.reference)
        del missing["K"]
        for parameters in (missing, {**self.reference, "unpriced_bonus": "100"}):
            for implementation in (study.evaluate, check_study.enumerate_branches):
                with self.assertRaises(ValueError):
                    implementation(parameters)

    def test_negative_cost_or_harm_is_rejected_but_bad_repair_is_allowed(self):
        for implementation in (study.evaluate, check_study.enumerate_branches):
            for key in ("K", "H"):
                with self.assertRaises(ValueError):
                    implementation({**self.reference, key: "-1"})
        bad_repair = {**self.reference, "G": "-10"}
        exact = study.evaluate(bad_repair)
        enumerated, _ = check_study.enumerate_branches(bad_repair)
        self.assertEqual(exact, enumerated)
        self.assertLess(Fraction(exact["delta"]), 0)

    def test_shared_detection_does_not_count_as_independent_evidence(self):
        expected = {"0": ("91/100", "9/100"), "4/5": ("371/500", "129/500"), "1": ("7/10", "3/10")}
        for rho, (coverage, joint_miss) in expected.items():
            produced = study.critic_pair("7/10", rho)
            checked = check_study.pair_enumeration("7/10", rho)
            self.assertEqual(produced, checked)
            self.assertEqual(produced["at_least_one_detects"], coverage)
            self.assertEqual(produced["neither_detects"], joint_miss)

    def test_infeasible_pair_correlations_are_rejected(self):
        for implementation in (study.critic_pair, check_study.pair_enumeration):
            for marginal, rho in (("7/10", "-1"), ("7/10", "2"), ("0", "0"), ("1", "0")):
                with self.subTest(marginal=marginal, rho=rho):
                    with self.assertRaises(ValueError):
                        implementation(marginal, rho)

    def test_tampered_publication_values_are_rejected(self):
        for filename in ("results.json", "results.csv", "results_table.tex"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                for original in self.output.iterdir():
                    shutil.copy2(original, output / original.name)
                path = output / filename
                if filename.endswith(".json"):
                    content = json.loads(path.read_text(encoding="utf-8"))
                    content["profiles"][0]["metrics"]["delta"] = "1000000"
                    path.write_text(json.dumps(content), encoding="utf-8")
                else:
                    text = path.read_text(encoding="utf-8")
                    self.assertIn("9.8875", text)
                    path.write_text(text.replace("9.8875", "999.8875", 1), encoding="utf-8")
                with self.assertRaises(ValueError):
                    check_study.check_publication(evidence=output)

    def test_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in study.SOURCE_FILES:
                shutil.copy2(ROOT / name, root / name)
            (root / "study.py").write_text("# changed source\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Changed source"):
                check_study.check_publication(root=root, evidence=self.output)

    def test_grid_omission_cannot_silently_change_the_denominator(self):
        grid = copy.deepcopy(self.protocol["grid"])
        grid["axes"]["pi"].pop()
        with self.assertRaisesRegex(ValueError, "declared count"):
            study.summarize_grid(grid)

    def test_misdeclared_expected_result_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in study.SOURCE_FILES:
                shutil.copy2(ROOT / name, root / name)
            protocol = copy.deepcopy(self.protocol)
            protocol["scenarios"][0]["expected_delta"] = "1000000"
            (root / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Declared arithmetic"):
                study.generate(root=root)
            self.assertFalse((root / "evidence" / "results.json").exists())


if __name__ == "__main__":
    unittest.main()
