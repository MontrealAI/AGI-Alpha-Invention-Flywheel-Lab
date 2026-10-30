import copy
import hashlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from . import run as c


class CommerceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifact = self.root / 'artifact.json'
        self.receipt = self.root / 'receipt.json'
        self.verifier = self.root / 'verifier.py'
        self.protocol = self.root / 'protocol.json'
        self.artifact.write_text('{"engineering_test_fixture":true,"plans":[1,2]}\n')
        self.verifier.write_text('ENGINEERING_FIXTURE = True\n')
        self.protocol.write_text('{"scope":"test-only"}\n')
        self.receipt_value = {'schema': 'agi-alpha/next009-delivery-acceptance/v1', 'accepted': True, 'artifact_sha256': self.hash(self.artifact), 'verifier_source_sha256': self.hash(self.verifier), 'protocol_sha256': self.hash(self.protocol), 'scope': 'model-based-water-observation-plan', 'engineering_fixture_only': True}
        self.receipt.write_text(json.dumps(self.receipt_value) + '\n')
        self.expected = {'artifact': self.hash(self.artifact), 'receipt': self.hash(self.receipt), 'verifier': self.hash(self.verifier), 'protocol': self.hash(self.protocol)}
        self.policy, _ = c.json_file(c.HERE / 'policy.json')

    def tearDown(self):
        self.temp.cleanup()

    def hash(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def execute(self):
        return c.run(self.artifact, self.receipt, self.verifier, self.protocol, self.expected, self.root / 'output')

    def test_existing_native_exchange_adverse_paths_bound_to_bytes(self):
        report = self.execute()
        native = report['native_exchange_mechanism']
        self.assertTrue(native['all_checks_passed'])
        self.assertGreaterEqual(len(native['checks']), 13)
        before = native['snapshots']['ideal_provider_before_clustered_reversal']
        self.assertEqual(len(before['trades']), 20)
        self.assertEqual(sum(t['state'] == 'released' for t in before['trades']), 18)
        self.assertGreater(before['snapshot_microUSD']['profit'], 0)
        self.assertGreater(before['snapshot_microUSD']['unrestrictedEarned'], 0)
        self.assertEqual(native['snapshots']['clustered_reversal']['snapshot_microUSD']['unrestrictedEarned'], 0)
        self.assertEqual(native['snapshots']['reversible_route_refused']['snapshot_microUSD']['revenue'], 0)
        self.assertEqual((self.root / 'output' / 'DELIVERED.json').read_bytes(), c.canonical(json.loads(self.artifact.read_text())))
        self.assertNotEqual(report['binding']['artifact'], report['binding']['artifact_canonical_sha256'])
        self.assertEqual(report['claims']['qualified_unrestricted_simulated_earnings_cad'], '0.00')
        self.assertEqual(native['currency'], 'simulated-microUSD')
        self.assertIsNone(native['native_provider_cost'])
        self.assertEqual(native['successful_investment_reservations'], 0)

    def test_projection_preserves_losses_delays_and_full_cohort_costs(self):
        results = {s['name']: c.card_projection(self.policy, s) for s in self.policy['scenarios']}
        base = results['conditional_base']
        stress = results['correlated_low_demand_overstatement_warranty']
        self.assertEqual(base['counts']['admitted_and_costed'], 20)
        self.assertEqual(base['counts']['modeled_paid'], 16)
        self.assertEqual(base['cashflow_cad']['accounting_profit_within_authored_scenario'], '2057.81')
        self.assertEqual(base['cashflow_cad']['retained_principal_plus_dispute_reserve'], '3710.00')
        self.assertEqual(base['cashflow_cad']['processing_fees_retained_on_refunds'], '120.80')
        self.assertEqual(base['cashflow_cad']['dispute_fees'], '15.00')
        self.assertEqual(stress['cashflow_cad']['accounting_profit_within_authored_scenario'], '-2388.61')
        self.assertLess(Decimal(results['zero_demand']['cashflow_cad']['accounting_profit_within_authored_scenario']), 0)
        for name in ('all_remaining_payouts_delayed', 'positive_profit_liquidity_deferral'):
            self.assertGreater(Decimal(results[name]['cashflow_cad']['accounting_profit_within_authored_scenario']), 0)
            self.assertEqual(results[name]['cashflow_cad']['conditional_earned_cash_after_equity_backing'], '0.00')
        for result in results.values():
            self.assertTrue(result['capital']['cash_plus_receivable_equals_equity_plus_profit'])
            self.assertEqual(result['reinvestment']['qualified_budget_cad'], '0.00')
            self.assertFalse(result['reinvestment']['investment_made'])

    def test_source_mutation_refused_before_effects(self):
        for path in (self.artifact, self.receipt, self.verifier, self.protocol):
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.assertRaisesRegex(ValueError, 'SOURCE_OR_FROZEN_RECEIPT_CHANGED'):
                self.execute()
            self.assertFalse((self.root / 'output').exists())
            path.write_bytes(original)

    def test_negative_or_wrong_scope_receipt_not_reauthorized_by_new_hash(self):
        for key, value in [('accepted', False), ('accepted', 'true'), ('scope', 'field-safe-operational-plan'), ('artifact_sha256', '0' * 64)]:
            bad = {**self.receipt_value, key: value}
            self.receipt.write_text(json.dumps(bad))
            self.expected['receipt'] = self.hash(self.receipt)
            with self.assertRaisesRegex(ValueError, 'INDEPENDENT_ACCEPTANCE_BINDING_OR_SCOPE'):
                self.execute()
            self.assertFalse((self.root / 'output').exists())

    def test_existing_evidence_never_overwritten(self):
        self.execute()
        before = {p.name: self.hash(p) for p in (self.root / 'output').iterdir() if p.is_file()}
        with self.assertRaises(FileExistsError):
            self.execute()
        self.assertEqual(before, {p.name: self.hash(p) for p in (self.root / 'output').iterdir() if p.is_file()})

    def test_inconsistent_policy_and_unearned_admission_refused(self):
        bad = copy.deepcopy(self.policy)
        bad['scenarios'][0]['sold_fraction'] = '0.01'
        with self.assertRaisesRegex(ValueError, 'INCONSISTENT_SCENARIO_COUNTS'):
            c.validate_policy(bad)
        bad = copy.deepcopy(self.policy)
        bad['qualified_unrestricted_simulated_earned_funds'] = '100.00'
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_COMMERCIAL_ADMISSION'):
            c.validate_policy(bad)
        bad = copy.deepcopy(self.policy)
        bad['card_route']['reserve_release_assumed'] = True
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_CARD_OR_RESERVE_POLICY'):
            c.validate_policy(bad)

    def test_no_seed_injection_or_implicit_credit_when_production_unfunded(self):
        bad = copy.deepcopy(self.policy)
        bad['seller_initial_simulated_equity_cad'] = '1.00'
        result = c.card_projection(bad, bad['scenarios'][0])
        self.assertFalse(result['capital']['prefunding_feasible'])
        self.assertEqual(result['cashflow_cad']['conditional_earned_cash_after_equity_backing'], '0.00')
        self.assertEqual(result['capital']['new_simulated_capital_after_start'], '0.00')

    def test_reported_price_and_inference_frontiers_actually_break_even(self):
        base = c.card_projection(self.policy, self.policy['scenarios'][0])
        candidate = copy.deepcopy(self.policy)
        candidate['price_cad'] = base['frontiers']['price_break_even_cad_at_fixed_scenario_counts']
        at_price = c.card_projection(candidate, candidate['scenarios'][0])
        self.assertLessEqual(abs(Decimal(at_price['cashflow_cad']['accounting_profit_within_authored_scenario'])), Decimal('.08'))
        scenario = copy.deepcopy(self.policy['scenarios'][0])
        scenario['inference_multiplier'] = base['frontiers']['inference_multiplier_break_even_against_policy_tokens']
        at_inference = c.card_projection(self.policy, scenario)
        self.assertEqual(at_inference['cashflow_cad']['accounting_profit_within_authored_scenario'], '0.00')

    def test_decimal_nan_and_json_duplicate_refused(self):
        with self.assertRaisesRegex(ValueError, 'DECIMAL_RANGE'):
            c.bounded_decimal('NaN', 'bad')
        self.artifact.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
            c.json_file(self.artifact)


if __name__ == '__main__':
    unittest.main()
