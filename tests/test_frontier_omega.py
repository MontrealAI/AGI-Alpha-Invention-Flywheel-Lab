"""Deterministic no-network qualification tests for FRONTIER Ω."""
import copy
import hashlib
import io
import unittest

from frontier_omega.__main__ import (
    COST_CATEGORIES, InventoryError, assess, assess_one, export_csv,
    rank, score, validate, watch_diff,
)


class FrontierOmegaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opportunities, cls.signals = validate()
        cls.o = next(o for o in cls.opportunities if o["id"] == "O002")

    def run_case(self, *, prior_accept=12, current_accept=20, synthetic=False):
        costs = {key: 0 for key in COST_CATEGORIES}
        costs["model_compute"] = 500
        costs["independent_verification"] = 350
        costs["human_work"] = 300
        costs["acquisition"] = 250
        costs["residual_obligations"] = 100
        base = {"date": "2026-10-11", "cases": 20, "accepted": prior_accept,
                "p95_turnaround_hours": 32, "costs_usd": dict(costs)}
        current = {"date": "2026-11-16", "cases": 20, "accepted": current_accept,
                   "p95_turnaround_hours": 20, "costs_usd": dict(costs)}
        return {"opportunity_id": "O002", "synthetic": synthetic,
                "task_suite_sha256": hashlib.sha256(b"frozen-suite").hexdigest(),
                "same_frozen_suite": True, "baseline": base, "current": current,
                "review": {"independent_verifier": True, "report_url": "https://example.org/review"}}

    def test_seed_56_unverified_buyer_problems(self):
        self.assertEqual(len(self.opportunities), 56)
        self.assertEqual(len(self.signals), 12)
        self.assertEqual(set(o["engine"] for o in self.opportunities),
                         {"MIGRATE", "PROVE", "OPERATE", "TRUST", "ENGINEER", "DISCOVER"})
        self.assertTrue(all(o["observed_paid_demand"] == "NONE" for o in self.opportunities))

    def test_triage_is_deterministic_not_claimed_roi(self):
        ids1 = [o["id"] for o in rank(self.opportunities)]
        ids2 = [o["id"] for o in rank(self.opportunities)]
        self.assertEqual(ids1, ids2)
        self.assertTrue(all(type(score(o)) is int for o in self.opportunities))

    def test_csv_exports_every_problem(self):
        out = io.StringIO()
        export_csv(self.opportunities, out)
        self.assertEqual(len(out.getvalue().splitlines()), 57)

    def test_synthetic_fixture_cannot_promote(self):
        report = assess_one(self.o, self.run_case(synthetic=True))
        self.assertEqual(report["stage"], "SYNTHETIC_REHEARSAL_ONLY")

    def test_new_threshold_crossing_is_reported_not_certified(self):
        report = assess_one(self.o, self.run_case())
        self.assertEqual(report["stage"], "REPORTED_NEW_TECHNICAL_CROSSING_AUDIT_REQUIRED")
        self.assertEqual(report["commercial_status"], "UNVERIFIED_EXTERNALLY")
        self.assertFalse(report["old"]["pass"])
        self.assertTrue(report["current"]["pass"])

    def test_baseline_already_passed_is_not_new_crossing(self):
        report = assess_one(self.o, self.run_case(prior_accept=20))
        self.assertEqual(report["stage"], "QUALIFIED_BUT_NO_NEW_FIVE_WEEK_CROSSING")

    def test_failure_of_new_acceptance_gate(self):
        report = assess_one(self.o, self.run_case(current_accept=17))
        self.assertEqual(report["stage"], "BLOCKED_CURRENT_BELOW_ACCEPTANCE_COST_OR_TIME_GATE")

    def test_self_attestation_does_not_confer_independence(self):
        case = self.run_case()
        case["review"]["independent_verifier"] = False
        self.assertEqual(assess_one(self.o, case)["stage"],
                         "UNINDEPENDENT_CROSSING_REPORT_NEEDS_VERIFIER")

    def test_reported_payment_never_claims_verified_revenue(self):
        case = self.run_case()
        case["sale"] = {"buyer_accepted": True, "collected": True,
                        "all_residual_obligations_costed": True,
                        "actual_collected_usd": 65000,
                        "receipt_url": "https://example.org/unverified"}
        report = assess_one(self.o, case)
        self.assertEqual(report["stage"], "REPORTED_PAID_OUTCOME_AUDIT_REQUIRED")
        self.assertEqual(report["commercial_status"], "UNVERIFIED_EXTERNALLY")

    def test_rejects_incomplete_lifecycle_cost(self):
        case = self.run_case()
        del case["current"]["costs_usd"]["acquisition"]
        with self.assertRaises(InventoryError):
            assess_one(self.o, case)

    def test_rejects_unmatched_old_and_new_suite(self):
        case = self.run_case()
        case["same_frozen_suite"] = False
        with self.assertRaises(InventoryError):
            assess_one(self.o, case)

    def test_rejects_post_cutoff_old_baseline(self):
        case = self.run_case()
        case["baseline"]["date"] = "2026-11-01"
        with self.assertRaises(InventoryError):
            assess_one(self.o, case)

    def test_rejects_duplicate_benchmark_reports(self):
        case = self.run_case()
        with self.assertRaises(InventoryError):
            assess(self.opportunities, [case, copy.deepcopy(case)])

    def test_watcher_flags_changes_without_claiming_releases(self):
        initial = watch_diff({}, {"openai_releases": "abc"})
        changed = watch_diff({"openai_releases": "abc"}, {"openai_releases": "def"})
        unchanged = watch_diff({"openai_releases": "abc"}, {"openai_releases": "abc"})
        self.assertEqual(initial[0]["event"], "INITIAL_OBSERVATION_NOT_A_NEW_RELEASE")
        self.assertEqual(changed[0]["event"], "PAGE_BYTES_CHANGED_REVIEW_REQUIRED")
        self.assertEqual(unchanged, [])


if __name__ == "__main__":
    unittest.main()
