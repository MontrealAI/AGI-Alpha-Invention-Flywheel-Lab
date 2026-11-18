import unittest

from rounding_audit import audit, conservative_reasons, rounding_envelope


def contract(**changes):
    base = {
        "model": "GPT-OSS 120B", "dataset": "perf",
        "min_concurrency": 1, "max_ttft_p90_ms": "500",
        "min_tps_per_user": "100", "load_mode": "reported",
        "rate_metric": "reported_tps_per_user",
        "require_point_accuracy": False,
        "require_price": False, "require_access": False,
    }
    return {**base, **changes}


def point(ttft="100.0", tps="100.0", tpot="10.00"):
    return {"ttft_p90_ms": ttft, "tps_per_user": tps,
            "tpot_p90_ms": tpot}


class PrecisionEnvelope(unittest.TestCase):
    def test_trailing_zeros_determine_the_declared_resolution(self):
        self.assertEqual(rounding_envelope("100.0"), (99.95, 100.05))
        self.assertEqual(rounding_envelope("10.00"), (9.995, 10.005))
        self.assertEqual(rounding_envelope("100"), (99.5, 100.5))

    def test_never_assume_exact_rounded_equality(self):
        reasons = conservative_reasons(point(), contract(), 100, 100)
        self.assertIn("first_token_within_display_rounding", reasons)
        self.assertIn("user_rate_within_display_rounding", reasons)

    def test_inverse_metric_uses_worst_case_time_without_float_roundoff(self):
        p = point(ttft="80.0", tpot="10.00")
        c = contract(rate_metric="inverse_p90_tpot")
        self.assertEqual(conservative_reasons(p, c, 100, 100),
                         ["output_token_time_within_display_rounding"])
        self.assertEqual(conservative_reasons(p, c, 100, 99), [])

    def test_clearly_qualifying_point_retains_status(self):
        self.assertEqual(conservative_reasons(
            point(ttft="99.8", tps="100.2"), contract(), 100, 100), [])

    def test_frozen_primary_public_report_stays_supported(self):
        result = audit(contract())
        original = result["original_decision"]
        self.assertEqual(original["decision"], "supported")
        self.assertEqual(original["selected"][0]["concurrency"], 140)
        self.assertEqual(result["conservative_decision"], "supported")
        self.assertEqual(result["conservative_selected"][0]["concurrency"], 140)
        self.assertTrue(result["original_selected_all_conservative"])
        source_rows = {(row["source"], row["run"]) for row in original["eligible"]}
        robust_rows = {(row["source"], row["run"]) for row in result["conservative_selected"]}
        sensitive_rows = {(row["source"], row["run"]) for row in result["display_supported_but_precision_sensitive"]}
        self.assertTrue(robust_rows <= source_rows)
        self.assertTrue(sensitive_rows <= source_rows)
        self.assertFalse(sensitive_rows & robust_rows)

    def test_unavailable_price_remains_unavailable(self):
        result = audit(contract(require_price=True))
        self.assertEqual(result["original_decision"]["decision"], "withheld")
        self.assertEqual(result["conservative_decision"], "withheld")
        self.assertEqual(result["conservative_selected"], [])
        self.assertFalse(result["original_selected_all_conservative"])


if __name__ == "__main__":
    unittest.main()
