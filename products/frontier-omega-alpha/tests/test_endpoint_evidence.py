import unittest

from research.possibility_observatory.endpoint_study import decision, reference
from research.possibility_observatory.endpoint_study.__main__ import checked_receipt

MATCH = {"dataset": "agentic", "role": "measurement", "status": "official"}
AS_OF = "2026-11-23"


def row(key, **changes):
    return {"id": key, "published": AS_OF, "facts": MATCH,
            "metric": "40", "objective": "50.00", "upper_metric": "500", **changes}


class DecisionTests(unittest.TestCase):
    def test_scope_dates_ties_and_both_inclusive_bounds(self):
        rows = [
            row("eligible"),
            row("tied", objective="50.0"),
            row("fast-but-other-dataset", facts={**MATCH, "dataset": "other"}, objective="999"),
            row("provisional", facts={**MATCH, "status": "provisional"}, objective="999"),
            row("announcement", facts={**MATCH, "role": "announcement"}, objective="999"),
            row("future", published="2026-11-24", objective="999"),
            row("unknown-date", published=None, objective="999"),
            row("unknown-metric", metric=None, objective="999"),
            row("unknown-ceiling-metric", upper_metric=None, objective="999"),
            row("below-floor", metric="39.999999999999999999999", objective="999"),
            row("above-ceiling", upper_metric="500.000000000000000000001", objective="999"),
        ]
        result = decision.evaluate(rows, MATCH, AS_OF, "40", "500")
        self.assertEqual(result, reference.evaluate_many(rows, MATCH, AS_OF, ["40"], "500")[0])
        self.assertEqual(result["winners"], ["eligible", "tied"])
        self.assertEqual(result["dispositions"], {
            "above-ceiling": "above-ceiling", "announcement": "outside-scope",
            "below-floor": "below-threshold", "eligible": "qualified",
            "fast-but-other-dataset": "outside-scope", "future": "not-yet-documented",
            "provisional": "outside-scope", "tied": "qualified",
            "unknown-ceiling-metric": "missing-measurement", "unknown-date": "missing-publication-date",
            "unknown-metric": "missing-measurement",
        })

    def test_announcement_cannot_replace_missing_operational_evidence(self):
        rows = [row("vendor-announcement", facts={**MATCH, "role": "announcement"}),
                row("on-bench", published="2026-11-24")]
        self.assertEqual(decision.evaluate(rows, MATCH, AS_OF, "40")["winners"], [])

    def test_duplicate_identity_and_invalid_numeric_are_rejected(self):
        for rows in ([row("same"), row("same")], [row("invalid", objective="Infinity")],
                     [row("invalid", metric=40)], [row("invalid", published="20261123")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                decision.evaluate(rows, MATCH, AS_OF, "40")

    def test_recorded_mlcommons_replay(self):
        evidence = checked_receipt()
        self.assertEqual(evidence["rows"], 365)
        self.assertEqual(evidence["registered_cases"]["40"]["witnesses"][0]["load"], 2048)
        self.assertEqual(evidence["exploratory_first_token_screen"]["witnesses"][0]["load"], 512)
        self.assertIs(evidence["production_authority"], False)


if __name__ == "__main__":
    unittest.main()
