import copy
from fractions import Fraction
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from commercial.ledger import canonical, strict_json
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from portfolio071.arrangement import finite_project, factorial, buyer_choice, rival_best_response
from portfolio071.economics import (World, commercial_choice, conditional_market_frontier,
                                   execute_trajectory, population, project_game)
from portfolio071.service import SOURCES, prepare_manifest, load_contracts, check_delivery
from portfolio071.thermal import construct, development_request

ROOT = Path(__file__).resolve().parents[1]


class ArrangementTests(unittest.TestCase):
    def setUp(self):
        self.buyers = [{'id': str(i), 'value_usd': 50, 'budget_usd': 40,
                        'adoption_usd': 1, 'outside_surplus_usd': 0} for i in range(3)]
        self.terms = dict(capital_usd=200, setup_usd=30, adapter_usd=2,
                          coordination_usd=1, supplier_cost_usd=2, supplier_hurdle_usd=1,
                          supplier_quote_usd=3, support_usd=2, rights_review_usd=1,
                          price_menu_usd=(10, 20, 30), tax_bps=2500)

    def test_equal_full_action_conventional_entrepreneur_ties(self):
        result = factorial(self.buyers, **self.terms)
        self.assertTrue(result['ordinary_ties_joint'])
        for arm in result['arms'].values():
            self.assertEqual(arm['best_response_regret_usd'], {'numerator': 0, 'denominator': 1})

    def test_positive_contribution_cannot_replace_prefunding(self):
        result = finite_project(self.buyers, **{**self.terms, 'capital_usd': 40})
        self.assertEqual(result['selected']['decision'], 'NON_ENTRY')
        self.assertTrue(any('UNFUNDED_PRECOLLECTION_PREFIX' in r['refusals']
                            and Fraction(**r['expected_before_tax_usd']) > 0 for r in result['evaluated']))

    def test_participants_can_refuse_and_sharing_needs_rights(self):
        no_value = [{**b, 'value_usd': 0} for b in self.buyers]
        self.assertEqual(finite_project(no_value, **self.terms)['selected']['decision'], 'NON_ENTRY')
        self.assertEqual(finite_project(self.buyers, **self.terms, rights_available=False)['selected']['decision'], 'NON_ENTRY')
        self.assertEqual(finite_project(self.buyers, **self.terms, supplier_available=False)['selected']['decision'], 'NON_ENTRY')

    def test_seed_financing_not_silently_extended(self):
        with self.assertRaisesRegex(ValueError, 'FINANCING_NATIVE_OPERATION_UNSUPPORTED'):
            finite_project(self.buyers, **self.terms, financing_available=True)

    def test_duplicate_buyer_cannot_fabricate_coalition(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_BUYER'):
            finite_project(self.buyers + [self.buyers[0]], **self.terms)

    def test_equal_offer_does_not_force_company_sale(self):
        result = buyer_choice(self.buyers[0], 20, rival_price_usd=20, self_service_cost_usd=45)
        self.assertNotEqual(result['choice'], 'company')

    def test_self_service_requires_upfront_budget(self):
        buyer = {**self.buyers[0], 'budget_usd': 5}
        result = buyer_choice(buyer, 20, rival_price_usd=20, self_service_cost_usd=10)
        self.assertNotIn('self_service', result['options_usd'])

    def test_rival_can_undercut_or_refuse_loss(self):
        result = rival_best_response(self.buyers, 30, rival_price_menu_usd=(10, 20, 30),
                                     rival_variable_usd=5, rival_fixed_usd=1)
        self.assertEqual(result['best_response_regret_usd'], 0)
        self.assertEqual(result['selected']['company_members'], [])
        self.assertGreater(result['selected']['rival_profit_usd'], 0)

    def test_low_value_and_physical_qualification_failure_block_license(self):
        for world in (World(value_bps=0), World(qualification_passes=False), World(rights_available=False)):
            self.assertIsNone(commercial_choice(population(world)[0], world, 30, False)['selected'])

    def test_full_cost_equal_capability_rival_can_take_the_market(self):
        world = World(equal_capability_rival=True)
        result = commercial_choice(population(world)[0], world, 30, False)
        self.assertIsNone(result['selected'])
        for candidate in result['evaluated']:
            response = candidate['rival']['selected']
            self.assertGreaterEqual(response['rival_profit_usd'], 0)
            self.assertEqual(candidate['rival']['best_response_regret_usd'], 0)

    def test_target_frontier_is_conditional_arithmetic_with_refusal(self):
        frontier = conditional_market_frontier()
        self.assertIsNone(frontier['market_reach_or_share_assumed'])
        self.assertTrue(any(row['required_annual_contracts_for_target']['3000000000'] is None
                            for row in frontier['rows']))
        for row in frontier['rows']:
            self.assertTrue(all(check['difference_numerator'] == 0
                                for check in row['small_explicit_arithmetic_checks']))


class NativeScientificAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='portfolio071-finance-test-')
        cls.root = Path(cls.temp.name) / 'source'
        for name in sorted(set(SOURCE_PATHS) | set(SOURCES)):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.deliveries = []
        for task in ('heat_delivery', 'thermal_continuity'):
            request = development_request(task)
            request['id'] = 'development-' + task
            cls.deliveries.append((request, construct(request)))
        cls.manifest = prepare_manifest(cls.root, cls.deliveries)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_unaccepted_scientific_artifact_is_not_native_service(self):
        altered = copy.deepcopy(self.deliveries[0][1])
        altered['delivered_kw'][0] = 0
        with self.assertRaisesRegex(ValueError, 'PREPARED_ARTIFACT_CHANGED'):
            check_delivery(self.root, self.manifest, self.deliveries[0][0]['id'], altered)
        with self.assertRaisesRegex(ValueError, 'UNACCEPTED_ARTIFACT'):
            prepare_manifest(self.root, [(self.deliveries[0][0], altered)])

    def test_all_source_and_receipt_bytes_remain_bound(self):
        broken = copy.deepcopy(self.manifest)
        broken['source_hashes']['portfolio071/verification.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SOURCE_CLOSURE_CHANGED'):
            load_contracts(self.root, broken)
        broken = copy.deepcopy(self.manifest)
        broken['jobs'][0]['receipt_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SOURCE_OR_ARTIFACT_CHANGED'):
            load_contracts(self.root, broken)

    def test_native_development_lifecycle_replays_with_no_external_financing(self):
        out = Path(self.temp.name) / 'development-lifecycle'
        result = execute_trajectory(self.root, self.manifest, out, capital_usd=100000,
                                    world=World(external_financing_requested=True), horizon_days=65)
        self.assertTrue(result['native_account_audit']['accepted'])
        self.assertTrue(result['opening_plus_flows_reconciles'])
        self.assertEqual(result['external_financing_received_usd'], 0)
        self.assertEqual(result['financing'][0]['decision'], 'REFUSED')
        self.assertTrue(result['financing'][0]['cash_unchanged'])
        self.assertFalse(result['rolling_profit']['complete_365_day_operating_history'])
        self.assertIsNone(result['rolling_profit']['trailing_365_day_profit_microUSD'])
        self.assertFalse(result['milestone_3b'])
        self.assertEqual(result['actual_scientific_artifacts'], 2)
        record = strict_json((out / 'native-at-horizon.json').read_bytes())
        self.assertTrue(audit_journal(record, root=self.root, manifest=self.manifest)['accepted'])

    def test_unfunded_research_has_costs_but_no_sales(self):
        out = Path(self.temp.name) / 'research-refusal'
        result = execute_trajectory(self.root, self.manifest, out, capital_usd=20000, horizon_days=5)
        self.assertEqual(result['modeled_licenses'], 0)
        self.assertEqual(result['stop_reason'], 'INITIAL_RESEARCH_PREFUNDING_UNAVAILABLE')
        self.assertLess(result['operating_endpoint']['profit'], 0)
        self.assertEqual(result['operating_endpoint']['revenue'], 0)

    def test_cash_choice_reselects_an_affordable_lower_price(self):
        result = execute_trajectory(self.root, self.manifest, Path(self.temp.name) / 'cash-price',
                                    capital_usd=95000, horizon_days=16)
        accepted = [d for d in result['decisions'] if d['decision'] == 'ACCEPTED_CONDITIONAL_LICENSE']
        self.assertEqual(len(accepted), 1)
        choice = accepted[0]['choice']
        self.assertLess(choice['selected']['price_usd'], choice['unconstrained_selected']['price_usd'])
        self.assertEqual(choice['cash_constrained_choice_regret_usd'], 0)
        self.assertTrue(all(day['tax_commitments_covered'] for day in result['daily']))

    def test_prepaid_capacity_is_applied_once_at_actual_delivery(self):
        result = execute_trajectory(self.root, self.manifest, Path(self.temp.name) / 'capacity',
                                    capital_usd=1000000, horizon_days=16,
                                    policy='stylized_prepaid_reach_capacity')
        accepted = [d for d in result['decisions'] if d['decision'] == 'ACCEPTED_CONDITIONAL_LICENSE']
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]['new_delivery_cost_usd'], 0)
        self.assertEqual(accepted[0]['prepaid_capacity_applied_usd'], accepted[0]['choice']['selected']['cost_usd'])
        self.assertTrue(result['native_account_audit']['accepted'])

    def test_delayed_defaulted_licenses_do_not_fake_renewals_or_omit_tail_tax(self):
        result = execute_trajectory(self.root, self.manifest, Path(self.temp.name) / 'late-tax',
                                    capital_usd=1000000, horizon_days=400,
                                    world=World(rival_change_months=None, collection_delay_days=400,
                                                default_every=2))
        accepted = [d for d in result['decisions'] if d['decision'] == 'ACCEPTED_CONDITIONAL_LICENSE']
        late = [d for d in accepted if d['day'] >= 365]
        self.assertTrue(late)
        self.assertTrue(all(not d['renewal_after_collected_prior_year'] for d in late))
        self.assertEqual(result['tax_paid_microUSD'], 0)
        self.assertGreater(result['total_tax_after_drain_microUSD'], 0)
        self.assertTrue(all(day['tax_commitments_covered'] for day in result['daily']))
        self.assertTrue(result['post_horizon_native_audit']['accepted'])
        for settlement in result['tax_settlements']:
            self.assertTrue(settlement['post_horizon'])
            self.assertLessEqual(settlement['tax_paid_microUSD'], settlement['gross_collection_microUSD'])
            self.assertLessEqual(settlement['tax_paid_microUSD'], settlement['available_before_tax_microUSD'])
            self.assertEqual(settlement['payables_after_tax_microUSD'], 0)

    def test_inferred_idle_days_match_explicit_native_daily_control(self):
        world = World(rival_change_months=None, default_every=2, collection_delay_days=31)
        inferred_out = Path(self.temp.name) / 'inferred-control'
        explicit_out = Path(self.temp.name) / 'explicit-control'
        inferred = execute_trajectory(self.root, self.manifest, inferred_out,
                                      capital_usd=1000000, horizon_days=390, world=world)
        explicit = execute_trajectory(self.root, self.manifest, explicit_out,
                                      capital_usd=1000000, horizon_days=390, world=world,
                                      infer_idle_days=False)
        self.assertGreater(inferred['observation_counts']['inferred_unchanged_daily_states'], 0)
        self.assertEqual(explicit['observation_counts']['inferred_unchanged_daily_states'], 0)
        for left, right in zip(inferred['daily'], explicit['daily']):
            self.assertEqual({k: v for k, v in left.items() if k != 'observation'},
                             {k: v for k, v in right.items() if k != 'observation'})
        for name in ('native-at-horizon.json', 'native-after-drain.json'):
            left = strict_json((inferred_out / name).read_bytes())['ledger']
            right = strict_json((explicit_out / name).read_bytes())['ledger']
            self.assertEqual(left, right)
        self.assertEqual(inferred['tax_settlements'], explicit['tax_settlements'])
        self.assertEqual(inferred['rolling_profit'], explicit['rolling_profit'])


if __name__ == '__main__':
    unittest.main()
