import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from commercial.ledger import TapeExchange, audit
from enterprise.frontier import BUDGET, SOURCES, run_frontier
from enterprise.services import SOURCE_PATHS, prepare_services

ROOT = Path(__file__).resolve().parents[1]


class FrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='enterprise011-frontier-test-')
        cls.root = Path(cls.temp.name)
        for source in set(SOURCE_PATHS) | set(SOURCES):
            target = cls.root / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, target)
        cls.manifest = prepare_services(cls.root, 'services')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def result(self, paid=True):
        with tempfile.TemporaryDirectory() as temporary:
            exchange = TapeExchange(Path(temporary) / 'base.sqlite', root=self.root, manifest=self.manifest, opening=5_000_000_000, working=100_000_000, contract='frontier-test', durable=False)
            try:
                exchange.execute('cost', {'id': 'complete-base-cost', 'amount': 5_000_000}, 0)
                if paid:
                    job = self.manifest['jobs'][0]['id']
                    exchange.execute('wallet', {'buyer': 'buyer', 'amount': 100_000_000}, 0)
                    exchange.execute('offer', {'id': 'sale', 'buyer': 'buyer', 'price': 100_000_000, 'job_id': job, 'deadline': 10}, 0)
                    for action in ['consent', 'fund', 'prepare', 'release']:
                        exchange.execute('event', {'id': 'sale', 'action': action, 'event_id': 'sale-' + action}, 1)
                tape = exchange.export()
            finally:
                exchange.close()
        return {'scope': 'SIMULATED', 'summary': tape['summary'], 'ledger': tape}

    def test_earned_funding_and_independent_native_accounting(self):
        base = self.result()
        preserved = copy.deepcopy(base)
        report = run_frontier(self.root, self.manifest, base)
        self.assertEqual(base, preserved)
        self.assertEqual(report['funding_status'], 'SIMULATED_UNRESTRICTED_EARNINGS_RESERVED_AND_SPENT')
        self.assertEqual(report['before']['cash'] - report['after']['cash'], BUDGET)
        self.assertEqual(report['before']['tailReserve'], report['after']['tailReserve'])
        self.assertEqual(report['before']['workingCapital'], report['after']['workingCapital'])
        self.assertEqual(report['before']['collections'], report['after']['collections'])
        self.assertTrue(audit(report['supplemental_ledger'], root=self.root, manifest=self.manifest)['accepted'])

    def test_no_earned_funds_means_no_experiment_or_seed_spend(self):
        base = self.result(paid=False)
        report = run_frontier(self.root, self.manifest, base)
        self.assertEqual(report['funding_status'], 'SKIPPED_INSUFFICIENT_UNRESTRICTED_EARNINGS')
        self.assertIsNone(report['experiment'])
        self.assertIsNone(report['supplemental_ledger'])
        self.assertEqual(report['before'], report['after'])

    def test_counterexample_repair_and_equal_content_controls(self):
        report = run_frontier(self.root, self.manifest, self.result())
        experiment = report['experiment']
        self.assertFalse(experiment['critic_counterexample']['receipt']['interrupted_marker'])
        self.assertTrue(experiment['repair_receipt']['independent_contract_check'])
        self.assertTrue(experiment['donor_target_mapping'][0]['applicable'])
        self.assertFalse(experiment['failed_transfer'][0]['applicable'])
        self.assertEqual(experiment['capability_compounding'], 'NOT_ESTABLISHED')
        self.assertEqual(experiment['blue_sky_enablement'], 'NOT_ESTABLISHED')
        for fresh in experiment['fresh_comparisons']:
            self.assertTrue(fresh['same_content_comparison'])
            for arm in fresh['arms'].values():
                self.assertTrue(arm['all_interruption_contracts_pass'])
                self.assertTrue(arm['executed_receipts'][0]['artifact_files'])
        self.assertEqual(experiment['failed_scope_retrieval']['records'], [])
        self.assertTrue(experiment['failed_scope_retrieval']['failures'])

    def test_summary_tampering_cannot_fund_frontier(self):
        result = self.result()
        result['summary']['unrestrictedEarned'] += 100
        with self.assertRaises(ValueError):
            run_frontier(self.root, self.manifest, result)

    def test_actual_scope_refused(self):
        result = self.result()
        result['scope'] = 'ACTUAL'
        with self.assertRaises(ValueError):
            run_frontier(self.root, self.manifest, result)

    def test_research_value_is_declared_assumption_not_income(self):
        report = run_frontier(self.root, self.manifest, self.result())
        valuation = report['research_valuation']
        self.assertEqual(valuation['expected_net_value_microUSD'], 5_000_000)
        self.assertEqual(valuation['hypothesis']['expected_avoided_rework_microUSD'], 30_000_000)
        self.assertEqual(valuation['actual_economic_benefit'], 'UNKNOWN')
        self.assertFalse(valuation['zero_expected_benefit_alternative']['would_invest'])
        self.assertEqual(report['after']['revenue'], report['before']['revenue'])

    def test_zero_research_value_defers_optional_investment(self):
        report = run_frontier(self.root, self.manifest, self.result(), research_hypothesis={'expected_avoided_rework_microUSD': 0, 'basis': 'Alternative assumption: no future useful recovery work is expected.'})
        self.assertEqual(report['funding_status'], 'SKIPPED_NONPOSITIVE_RESEARCH_VALUE_HYPOTHESIS')
        self.assertEqual(report['before'], report['after'])
        self.assertIsNone(report['supplemental_ledger'])
        self.assertIsNone(report['experiment'])
