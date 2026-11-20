"""Frozen 19 November 2026 source-bound incentive tests, not real demand."""
import unittest

from invent import value
from verifier_incentive import evaluate


class VerifierIncentiveTests(unittest.TestCase):
    def setUp(self):
        self.proof = evaluate()
        self.arms = self.proof["scenarios"]

    def test_original_positive_synthetic_quote_is_not_actual_receipt(self):
        old = self.proof["original_buyer_escrow_value"]
        self.assertTrue(old["accepted"])
        self.assertEqual((old["buyer_surplus"], old["seller_surplus"],
                          old["protocol_surplus"]), ("50", "59", "1"))
        self.assertEqual(self.proof["actual_revenue"], "NONE_OBSERVED")

    def test_buyer_has_strict_refund_incentive_after_receiving_artifact(self):
        self.assertEqual(self.proof["buyer_after_delivery"]["accept_surplus"], "50")
        self.assertEqual(self.proof["buyer_after_delivery"]["refund_surplus"], "150")
        self.assertEqual(self.proof["buyer_after_delivery"]["strict_best_response"],
                         "WITHHOLD_AND_REFUND")
        self.assertEqual(self.arms["buyer_verifier_after_accessible_delivery_and_strategic_refund"]["seller_surplus"], "-40")
        self.assertEqual(self.arms["buyer_verifier_after_accessible_delivery_and_strategic_refund"]["protocol_surplus"], "0")

    def test_seller_declines_predictable_loss_rather_than_fund_future_fees(self):
        self.assertEqual(self.proof["seller_best_response_before_entry"], "NO_ENTRY")
        self.assertEqual(self.arms["buyer_verifier_rational_preentry"]["seller_surplus"], "0")
        self.assertEqual(self.arms["buyer_verifier_rational_preentry"]["protocol_surplus"], "0")

    def test_honest_independent_verifier_enables_but_does_not_prove_commerce(self):
        fee = self.arms["honest_independent_verifier_fee_bearing"]
        free = self.arms["honest_independent_verifier_fee_free_incumbent"]
        self.assertEqual((fee["buyer_surplus"], fee["seller_surplus"],
                          fee["protocol_surplus"]), ("47", "59", "1"))
        self.assertEqual((free["buyer_surplus"], free["seller_surplus"],
                          free["protocol_surplus"]), ("47", "60", "0"))
        self.assertEqual(fee["verification_cost"], "3")
        self.assertEqual(free["verification_cost"], "3")

    def test_strong_direct_and_no_deploy_controls_not_assumed_inferior(self):
        direct = self.arms["direct_prepaid_competent_seller"]
        none = self.arms["no_deploy"]
        self.assertEqual((direct["buyer_surplus"], direct["seller_surplus"]),
                         ("50", "60"))
        self.assertEqual((none["buyer_surplus"], none["seller_surplus"],
                          none["protocol_surplus"]), ("0", "0", "0"))
        self.assertEqual(self.proof["new_invention_or_universal_equilibrium"],
                         "NOT_ESTABLISHED")

    def test_explicit_info_pattern_and_missing_real_costs(self):
        a = self.proof["assumptions"]
        self.assertTrue(a["artifact_accessible_before_acceptance"])
        self.assertEqual(a["external_penalty_for_false_refusal"], 0)
        self.assertEqual(a["actual_buyers"], 0)
        self.assertEqual(a["actual_payments"], 0)
        self.assertEqual(self.proof["actual_model_host_billing"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
