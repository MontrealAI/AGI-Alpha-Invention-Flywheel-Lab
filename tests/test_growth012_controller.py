import copy
from pathlib import Path
import tempfile
import unittest

from enterprise.growth012 import default_config, run_growth, validate_config
from enterprise.model import money
from enterprise.services import prepare_services
from verification.growth012 import audit_growth

ROOT = Path(__file__).resolve().parents[1]


class Growth012ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='growth012-controller-test-', dir=ROOT)
        cls.folder = Path(cls.temp.name)
        cls.manifest = prepare_services(ROOT, str(cls.folder.relative_to(ROOT) / 'services'))
        cls.config = default_config()
        cls.config.update(horizon_hours=96, customer_pool=6, contacts_per_day=6,
            initial_capacity=4, maximum_capacity=4, opening=money(10000), setup_cost=money(1),
            daily_overhead=money(.01), repeat_interval_hours=24, settlement_hours=12,
            sales_cycle_hours=1, rival_update_hours=24, choice_model='utility',
            human_ai_complete_cost_ratio=1.2)
        cls.worlds = {controller: run_growth(ROOT, cls.manifest, copy.deepcopy(cls.config),
            12002, controller, persist=False) for controller in ['baseline', 'simple', 'joint']}
        zero = copy.deepcopy(cls.config)
        zero['settlement_hours'] = 0
        cls.zero = run_growth(ROOT, cls.manifest, zero, 12002, 'joint', persist=False)
        finite = copy.deepcopy(zero)
        finite['finite_liability_hours'] = 4
        cls.finite = run_growth(ROOT, cls.manifest, finite, 12002, 'joint', persist=False)
        unexpired = copy.deepcopy(zero)
        unexpired['finite_liability_hours'] = 200
        cls.unexpired = run_growth(ROOT, cls.manifest, unexpired, 12002, 'joint', persist=False)
        no_bid = copy.deepcopy(cls.config)
        no_bid['policy']['costs_usd']['quote_acquisition'] = 10000
        cls.no_bid = run_growth(ROOT, cls.manifest, no_bid, 12002, 'joint', persist=False)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_first_comparison_preserves_equal_capital_and_all_business_assumptions(self):
        for controller, world in self.worlds.items():
            self.assertEqual(world['controller'], controller)
            self.assertEqual(world['config'], self.config)
            self.assertEqual(world['manifest_sha256'], self.worlds['joint']['manifest_sha256'])
            self.assertEqual(world['ledger']['config']['opening'], self.config['opening'])
            self.assertEqual(world['ledger']['config']['working'], self.config['working'])
            self.assertIsNone(world['config']['finite_liability_hours'])
            self.assertEqual(world['actual_revenue'], 0)

    def test_real_fulfilled_work_repeats_with_unique_artifacts_and_native_acceptance(self):
        world = self.worlds['joint']
        work = world['work_executions']
        self.assertGreater(len(work), 6)
        self.assertGreater(world['metrics']['repeat_buyers'], 0)
        self.assertGreater(world['metrics']['earned_funded_deliveries'], 0)
        self.assertEqual(len({row['job_id'] for row in work}), len(work))
        self.assertTrue(all(row['receipt']['accepted'] and row['receipt']['reexecuted'] for row in work))
        self.assertTrue(all(row['receipt']['model_calls'] == 0 for row in work))
        prepared = {a['args']['id'] for a in world['ledger']['actions'] if a['op'] == 'event' and a['args']['action'] == 'prepare'}
        self.assertEqual(prepared, {row['order_id'] for row in work})
        proof = audit_growth(world, root=ROOT, manifest=self.manifest)
        self.assertTrue(proof['accepted'])
        self.assertEqual(proof['actual_service_executions'], len(work))

    def test_zero_settlement_clears_after_real_production_in_same_event_hour(self):
        world = self.zero
        funded, prepared, released = {}, {}, {}
        for event in world['ledger']['actions']:
            if event['op'] != 'event':
                continue
            target = {'fund': funded, 'prepare': prepared, 'release': released}.get(event['args']['action'])
            if target is not None:
                target[event['args']['id']] = (event['day'], event['seq'])
        self.assertGreater(len(released), 0)
        for ident, (hour, seq) in released.items():
            self.assertEqual(hour, prepared[ident][0])
            self.assertGreater(seq, prepared[ident][1])
            self.assertEqual(prepared[ident][0] - funded[ident][0], world['config']['production_hours'])
            self.assertGreater(prepared[ident][0], funded[ident][0])
        self.assertLess(max(t[0] for t in released.values()), 30 * 24)
        self.assertTrue(audit_growth(world, root=ROOT, manifest=self.manifest)['accepted'])

    def test_reported_counts_and_money_derive_from_native_events(self):
        for world in [*self.worlds.values(), self.zero, self.finite, self.unexpired]:
            actions = world['ledger']['actions']
            prepared = {a['args']['id'] for a in actions if a['op'] == 'event' and a['args']['action'] == 'prepare'}
            released = {a['args']['id'] for a in actions if a['op'] == 'event' and a['args']['action'] == 'release'}
            self.assertEqual(world['metrics']['accepted_jobs'], len(prepared))
            self.assertEqual(world['metrics']['paid_jobs'], len(released))
            self.assertEqual(world['metrics']['qualified_unique_work_executed'], len(prepared))
            self.assertEqual(world['metrics']['collections_microUSD'], world['ledger']['summary']['collections'])
            self.assertEqual(world['metrics']['profit_microUSD'], world['ledger']['summary']['profit'])
            self.assertEqual(world['metrics']['costs_microUSD'], world['ledger']['summary']['expenses'])
            collected = sum(int(row['amount']) for row in world['ledger']['journal'] if row['kind'] == 'collections')
            self.assertEqual(collected, world['metrics']['collections_microUSD'])

    def test_observations_retain_current_state_without_hidden_values_or_future_draws(self):
        forbidden = {'private', 'factor', 'budget', 'reservation_value', 'future_draw', 'future_shocks', 'hidden_scenario_label'}
        def inspect(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & forbidden)
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
        world = self.worlds['joint']
        for decision in world['decisions']:
            observation = decision['observation']
            inspect(observation)
            prefix = observation['native_actions_through']
            state = world['ledger']['actions'][prefix - 1]['after'] if prefix else world['ledger']['actions'][0]['before']
            self.assertEqual(observation['snapshot'], state)
            self.assertIn('forecast_accepted_workload', observation)

    def test_unprofitable_acquisition_retains_cash_and_is_not_a_success(self):
        world = self.no_bid
        self.assertEqual(world['work_executions'], [])
        self.assertEqual(world['metrics']['paid_jobs'], 0)
        self.assertFalse(world['conditional_simulated_go'])
        self.assertFalse(any(a['op'] in {'offer', 'reserve'} for a in world['ledger']['actions']))
        self.assertTrue(all(d['selected_action'] == 'retain_cash' for d in world['decisions']))
        self.assertTrue(any(row['reason'] == 'NONPOSITIVE_MARGINAL_CONTRIBUTION' for row in world['rejected_growth_actions']))
        self.assertEqual(world['summary']['cash'], self.config['opening'] - world['summary']['expensePaid'])
        self.assertLess(world['summary']['expenses'], money(2))
        self.assertTrue(audit_growth(world, root=ROOT, manifest=self.manifest)['accepted'])

    def test_original_native_tail_is_retained(self):
        world = self.worlds['joint']
        released = [row for row in world['ledger']['orders'] if row['state'] == 'released']
        self.assertGreater(len(released), 0)
        self.assertEqual(world['summary']['tailReserve'], sum(int(row['price']) + 200000 for row in released))
        self.assertFalse(any(a['op'] == 'mature' for a in world['ledger']['actions']))

    def test_costed_finite_contract_releases_only_matured_exposures(self):
        world = self.finite
        actions = world['ledger']['actions']
        releases = {a['args']['id']: a['day'] for a in actions if a['op'] == 'event' and a['args']['action'] == 'release'}
        maturities = [a for a in actions if a['op'] == 'mature']
        self.assertGreater(len(maturities), 0)
        self.assertTrue(any(a['op'] == 'arrange' for a in actions))
        for action in maturities:
            self.assertGreaterEqual(action['day'], releases[action['args']['id']] + world['config']['finite_liability_hours'])
            for key in ['cash', 'revenue', 'collections', 'profit', 'expenses']:
                self.assertEqual(action['before'][key], action['after'][key])
        still_released = [row for row in world['ledger']['orders'] if row['state'] == 'released']
        self.assertEqual(world['summary']['tailReserve'], sum(int(row['price']) + 200000 for row in still_released))
        self.assertTrue(audit_growth(world, root=ROOT, manifest=self.manifest)['accepted'])

    def test_finite_horizon_does_not_release_unexpired_tail(self):
        world = self.unexpired
        self.assertGreater(world['metrics']['paid_jobs'], 0)
        self.assertFalse(any(a['op'] == 'mature' for a in world['ledger']['actions']))
        released = [row for row in world['ledger']['orders'] if row['state'] == 'released']
        self.assertEqual(world['summary']['tailReserve'], sum(int(row['price']) + 200000 for row in released))
        self.assertGreater(world['summary']['tailReserve'], 0)
        self.assertTrue(all(a['day'] <= world['config']['horizon_hours'] for a in world['ledger']['actions']))

    def test_zero_production_duration_is_refused(self):
        config = copy.deepcopy(self.config)
        config['production_hours'] = 0
        with self.assertRaisesRegex(ValueError, 'FINITE_THROUGHPUT'):
            validate_config(config)


if __name__ == '__main__':
    unittest.main()
