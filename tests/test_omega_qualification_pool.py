"""Adverse constraints and separately implemented ordinary exact control."""
from dataclasses import replace
from fractions import Fraction
import unittest
from unittest.mock import patch

from omega.qualification_pool import Plan, check, construct, fixtures, ordinary, run, validate


class SharedQualificationTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c.id: c for c in fixtures()}
        self.base = self.cases['compatible_pool']
        self.plan = Plan('standard', 1, (('a', 550000), ('b', 400000), ('c', 250000)))

    def test_all_authored_cohorts_match_unrestricted_ordinary_control(self):
        self.assertEqual(len(self.cases), 12)
        for case in self.cases.values():
            with self.subTest(case=case.id):
                self.assertEqual(construct(case), ordinary(case))
        self.assertEqual(sum(construct(c) is not None for c in self.cases.values()), 4)

    def test_known_cooperation_can_enable_without_harness_superiority(self):
        result = construct(self.base)
        self.assertEqual(result.plan, self.plan)
        self.assertEqual(result.expected_supplier_margin_cents, Fraction(269000))
        self.assertEqual(result.success_margin_cents, 300000)
        self.assertEqual(result.failure_margin_cents, -10000)
        self.assertEqual(result.minimum_unrestricted_cash_cents, 190000)
        self.assertIsNone(construct(self.base, allow_pooling=False))
        self.assertEqual(ordinary(self.base), result)

    def test_heterogeneous_acceptance_requires_actual_qualified_scope(self):
        case = self.cases['heterogeneous_precision']
        self.assertIsNone(check(case, self.plan))
        self.assertEqual(construct(case).plan.qualification, 'precision')
        self.assertIsNone(construct(self.cases['unsupported_acceptance']))

    def test_capacity_and_deadline_cannot_be_wished_away(self):
        self.assertIsNone(construct(self.cases['no_validation_capacity']))
        self.assertIsNone(construct(self.cases['qualification_misses_deadline']))
        q = self.base.qualifications[0]
        # Endpoints have capacity, but one interior qualification day does not.
        broken = replace(self.base, available_capacity=(1, 1, 0, 1, 1, 1, 1, 1))
        self.assertIsNone(check(broken, self.plan))
        self.assertIsNone(check(replace(self.base, qualifications=(replace(q, capacity_units=2),)), self.plan))

    def test_future_and_same_day_later_collection_are_not_current_cash(self):
        self.assertIsNone(construct(self.cases['settlement_after_deadline']))
        self.assertIsNone(construct(self.cases['same_day_cash_shortfall']))
        bridge = construct(self.cases['same_day_funded_bridge'])
        self.assertIsNotNone(bridge)
        self.assertEqual(bridge.minimum_unrestricted_cash_cents, 90000)
        just_enough = replace(self.cases['same_day_cash_shortfall'], available_cash_cap_cents=310000)
        self.assertEqual(check(just_enough, self.plan).minimum_unrestricted_cash_cents, 0)
        self.assertIsNone(check(replace(just_enough, available_cash_cap_cents=309999), self.plan))
        # Moving only settlement earlier makes the low-cash case feasible.
        low = self.cases['same_day_cash_shortfall']
        earlier = replace(low, buyers=tuple(replace(b, settlement_day=0) for b in low.buyers))
        self.assertIsNotNone(check(earlier, self.plan))

    def test_full_failure_refund_is_reserved_not_spent_on_construction(self):
        self.assertIsNone(construct(self.cases['full_refund_reserve_unfunded']))
        funded = construct(self.cases['full_refund_funded_bridge'])
        self.assertIsNotNone(funded)
        self.assertEqual(funded.expected_supplier_margin_cents, Fraction(179000))
        self.assertEqual(funded.failure_margin_cents, -910000)
        self.assertEqual(funded.minimum_unrestricted_cash_cents, 90000)

    def test_buyer_outside_option_budget_and_indifference_all_bind(self):
        self.assertIsNone(construct(self.cases['outside_alternative_wins']))
        self.assertIsNone(construct(self.cases['buyer_budget_shortfall']))
        witness = check(self.base, self.plan)
        net = dict(witness.buyer_net_utilities_cents)['a']
        self.assertEqual(net.denominator, 1)
        buyers = (replace(self.base.buyers[0], outside_utility_cents=int(net)),) + self.base.buyers[1:]
        self.assertIsNone(check(replace(self.base, buyers=buyers), self.plan))
        # Fees fit alone, but adoption plus fee exceeds the actual buyer budget.
        buyers = (replace(self.base.buyers[0], budget_cents=550000),) + self.base.buyers[1:]
        self.assertIsNone(check(replace(self.base, buyers=buyers), self.plan))

    def test_missing_reuse_permission_and_failure_certain_are_not_free_success(self):
        buyers = (replace(self.base.buyers[0], permits_shared_qualification=False),) + self.base.buyers[1:]
        self.assertIsNone(check(replace(self.base, buyers=buyers), self.plan))
        failed = replace(self.base, success_probability=Fraction(0))
        self.assertIsNone(construct(failed))
        self.assertIsNone(ordinary(failed))

    def test_unfunded_threshold_or_duplicate_buyer_cannot_create_pledges(self):
        self.assertIsNone(check(self.base, Plan('standard', 1, (('a', 550000),))))
        self.assertIsNone(check(self.base, Plan('standard', 1, (('a', 550000), ('a', 550000)))))
        self.assertIsNone(check(self.base, Plan('standard', 1, (('unknown', 550000),))))
        self.assertIsNone(check(self.base, Plan('standard', 1, (('a', True),))))
        self.assertIsNone(check(self.base, replace(self.plan, start_day=True)))

    def test_ordinary_control_does_not_call_candidate_check_or_eligibility(self):
        expected = ordinary(self.base)
        with patch('omega.qualification_pool.check', side_effect=AssertionError('candidate called')):
            with patch('omega.qualification_pool._eligible', side_effect=AssertionError('candidate eligibility called')):
                self.assertEqual(ordinary(self.base), expected)

    def test_cost_order_and_input_permutations_preserve_result(self):
        q = self.base.qualifications[0]
        reordered = replace(self.base, buyers=tuple(reversed(self.base.buyers)),
                            fee_menu_cents=tuple(reversed(self.base.fee_menu_cents)),
                            qualifications=(replace(q, costs=tuple(reversed(q.costs))),))
        self.assertEqual(construct(reordered), construct(self.base))
        self.assertEqual(ordinary(reordered), ordinary(self.base))
        # Two same-day costs are both due before that day's settlement.
        split = replace(q, costs=((0, 'a', 100000), (0, 'b', 200000)) + q.costs[1:])
        case = replace(self.cases['same_day_cash_shortfall'], qualifications=(split,))
        self.assertIsNone(construct(case))
        self.assertIsNone(ordinary(case))

    def test_rejects_inexact_or_ambiguous_inputs(self):
        for case in (replace(self.base, success_probability=0.9),
                     replace(self.base, available_cash_cap_cents=True),
                     replace(self.base, failure_refund_fraction=Fraction(2)),
                     replace(self.base, buyers=(self.base.buyers[0],) * 2)):
            with self.assertRaises(ValueError):
                validate(case)

    def test_receipt_has_no_accounts_actual_demand_or_physical_claim(self):
        receipt = run()
        self.assertEqual(receipt['ordinary_ties'], 12)
        self.assertEqual(receipt['native_postings'], 0)
        self.assertEqual(receipt['new_funded_accounts'], 0)
        self.assertFalse(receipt['observed_demand'])
        self.assertFalse(receipt['physical_acceptance'])
        self.assertEqual(receipt['verdict'], 'CONDITIONAL_SHARED_FEASIBILITY_NO_HARNESS_METHOD_ADVANTAGE')


if __name__ == '__main__':
    unittest.main()
