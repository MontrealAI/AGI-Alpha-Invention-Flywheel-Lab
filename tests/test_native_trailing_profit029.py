import copy
import unittest
from connected_enterprise.scale import trailing_profit, aggregate_native, _digest, FLOW_FIELDS, STATE_FIELDS


def tape(events):
    s = {k: 0 for k in set(FLOW_FIELDS + STATE_FIELDS)}
    s.update(cash=1000, available=1000, investmentStopped=False)
    rows = []
    for hour, changes in events:
        before = copy.deepcopy(s)
        for k, delta in changes.items(): s[k] += delta
        s['cash'] = 1000 + s['collections'] + s['recoveryIncome'] - s['expensePaid']
        s['profit'] = s['revenue'] + s['recoveryIncome'] - s['expenses']
        rows.append({'seq': len(rows), 'day': hour, 'op': 'cost', 'args': {}, 'before': before, 'after': copy.deepcopy(s)})
    return {'config': {'opening': 1000}, 'actions': rows, 'actions_sha256': _digest(rows), 'summary': s, 'receivables': 0}


class TrailingProfit(unittest.TestCase):
    def test_boundary_setup_and_negative_revision(self):
        t = tape([(0, {'expenses': 10, 'expensePaid': 10}), (1, {'revenue': 100, 'collections': 100}),
                  (8759, {'revenue': -20}), (8760, {'revenue': -30})])
        r = trailing_profit(t, operating_end_hour=8760, operating_complete=True)
        self.assertEqual(r['trailing_365_day_profit_microUSD'], 70)
        self.assertEqual(r['settlement_drain_actions_excluded'], 1)
        r = trailing_profit(t, operating_end_hour=8761, operating_complete=True)
        self.assertEqual(r['trailing_365_day_profit_microUSD'], 50)
        self.assertEqual(r['interval']['start_hour_inclusive'], 1)

    def test_short_horizon_not_year_even_long_drain(self):
        t = tape([(0, {'expenses': 10}), (9000, {'revenue': 100})])
        r = trailing_profit(t, operating_end_hour=24, operating_complete=True)
        self.assertIsNone(r['trailing_365_day_profit_microUSD'])
        self.assertEqual(r['observed_window_profit_microUSD'], -10)

    def test_incomplete_year_unknown(self):
        t = tape([(0, {}), (9000, {'expenses': 5})])
        r = trailing_profit(t, operating_end_hour=10000, operating_complete=False)
        self.assertIsNone(r['trailing_365_day_profit_microUSD'])

    def test_reserve_release_and_seed_not_profit(self):
        t = tape([(0, {'tailReserve': 100}), (8760, {'tailReserve': -100, 'available': 100})])
        r = trailing_profit(t, operating_end_hour=8761, operating_complete=True)
        self.assertEqual(r['trailing_365_day_profit_microUSD'], 0)

    def test_payables_refund_recovery_and_signed_expense(self):
        t = tape([(0, {}), (24, {'revenue': 100}), (25, {'revenue': -100}),
                  (26, {'expenses': 40, 'payables': 40}), (27, {'recoveryIncome': 5}),
                  (28, {'expenses': -3}), (29, {'expensePaid': 20, 'payables': -20})])
        r = trailing_profit(t, operating_end_hour=8760, operating_complete=True)
        self.assertEqual(r['trailing_365_day_profit_microUSD'], -32)
        self.assertEqual(r['event_prefix_max_deviation_microUSD'], 0)
        self.assertEqual(t['summary']['payables'], 20)

    def test_tamper_rejected_and_read_only(self):
        t = tape([(0, {'expenses': 2})]); original = copy.deepcopy(t)
        trailing_profit(t, operating_end_hour=8760, operating_complete=True)
        self.assertEqual(t, original)
        t['actions'][0]['after']['expenses'] += 1
        with self.assertRaises(ValueError): trailing_profit(t, operating_end_hour=8760, operating_complete=True)

    def test_stale_aggregation_does_not_bypass_hash(self):
        t = tape([(0, {'expenses': 2})])
        a = aggregate_native(t)
        t['actions'][0]['after']['expenses'] += 1
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_HASH_MISMATCH'):
            trailing_profit(t, operating_end_hour=8760, operating_complete=True, aggregation=a)

    def test_legacy_partial_config_horizon_unknown(self):
        from tests.test_connected_scale import fixture
        from connected_enterprise.scale import analyze
        for cfg in ({}, {'opening': 1000}):
            result = {'owned_account': {'ledger': fixture()}, 'config': cfg,
                      'complete': True, 'orders': [], 'investments': [], 'costs': []}
            r = analyze(result)
            self.assertEqual(r['terminal_state_microUSD']['profit'], 160)
            self.assertEqual(r['trailing_profit']['qualification'], 'OPERATING_HORIZON_UNAVAILABLE')
            self.assertIsNone(r['trailing_profit']['trailing_365_day_profit_microUSD'])
            self.assertIsNone(r['trailing_profit']['interval'])
            self.assertFalse(r['trailing_profit']['complete_365_day_operating_history'])

    def test_source_inclusion(self):
        from connected_enterprise.finance import SOURCE_PATHS
        self.assertIn('connected_enterprise/scale.py', SOURCE_PATHS)

if __name__ == '__main__': unittest.main()
