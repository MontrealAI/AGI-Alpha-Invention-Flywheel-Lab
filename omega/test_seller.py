"""Regressions for voluntary demand, honest non-sales and native cost conservation."""
import json
from pathlib import Path
import tempfile
import unittest

from omega.seller import (BASELINE_VALUES, END_HOUR, MICRO, OFFERS, OPENING,
                          OPTIMISTIC_VALUES, cost_schedule, replay_audit, run,
                          voluntary_choice, webinar_sessions)


class ChoiceTests(unittest.TestCase):
    def test_free_incumbent_can_dominate(self):
        self.assertEqual(voluntary_choice(BASELINE_VALUES)['choice'], 'self_service_incumbent')

    def test_optimistic_preference_is_not_consent(self):
        choice = voluntary_choice(OPTIMISTIC_VALUES)
        self.assertEqual(choice['choice'], 'self_hosted')
        self.assertFalse(choice['consent'])

    def test_no_purchase_and_outside_options_required(self):
        self.assertEqual(voluntary_choice({name: 0 for name in OFFERS})['choice'], 'no_purchase')
        with self.assertRaises(ValueError):
            voluntary_choice({'self_hosted': 999})
        with self.assertRaises(ValueError):
            voluntary_choice(BASELINE_VALUES, unavailable=['no_purchase'])

    def test_capacity_is_per_session_not_universal_cap(self):
        self.assertEqual(webinar_sessions(0), 0)
        self.assertEqual(webinar_sessions(500), 1)
        self.assertEqual(webinar_sessions(501), 2)
        self.assertEqual(webinar_sessions(1_000_000), 2000)
        with self.assertRaises(ValueError):
            webinar_sessions(True)


class NativeSellerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='omega-seller-tests-')
        cls.output = Path(cls.tmp.name) / 'fresh'
        cls.result = run(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_native_expense_conservation_full_registered_year(self):
        result = self.result
        expense = sum(r['microUSD'] for r in cost_schedule())
        summary = result['native_summary_microUSD']
        self.assertTrue(result['native_audit']['accepted'])
        self.assertEqual(summary['cash'], OPENING - expense)
        self.assertEqual(summary['expenses'], expense)
        self.assertEqual(summary['profit'], -expense)
        self.assertEqual(summary['collections'], 0)
        annual = result['native_trailing_profit']
        self.assertEqual(annual['trailing_365_day_profit_microUSD'], -expense)
        self.assertEqual(annual['interval']['end_hour_exclusive'], END_HOUR)
        self.assertEqual(result['completed_operating_days'], 365)
        self.assertIsNone(result['actual_complete_cost_profit_microUSD'])
        self.assertEqual(result['modeled_profit_after_founder_opportunity_before_unknown_taxes_microUSD'],
                         -expense - 40_000 * MICRO)
        self.assertTrue(replay_audit(self.output)['accepted'])

    def test_existing_account_never_reset(self):
        before = (self.output / 'native-public-export.json').read_bytes()
        with self.assertRaises(FileExistsError):
            run(self.output)
        self.assertEqual(before, (self.output / 'native-public-export.json').read_bytes())

    def test_every_headline_and_nested_claim_tamper_rejected(self):
        path = self.output / 'result.json'
        original = path.read_bytes()
        mutations = [
            (('native_product_sales',), 10_000_000),
            (('native_product_revenue_microUSD',), 3_000_000_000 * MICRO),
            (('actual_complete_cost_profit_microUSD',), 3_000_000_000 * MICRO),
            (('modeled_profit_after_founder_opportunity_before_unknown_taxes_microUSD',), 3_000_000_000 * MICRO),
            (('native_audit', 'scope'), 'LIVE_COMMERCE_CERTIFIED'),
            (('native_audit', 'accepted'), False),
            (('completed_operating_days',), 1),
            (('scope',), 'LIVE_COMMERCE'),
            (('complete_cost_status',), 'COMPLETE'),
            (('preference_scenarios', 'optimistic_hypothetical_opt_in', 'consent'), True),
            (('preference_scenarios', 'free_incumbent_baseline', 'choice'), 'self_hosted'),
            (('tax_sensitivity', 'taxable_profit_assumed_microUSD'), 3_000_000_000 * MICRO),
            (('tax_sensitivity', 'rates_bps'), [0]),
            (('limits',), []),
            (('native_product_sales',), False),  # reject bool/int equality tricks
            (('invented_headline',), 'global optimum achieved'),
        ]
        try:
            for keys, value in mutations:
                with self.subTest(field='.'.join(keys)):
                    changed = json.loads(original)
                    target = changed
                    for key in keys[:-1]:
                        target = target[key]
                    target[keys[-1]] = value
                    path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, 'SELLER_REPORTED_RESULT_CHANGED'):
                        replay_audit(self.output)
        finally:
            path.write_bytes(original)

    def test_rehashed_registration_does_not_change_declared_policy(self):
        from commercial.ledger import digest
        path = self.output / 'registration.json'
        report_path = self.output / 'result.json'
        original, original_report = path.read_bytes(), report_path.read_bytes()
        try:
            changed = json.loads(original)
            changed['actual_complete_cost_profit_microUSD'] = 3_000_000_000 * MICRO
            report = json.loads(original_report)
            report['registration_sha256'] = digest(changed)
            path.write_text(json.dumps(changed))
            report_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'SELLER_REGISTRATION_CHANGED'):
                replay_audit(self.output)
        finally:
            path.write_bytes(original)
            report_path.write_bytes(original_report)

    def test_policy_registration_tamper_rejected(self):
        path = self.output / 'registration.json'
        original = path.read_bytes()
        try:
            registration = json.loads(original)
            registration['opening_microUSD'] += 1
            path.write_text(json.dumps(registration))
            with self.assertRaisesRegex(ValueError, 'SELLER_REGISTRATION_CHANGED'):
                replay_audit(self.output)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
