import copy
import unittest

from ignition.economics import CATEGORIES, assessment, validate_case


def interval(low, high, **fields):
    return {"low": low, "high": high, "provenance": "assumption",
            "source": "Synthetic arithmetic test input", **fields}


def scenario():
    costs = {k: [interval("0", "0", basis="per_unit")] for k in CATEGORIES}
    costs["search_construction"] = [interval("100.00", "150.00", basis="fixed")]
    costs["support_maintenance"] = [interval("8.30", "10.75", basis="per_unit")]
    costs["opportunity_cost"] = [interval("4.05", "6.25", basis="per_unit")]
    return {"currency": "CAD", "unit": "accepted delivery", "horizon": "single synthetic comparison",
            "costs": costs, "price": interval("27", "32.35"),
            "volume": {"units": 6, "provenance": "assumption", "source": "Synthetic sensitivity test"}}


def assess(case=None, calls=None):
    return assessment({"purpose": "Check delivered bytes", "beneficiary": "Release reviewer",
                       "resources": {"commercial_case": case}}, {"selected": {"alternative": "Conventional SHA-256 and inventory"},
                                                                  "signals": []}, calls or {})


class CommercialAssessmentTests(unittest.TestCase):
    def test_unknown_preserves_usage_and_does_not_report_money(self):
        rec = {"run_id": "r1", "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 2},
               "application_model_calls": 1}
        manual = {"request_sha256": "s2", "status": "reviewed_exchange", "application_model_calls": 0}
        calls = {"completed": [{"receipt": [rec], "response": {"secret": True}}, {"receipt": [manual]}],
                 "failed": [{"receipts": [rec]}, {"elapsed_seconds": 0.3}]}
        report = assess(calls=calls)
        self.assertEqual(report["status"], "unknown")
        self.assertIsNone(report["booked_revenue"])
        self.assertIsNone(report["scenario"])
        self.assertEqual(report["usage"]["recorded_application_model_calls"], 1)
        self.assertEqual(report["usage"]["failed_attempts"], 2)
        self.assertEqual(report["usage"]["tokens"]["input_tokens"]["observed_sum"], 10)
        self.assertEqual(report["usage"]["assisted_exchanges"], 1)
        self.assertIsNone(report["usage"]["human_work_seconds"])
        self.assertNotIn("secret", str(report))
        self.assertEqual(len(report["missing_cost_categories"]), len(CATEGORIES))

    def test_interval_arithmetic_costs_favorable_and_adverse(self):
        report = assess(scenario())
        model = report["scenario"]
        self.assertEqual(report["status"], "bounded_scenario")
        self.assertEqual(model["modeled_total_economic_cost"], {"low": "174.10", "high": "252.00"})
        self.assertEqual(model["projected_gross_revenue"], {"low": "162", "high": "194.10"})
        self.assertEqual(model["modeled_economic_contribution"], {"low": "-90.00", "high": "20.00"})
        self.assertEqual((model["break_even_units"]["favorable"], model["break_even_units"]["adverse"]), (5, 15))
        self.assertIsNone(report["verified_demand"])
        self.assertIsNone(report["funding_received"])

    def test_missing_costs_leave_break_even_unknown_without_hiding_revenue_assumptions(self):
        case = scenario()
        del case["costs"]["retained_obligations"]
        result = assess(case)
        self.assertEqual(result["missing_cost_categories"], ["retained_obligations"])
        self.assertIsNone(result["scenario"]["modeled_total_economic_cost"])
        self.assertIsNone(result["scenario"]["break_even_units"])
        self.assertIsNotNone(result["scenario"]["projected_gross_revenue"])
        del case["price"]
        self.assertIsNone(assess(case)["scenario"]["projected_gross_revenue"])

    def test_zero_and_negative_margin_do_not_create_economic_break_even(self):
        case = scenario()
        case["price"] = interval("12", "17")
        be = assess(case)["scenario"]["break_even_units"]
        self.assertEqual(be["favorable"], 22)
        self.assertIsNone(be["adverse"])
        case["price"] = interval("0", "0")
        self.assertIsNone(assess(case)["scenario"]["break_even_units"]["favorable"])

    def test_malformed_or_unsourced_costs_never_enter_arithmetic(self):
        for mutation in ({"low": 1.5}, {"low": "-0.7"}, {"high": "0"}, {"source": ""},
                         {"provenance": "verified"}, {"low": "1e6"}):
            case = scenario()
            case["costs"]["search_construction"][0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_case(case)
            self.assertEqual(assess(case)["status"], "invalid_case")
        case = scenario()
        case["volume"]["units"] = True
        self.assertEqual(assess(case)["status"], "invalid_case")

    def test_rights_and_multi_party_claims_remain_attributed(self):
        case = scenario()
        case["rights"] = {"claim": "Public inputs only", "provenance": "assumption", "source": "Synthetic rights fixture"}
        case["participants"] = [{"role": "reviewer", "incentive": "usable verification", "outside_option": "self-service",
                                 "provenance": "assumption", "source": "Synthetic participant fixture"}]
        original = copy.deepcopy(case)
        result = assess(case)
        self.assertEqual(result["operator_evidence"]["rights"], case["rights"])
        self.assertEqual(result["participants"][0]["outside_option"], "self-service")
        self.assertEqual(case, original)
