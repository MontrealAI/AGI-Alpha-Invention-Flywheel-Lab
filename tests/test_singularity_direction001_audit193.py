"""Independent preregistered proof-closure review, frozen in PROOF_REVIEW_193.md.

Failing tests are retained as failures; no original source or case modifications.
"""
from __future__ import annotations

import copy
import unittest

from research.singularity_direction001 import experiment as engine
from research.singularity_direction001 import verify as checker


class ProofClosure193(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = engine.experiment()

    @staticmethod
    def nonselected(evidence):
        row = evidence["cases"][0]
        return next(r for r in row["responses"] if r["switch"] != row["selected_additional_switch"])

    def test_original_source_and_both_outcomes_pass(self):
        result = checker.verify(self.evidence)
        self.assertEqual(result["status"], "PASS_SCOPED_DC_PROOF")
        self.assertEqual({r["case"] for r in result["results"]}, set(engine.SOURCE))
        self.assertAlmostEqual(result["results"][0]["gain_mw"], 11.55573817, places=5)
        self.assertAlmostEqual(result["results"][1]["gain_mw"], 28.68939554, places=5)

    def test_duplicate_case_substitutes_missing_source_must_fail(self):
        tampered = copy.deepcopy(self.evidence)
        tampered["cases"][1] = copy.deepcopy(tampered["cases"][0])
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            checker.verify(tampered)

    def test_nonselected_cost_forgery_must_fail(self):
        tampered = copy.deepcopy(self.evidence)
        self.nonselected(tampered)["unserved_mw"] += 1000.0
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            checker.verify(tampered)

    def test_nonselected_witnesses_are_present_and_verified(self):
        for item in self.evidence["cases"]:
            outage = item["selected_outage"]
            case = engine.parse_case(item["case"])
            for response in item["responses"]:
                self.assertIn("witness", response,
                    "Each alternative must contain independent primal/dual evidence")
                proof = response["witness"]
                self.assertAlmostEqual(
                    checker.check_dual(case, {outage, response["switch"]}, proof),
                    response["unserved_mw"], places=4)

    def test_missing_nonselected_witness_must_fail(self):
        tampered = copy.deepcopy(self.evidence)
        self.nonselected(tampered).pop("witness", None)
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            checker.verify(tampered)

    def test_forged_nonselected_primal_must_fail(self):
        tampered = copy.deepcopy(self.evidence)
        alt = self.nonselected(tampered)
        if "witness" in alt:
            alt["witness"]["primal"][0] += 5000.0
        else:
            alt["witness"] = {"primal": [5000.0]}
        with self.assertRaises((ValueError, KeyError, AssertionError)):
            checker.verify(tampered)


if __name__ == "__main__":
    unittest.main()
