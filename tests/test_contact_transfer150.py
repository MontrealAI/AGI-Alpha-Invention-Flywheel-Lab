"""Adversarial standard-library tests for declared numeric measurement bounds."""
import copy
from decimal import Decimal
import json
import unittest

from research.contact_transfer150.metrology import (
    SCHEMA, NOMINAL, demo, measure, parse, source_model_demo, decimal_text,
)


class TestContactTransfer150(unittest.TestCase):
    def sample(self, epsilon="0"):
        return source_model_demo(Decimal(epsilon))

    def assert_rejected(self, payload):
        with self.assertRaises(ValueError):
            measure(payload)

    def test_demo_exactly_declared(self):
        d = demo()
        self.assertEqual(d["decision"], "PHYSICAL_TRANSFER_AND_ERROR_CALIBRATION_REQUIRED_NO_BID_NO_DEPLOY")
        self.assertFalse(d["physical_data_acquired"])
        self.assertFalse(d["complete_comparator_or_commerce_proven"])

    def test_source_nominal_only_not_real(self):
        r = measure(self.sample())
        self.assertEqual(r["declared_input_scope"], "SOURCE_MODEL_DEMO")
        self.assertFalse(r["physical_transfer_verified"])
        self.assertFalse(r["error_model_independently_validated"])
        self.assertFalse(r["commercial_customer_or_revenue"])
        self.assertTrue(Decimal(r["nominal_change"]) > Decimal(".1721"))

    def test_low_error_conditional_pass(self):
        self.assertEqual(measure(self.sample(".02"))["numeric_verdict"], "SUFFICIENT_WITHIN_DECLARED_BOUNDS")

    def test_high_error_conditional_hold(self):
        self.assertEqual(measure(self.sample(".04"))["numeric_verdict"], "HOLD_DECLARED_BOUNDS_ALLOW_FAILURE")

    def test_frozen_threshold_bracket(self):
        lo, hi = map(Decimal, demo()["symmetric_relative_force_error_threshold_bracket"])
        self.assertLess(hi - lo, Decimal("1e-18"))
        self.assertTrue(Decimal(".0279") < lo < hi < Decimal(".0281"))

    def test_monotone_widening(self):
        a, b = measure(self.sample(".01")), measure(self.sample(".03"))
        self.assertGreater(Decimal(a["lower_change"]), Decimal(b["lower_change"]))
        self.assertLess(Decimal(a["upper_change"]), Decimal(b["upper_change"]))

    def test_exact_threshold_equality_passes(self):
        d = self.sample()
        d["states"][0]["static_N"] = "1"
        d["states"][0]["dynamic_N"] = "1"
        d["states"][1]["static_N"] = "1.05"
        d["states"][1]["dynamic_N"] = "1"
        self.assertEqual(measure(d)["numeric_verdict"], "SUFFICIENT_WITHIN_DECLARED_BOUNDS")
        d["states"][1]["static_N"] = "1.049999"
        self.assertEqual(measure(d)["numeric_verdict"], "HOLD_DECLARED_BOUNDS_ALLOW_FAILURE")

    def test_nonpositive_force_interval(self):
        d = self.sample()
        d["states"][0]["dynamic_error_N"] = d["states"][0]["dynamic_N"]
        self.assert_rejected(d)
        d["states"][0]["dynamic_error_N"] = "0"
        d["states"][0]["static_error_N"] = d["states"][0]["static_N"]
        self.assert_rejected(d)

    def test_zero_dynamic_rejected(self):
        d = self.sample()
        d["states"][0]["dynamic_N"] = "0"
        self.assert_rejected(d)

    def test_negative_error_rejected(self):
        d = self.sample()
        d["states"][0]["static_error_N"] = "-0.01"
        self.assert_rejected(d)

    def test_nonfinite_rejected(self):
        for s in ("NaN", "Infinity", "-Infinity", "1e1000"):
            d = self.sample()
            d["states"][0]["static_N"] = s
            self.assert_rejected(d)

    def test_number_not_decimal_string_rejected(self):
        d = self.sample()
        d["states"][0]["dynamic_N"] = .1
        self.assert_rejected(d)

    def test_load_order_rejected(self):
        d = self.sample()
        d["states"][0]["indentation_mm"], d["states"][1]["indentation_mm"] = (
            d["states"][1]["indentation_mm"], d["states"][0]["indentation_mm"]
        )
        self.assert_rejected(d)

    def test_missing_fields_rejected(self):
        d = self.sample()
        del d["states"][1]["static_error_N"]
        self.assert_rejected(d)
        d = self.sample()
        d["unregistered_override"] = True
        self.assert_rejected(d)

    def test_wrong_unit_or_velocity(self):
        d = self.sample()
        d["force_unit"] = "kN"
        self.assert_rejected(d)
        d = self.sample()
        d["velocity_mm_s"] = "0.2"
        self.assert_rejected(d)

    def test_missing_or_unsupported_provenance(self):
        d = self.sample()
        d["source_declaration"] = " "
        self.assert_rejected(d)
        d = self.sample()
        d["provenance"] = ""
        self.assert_rejected(d)
        d = self.sample()
        d["scope"] = "PHYSICAL_VERIFIED"
        self.assert_rejected(d)

    def test_external_label_still_unverified(self):
        d = self.sample()
        d["scope"] = "EXTERNAL_DECLARED_UNVERIFIED"
        r = measure(d)
        self.assertFalse(r["error_model_independently_validated"])
        self.assertFalse(r["physical_transfer_verified"])

    def test_json_duplicate_and_nonfinite_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
            parse(b'{"schema":1,"schema":2}')
        with self.assertRaisesRegex(ValueError, "NONFINITE_JSON"):
            parse(b'{"a":NaN}')

    def test_bounded_json(self):
        with self.assertRaises(ValueError):
            parse(b" " * 65537)

    def test_bounded_numeric_strings(self):
        with self.assertRaises(ValueError):
            decimal_text("9999999999999999999999999999999999999999999999")
        with self.assertRaises(ValueError):
            decimal_text("1e10")

    def test_declared_interval_not_physical_certificate(self):
        r = measure(self.sample(".02"))
        self.assertIn("Conditional interval arithmetic", r["interpretation"])
        self.assertFalse(r["device_safety_or_beneficiary_acceptance"])
        self.assertEqual(r["threshold"], "0.05")

    def test_demo_uses_fixed_source_model(self):
        d = self.sample()
        self.assertEqual(len(d["states"]), len(NOMINAL))
        self.assertEqual([x["indentation_mm"] for x in d["states"]], ["0.01", "0.10"])
        self.assertEqual(d["schema"], SCHEMA)

    def test_any_static_or_dynamic_error_widens(self):
        base = self.sample()
        trial = copy.deepcopy(base)
        trial["states"][1]["dynamic_error_N"] = "0.001"
        self.assertLess(Decimal(measure(trial)["lower_change"]), Decimal(measure(base)["lower_change"]))
        trial = copy.deepcopy(base)
        trial["states"][0]["static_error_N"] = "0.001"
        self.assertLess(Decimal(measure(trial)["lower_change"]), Decimal(measure(base)["lower_change"]))


if __name__ == "__main__":
    unittest.main()
