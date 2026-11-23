"""Independent negative/control oracle for OUTCOME-CLOSURE243, research-only."""
import copy
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import unittest

from enterprise.complete_arrangements242 import evaluate as parent_evaluate
from enterprise.outcome_closure243 import (
    PERMISSION_FIELDS, POLICIES, evaluate_complete, registered_witnesses,
    report, validate_permission,
)


class OutcomeClosure243Tests(unittest.TestCase):
    def test_exact_parent_source_and_exposed_partial_witness(self):
        cases = registered_witnesses()
        self.assertEqual(list(cases), [
            "NO_RIGHTS", "MODEL_AUTHORIZED", "MODEL_FAILURE", "WAR", "ABSENT"])
        for name, (case, _) in cases.items():
            row = parent_evaluate("STANDALONE_B@0.95", case)
            expected = -21 if name in ("WAR", "ABSENT") else 25.5
            self.assertAlmostEqual(row["contribution"], expected)
        self.assertEqual(POLICIES, ("STANDALONE_B@0.95", "NO_BID"))

    def test_missing_supplier_rights_does_not_monetize_incomplete_outcome(self):
        case, record = registered_witnesses()["NO_RIGHTS"]
        value = evaluate_complete(case, record, "STANDALONE_B@0.95")
        self.assertAlmostEqual(value["parent_partial_contribution_usd"], 25.5)
        self.assertIsNone(value["modeled_complete_contribution_usd"])
        self.assertFalse(value["selected_if_known_case"])
        self.assertEqual(value["model_evidence_tier"], "UNVERIFIED_COMPLETE_OUTCOME")
        self.assertEqual(value["operational_authority"], [])
        self.assertIsNone(value["qualified_paid_outcome"])

    def test_authored_full_completion_does_not_create_actual_authority(self):
        case, record = registered_witnesses()["MODEL_AUTHORIZED"]
        value = evaluate_complete(case, record, "STANDALONE_B@0.95")
        self.assertAlmostEqual(value["modeled_complete_contribution_usd"], 20.5)
        self.assertEqual(value["complete_acceptance_probability"], 1.)
        self.assertTrue(value["selected_if_known_case"])
        self.assertEqual(value["model_evidence_tier"], "AUTHOR_ASSUMPTIONS_ONLY")
        self.assertEqual(value["operational_authority"], [])
        self.assertIsNone(value["qualified_paid_outcome"])

    def test_failure_exposure_costs_and_no_bid(self):
        case, record = registered_witnesses()["MODEL_FAILURE"]
        row = evaluate_complete(case, record, "STANDALONE_B@0.95")
        self.assertAlmostEqual(row["complete_acceptance_probability"], .5)
        self.assertAlmostEqual(row["modeled_complete_contribution_usd"], -5.25)
        self.assertFalse(row["selected_if_known_case"])
        self.assertEqual(evaluate_complete(case, record, "NO_BID")[
            "modeled_complete_contribution_usd"], 0.)

    def test_independent_both_outcomes_bernoulli_payoff_oracle(self):
        # Independent branch-by-branch oracle, not the module's shortcut formula.
        for case_name in ("MODEL_AUTHORIZED", "MODEL_FAILURE", "WAR", "ABSENT"):
            case, record = registered_witnesses()[case_name]
            parent = parent_evaluate("STANDALONE_B@0.95", case)
            q = parent["initial_win_probability"]
            p = record["completion_probability"]
            fee = parent["initial_attempt_cost"]
            received = parent["conditional_collected_net_receipt"]
            onboarding = case["publics"][1]["onboarding_cost_usd"]
            value = -fee
            for sale, complete in product((0, 1), repeat=2):
                prob = (q if sale else 1 - q) * (p if complete else 1 - p)
                cash = 0
                if sale:
                    cash -= onboarding
                    cash -= record["verification_cost_usd"]
                    cash -= record["coordination_cost_usd"]
                    if complete:
                        cash += received
                    else:
                        cash -= record["correction_cost_usd"]
                value += prob * cash
            row = evaluate_complete(case, record, "STANDALONE_B@0.95")
            self.assertAlmostEqual(row["modeled_complete_contribution_usd"], value)

    def test_negative_controls_price_war_no_arrivals(self):
        for name in ("WAR", "ABSENT"):
            case, record = registered_witnesses()[name]
            row = evaluate_complete(case, record, "STANDALONE_B@0.95")
            self.assertAlmostEqual(row["modeled_complete_contribution_usd"], -21.)
            self.assertAlmostEqual(row["complete_acceptance_probability"], 0.)
            self.assertFalse(row["selected_if_known_case"])

    def test_no_bid_is_zero_with_and_without_rights(self):
        for name, (case, record) in registered_witnesses().items():
            row = evaluate_complete(case, record, "NO_BID")
            self.assertEqual(row["modeled_complete_contribution_usd"], 0)
            self.assertEqual(row["operational_authority"], [])
            self.assertIsNone(row["qualified_paid_outcome"])

    def test_adversarial_missing_boolean_invalid_probability_and_cost(self):
        case, record = registered_witnesses()["MODEL_AUTHORIZED"]
        examples = []
        modified = dict(record)
        modified.pop("rights_asserted")
        examples.append(modified)
        for key, v in (
            ("rights_asserted", "true"),
            ("rights_asserted", False),
            ("acceptance_asserted", False),
            ("completion_probability", 1.01),
            ("completion_probability", -0.1),
            ("completion_probability", float("nan")),
            ("verification_cost_usd", True),
            ("coordination_cost_usd", -1.),
            ("correction_cost_usd", float("inf")),
            ("evidence_tier", "real_money_approved"),
        ):
            modified = dict(record)
            modified[key] = v
            examples.append(modified)
        no_rights = registered_witnesses()["NO_RIGHTS"][1]
        modified = dict(no_rights)
        modified["rights_asserted"] = True
        examples.append(modified)
        modified = dict(no_rights)
        modified["completion_probability"] = 1.
        examples.append(modified)
        for variant in examples:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                evaluate_complete(case, variant, "STANDALONE_B@0.95")
        self.assertEqual(frozenset(record), PERMISSION_FIELDS)
        for policy in ("BUNDLE@0.95", "STANDALONE_B@nan", "", None):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                evaluate_complete(case, record, policy)

    def test_parent_buyer_cost_invalidity_still_fails_on_abstention(self):
        case, record = registered_witnesses()["NO_RIGHTS"]
        case["regime"]["arrival_probability"] = 2.
        with self.assertRaises(ValueError):
            evaluate_complete(case, record, "NO_BID")

    def test_source_hashes_and_no_actual_commerce_in_report(self):
        receipt = report()
        self.assertEqual(receipt["scenario_count"], 5)
        self.assertEqual(receipt["native_financial_authority"], [])
        self.assertIsNone(receipt["real_supplier_rights_verified"])
        self.assertIsNone(receipt["real_buyer_acceptance_verified"])
        self.assertIsNone(receipt["real_customer_collections_usd"])
        self.assertIsNone(receipt["native_trailing365_complete_cost_profit_usd"])
        self.assertEqual(receipt["commercial_verdict"], "UNQUALIFIED_HOLD_NO_NATIVE_ACTION")
        self.assertEqual(receipt["all_cases"]["NO_RIGHTS"]["decision"], "HOLD_UNVERIFIED")
        self.assertEqual(receipt["all_cases"]["MODEL_AUTHORIZED"]["decision"],
                         "CONDITIONAL_MODEL_OFFER")
        self.assertEqual(receipt["all_cases"]["MODEL_FAILURE"]["decision"],
                         "CONDITIONAL_MODEL_NO_BID")
        self.assertEqual(receipt["all_cases"]["WAR"]["decision"],
                         "CONDITIONAL_MODEL_NO_BID")
        self.assertEqual(receipt["all_cases"]["ABSENT"]["decision"],
                         "CONDITIONAL_MODEL_NO_BID")
        self.assertEqual(len({row["scenario_sha256"] for row in receipt["all_cases"].values()}), 5)

    def test_create_only_cli_does_not_operate_native_accounts(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "closure.json"
            command = [sys.executable, "-B", "-m", "enterprise.outcome_closure243",
                       "--out", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            saved = json.loads(output.read_text())
            self.assertEqual(saved["schema"], "agi-alpha/outcome-closure243/research-v1")
            self.assertTrue(saved["source_sha256"])
            self.assertTrue(saved["parent_source_sha256"])
            self.assertEqual(sorted(Path(tmp).iterdir()), [output])
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("CREATE_ONLY_RESEARCH_RESULT_REQUIRED", second.stderr)


if __name__ == "__main__":
    unittest.main()
