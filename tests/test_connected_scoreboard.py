import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import canonical, digest
from connected_enterprise.scoreboard import scoreboard, _daily
from tests.test_connected_scale import fixture


class ConnectedScoreboardTests(unittest.TestCase):
    def test_daily_clock_contains_all_counted_events(self):
        result={'events':[{'kind':'EXPOSURE','time':2},{'kind':'EXPOSURE','time':20}],
                'decisions':[],'orders':[]}
        row=_daily(result,{'days':[]})[0]
        self.assertEqual((row['first_hour'],row['last_hour']),(2,20))
        self.assertEqual(row['recorded_counts']['contacts'],2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='connected-scoreboard-')
        self.output = Path(self.temp.name)
        (self.output / 'source').mkdir()
        (self.output / 'source' / 'source.py').write_bytes(b'fixed source\n')
        files = {'source.py': hashlib.sha256(b'fixed source\n').hexdigest()}
        self.source = {'files': files, 'sha256': digest(files)}
        tape = fixture()
        tape['actions'] = tape['actions'][:4]
        tape['actions_sha256'] = digest(tape['actions'])
        tape['summary'] = copy.deepcopy(tape['actions'][-1]['after'])
        tape['orders'] = tape['orders'][:1]
        self.config = {'opening': 1000, 'cost_evidence': 'Unknown actual host/model billing; authored costs.', 'limits': ['Synthetic work.']}
        self.result = {'schema': 'agi-alpha/connected014-result/v1', 'scope': 'CONDITIONAL_SIMULATION',
                       'seed': 12, 'case': 'central', 'arm': 'baseline', 'config': self.config, 'source': self.source,
                       'owned_account': {'schema': 'agi-alpha/adaptive012-owned-account/v1', 'scope': 'SIMULATED', 'ledger': tape},
                       'summary': copy.deepcopy(tape['summary']), 'complete': True,
                       'orders': [{'id': 'one', 'customer_id': 'customer', 'qualified_time': 1, 'production_time': 2,
                                   'collection_time': 24, 'acceptance_time': 2, 'price': 200, 'complete_cost': 10,
                                   'outcome': 'SETTLED', 'service_receipt': {'accepted': True}, 'offer': {'service_id': 'reconciliation'}}],
                       'decisions': [{'kind': 'offer', 'time': 1, 'customer_id': 'customer', 'buyer_choice': 'us'}],
                       'events': [{'id': 'contact', 'kind': 'EXPOSURE', 'time': 0}], 'investments': [],
                       'costs': [{'id': 'resources', 'amount': 10, 'category': 'production_contract', 'time': 1},
                                 {'id': 'setup', 'amount': 30, 'category': 'setup', 'time': 0}],
                       'actual_customers': 0, 'actual_collections': 0, 'actual_profit': None,
                       'resource_receipt': {'process_cpu_seconds': .01, 'billing': 'UNAVAILABLE'}}
        self.frozen = {'schema': 'agi-alpha/connected014-freeze/v1', 'source': self.source, 'protocol': {'central_seeds': [12], 'adverse_seeds': [],
                                                         'channel_control_seeds': [], 'arms': ['baseline'], 'cases': ['central']},
                       'configs': {'central': self.config}}
        self.frozen['sha256'] = digest(self.frozen)
        self.task = {'seed': 12, 'case': 'central', 'arm': 'baseline', 'id': '12-central-baseline'}
        self.report = {'schema': 'agi-alpha/connected014-report/v1', 'scope': 'CONDITIONAL_SIMULATION',
                       'source_sha256': self.source['sha256'], 'frozen_sha256': self.frozen['sha256'],
                       'worlds': 1, 'worlds_index': [{'task': self.task, 'result_sha256': digest(self.result)}]}
        self.directory = self.output / 'worlds' / self.task['id']
        self.directory.mkdir(parents=True)
        self.write('FROZEN.json', self.frozen)
        self.write('worlds/' + self.task['id'] + '/AUDIT.json', {'accepted': True})
        self.save_result()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        (self.output / path).write_bytes(canonical(value) + b'\n')

    def save_report(self):
        self.write('REPORT.json', self.report)
        self.write('COMPLETE.json', {'source_sha256': self.source['sha256'],
                                     'report_sha256': digest(self.report), 'worlds': self.report['worlds']})

    def save_result(self):
        self.write('worlds/' + self.task['id'] + '/RESULT.json', self.result)
        self.report['worlds_index'][0]['result_sha256'] = digest(self.result)
        self.save_report()

    def test_records_full_profit_liquidity_and_unknown_costs_without_annualizing(self):
        shown = scoreboard(self.output)
        world = shown['businesses'][0]
        self.assertEqual(world['financial_state_microUSD']['profit'], 160)
        self.assertEqual(world['financial_state_microUSD']['tailReserve'], 200)
        self.assertEqual(world['cash_generation_microUSD'], 160)
        self.assertEqual(world['recorded_counts']['settled_orders'], 1)
        self.assertEqual(world['recorded_counts']['repeat_paying_customers'], 0)
        self.assertEqual(world['cohorts_and_nonadditive_investment_attribution']['whole_enterprise_cost_allocation']['allocated_complete_cost_microUSD'], 40)
        self.assertIsNone(world['measured_host_billing_microUSD'])
        self.assertIsNone(world['measured_frontier_inference_billing_microUSD'])
        self.assertIsNone(world['ratios']['retention_fraction'])
        self.assertIsNone(world['trailing_twelve_month_profit_microUSD'])
        self.assertIsNone(world['actual_external_commerce']['profit_microUSD'])
        self.assertIsNone(world['account_identity'])
        self.assertNotIn('annualized_collections_run_rate_microUSD', json.dumps(shown))
        self.assertEqual(shown['target_status'], 'NOT_ESTABLISHED_BY_THIS_SCOREBOARD')

    def test_read_only_display_does_not_certify_recorded_audit_or_open_live_account(self):
        before = {p.relative_to(self.output): p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        world = scoreboard(self.output)['businesses'][0]
        after = {p.relative_to(self.output): p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(world['verification']['stored_audit_accepted'])
        self.assertIn('NOT_ACCOUNT_AUTHORITY_AUDIT', world['verification']['financial_display'])
        self.assertEqual(world['growth_ledger'][0]['recorded_counts']['contacts'], 1)
        self.assertEqual(world['growth_ledger'][1]['recorded_counts']['settled_orders'], 1)

    def test_declared_complete_year_displays_reconciled_observer_without_certifying_authority(self):
        self.config['horizon_days'] = 365
        self.frozen.pop('sha256')
        self.frozen['sha256'] = digest(self.frozen)
        self.write('FROZEN.json', self.frozen)
        self.report['frozen_sha256'] = self.frozen['sha256']
        self.save_result()
        world = scoreboard(self.output)['businesses'][0]
        self.assertEqual(world['trailing_twelve_month_profit_microUSD'], 160)
        self.assertEqual(world['trailing_365_profit_observer']['interval']['end_hour_exclusive'], 8760)
        self.assertEqual(world['annual_profit_status'], 'RECONCILED_DECLARED_365_DAY_MODELED_WINDOW')
        self.assertIn('NOT_ACCOUNT_AUTHORITY_AUDIT', world['verification']['financial_display'])
        self.assertIsNone(world['actual_external_commerce']['profit_microUSD'])

    def test_declared_short_horizon_remains_unavailable_even_with_profit(self):
        self.config['horizon_days'] = 364
        self.frozen.pop('sha256')
        self.frozen['sha256'] = digest(self.frozen)
        self.write('FROZEN.json', self.frozen)
        self.report['frozen_sha256'] = self.frozen['sha256']
        self.save_result()
        world = scoreboard(self.output)['businesses'][0]
        self.assertIsNone(world['trailing_twelve_month_profit_microUSD'])
        self.assertFalse(world['trailing_365_profit_observer']['complete_365_day_operating_history'])

    def test_separately_seeded_businesses_are_retained_without_pooled_money(self):
        second = copy.deepcopy(self.result)
        second['seed'] = 13
        task = {**self.task, 'seed': 13, 'id': '13-central-baseline'}
        self.frozen['protocol']['central_seeds'].append(13)
        self.frozen.pop('sha256')
        self.frozen['sha256'] = digest(self.frozen)
        self.write('FROZEN.json', self.frozen)
        self.report.update(worlds=2, frozen_sha256=self.frozen['sha256'])
        self.report['worlds_index'].append({'task': task, 'result_sha256': digest(second)})
        directory = self.output / 'worlds' / task['id']
        directory.mkdir()
        self.write('worlds/' + task['id'] + '/RESULT.json', second)
        self.write('worlds/' + task['id'] + '/AUDIT.json', {'accepted': True})
        self.save_report()
        shown = scoreboard(self.output)
        self.assertEqual(shown['world_count'], 2)
        self.assertEqual([row['seed'] for row in shown['businesses']], [12, 13])
        self.assertNotIn('financial_state_microUSD', shown)
        self.assertNotIn('profit', shown)

    def test_missing_or_duplicate_business_is_rejected_even_with_rebound_report(self):
        self.report['worlds_index'].append(copy.deepcopy(self.report['worlds_index'][0]))
        self.report['worlds'] = 2
        self.save_report()
        with self.assertRaisesRegex(ValueError, 'BUSINESS_DUPLICATE'):
            scoreboard(self.output)
        self.report['worlds_index'] = self.report['worlds_index'][:1]
        self.report['worlds'] = 1
        self.frozen['protocol']['central_seeds'].append(13)
        self.frozen.pop('sha256')
        self.frozen['sha256'] = digest(self.frozen)
        self.write('FROZEN.json', self.frozen)
        self.report['frozen_sha256'] = self.frozen['sha256']
        self.save_report()
        with self.assertRaisesRegex(ValueError, 'REGISTERED_BUSINESS_SET'):
            scoreboard(self.output)

    def test_result_hash_and_native_summary_changes_fail_closed(self):
        changed = copy.deepcopy(self.result)
        changed['summary']['profit'] += 1
        self.write('worlds/' + self.task['id'] + '/RESULT.json', changed)
        with self.assertRaisesRegex(ValueError, 'WORLD_RESULT_BINDING'):
            scoreboard(self.output)
        self.result = changed
        self.save_result()
        with self.assertRaisesRegex(ValueError, 'NATIVE_SUMMARY'):
            scoreboard(self.output)

    def test_native_cash_error_is_rejected_even_after_all_output_hashes_are_updated(self):
        tape = self.result['owned_account']['ledger']
        tape['actions'][-1]['after']['cash'] += 1
        tape['summary']['cash'] += 1
        self.result['summary']['cash'] += 1
        tape['actions_sha256'] = digest(tape['actions'])
        self.save_result()
        with self.assertRaisesRegex(ValueError, 'CASH_OR_PROFIT'):
            scoreboard(self.output)

    def test_changed_source_and_completion_are_rejected(self):
        (self.output / 'source' / 'source.py').write_bytes(b'changed\n')
        with self.assertRaisesRegex(ValueError, 'FROZEN_SOURCE_BYTES_CHANGED'):
            scoreboard(self.output)
        (self.output / 'source' / 'source.py').write_bytes(b'fixed source\n')
        self.write('COMPLETE.json', {'source_sha256': self.source['sha256'], 'report_sha256': '0' * 64, 'worlds': 1})
        with self.assertRaisesRegex(ValueError, 'COMPLETION_OR_REPORT'):
            scoreboard(self.output)

    def test_missing_file_and_symlink_are_actionable_errors(self):
        target = self.directory / 'AUDIT.json'
        target.unlink()
        with self.assertRaisesRegex(ValueError, 'REQUIRED_FILE_MISSING:.*AUDIT'):
            scoreboard(self.output)
        target.symlink_to(self.output / 'REPORT.json')
        with self.assertRaisesRegex(ValueError, 'SYMLINK_REFUSED'):
            scoreboard(self.output)

    def test_zero_offer_denominators_remain_unknown(self):
        self.result['decisions'] = []
        self.save_result()
        shown = scoreboard(self.output)['businesses'][0]
        self.assertIsNone(shown['ratios']['qualified_per_offer'])
        self.assertIsNone(shown['ratios']['settled_per_offer'])


if __name__ == '__main__':
    unittest.main()
