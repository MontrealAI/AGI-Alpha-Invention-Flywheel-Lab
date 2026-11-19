"""Registered micro-fee cases; distinct conditional raw units versus synthetic units."""
from fractions import Fraction
import unittest

from products.frontier_mechanism_foundry.microfee_precision import (
    PrecisionRefusal, UINT256_MAX, microfee_receipt,
)
from products.frontier_mechanism_foundry.invent import value


class MicrofeePrecisionTest(unittest.TestCase):
    def test_ninety_nine_raw_units_produce_zero_protocol_fee(self):
        r = microfee_receipt([99], 100)
        self.assertEqual(r["conditional_per_order_fee_sum_raw"], "0")
        self.assertEqual(r["ideal_rational_fee_if_same_unit"], "99/100")
        self.assertIsNone(r["actual_collected_raw_fees"])
        self.assertEqual(r["decision"], "NO_DEPLOY_NO_REAL_PROFIT_CLAIM")

    def test_threshold_hundred_raw_units_produces_one(self):
        r = microfee_receipt([100], 100)
        self.assertEqual(r["conditional_per_order_fee_sum_raw"], "1")
        self.assertEqual(r["one_bundle_fee_raw_if_representable"], "1")

    def test_twenty_distinct_jobs_differ_from_one_bundle(self):
        r = microfee_receipt([99] * 20, 100)
        self.assertEqual(r["number_of_independent_orders"], 20)
        self.assertEqual(r["total_raw_principal"], "1980")
        self.assertEqual(r["conditional_per_order_fee_sum_raw"], "0")
        self.assertEqual(r["one_bundle_fee_raw_if_representable"], "19")
        self.assertEqual(r["ideal_rational_fee_if_same_unit"], "99/5")
        self.assertEqual(r["difference_bundle_minus_independent_raw_if_representable"], "19")
        self.assertTrue(r["one_bundle_is_distinct_contract_and_delivery"])

    def test_thousand_raw_units_produce_ten(self):
        r = microfee_receipt([1000], 100)
        self.assertEqual(r["conditional_per_order_fee_sum_raw"], "10")
        self.assertEqual(r["ideal_rational_fee_if_same_unit"], "10")

    def test_original_model_uses_distinct_synthetic_fraction_units(self):
        c = {
            "id": "conditional-units", "price": 99, "value_if_accepted": 200,
            "seller_cost": 0, "success_ppm": 1000000, "network_cost": 0,
            "independent_check_cost": 0, "operator_cost": 0,
            "buyer_outside": 0, "seller_outside": 0, "time_limit_days": 7,
        }
        mechanism = {"kind": "buyer_escrow", "verifier": "buyer",
                     "fee_bps": 100, "expiry_days": 1, "deployable": True}
        modeled = value(c, mechanism)
        self.assertTrue(modeled["accepted"])
        self.assertEqual(modeled["owner"], Fraction(99, 100))
        self.assertEqual(microfee_receipt([99], 100)["conditional_per_order_fee_sum_raw"], "0")
        # This is a CONDITIONAL unit-mapping discrepancy, not an observed
        # problem with the explicitly synthetic model or a claim of cash.

    def test_bad_values_and_actual_uint256_overflow_refused(self):
        for xs, bps in (([], 100), ([True], 100), ([0], 100),
                        ([-1], 100), ([99], -1), ([99], 251),
                        ([1.0], 100), ([99], True),
                        ([UINT256_MAX + 1], 0),
                        ([UINT256_MAX], 250)):
            with self.subTest(xs=xs, bps=bps):
                with self.assertRaises(PrecisionRefusal):
                    microfee_receipt(xs, bps)

    def test_nonbundleable_total_is_explicit_not_false_revenue(self):
        r = microfee_receipt([UINT256_MAX, 1], 0)
        self.assertIsNone(r["one_bundle_fee_raw_if_representable"])
        self.assertIsNone(r["difference_bundle_minus_independent_raw_if_representable"])
        self.assertEqual(r["conditional_per_order_fee_sum_raw"], "0")


if __name__ == "__main__":
    unittest.main()
