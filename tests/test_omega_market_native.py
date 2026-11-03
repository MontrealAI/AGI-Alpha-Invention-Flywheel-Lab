"""Actual source-bound native commerce, interruption and independent replay."""
import copy
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import canonical, digest, strict_json
from omega import market, market_native


class MarketNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='omega-market-development-')
        cls.output = Path(cls.tmp.name) / 'run'
        cases = (market.registered_cases(development=True)[2],)
        cls.registration = market_native.register(cls.output, development=True,
                                                  modes=('nonentry', 'simple'), cases=cases)
        cls.checkpoint = market_native.operate(cls.output, max_steps=1)
        cls.first = {a['id']: strict_json((cls.output / 'accounts' / a['id'] / 'public.json').read_bytes())
                     for a in cls.registration['arms']}
        cls.result = market_native.operate(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sales_are_native_and_not_structurally_disabled(self):
        sold = next(r for r in self.result['accounts'] if r['policy'] == 'simple')
        self.assertGreater(sold['outcomes']['released'], 0)
        summary = sold['native_summary_microUSD']
        self.assertGreater(summary['collections'], 0)
        self.assertEqual(summary['collections'], summary['revenue'])
        self.assertEqual(summary['profit'], summary['revenue'] - summary['expenses'])
        self.assertEqual(summary['payables'], 0)
        self.assertGreater(summary['tailReserve'], 0)
        self.assertFalse(sold['claims']['three_billion_primary_objective_established'])

    def test_nonentry_is_available_with_no_forced_costs(self):
        row = next(r for r in self.result['accounts'] if r['policy'] == 'nonentry')
        s = row['native_summary_microUSD']
        self.assertEqual(s['profit'], 0)
        self.assertEqual(s['expenses'], 0)
        self.assertEqual(s['cash'], 100000 * 1_000_000)
        self.assertEqual(row['founder_minutes'], 0)

    def test_resume_preserves_exact_history_identity_and_native_replay(self):
        self.assertFalse(self.checkpoint['complete'])
        self.assertTrue(self.result['complete'])
        for arm in self.registration['arms']:
            directory = self.output / 'accounts' / arm['id']
            final = strict_json((directory / 'public.json').read_bytes())
            prior = self.first[arm['id']]
            self.assertEqual(final['ledger']['config'], prior['ledger']['config'])
            self.assertEqual(final['ledger']['actions'][:len(prior['ledger']['actions'])], prior['ledger']['actions'])
        self.assertTrue(market_native.audit(self.output)['accepted'])

    def test_destination_cannot_reset_or_copy_an_opening(self):
        with self.assertRaises(FileExistsError):
            market_native.register(self.output, development=True)

    def test_repeated_operation_does_not_repeat_money(self):
        before = {a['id']: (self.output / 'accounts' / a['id'] / 'public.json').read_bytes()
                  for a in self.registration['arms']}
        market_native.operate(self.output)
        after = {a['id']: (self.output / 'accounts' / a['id'] / 'public.json').read_bytes()
                 for a in self.registration['arms']}
        self.assertEqual(before, after)

    def test_changed_report_cannot_claim_untested_profit(self):
        path = self.output / 'result.json'; original = path.read_bytes()
        try:
            value = strict_json(original)
            value['accounts'][0]['modeled_complete_economic_profit_cents'] = 300_000_000_000
            path.write_bytes(canonical(value))
            with self.assertRaisesRegex(ValueError, 'REPORT_CHANGED'):
                market_native.audit(self.output)
        finally:
            path.write_bytes(original)

    def test_policy_and_manifest_remain_bound_before_reopen(self):
        arm = self.registration['arms'][-1]
        path = self.output / 'accounts' / arm['id'] / 'plan.json'; original = path.read_bytes()
        try:
            value = strict_json(original)
            value['capital_cents'] += 1
            path.write_bytes(canonical(value))
            with self.assertRaisesRegex(ValueError, 'ARM_CHANGED'):
                market_native.operate(self.output)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
