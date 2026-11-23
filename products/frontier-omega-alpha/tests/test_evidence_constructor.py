import json
import unittest

from research.possibility_observatory.evidence_constructor import oracle, plans, records
from research.possibility_observatory.evidence_constructor.__main__ import RECEIPT, run


class EvidenceConstructorTests(unittest.TestCase):
    def test_unknown_verdict_requires_no_contrary_condition(self):
        fixed = ("printer", "2026-10-20", "orderable", True)
        cases = [
            records.case("pending", "reference", ("printer", None, "orderable", True), fixed),
            records.case("wrong", "reference", ("printer", None, "announcement", True), fixed),
            records.case("future", "reference", ("printer", "2026-10-21", "orderable", True), fixed),
            records.case("proved", "reference", ("printer", "2026-10-20", "orderable", True), fixed),
        ]
        meanings = {"pending": "insufficient", "wrong": "inapplicable",
                    "future": "inapplicable", "proved": "supported"}
        self.assertEqual(oracle.outcomes(cases), meanings)
        for plan in (plans.FIXED, tuple(reversed(plans.FIXED))):
            self.assertEqual({case["id"]: plans.evaluate(case, plan)[0] for case in cases}, meanings)

    def test_exact_constructor_and_exhaustive_agree(self):
        for rejected in ((0, 0, 0, 0), (4, 10, 3, 13), (15, 1, 2, 12)):
            with self.subTest(rejected=rejected):
                self.assertEqual(plans.optimal(rejected, 4), plans.exhaustive(rejected, 4))

    def test_frozen_evidence_acceptance_and_cost_comparisons(self):
        result, _ = run()
        self.assertEqual(result, json.loads(RECEIPT.read_bytes()))
        self.assertEqual(result["orderable_before_october_21"][0]["documented"], "2026-09-29")
        self.assertEqual(result["without_archived_offer"], [])
        self.assertEqual(result["independent_production_evidence"], [])
        for campaign in result["campaigns"]:
            arms = campaign["arms"]
            self.assertEqual(arms["ordinary_reuse"], arms["pooled_constructor"])
            self.assertLessEqual(arms["fixed_no_history"]["predicate_checks"],
                                 arms["learned_update"]["predicate_checks"])
        self.assertFalse(result["production_authority"])


if __name__ == "__main__":
    unittest.main()
