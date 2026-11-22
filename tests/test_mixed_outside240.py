"""Independent, adversarial MIXED-OUTSIDE240 preregistered regressions."""
from __future__ import annotations

from itertools import product
import math
import unittest

from enterprise.pricing import optimize_bundle, utilities
from enterprise.mixed_bundle240 import (
    VALUE_FACTORS, PRICE_FACTORS, frozen_case, mixed_choice_probability,
    optimize_mixed_bundle, run_frozen,
)


class MixedOutsideIndependentTests(unittest.TestCase):
    def test_exact_frozen_hypothesis_versus_legacy_homogeneous_selection(self):
        receipt = run_frozen()
        self.assertTrue(receipt["buyer_choice_set_falsification"])
        self.assertGreater(receipt["legacy_homogeneous_modeled_contribution"], 0)
        self.assertGreater(receipt["legacy_homogeneous_quote"], 0)
        self.assertEqual(receipt["mixed_decision"], "NO_BID_NONPOSITIVE_COMPLETE_CONTRIBUTION")
        self.assertEqual(receipt["mixed_best_rejected_attempt"]["win_probability"], 0)
        self.assertEqual(receipt["mixed_best_rejected_attempt"]["unconditional_attempt_acquisition_coordination_cost"], 45)
        self.assertEqual(receipt["observed_paid_revenue_usd"], 0)
        self.assertIsNone(receipt["native_profit_usd"])

    def test_mathematical_mixed_outside_is_never_weaker_than_homogeneous(self):
        case = frozen_case()
        for factor in PRICE_FACTORS:
            for value in VALUE_FACTORS:
                rows = [utilities(p["anchor_usd"] * value, q["price"] * factor,
                                  q["rival"]["price"], p, case["regime"])
                        for p, q in zip(case["publics"], case["quotes"])]
                best_homogeneous = max(sum(row[j] for row in rows) for j in range(5))
                best_mixed = sum(max(row) for row in rows)
                self.assertGreaterEqual(best_mixed + 1e-12, best_homogeneous)
                # Explicit strong outside witness: rival A + self-service B.
                if factor == .70 and value == 2.1:
                    ours = sum(r[0] for r in rows) + 5
                    self.assertGreater(ours, best_homogeneous)
                    self.assertLess(ours, best_mixed)

    def test_factorized_logit_equals_independent_full_cartesian_enumeration(self):
        for rows, b, temperature in (
            ([[2., 1., 0., -1., 0.], [0., 2., -1., 1., 0.]], 3.0, .75),
            ([[1., 2., 0., -3., 0.], [2., -3., 1., 0., 0.],
              [3., -1., 0., 2., 0.]], 3.25, 1.5),
            ([[-90., -10., 0., -100., 0.], [100., 20., -8., -2., 0.]], -32., 1.5),
        ):
            weight = math.exp(b / temperature)
            outside = sum(math.exp(sum(combo) / temperature)
                          for combo in product(*rows))
            oracle = weight / (weight + outside)
            actual = mixed_choice_probability(rows, b, "logit", temperature)
            self.assertAlmostEqual(actual, oracle, places=12)

    def test_finite_deterministic_utility_vs_independent_cartesian_oracle(self):
        rows = [[-5., 4., 0., 3., 0.], [2., -1., 6., 0., 0.]]
        outside = max(map(sum, product(*rows)))
        self.assertEqual(outside, 10.)
        self.assertEqual(mixed_choice_probability(rows, 9.9, "utility", 0), 0.)
        self.assertEqual(mixed_choice_probability(rows, 10., "utility", 0), 1.)

    def test_conservative_shared_friction_and_per_component_fees_are_order_invariant(self):
        case = frozen_case()
        case["publics"][0].update(friction_usd=7, onboarding_cost_usd=3,
                                  payment_fraction=.01, payment_fixed_usd=2)
        case["publics"][1].update(friction_usd=2, onboarding_cost_usd=5,
                                  payment_fraction=.09, payment_fixed_usd=1)
        first = optimize_mixed_bundle(case["publics"], case["quotes"], case["regime"], "logit")
        reverse = optimize_mixed_bundle(case["publics"][::-1], case["quotes"][::-1], case["regime"], "logit")
        self.assertEqual(first["decision"], reverse["decision"])
        self.assertEqual(first["total_price"], reverse["total_price"])
        for a, b in zip(first["candidate_curve"], reverse["candidate_curve"]):
            self.assertAlmostEqual(a["expected_immediate_contribution_per_opportunity"],
                                   b["expected_immediate_contribution_per_opportunity"], places=10)

    def test_high_unconditional_cost_can_trigger_genuine_zero_cost_no_bid(self):
        case = frozen_case()
        result = optimize_mixed_bundle(case["publics"], case["quotes"], case["regime"], "utility")
        self.assertEqual(result["decision"], "NO_BID_NONPOSITIVE_COMPLETE_CONTRIBUTION")
        self.assertEqual(result["expected_immediate_contribution_per_opportunity"], 0)
        self.assertIsNone(result["total_price"])
        self.assertEqual(len(result["candidate_curve"]), 7)
        self.assertTrue(all(c["expected_immediate_contribution_per_opportunity"] < 0
                            for c in result["candidate_curve"]))
        self.assertEqual(result["native_financial_authority"], [])

    def test_bundle_discount_not_smuggled_into_unbundled_outside_price(self):
        # Independent test-only perturbation, NOT a reroll of the frozen
        # observational experiment. A public standalone price remains $50,
        # even if the complete-bundle search considers a 30% discount.
        case = frozen_case()
        case["quotes"][0]["rival"]["price"] = 25
        priced = optimize_mixed_bundle(case["publics"], case["quotes"],
                                      case["regime"], "utility")
        searched = priced["candidate_curve"][0]
        self.assertEqual(searched["factor"], .70)
        # At this rival price, properly priced standalone alternatives do not
        # crowd out the discounted bundle; incorrectly discounting standalone
        # items would change this result. No buyer actually purchased it.
        self.assertAlmostEqual(searched["conditional_choice_probability_on_exposure"], 1.)
        self.assertGreater(searched["expected_immediate_contribution_per_opportunity"], 0)
        self.assertEqual(priced["native_financial_authority"], [])

    def test_default_source_regression_is_unmodified(self):
        case = frozen_case()
        before = optimize_bundle(case["publics"], case["quotes"], case["regime"], "utility")
        optimize_mixed_bundle(case["publics"], case["quotes"], case["regime"], "utility")
        after = optimize_bundle(case["publics"], case["quotes"], case["regime"], "utility")
        self.assertEqual(before, after)

    def test_reject_unregistered_buyer_and_unsafe_probabilities(self):
        case = frozen_case()
        for field, bad in (("collection_probability", 1.1), ("arrival_probability", -1),
                           ("quote_cost_usd", float("nan")),
                           ("supplier_outage_probability", True)):
            with self.subTest(field=field):
                modified = {**case["regime"], field: bad}
                with self.assertRaises(ValueError):
                    optimize_mixed_bundle(case["publics"], case["quotes"], modified, "utility")
        with self.assertRaises(ValueError):
            optimize_mixed_bundle(case["publics"], case["quotes"], case["regime"], "unknown")
        with self.assertRaises(ValueError):
            optimize_mixed_bundle(case["publics"][:1], case["quotes"][:1], case["regime"], "utility")
        with self.assertRaises(ValueError):
            mixed_choice_probability([[1.]*5,[1.]*5], 1., "logit", 0.)
        with self.assertRaises(ValueError):
            mixed_choice_probability([[1.,2.],[1.]*5], 1., "utility", 1.)

    def test_hypothetical_price_not_authority_to_trade(self):
        case = frozen_case()
        case["publics"] = [dict(x, autonomous_cost_usd=0) for x in case["publics"]]
        case["regime"]["quote_cost_usd"] = 0
        conditional = optimize_mixed_bundle(case["publics"], case["quotes"], case["regime"], "logit")
        self.assertEqual(conditional["native_financial_authority"], [])
        self.assertIn(conditional["decision"], (
            "CONDITIONAL_AUTHORED_GAME_QUOTE_ONLY",
            "NO_BID_NONPOSITIVE_COMPLETE_CONTRIBUTION"))


if __name__ == "__main__":
    unittest.main()
