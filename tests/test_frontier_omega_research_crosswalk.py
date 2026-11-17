"""No money, no live buyers, no database writes: crosswalk acceptance checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from frontier_omega.core import validate_problem
from frontier_omega.research_crosswalk import (
    SOURCE_FIELDS, git_blob, pin_input, review_proposals,
)


def fixture():
    row = {
        "id": "O002", "engine": "MIGRATE",
        "title": "Critical service migration", "buyer": "Software infrastructure operators",
        "blocked_problem": "Compatibility and costs prevent safe replacement",
        "deliverable": "Versioned behavior-preserving service", "acceptance_test": "Frozen outputs agree",
        "strongest_complete_alternative": "Competent specialist developer with conventional tools",
        "frontier_signal_ids": ["S001"],
        "first_discriminating_test": "Compare current and competent conventional delivery under one frozen scope.",
        "pilot_quote_usd_hypothesis": 65000,
        "pilot_quote_status": "UNTESTED_PRICE_HYPOTHESIS_NOT_A_CUSTOMER_OFFER",
        "crossing_threshold": {"minimum_matched_cases": 20, "minimum_acceptance_fraction": 0.95,
                               "max_complete_cost_per_accepted_usd": 22750,
                               "max_p95_turnaround_hours": 168},
        "ordinal_hypotheses": {"buyer_urgency": 4, "autonomy_fit": 4, "acceptance_clarity": 4,
                              "repeatability": 4, "differentiation": 3, "capital_intensity": 2,
                              "sales_friction": 4},
        "initial_state": "WATCH_NO_MATCHED_BENCHMARK",
        "technical_old_vs_new": "NOT_TESTED",
        "observed_paid_demand": "NONE",
        "strict_unattended_autonomy": "NOT_DEMONSTRATED",
        "customer_authority": "REQUIRES_CONTRACT_AND_ACCESS",
        "note": "Research hypothesis and untested pricing, not a customer order.",
    }
    opportunities = {
        "schema": "frontier-omega-opportunities/v1",
        "as_of": "2026-11-16", "definition": "Audited example of authored research hypotheses",
        "baseline_cutoff": "2026-10-12", "currency": "USD",
        "pricing_policy": "Assumed and untested price, not buyer terms.",
        "dimension_policy": "Ordinal editorial priors, not probabilities.",
        "results": [dict(row, id="O%03d" % (i + 1)) for i in range(57)],
    }
    signal = {
        "id": "S001", "date": "2026-11-09", "title": "Reported technical signal",
        "url": "https://example.org/technical-signal", "type": "vendor_demonstration",
        "access": "Available but not ALPHA independently reproduced.",
        "implication": "Research trigger, not new proof of feasibility.",
        "verified_corpus_date": "2026-11-16", "reproduced_by_alpha": False,
    }
    signals = {
        "schema": "frontier-omega-signals/v1", "as_of": "2026-11-16",
        "baseline_cutoff": "2026-10-12",
        "status": "Source-reported, not independently reproduced.",
        "signals": [dict(signal, id="S%03d" % (i + 1)) for i in range(12)],
    }
    return opportunities, signals


class SourceBoundCrosswalkTests(unittest.TestCase):
    def test_canonical_schema_and_research_only(self):
        opportunities, signals = fixture()
        initial = copy.deepcopy((opportunities, signals))
        result = review_proposals(opportunities, signals)
        self.assertEqual((opportunities, signals), initial)
        self.assertEqual(result["case_count"], 57)
        self.assertEqual(result["signal_count"], 12)
        self.assertEqual(result["disposition"], "READ_ONLY_UNIMPORTED_REVIEW_ONLY")
        self.assertFalse(result["canonical_reservoir_modified"])
        self.assertEqual(result["financial_authority"], "NONE")
        self.assertFalse(result["actual_buyers_or_paid_outcomes_established"])
        self.assertEqual(len(set(x["id"] for x in result["candidate_problems"])), 57)
        for item in result["candidate_problems"]:
            validate_problem(item)
            self.assertEqual(item["demand"]["status"], "HYPOTHESIS")
            self.assertIsNone(item["demand"]["ceiling_microUSD"])
            self.assertIsNone(item["demand"]["terms_sha256"])
            self.assertEqual(item["demand"]["consent_verification"], "NOT_VERIFIED")
            self.assertIn("No purchase", {a["name"] for a in item["alternatives"]})
            self.assertTrue(item["id"].startswith("study-o"))
        self.assertEqual(len(result["index"]), 57)
        self.assertTrue(all(r["semantic_overlap_review_required"] for r in result["index"]))

    def test_frozen_blob_verification_before_import(self):
        data = b'{"schema":"example"}'
        pin_input(data, git_blob(data))
        with self.assertRaisesRegex(ValueError, "SOURCE_BLOB_CHANGED"):
            pin_input(data + b" ", git_blob(data))

    def test_no_duplicate_or_ambiguous_source(self):
        opportunities, signals = fixture()
        opportunities["results"][1]["id"] = "O001"
        with self.assertRaisesRegex(ValueError, "STUDY_ID"):
            review_proposals(opportunities, signals)

    def test_unknown_catalyst_rejected(self):
        opportunities, signals = fixture()
        opportunities["results"][0]["frontier_signal_ids"] = ["S999"]
        with self.assertRaisesRegex(ValueError, "SOURCE_SIGNAL"):
            review_proposals(opportunities, signals)

    def test_claim_upgrade_rejected(self):
        opportunities, signals = fixture()
        opportunities["results"][0]["observed_paid_demand"] = "CUSTOMERS"
        with self.assertRaisesRegex(ValueError, "CLAIM_PROMOTION"):
            review_proposals(opportunities, signals)

    def test_unreviewed_schema_change_rejected(self):
        opportunities, signals = fixture()
        opportunities["results"][0]["buyer_contact_email"] = "private@example.org"
        with self.assertRaisesRegex(ValueError, "EXACT_SCHEMA"):
            review_proposals(opportunities, signals)

    def test_source_signal_cannot_claim_reproduction(self):
        opportunities, signals = fixture()
        signals["signals"][0]["reproduced_by_alpha"] = True
        with self.assertRaisesRegex(ValueError, "CLAIM_CHANGED"):
            review_proposals(opportunities, signals)

    def test_price_is_never_imported_as_verified_ceiling(self):
        opportunities, signals = fixture()
        opportunities["results"][0]["pilot_quote_usd_hypothesis"] = 10**12
        result = review_proposals(opportunities, signals)
        p = result["candidate_problems"][0]
        self.assertIsNone(p["demand"]["ceiling_microUSD"])
        self.assertNotIn("price_microUSD", p)
        self.assertFalse(result["actual_buyers_or_paid_outcomes_established"])

    def test_unbounded_or_boolean_editor_priors_fail(self):
        opportunities, signals = fixture()
        opportunities["results"][0]["ordinal_hypotheses"]["autonomy_fit"] = True
        with self.assertRaisesRegex(ValueError, "EDITOR_PRIOR"):
            review_proposals(opportunities, signals)

    def test_study_schema_mismatch_fails(self):
        opportunities, signals = fixture()
        opportunities["schema"] = "frontier-omega/problem/v1"
        with self.assertRaisesRegex(ValueError, "STUDY_VERSION"):
            review_proposals(opportunities, signals)

    def test_no_import_and_no_generated_account_or_queues(self):
        opportunities, signals = fixture()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            before = list(root.iterdir())
            review_proposals(opportunities, signals)
            self.assertEqual(before, list(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
