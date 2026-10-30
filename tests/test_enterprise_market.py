import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from commercial.ledger import audit, digest
from enterprise.model import default_policy, validate_policy, run_world, seller_observation, human_anchor, aggregate, draw
from enterprise.pricing import optimize_price, public_observation
from enterprise.services import prepare_services

ROOT = Path(__file__).resolve().parents[1]


class EnterpriseMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=ROOT, prefix='enterprise-market-test-')
        cls.manifest = prepare_services(ROOT, (Path(cls.tmp.name) / 'services').relative_to(ROOT))
        cls.policy = default_policy()
        cls.result = run_world(ROOT, cls.manifest, cls.policy, 1103, 'differentiation')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_policy_requires_exact_scope_currency_and_integer_money(self):
        for key, value in [('currency', 'CAD'), ('opening', True), ('cycles', 0), ('bundle_enabled', 1)]:
            policy = copy.deepcopy(self.policy)
            policy[key] = value
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_omitted_costs_and_invalid_regime_refused(self):
        policy = copy.deepcopy(self.policy)
        del policy['costs_usd']['maintenance_failure_retry']
        with self.assertRaises(ValueError):
            validate_policy(policy)
        policy = copy.deepcopy(self.policy)
        policy['regimes']['ordinary']['arrival_probability'] = 2
        with self.assertRaises(ValueError):
            validate_policy(policy)

    def test_malformed_regime_human_and_model_schemas_raise_value_error(self):
        malformed = []
        policy = copy.deepcopy(self.policy)
        del policy['regimes']['ordinary']['trust']
        malformed.append(policy)
        policy = copy.deepcopy(self.policy)
        policy['regimes']['ordinary']['temperature_ratio'] = 0
        malformed.append(policy)
        policy = copy.deepcopy(self.policy)
        policy['human_services']['reconciliation']['loaded_hourly_usd'] = 'free'
        malformed.append(policy)
        policy = copy.deepcopy(self.policy)
        policy['human_services']['kpi_variance']['tool_external_usd'] = float('nan')
        malformed.append(policy)
        policy = copy.deepcopy(self.policy)
        policy['regime_weights']['ordinary'] = float('nan')
        malformed.append(policy)
        policy = copy.deepcopy(self.policy)
        policy['competitor_models'].append('oracle')
        malformed.append(policy)
        policy = copy.deepcopy(self.policy)
        policy['arms'][0]['strategic_pricing'] = 'yes'
        malformed.append(policy)
        for policy in malformed:
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                validate_policy(policy)

    def test_secret_buyer_values_do_not_reach_seller_or_pricing(self):
        regime = self.policy['regimes']['ordinary']
        history = {'onboarded': False, 'trust': .95}
        left = seller_observation(self.policy, regime, 'reconciliation', dict(history, private_value=999, seed=123))
        right = seller_observation(self.policy, regime, 'reconciliation', dict(history, private_value=1, seed=999))
        self.assertEqual(left, right)
        self.assertFalse(any('seed' in k or 'private' in k or 'budget' in k for k in left))
        with self.assertRaises(ValueError):
            public_observation(dict(left, private_reservation=999))

    def test_price_grid_includes_human_anchor_and_no_fixed_discount(self):
        world = self.policy['regimes']['ordinary']
        public = seller_observation(self.policy, world, 'reconciliation', {'onboarded': False, 'trust': .95})
        quote = optimize_price(public, world, 'logit')
        self.assertLessEqual(quote['tested_price_range'][0], public['anchor_usd'] * .2)
        self.assertGreaterEqual(quote['tested_price_range'][1] + 1e-6, public['anchor_usd'] * 2)
        self.assertNotEqual(quote['price'], public['anchor_usd'] * .95)
        self.assertEqual(quote['grid_profitable_deviation_residual'], 0)

    def test_no_bid_and_rival_response_are_explicit(self):
        world = self.policy['regimes']['ordinary']
        public = seller_observation(self.policy, world, 'reconciliation', {'onboarded': False, 'trust': .95})
        quote = optimize_price(dict(public, autonomous_cost_usd=1000000), world, 'logit')
        self.assertIsNone(quote['price'])
        quote = optimize_price(public, world, 'logit', lagged=True)
        self.assertEqual(quote['rival']['response'], 'lagged_public_list_price')

    def test_no_arrivals_preserves_cash_without_uncommitted_attempts(self):
        policy = copy.deepcopy(self.policy)
        policy['regimes']['ordinary']['arrival_probability'] = 0
        with patch('enterprise.services.execute_job', side_effect=AssertionError('uncommitted attempt executed')):
            result = run_world(ROOT, self.manifest, policy, 1108, 'ordinary')
        self.assertEqual(result['summary']['expenses'], policy['setup_cost'])
        self.assertEqual(result['paid_jobs'], 0)
        self.assertEqual(result['reinvested_earned'], 0)
        self.assertEqual(result['cycles'], [])
        self.assertEqual(result['stop'], 'NO_BID_NONPOSITIVE_EXPECTED_INCREMENTAL_RETURN_BEFORE_COMMITMENT')

    def test_small_actual_workload_human_comparator_and_no_staffing(self):
        for service, expected in [('reconciliation', .65), ('kpi_variance', .65), ('evidence_matrix', .8)]:
            self.assertAlmostEqual(sum(self.policy['human_services'][service]['stages_hours'].values()), expected)
            self.assertEqual(self.policy['human_services'][service]['tool_external_usd'], 2)
        self.assertAlmostEqual(sum(self.policy['costs_usd'][k] for k in ['inference_tools_production', 'independent_verification_corrections', 'compute_storage_infrastructure', 'delivery_support_obligation', 'maintenance_failure_retry']), 3)
        self.assertFalse(any('human' in k for k in self.policy['costs_usd']))

    def test_low_win_scores_include_unconditional_attempt_and_acquisition(self):
        world = copy.deepcopy(self.policy['regimes']['ordinary'])
        public = seller_observation(self.policy, world, 'reconciliation', {'onboarded': False, 'trust': .95})
        world['arrival_probability'] = 0
        quote = optimize_price(public, world, 'logit')
        self.assertIsNone(quote['price'])
        for candidate in quote['candidate_curve']:
            self.assertEqual(candidate['win_probability'], 0)
            self.assertAlmostEqual(candidate['expected_immediate_contribution_per_opportunity'], -public['autonomous_cost_usd'] - world['quote_cost_usd'])
            expected_lifetime = -(1+public['repeat_probability']+public['repeat_probability']**2) * (public['autonomous_cost_usd'] + world['quote_cost_usd'])
            self.assertAlmostEqual(candidate['expected_lifetime_contribution_per_opportunity'], expected_lifetime)

    def test_actual_acceptance_and_unique_capacity(self):
        result = self.result
        jobs = [j for c in result['cycles'] for j in c['jobs']]
        self.assertEqual(len(jobs), len(set(jobs)))
        self.assertEqual(len(jobs), 96)
        self.assertTrue(all(len(c['jobs']) <= self.policy['capacity_per_cycle'] for c in result['cycles']))
        self.assertTrue(all(w['receipt']['accepted'] and w['receipt']['reexecuted'] for c in result['cycles'] if not c['outage'] for w in c['post_commitment_actual_work']))
        self.assertTrue(all(w['receipt']['model_calls'] == 0 for c in result['cycles'] if not c['outage'] for w in c['post_commitment_actual_work']))

    def test_complete_cost_receipts_reconcile_ledger(self):
        result = self.result
        self.assertEqual(sum(r['amount'] for r in result['cost_receipts']), result['summary']['expenses'])
        self.assertEqual(result['summary']['cash'], self.policy['opening'] + result['summary']['collections'] - result['summary']['expensePaid'])
        self.assertEqual(result['summary']['profit'], result['summary']['revenue'] - result['summary']['expenses'])
        self.assertEqual(result['actual_collections'], 0)
        self.assertGreater(result['summary']['collections'], 0)
        self.assertGreater(result['seed_still_supporting_reserves'], 0)

    def test_onboarding_charged_once_and_repeat_human_cost_deducted(self):
        costs = [r['event'] for r in self.result['cost_receipts'] if r['category'] == 'provider_autonomous_onboarding_once']
        self.assertEqual(len(costs), len(set(costs)))
        self.assertLessEqual(len(costs), self.policy['customer_pool'])
        self.assertAlmostEqual(human_anchor(self.policy, 'reconciliation', False) - human_anchor(self.policy, 'reconciliation', True), .1 * 34.75)

    def test_earned_funding_is_prior_cash_and_profitable_followon_cycle(self):
        expected = [c for c in self.result['cycles'] if c['funding'] == 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS' and c['settled_jobs'] > 0 and c['after']['profit'] > c['before']['profit']]
        self.assertEqual(self.result['earned_funded_cycles'], len(expected))
        self.assertTrue(expected)
        self.assertTrue(all(c['before']['unrestrictedEarned'] >= c['base_budget'] for c in expected))
        self.assertEqual(self.result['reinvested_earned'], sum(int(i['actual']) for i in self.result['ledger']['investments'] if i['state'] == 'complete'))

    def test_native_funding_forecast_uses_complete_joint_bundle_score(self):
        for cycle in self.result['cycles']:
            quotes = cycle['forecast_quotes']
            expected = (cycle['bundle_plan']['expected_immediate_contribution_per_opportunity'] + sum(q['expected_immediate_contribution_per_opportunity'] for q in quotes[3:])) if cycle['bundle'] else sum(q['expected_immediate_contribution_per_opportunity'] for q in quotes)
            self.assertAlmostEqual(cycle['forecast_expected_incremental_usd'], expected)
            self.assertGreater(expected, 0)

    def test_joint_bundle_price_equals_frozen_component_prices_and_dedup(self):
        offered = [c for c in self.result['cycles'] if c['bundle']]
        self.assertTrue(offered)
        for cycle in offered:
            self.assertAlmostEqual(sum(d['price'] / 1e6 for d in cycle['decisions'][:3]), cycle['bundle_plan']['total_price'], places=5)
            component_ids = [d['job_id'] for d in cycle['decisions'][:3]]
            self.assertEqual(len(set(component_ids)), 3)
            self.assertTrue(all(d['bundle_id'] == f"bundle-{cycle['cycle']}" for d in cycle['decisions'][:3]))
            self.assertEqual(len({d['participates'] for d in cycle['decisions'][:3]}), 1)
        paid_prices = sum(d['price'] for c in self.result['cycles'] for d in c['decisions'] if d['outcome'] == 'SIMULATED_SETTLED')
        self.assertEqual(paid_prices, self.result['summary']['revenue'])

    def test_no_unavailable_supplier_execution_or_fabricated_acceptance(self):
        policy = copy.deepcopy(self.policy)
        policy['regimes']['ordinary']['supplier_outage_probability'] = 1
        with patch('enterprise.services.execute_job', side_effect=AssertionError('unavailable producer called')):
            result = run_world(ROOT, self.manifest, policy, 1104, 'ordinary')
        self.assertEqual(result['paid_jobs'], 0)
        self.assertFalse(result['conditional_simulated_go'])
        self.assertTrue(all(not w['receipt']['reexecuted'] for c in result['cycles'] for w in c['post_commitment_actual_work']))
        self.assertEqual(result['summary']['expenses'], policy['setup_cost'])
        self.assertEqual(result['stop'], 'NO_BID_NONPOSITIVE_EXPECTED_INCREMENTAL_RETURN_BEFORE_COMMITMENT')

    def test_churn_persists_until_bounded_reacquisition(self):
        policy = copy.deepcopy(self.policy)
        policy['regimes']['differentiation']['retention_probability'] = 0
        policy['regimes']['differentiation']['reacquisition_probability'] = 0
        result = run_world(ROOT, self.manifest, policy, 1107, 'differentiation')
        self.assertGreater(result['counts']['churn_events'], 0)
        self.assertEqual(result['counts']['reacquired_customers'], 0)
        self.assertTrue(all(not d['participates'] for c in result['cycles'] for d in c['decisions'] if not d['customer_lifecycle']['active_before']))
        self.assertTrue(any(not h['active'] for h in result['buyers_public_final_history']))

    def test_failed_collection_and_refunds_keep_costs(self):
        policy = copy.deepcopy(self.policy)
        def failed_collection(seed, cycle, buyer, channel):
            return 1. if channel == 'collection' else draw(seed, cycle, buyer, channel)
        with patch('enterprise.model.draw', side_effect=failed_collection):
            result = run_world(ROOT, self.manifest, policy, 1105, 'differentiation', arm=policy['arms'][0])
        self.assertEqual(result['paid_jobs'], 0)
        self.assertGreater(result['accepted_jobs'], 0)
        self.assertGreater(result['summary']['expenses'], policy['setup_cost'])
        self.assertEqual(result['summary']['collections'], 0)
        self.assertFalse(result['conditional_simulated_go'])

    def test_liquidity_boundary_and_restricted_funds(self):
        policy = copy.deepcopy(self.policy)
        policy['opening'] = policy['setup_cost'] + policy['working']
        result = run_world(ROOT, self.manifest, policy, 1106, 'ordinary')
        self.assertEqual(result['stop'], 'LIQUIDITY_BEFORE_DELIVERY_COMMITMENT')
        self.assertEqual(result['reinvested_earned'], 0)
        self.assertFalse(result['conditional_simulated_go'])

    def test_deterministic_reexecution_and_tamper_rejection(self):
        repeated = run_world(ROOT, self.manifest, self.policy, 1103, 'differentiation')
        self.assertEqual(repeated['ledger'], self.result['ledger'])
        self.assertEqual(repeated['summary'], self.result['summary'])
        corrupt = copy.deepcopy(self.result['ledger'])
        corrupt['summary']['revenue'] += 1
        with self.assertRaises(ValueError):
            audit(corrupt, root=ROOT, manifest=self.manifest)

    def test_matched_controls_and_aggregate_are_separate_scopes(self):
        fixed = run_world(ROOT, self.manifest, self.policy, 1103, 'differentiation', arm=self.policy['arms'][0])
        self.assertEqual(fixed['seed'], self.result['seed'])
        self.assertNotEqual(fixed['arm'], self.result['arm'])
        result = aggregate([self.result, fixed])
        self.assertEqual(result['runs'], 2)
        self.assertLessEqual(result['engineering_wilson95_interval'][0], result['go_fraction'])
        self.assertEqual(self.result['invention_compounding'], 'NOT_ESTABLISHED')

    def test_unknown_information_models_and_overwrite_refused(self):
        with self.assertRaises(ValueError):
            run_world(ROOT, self.manifest, self.policy, 1, 'ordinary', 'oracle')
        with self.assertRaises(ValueError):
            run_world(ROOT, self.manifest, self.policy, 1, 'ordinary', persist=True)
        with self.assertRaises(FileExistsError):
            run_world(ROOT, self.manifest, self.policy, 1, 'ordinary', output=self.tmp.name)
