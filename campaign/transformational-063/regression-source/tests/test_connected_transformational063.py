"""Numerical decision regressions over real canonical native accounts."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest

from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS
from connected_enterprise.transformational063 import financial_states, qualifications, audit, run
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services
from enterprise.checkers import audit_delivery

ROOT = Path(__file__).resolve().parents[1]
USD = 1_000_000


class Transformational063DecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='transformational063-source-')
        cls.root = Path(cls.fixture.name)
        for name in set(SOURCE_PATHS) | set(SERVICE_PATHS):
            target = cls.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
        cls.manifest = prepare_services(cls.root, 'services')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='transformational063-account-')
        self.account = JournalAccount(self.root, self.manifest, Path(self.tmp.name)/'account',
                                      opening=100_000*USD, working=0, contract='transformational063-regression')
        self.day = 0
        self.count = 0

    def tearDown(self):
        self.account.close()
        self.tmp.cleanup()

    def earn(self, price=100, cost=10):
        ident = 'order-'+str(self.count)
        job = next(j for j in self.manifest['jobs'] if j['service_id'] == 'reconciliation')
        self.day += 1
        self.account.execute('wallet', {'buyer': ident, 'amount': price*USD}, self.day)
        self.account.execute('offer', {'id': ident, 'buyer': ident, 'price': price*USD,
                                      'job_id': job['id'], 'deadline': self.day+1}, self.day)
        for action in ('consent', 'fund', 'prepare', 'release'):
            self.account.execute('event', {'id': ident, 'action': action, 'event_id': ident+'-'+action}, self.day)
        self.account.cost(ident+'-production', cost*USD, self.day)
        self.count += 1

    def states(self, **kwargs):
        return financial_states(self.account.export(), root=self.root, manifest=self.manifest, **kwargs)

    def decide(self, states=None, **kwargs):
        return qualifications(states or self.states(), accepted_deliveries=self.count,
                              completed_cycles=self.count, minimum_cycles=3,
                              modeled_cost_scope_complete=True, **kwargs)

    def profitable(self):
        for _ in range(3):
            self.earn()

    def test_conventional_technical_tie_does_not_veto_profitable_delivery(self):
        self.profitable()
        result = self.decide()
        self.assertEqual(result['commercial']['verdict'], 'CONDITIONAL_GO')
        self.assertEqual(self.states()['accounting_profit']['lifetime_microUSD'], 270*USD)
        self.assertEqual(result['blue_sky_flagship']['verdict'], 'NOT_ESTABLISHED')

    def test_technical_win_cannot_rescue_complete_cost_loss(self):
        self.account.cost('construction', 1000*USD, 0)
        self.profitable()
        result = self.decide(kernel_comparison=self.comparison(blue=True, with_asset_accepted=3, without_asset_accepted=0))
        self.assertEqual(self.states()['accounting_profit']['lifetime_microUSD'], -730*USD)
        self.assertEqual(result['commercial']['verdict'], 'NOT_ESTABLISHED')
        self.assertEqual(result['blue_sky_flagship']['verdict'], 'CONDITIONAL_GO')

    def test_profitable_base_continues_without_uneconomic_specialist(self):
        self.profitable()
        result = self.decide(investment={'cost_microUSD': 100*USD, 'incremental_benefit_microUSD': 50*USD})
        self.assertEqual(result['commercial']['verdict'], 'CONDITIONAL_GO')
        self.assertEqual(result['investment']['verdict'], 'NOT_ESTABLISHED')
        self.assertEqual(result['investment']['failed_conditions'][0]['value'], -50*USD)

    def test_positive_cash_from_initial_equity_is_not_profit(self):
        self.account.cost('failed-search', 10*USD, 0)
        states = self.states()
        self.assertEqual(states['available_cash']['cash'], 99_990*USD)
        self.assertEqual(states['accounting_profit']['lifetime_microUSD'], -10*USD)
        self.assertEqual(self.decide(states)['commercial']['verdict'], 'NOT_ESTABLISHED')

    def test_positive_current_profit_incomplete_payback_and_seed_funded_investment(self):
        self.account.cost('development', 1000*USD, 0)
        start = len(self.account.export()['ledger']['actions'])
        self.profitable()
        states = self.states(development_ids=['development'], period_start_sequence=start)
        self.assertEqual(states['accounting_profit']['period']['profit'], 270*USD)
        self.assertEqual(states['project_payback']['unrecovered_microUSD'], 730*USD)
        result = self.decide(states, investment={'cost_microUSD': 100*USD,
                'incremental_benefit_microUSD': 150*USD, 'allow_seed': True})
        self.assertEqual(result['investment']['verdict'], 'CONDITIONAL_GO')
        self.assertEqual(result['investment']['prospective_funding'], 'SEED')
        self.assertFalse(result['investment']['project_payback_complete'])

    def test_unpaid_liability_and_expense_survive_insufficient_cash(self):
        self.account.cost('incurred-unfunded-work', 100_050*USD, 0)
        states = self.states()
        self.assertEqual(states['accounting_profit']['lifetime_microUSD'], -100_050*USD)
        self.assertEqual(states['available_cash']['payables'], 50*USD)
        self.assertEqual(states['available_cash']['available'], 0)

    def test_development_once_and_duplicate_amortization_policy_refused(self):
        self.account.cost('development', 100*USD, 0)
        original = self.account.export()
        self.account.cost('development', 100*USD, 0)
        self.assertEqual(self.account.export(), original)
        states = self.states(development_ids=['development'])
        self.assertEqual(states['accounting_profit']['lifetime_microUSD'], -100*USD)
        self.assertEqual(states['available_cash']['cash'], 99_900*USD)
        with self.assertRaisesRegex(ValueError, 'NO_DUPLICATE_AMORTIZATION'):
            self.states(development_ids=['development'], accounting_policy='capitalized-plus-expense')

    def test_opening_equity_investment_never_becomes_profit_funded(self):
        receipt = self.account.spend('seed-instrument', 'construction', 10*USD, 0,
                                     {'purpose': 'declared seed construction'}, expected_net=20*USD, allow_seed=True)
        self.assertEqual(receipt['funding'], 'SEED')
        funding = self.states()['investment_funding']
        self.assertEqual(funding[0]['funding'], 'SEED')
        self.assertEqual(self.states()['available_cash']['unrestrictedEarned'], 0)

    def test_failed_delivery_refund_retains_execution_cost(self):
        job = next(j for j in self.manifest['jobs'] if j['service_id'] == 'reconciliation')
        from enterprise.services import produce, synthetic_order
        order = synthetic_order('reconciliation', 0)
        artifact = produce('reconciliation', order)
        artifact['totals']['invoice_cents'] += 1
        self.assertFalse(audit_delivery('reconciliation', order, artifact)['accepted'])
        self.account.execute('wallet', {'buyer': 'failed', 'amount': 100*USD}, 0)
        self.account.execute('offer', {'id': 'failed', 'buyer': 'failed', 'price': 100*USD,
            'job_id': job['id'], 'deadline': 2}, 0)
        for action in ('consent', 'fund'):
            self.account.execute('event', {'id': 'failed', 'action': action, 'event_id': action}, 0)
        self.account.cost('failed-execution-and-checking', 7*USD, 1)
        self.account.execute('event', {'id': 'failed', 'action': 'refund', 'event_id': 'refund'}, 1)
        states = self.states()
        self.assertEqual(states['accounting_profit']['lifetime_microUSD'], -7*USD)
        self.assertEqual(states['accounting_profit']['period']['revenue'], 0)
        self.assertEqual(states['native_delivery_counts']['accepted_and_released'], 0)
        self.assertEqual(states['available_cash']['custodyReserve'], 0)

    def test_no_incremental_successor_value_does_not_stop_base(self):
        self.profitable()
        result = self.decide(successor_comparison=self.comparison())
        self.assertEqual(result['commercial']['verdict'], 'CONDITIONAL_GO')
        self.assertEqual(result['successor']['verdict'], 'NOT_ESTABLISHED')

    def test_unfunded_investment_rejected_even_with_positive_forecast(self):
        result = self.decide(investment={'cost_microUSD': 100_001*USD,
                             'incremental_benefit_microUSD': 200_000*USD, 'allow_seed': True})
        self.assertEqual(result['investment']['verdict'], 'NOT_ESTABLISHED')
        self.assertIn('available_microUSD', [r['metric'] for r in result['investment']['failed_conditions']])

    def test_qualification_cannot_invent_accepted_release_counts(self):
        with self.assertRaisesRegex(ValueError, 'COUNTS_MUST_MATCH'):
            qualifications(self.states(), accepted_deliveries=1, completed_cycles=1,
                           modeled_cost_scope_complete=True)

    def test_blue_sky_requires_threshold_crossing_not_one_micro_cost_saving(self):
        self.profitable()
        comparison = self.comparison(blue=True, without_asset_complete_cost_microUSD=20*USD+1)
        result = self.decide(kernel_comparison=comparison)
        self.assertEqual(result['blue_sky_flagship']['verdict'], 'NOT_ESTABLISHED')
        condition = result['blue_sky_flagship']['failed_conditions'][0]
        self.assertEqual(condition['metric'], 'consequential_feasibility_threshold')
        self.assertEqual(condition['threshold'], 1)

    def test_unpaid_development_is_not_fully_paid_back(self):
        self.account.cost('development', 100_050*USD, 0)
        states = self.states(development_ids=['development'])
        self.assertEqual(states['project_payback']['unpaid_development_microUSD'], 50*USD)
        self.assertEqual(states['project_payback']['unrecovered_microUSD'], 100_050*USD)

    @staticmethod
    def comparison(blue=False, **changes):
        result = {'with_asset_accepted': 3, 'without_asset_accepted': 3,
                  'with_asset_complete_cost_microUSD': 20*USD, 'without_asset_complete_cost_microUSD': 20*USD,
                  'matched_resources': True, 'fresh_work': True, 'evidence_sha256': digest({'fixture': 'numerical-regression'})}
        if blue:
            result.update(consequential_outcome='Registered regression outcome', minimum_accepted_outcomes=1)
        return {**result, **changes}


class Transformational063CampaignAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='transformational063-native-campaign-')
        cls.baseline = Path(cls.tmp.name)/'baseline'
        run(ROOT, cls.baseline)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix='transformational063-public-audit-'))
        for name in ('source', 'public'):
            shutil.copytree(self.baseline/name, self.case/name)
        for name in ('REPORT.json', 'SOURCE.json', 'PROTOCOL.json'):
            shutil.copyfile(self.baseline/name, self.case/name)

    def tearDown(self):
        shutil.rmtree(self.case)

    def mutate_row(self, change):
        import json
        from commercial.ledger import canonical
        result = self.case/'public/central/result.json'
        row = json.loads(result.read_text())
        change(row)
        result.write_bytes(canonical(row))
        report_path = self.case/'REPORT.json'
        report = json.loads(report_path.read_text())
        report['scenarios']['central']['result_sha256'] = digest(row)
        report_path.write_bytes(canonical(report))

    def test_complete_key_free_campaign_replays(self):
        self.assertTrue(audit(self.case)['accepted'])
        self.assertFalse((self.case/'private').exists())

    def test_empty_source_and_scenario_omission_fail_closed(self):
        import json
        from commercial.ledger import canonical
        (self.case/'SOURCE.json').write_bytes(canonical({'files': {}, 'sha256': digest({})}))
        with self.assertRaisesRegex(ValueError, 'COMPLETE_SOURCE_COVERAGE'):
            audit(self.case)
        shutil.copyfile(self.baseline/'SOURCE.json', self.case/'SOURCE.json')
        report = json.loads((self.case/'REPORT.json').read_text())
        report['scenarios'] = {}
        (self.case/'REPORT.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'SCENARIO_COVERAGE'):
            audit(self.case)

    def test_rehashed_fabricated_buyer_choice_is_rejected(self):
        self.mutate_row(lambda row: row['attempts'][0].update(quote_microUSD=1))
        with self.assertRaisesRegex(ValueError, 'BUYER_CHOICE_OR_QUOTE_CHANGED'):
            audit(self.case)

    def test_rehashed_fabricated_acceptance_is_rejected(self):
        self.mutate_row(lambda row: row['attempts'][0].update(accepted=False))
        with self.assertRaisesRegex(ValueError, 'ACCEPTANCE_OR_ACTUAL_ARTIFACT_CHANGED'):
            audit(self.case)

    def test_rehashed_fabricated_successor_advantage_is_rejected(self):
        self.mutate_row(lambda row: row['successor']['comparison'].update(without_asset_complete_cost_microUSD=999_000_000))
        with self.assertRaisesRegex(ValueError, 'SUCCESSOR_COMPARISON_CHANGED'):
            audit(self.case)

    def test_fabricated_public_go_and_capital_are_rejected(self):
        import json
        from commercial.ledger import canonical
        path = self.case/'REPORT.json'
        report = json.loads(path.read_text())
        report['scenarios']['copycat']['commercial'] = 'CONDITIONAL_GO'
        path.write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'PUBLIC_SUMMARY_CHANGED'):
            audit(self.case)
        report['primary_seed_microUSD'] = 0
        path.write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'REPORT_SCOPE_OR_CAPITAL_CHANGED'):
            audit(self.case)

    def test_frozen_source_replays_in_separate_process(self):
        import os
        import subprocess
        import sys
        env = dict(os.environ, PYTHONPATH=str(self.case/'source'))
        completed = subprocess.run([sys.executable, '-m', 'connected_enterprise.transformational063',
            'audit', '--output', str(self.case)], cwd=self.case/'source', env=env,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stderr)
