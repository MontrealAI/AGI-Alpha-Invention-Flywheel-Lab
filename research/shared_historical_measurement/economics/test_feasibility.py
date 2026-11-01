"""Authored dimensionless unit tests; numbers are NOT empirical prices or buyers."""
import math
import unittest
from feasibility import Requester, COST_COMPONENTS, complete_cost, funding_region, comparative_region


def costs(total):
    return {k: total if k == 'feature_execution' else 0 for k in COST_COMPONENTS}


class FundingTests(unittest.TestCase):
    def test_unknown_demand_is_unknown(self):
        self.assertEqual(funding_region([Requester('unknown', None, None, None)], costs(1))['status'], 'unknown')

    def test_unknown_cost_cannot_be_ignored(self):
        c = costs(1); c.pop('model_work')
        result = funding_region([Requester('fixture', 10, 10, 0)], c)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['unpriced_cost_components'], ['model_work'])

    def test_budget_and_outside_option_both_bind(self):
        self.assertEqual(Requester('fixture', 10, 3, 2).cap(), 3)
        self.assertEqual(Requester('fixture', 10, 30, 8).cap(), 2)

    def test_leakage_equivalent_free_copy(self):
        self.assertEqual(Requester('fixture', 10, 10, 10).cap(), 0)
        self.assertEqual(funding_region([Requester('fixture', 10, 10, 10)], costs(1))['status'], 'infeasible')

    def test_cheap_rival(self):
        self.assertEqual(Requester('fixture', 10, 10, 9.5).cap(), 0.5)

    def test_no_demand(self):
        self.assertEqual(funding_region([], costs(1))['status'], 'infeasible')
        self.assertEqual(Requester('fixture', 0, 10, 0).cap(), 0)

    def test_boundary_weak_participation_not_profit(self):
        r = funding_region([Requester('fixture', 2, 2, 0)], costs(2), True)
        self.assertEqual(r['status'], 'conditionally_feasible')
        self.assertFalse(r['implementable_transaction_established'])

    def test_nonnegative_overhead_cannot_beat_competent_sharing(self):
        for shared in (0, 1, 3):
            for overhead in (0, 1, 10):
                for cap in (0, 1, 2, 4, 20):
                    r = comparative_region(9, shared, shared+overhead, cap)
                    self.assertFalse(r['commissioning_opens_region_vs_ordinary_shared'])

    def test_ordinary_sharing_can_open_only_separate_comparison(self):
        r = comparative_region(5, 3, 4, 3.5)
        self.assertTrue(r['sharing_opens_region_vs_separate'])
        self.assertFalse(r['commissioning_cost_recoverable'])

    def test_outside_option_dominates_even_free_delivery(self):
        r = funding_region([Requester('fixture', 1, 2, 3)], costs(0))
        self.assertEqual(r['status'], 'infeasible')
        self.assertEqual(r['requesters_rejecting_even_free_full_allocation'], ['fixture'])

    def test_identity_and_input_validation(self):
        with self.assertRaises(ValueError):
            funding_region([Requester('x', 1, 1, 0)]*2, costs(1))
        for value in (-1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                Requester('fixture', value, 1, 0).cap()
        with self.assertRaises(ValueError):
            complete_cost({'invented': 1})


if __name__ == '__main__':
    unittest.main()
