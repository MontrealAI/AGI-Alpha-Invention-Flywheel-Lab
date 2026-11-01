import copy
import unittest
from connected_enterprise.billion036 import (
    OPENING, TARGET, registered_design, preflight, horizon_days, first_passage)
from connected_enterprise.scale import _digest


def tape(changes):
    balance = {'profit': 0, 'revenue': 0, 'recoveryIncome': 0,
               'expenses': 0, 'cash': OPENING, 'collections': 0,
               'expensePaid': 0, 'tailReserve': 0, 'available': OPENING}
    actions = []
    for hour, diff in changes:
        before = copy.deepcopy(balance)
        for key, value in diff.items(): balance[key] += value
        balance['profit'] = balance['revenue']+balance['recoveryIncome']-balance['expenses']
        actions.append({'seq': len(actions), 'day': hour, 'before': before,
                        'after': copy.deepcopy(balance), 'args': {}, 'op': 'cost'})
    return {'config': {'opening': OPENING}, 'actions': actions,
            'actions_sha256': _digest(actions), 'summary': balance}


class HundredThousandChallenge(unittest.TestCase):
    def test_exact_100k_sixty_calendar_months_from_november_2026(self):
        reg = registered_design()
        self.assertEqual(horizon_days('2026-11-01T00:00:00Z'), 1826)
        self.assertEqual(reg['arms'], ['baseline', 'growth'])
        self.assertEqual(len(reg['configs']), 2)
        for config in reg['configs'].values():
            self.assertEqual(config['opening'], OPENING)
            self.assertEqual(config['horizon_days'], 1826)
        pre = preflight(reg)
        self.assertEqual(pre['matched_businesses'], 4)
        for row in pre['cases']:
            self.assertEqual(row['qualification'], 'STRUCTURAL_FIXED_BUYER_BUDGET_BARRIER')
            self.assertLess(row['lifetime_buyer_spending_upper_bound_microUSD'], TARGET)

    def test_design_cannot_silently_replace_capital_or_horizon(self):
        for field, value in [('opening', OPENING+1), ('horizon_days', 1825)]:
            reg = registered_design()
            reg['configs']['central'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'EXACT_100K_AND_60_CALENDAR_MONTHS'):
                preflight(reg)

    def test_cannot_turn_unknown_buyer_demand_into_observed_demand(self):
        reg = registered_design()
        reg['configs']['central']['buyer_budget_multiplier_bps'] = 10**9
        row = next(r for r in preflight(reg)['cases'] if r['case'] == 'central')
        self.assertEqual(row['qualification'], 'NO_CONCLUSION_FROM_BUYER_BUDGET_BOUND')
        self.assertFalse(row['finite_buyer_budget_barrier'])

    def test_full_year_first_passage_with_same_hour_and_corrections(self):
        t = tape([(0, {'expenses': 100}), (8759, {'revenue': TARGET+200}),
                  (8759, {'expenses': 50}), (8760, {'revenue': -300})])
        p = first_passage(t, operating_end_hour=8761, operating_complete=True)
        self.assertEqual(p['first_attainment']['operating_hour_exclusive'], 8760)
        self.assertEqual(p['trailing_365_day_profit_microUSD'], TARGET-150)
        self.assertFalse(p['terminal_above_target'])
        self.assertEqual(p['status'], 'ATTAINED_WITH_AUDIT_PREREQUISITE')

    def test_aged_out_expense_can_create_first_crossing_without_new_sale(self):
        t = tape([(0, {'expenses': 10}), (1, {'revenue': TARGET+9})])
        p = first_passage(t, operating_end_hour=8761, operating_complete=True)
        self.assertEqual(p['first_attainment']['operating_hour_exclusive'], 8761)
        self.assertEqual(p['trailing_365_day_profit_microUSD'], TARGET+9)

    def test_same_hour_reversal_is_not_false_intermediate_attainment(self):
        t = tape([(8759, {'revenue': TARGET+1}), (8759, {'expenses': 3})])
        p = first_passage(t, operating_end_hour=8760, operating_complete=True)
        self.assertIsNone(p['first_attainment'])
        self.assertEqual(p['trailing_365_day_profit_microUSD'], TARGET-2)

    def test_initial_seed_and_reserve_release_are_not_profit(self):
        t = tape([(0, {'tailReserve': 100}), (8759, {'tailReserve': -100})])
        p = first_passage(t, operating_end_hour=8760, operating_complete=True)
        self.assertIsNone(p['first_attainment'])
        self.assertEqual(p['trailing_365_day_profit_microUSD'], 0)

    def test_drain_outside_operating_horizon_cannot_create_success(self):
        t = tape([(0, {'expenses': 5}), (8760, {'revenue': TARGET+6})])
        p = first_passage(t, operating_end_hour=8760, operating_complete=True)
        self.assertIsNone(p['first_attainment'])
        self.assertEqual(p['trailing_365_day_profit_microUSD'], -5)

    def test_incomplete_run_remains_unknown_even_with_large_profit(self):
        t = tape([(1, {'revenue': TARGET*2})])
        p = first_passage(t, operating_end_hour=10000, operating_complete=False)
        self.assertEqual(p['status'], 'INCOMPLETE_NO_ATTAINMENT_VERDICT')
        self.assertIsNone(p['trailing_365_day_profit_microUSD'])

    def test_chain_and_flow_tampering_fail(self):
        t = tape([(0, {'expenses': 5}), (1, {'revenue': 100})])
        t['actions'][1]['before']['profit'] = 555
        t['actions_sha256'] = _digest(t['actions'])
        with self.assertRaisesRegex(ValueError, 'NONCAUSAL_NATIVE_PROFIT_SEQUENCE'):
            first_passage(t, operating_end_hour=8760, operating_complete=True)
        t = tape([(0, {'expenses': 5})]); t['actions'][0]['after']['profit'] = 100
        t['actions_sha256'] = _digest(t['actions']); t['summary'] = t['actions'][0]['after']
        with self.assertRaisesRegex(ValueError, 'PROFIT_NOT_RECONCILED'):
            first_passage(t, operating_end_hour=8760, operating_complete=True)

    def test_read_only_and_protected_hash(self):
        t = tape([(0, {'expenses': 1}), (8759, {'revenue': 10})])
        original = copy.deepcopy(t)
        first_passage(t, operating_end_hour=8760, operating_complete=True)
        self.assertEqual(t, original)
        t['actions'][0]['after']['expenses'] += 1
        with self.assertRaisesRegex(ValueError, 'VALID_NATIVE_ACTIONS_HASH_REQUIRED'):
            first_passage(t, operating_end_hour=8760, operating_complete=True)


if __name__ == '__main__':
    unittest.main()
