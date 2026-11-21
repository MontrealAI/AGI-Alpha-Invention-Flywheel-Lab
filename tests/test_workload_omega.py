"""Finite fixture and adversarial controls for WORKLOAD Ω; no model, network or sales."""
import copy
import unittest

from commercial.workload_omega.engine import evaluate


def fixture():
    observations = []
    for split, prefix in (("train", "T"), ("holdout", "H")):
        for n in range(4):
            case = f"{prefix}{n}"
            for arm, cost, latency, accepted in (
                ("reference", 60000, 300, True),
                ("efficient", 20000, 150, True),
                ("cheap_bad", 1000, 100, n != 1),
            ):
                observations.append({
                    "split": split, "case_id": case, "arm": arm,
                    "cost_microusd": cost, "latency_ms": latency,
                    "accepted": accepted,
                })
    return {
        "schema": "workload-omega/v1",
        "workload_id": "synthetic-comparable-task",
        "evidence_type": "synthetic",
        "reference_arm": "reference",
        "candidate_arms": ["cheap_bad", "efficient"],
        "max_latency_ms": 500,
        "min_acceptance_bps": 10000,
        "min_train_pairs": 4,
        "min_holdout_pairs": 4,
        "observations": observations,
        "economics": {
            "expected_monthly_requests": 10000,
            "savings_share_bps": 2000,
            "monthly_operating_cost_microusd": 25000000,
            "monthly_onboarding_amortization_microusd": 5000000,
            "monitoring_cost_per_request_microusd": 500,
            "other_monthly_cost_microusd": 0,
        },
    }


def row(c, split, case, arm):
    return next(x for x in c["observations"]
                if x["split"] == split and x["case_id"] == case and x["arm"] == arm)


class WorkloadAssetTest(unittest.TestCase):
    def test_frozen_selection_and_model_only_money(self):
        r = evaluate(fixture())
        self.assertEqual(r["selected_arm"], "efficient")
        self.assertEqual(r["decision"], "ENGINEERING_ONLY")
        self.assertFalse(r["train_candidate_results"]["cheap_bad"]["eligible"])
        self.assertEqual(r["holdout_result"]["gross_savings_microusd"], 160000)
        self.assertEqual(r["economics"]["modeled_monthly_provider_contribution_microusd"], 45000000)
        self.assertFalse(r["first_dollar_proven"])
        self.assertFalse(r["second_distinct_asset_proven"])
        self.assertFalse(r["live_deployment_authorized"])

    def test_holdout_quality_regression_does_not_select_runner_up(self):
        c = fixture()
        row(c, "holdout", "H0", "efficient")["accepted"] = False
        r = evaluate(c)
        self.assertEqual(r["selected_arm"], "efficient")
        self.assertEqual(r["decision"], "HOLD_HOLDOUT")
        self.assertFalse(r["holdout_result"]["qualified"])

    def test_holdout_latency_failure(self):
        c = fixture()
        row(c, "holdout", "H2", "efficient")["latency_ms"] = 501
        self.assertEqual(evaluate(c)["decision"], "HOLD_HOLDOUT")

    def test_holdout_reversal(self):
        c = fixture()
        for x in c["observations"]:
            if x["split"] == "holdout" and x["arm"] == "efficient":
                x["cost_microusd"] = 70000
        self.assertEqual(evaluate(c)["decision"], "HOLD_HOLDOUT")

    def test_no_train_qualified(self):
        c = fixture()
        row(c, "train", "T0", "efficient")["accepted"] = False
        r = evaluate(c)
        self.assertEqual(r["decision"], "HOLD_TRAINING")
        self.assertEqual(r["selected_arm"], "reference")

    def test_negative_modeled_margin_is_not_go(self):
        c = fixture()
        c["economics"]["monthly_operating_cost_microusd"] = 300000000
        r = evaluate(c)
        self.assertEqual(r["decision"], "HOLD_ECONOMICS")
        self.assertEqual(r["economics"]["status"], "MODEL_ONLY_NONPOSITIVE")

    def test_measured_claim_cannot_become_first_dollar(self):
        c = fixture()
        c["evidence_type"] = "measured_unverified"
        r = evaluate(c)
        self.assertEqual(r["decision"], "SHADOW_CANDIDATE")
        self.assertFalse(r["first_dollar_proven"])
        self.assertEqual(r["actual_settled_revenue_microusd"], 0)

    def test_missing_economics_never_zero_cost(self):
        c = fixture()
        del c["economics"]
        r = evaluate(c)
        self.assertEqual(r["economics"]["status"], "NOT_MODELED")
        self.assertNotIn("modeled_monthly_provider_contribution_microusd", r["economics"])

    def test_overlap_rejected(self):
        c = fixture()
        for x in c["observations"]:
            if x["split"] == "holdout" and x["case_id"] == "H1":
                x["case_id"] = "T1"
        with self.assertRaisesRegex(ValueError, "leakage"):
            evaluate(c)

    def test_missing_paired_arm_rejected(self):
        c = fixture()
        c["observations"] = [x for x in c["observations"]
                             if not (x["split"] == "holdout"
                                     and x["case_id"] == "H1"
                                     and x["arm"] == "reference")]
        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate(c)

    def test_duplicate_rejected(self):
        c = fixture()
        c["observations"].append(copy.deepcopy(c["observations"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate(c)

    def test_unknown_arm_rejected(self):
        c = fixture()
        c["observations"][0]["arm"] = "intruder"
        with self.assertRaisesRegex(ValueError, "unknown arm"):
            evaluate(c)

    def test_boolean_integer_confusion_rejected(self):
        c = fixture()
        c["observations"][0]["cost_microusd"] = False
        with self.assertRaisesRegex(ValueError, "integer"):
            evaluate(c)

    def test_partial_financial_costs_rejected(self):
        c = fixture()
        del c["economics"]["other_monthly_cost_microusd"]
        with self.assertRaisesRegex(ValueError, "all six"):
            evaluate(c)

    def test_receipt_is_deterministic(self):
        c = fixture()
        self.assertEqual(evaluate(c), evaluate(copy.deepcopy(c)))


if __name__ == "__main__":
    unittest.main()
