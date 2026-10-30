import copy
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import TapeExchange
from enterprise.services import prepare_services, execute_job
from verification.growth012 import audit_growth, collected_frontier, reproduce_baseline_bottlenecks

ROOT = Path(__file__).resolve().parents[1]


class Growth012AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='growth012-audit-', dir=ROOT)
        cls.folder = Path(cls.temp.name)
        cls.manifest = prepare_services(ROOT, str(cls.folder.relative_to(ROOT) / 'services'))
        cls.job = cls.manifest['jobs'][0]
        exchange = TapeExchange(cls.folder / 'money.sqlite', root=ROOT, manifest=cls.manifest,
            opening=1_000_000_000, working=0, contract='growth012-independent-fixture', durable=False)
        try:
            exchange.execute('cost', {'id': 'complete-cost-fixture', 'amount': 10_000_000}, 0)
            exchange.execute('wallet', {'buyer': 'buyer-1', 'amount': 100_000_000}, 1)
            exchange.execute('offer', {'id': 'order-1', 'buyer': 'buyer-1', 'price': 100_000_000,
                'job_id': cls.job['id'], 'deadline': 20}, 1)
            exchange.execute('event', {'id': 'order-1', 'action': 'consent', 'event_id': 'consent-1'}, 1)
            exchange.execute('event', {'id': 'order-1', 'action': 'fund', 'event_id': 'fund-1'}, 1)
            commitment = exchange.actions[-1]['seq']
            receipt = execute_job(ROOT, cls.job)
            exchange.execute('event', {'id': 'order-1', 'action': 'prepare', 'event_id': 'prepare-1'}, 3)
            exchange.execute('event', {'id': 'order-1', 'action': 'release', 'event_id': 'release-1'}, 5)
            cls.fixture = {'config': {'production_hours': 2, 'settlement_hours': 2, 'horizon_hours': 10,
                'targets_collected_microUSD': [50_000_000, 100_000_000, 1_000_000_000]},
                'ledger': exchange.export(), 'work_executions': [{'order_id': 'order-1', 'job_id': cls.job['id'],
                    'time': 3, 'commitment_action_seq': commitment, 'receipt': receipt}],
                'decisions': [{'id': 'decision-0', 'time': 0, 'observation': {'snapshot': exchange.actions[0]['before'], 'native_actions_through': 0},
                    'feasible_actions': [{'id': 'retain', 'kind': 'retain_cash', 'cash_required': 0,
                        'projected_contribution': 0, 'payback_hours': 0, 'downside': 0, 'feasible': True,
                        'reason': 'no_pending_commitment', 'constraint_class': 'controller_policy'}],
                    'selected_action': 'retain', 'realized_outcome': {'cash_retained': True}}]}
        finally:
            exchange.close()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_actual_delivery_and_independent_milestones(self):
        proof = audit_growth(self.fixture, root=ROOT, manifest=self.manifest)
        self.assertTrue(proof['accepted'])
        self.assertEqual(proof['complete_cost_profit_microUSD'], 90_000_000)
        self.assertEqual(proof['net_collected_microUSD'], 100_000_000)
        self.assertEqual(proof['milestones'], {'50000000': 5, '100000000': 5, '1000000000': None})
        self.assertEqual(proof['actual_service_executions'], 1)

    def test_claimed_summary_cannot_override_native_result(self):
        altered = copy.deepcopy(self.fixture)
        altered['summary'] = {'profit': 10**30, 'actual_revenue': 10**30}
        proof = audit_growth(altered, root=ROOT, manifest=self.manifest)
        self.assertEqual(proof['complete_cost_profit_microUSD'], 90_000_000)

    def test_native_money_tamper_rejected(self):
        altered = copy.deepcopy(self.fixture)
        altered['ledger']['summary']['cash'] += 1
        with self.assertRaises(ValueError):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_duplicate_work_rejected(self):
        altered = copy.deepcopy(self.fixture)
        altered['work_executions'].append(altered['work_executions'][0])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_OR_UNPREPARED_WORK'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_unexecuted_native_prepare_rejected(self):
        altered = copy.deepcopy(self.fixture)
        altered['work_executions'] = []
        with self.assertRaisesRegex(ValueError, 'WITHOUT_ACTUAL_WORK'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_production_time_cannot_be_eliminated(self):
        altered = copy.deepcopy(self.fixture)
        altered['config']['production_hours'] = 3
        with self.assertRaisesRegex(ValueError, 'PRODUCTION_CAUSALITY'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_clearing_time_enforced(self):
        altered = copy.deepcopy(self.fixture)
        altered['config']['settlement_hours'] = 3
        with self.assertRaisesRegex(ValueError, 'SETTLEMENT_CAUSALITY'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_false_execution_acceptance_rejected(self):
        altered = copy.deepcopy(self.fixture)
        altered['work_executions'][0]['receipt']['accepted'] = False
        with self.assertRaisesRegex(ValueError, 'EXECUTED_ACCEPTANCE_REQUIRED'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_private_observation_rejected(self):
        altered = copy.deepcopy(self.fixture)
        altered['decisions'][0]['observation']['future_shocks'] = [1]
        with self.assertRaisesRegex(ValueError, 'PRIVATE_INFORMATION'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_observation_cannot_reference_future_native_actions(self):
        altered = copy.deepcopy(self.fixture)
        altered['decisions'][0]['observation']['native_actions_through'] = 3
        with self.assertRaisesRegex(ValueError, 'FUTURE_OR_STALE_PREFIX'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_observation_snapshot_must_match_native_prefix(self):
        altered = copy.deepcopy(self.fixture)
        altered['decisions'][0]['observation']['snapshot'] = altered['ledger']['summary']
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_STATE_BINDING'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_selected_infeasible_action_rejected(self):
        altered = copy.deepcopy(self.fixture)
        altered['decisions'][0]['feasible_actions'][0]['feasible'] = False
        with self.assertRaisesRegex(ValueError, 'SELECTED_ACTION_NOT_FEASIBLE'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_rejected_action_requires_recorded_reason(self):
        altered = copy.deepcopy(self.fixture)
        item = dict(altered['decisions'][0]['feasible_actions'][0], id='reject', feasible=False, reason='')
        altered['decisions'][0]['feasible_actions'].append(item)
        with self.assertRaisesRegex(ValueError, 'REJECTION_WITHOUT_EVIDENCE'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)

    def test_late_reversal_and_trailing365_window(self):
        def action(hour, before, after):
            return {'day': hour, 'before': {'collections': before},
                'after': {'collections': after, 'profit': after, 'payables': 0, 'investmentStopped': False}}
        actions = [action(0, 0, 100), action(10, 100, 80), action(8761, 80, 110)]
        proof = collected_frontier(actions, [90, 150], 8761)
        self.assertEqual(proof['milestones'], {'90': 0, '150': None})
        self.assertEqual(proof['terminal_trailing365_collected_microUSD'], 10)

    def test_historical_bottlenecks_reproduce_without_policy_edits(self):
        result = reproduce_baseline_bottlenecks()
        self.assertTrue(result['settlement']['zero_and_one_month_financial_rows_identical'])
        self.assertEqual(result['capacity']['default_fraction']['executed_projection_attempts'], 0)
        self.assertEqual(result['capacity']['full_fraction']['executed_projection_attempts'], 1)
        self.assertEqual(result['capacity']['full_fraction']['cumulative_profit_cents'], 29000)

    def test_finite_contract_maturity_releases_reserve_without_revenue(self):
        from enterprise.contract012 import FiniteTapeExchange
        exchange = FiniteTapeExchange(self.folder / 'finite.sqlite', root=ROOT, manifest=self.manifest,
            opening=1_000_000_000, working=0, contract='finite-audit-fixture',
            liability_ticks=2, time_unit='hours', arrangement_cost=1_000_000, durable=False)
        try:
            exchange.execute('arrange', {}, 0)
            exchange.execute('cost', {'id': 'complete-cost', 'amount': 10_000_000}, 0)
            exchange.execute('wallet', {'buyer': 'buyer-finite', 'amount': 100_000_000}, 1)
            exchange.execute('offer', {'id': 'order-finite', 'buyer': 'buyer-finite', 'price': 100_000_000,
                'job_id': self.job['id'], 'deadline': 20}, 1)
            exchange.execute('event', {'id': 'order-finite', 'action': 'consent', 'event_id': 'finite-consent'}, 1)
            exchange.execute('event', {'id': 'order-finite', 'action': 'fund', 'event_id': 'finite-fund'}, 1)
            commitment = exchange.actions[-1]['seq']
            receipt = execute_job(ROOT, self.job)
            exchange.execute('event', {'id': 'order-finite', 'action': 'prepare', 'event_id': 'finite-prepare'}, 3)
            exchange.execute('event', {'id': 'order-finite', 'action': 'release', 'event_id': 'finite-release'}, 5)
            self.assertEqual(exchange.ex.snapshot()['tailReserve'], 100_200_000)
            exchange.execute('mature', {'id': 'order-finite', 'event_id': 'finite-maturity'}, 7)
            result = copy.deepcopy(self.fixture)
            result['config']['finite_liability_hours'] = 2
            result['ledger'] = exchange.export()
            result['work_executions'] = [{'order_id': 'order-finite', 'job_id': self.job['id'], 'time': 3,
                'commitment_action_seq': commitment, 'receipt': receipt}]
            proof = audit_growth(result, root=ROOT, manifest=self.manifest)
            self.assertEqual(proof['tail_reserve_microUSD'], 0)
            self.assertEqual(proof['net_collected_microUSD'], 100_000_000)
            self.assertEqual(proof['complete_cost_profit_microUSD'], 89_000_000)
            result['config']['finite_liability_hours'] = 1
            with self.assertRaisesRegex(ValueError, 'FINITE_TERMS_TIME_BINDING'):
                audit_growth(result, root=ROOT, manifest=self.manifest)
        finally:
            exchange.close()

    def test_original_contract_cannot_claim_finite_liability(self):
        altered = copy.deepcopy(self.fixture)
        altered['config']['finite_liability_hours'] = 1
        with self.assertRaisesRegex(ValueError, 'UNIMPLEMENTED_FINITE_LIABILITY_CLAIM'):
            audit_growth(altered, root=ROOT, manifest=self.manifest)


if __name__ == '__main__':
    unittest.main()
