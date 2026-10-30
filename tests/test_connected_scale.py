import copy
import unittest
from commercial.ledger import digest
from connected_enterprise.scale import aggregate_native, analyze, compare


def fixture():
    summary = {'collections': 0, 'recoveryIncome': 0, 'revenue': 0, 'expenses': 0, 'expensePaid': 0,
               'cash': 1000, 'profit': 0, 'payables': 0, 'tailReserve': 0, 'custodyReserve': 0,
               'workingCapital': 100, 'unrestrictedEarned': 0, 'available': 900,
               'equityProtectionBacking': 100, 'investmentStopped': False}
    actions = []
    def add(hour, op, args, changes):
        before = copy.deepcopy(summary)
        summary.update(changes)
        actions.append({'seq': len(actions), 'day': hour, 'op': op, 'args': args,
                        'before': before, 'after': copy.deepcopy(summary)})
    add(0, 'cost', {'id': 'setup', 'amount': 40}, {'expenses': 40, 'expensePaid': 40, 'cash': 960, 'profit': -40, 'available': 860})
    add(1, 'offer', {'id': 'one', 'price': 200}, {})
    add(2, 'event', {'id': 'one', 'action': 'prepare'}, {})
    add(24, 'event', {'id': 'one', 'action': 'release'}, {'collections': 200, 'revenue': 200, 'cash': 1160, 'profit': 160, 'tailReserve': 200, 'unrestrictedEarned': 160})
    add(9000, 'offer', {'id': 'two', 'price': 300}, {})
    add(9001, 'event', {'id': 'two', 'action': 'prepare'}, {})
    add(9002, 'event', {'id': 'two', 'action': 'refund'}, {})
    return {'config': {'opening': 1000}, 'actions': actions, 'actions_sha256': digest(actions),
            'summary': copy.deepcopy(summary), 'receivables': 0,
            'orders': [{'id': 'one', 'state': 'released'}, {'id': 'two', 'state': 'refunded'}]}


class NativeScaleBridgeTests(unittest.TestCase):
    def test_receivables_are_not_collections_and_refund_is_preserved(self):
        result = aggregate_native(fixture(), checkpoints=(1, 2))
        self.assertEqual(result['end_state_microUSD']['collections'], 200)
        self.assertEqual(result['end_state_microUSD']['receivables'], 0)
        self.assertEqual(result['collected_deliveries'], 1)
        self.assertEqual(result['unreached_overlap_delivery_counts'], [2])
        self.assertEqual(result['overlap_checks'][0]['max_absolute_deviation_microUSD'], 0)
        self.assertEqual(result['days'][-1]['trailing_365_day_collections_microUSD'], 0)

    def test_cost_and_cash_flow_are_kept_separate(self):
        result = aggregate_native(fixture(), checkpoints=(1,))
        self.assertEqual(result['days'][0]['flow_microUSD']['expensePaid'], 40)
        self.assertEqual(result['days'][1]['flow_microUSD']['collections'], 200)
        self.assertEqual(result['end_state_microUSD']['cash_generation'], 160)

    def test_changed_summary_or_prefix_is_rejected(self):
        tape = fixture()
        tape['summary']['profit'] += 1
        with self.assertRaisesRegex(ValueError, 'FINAL_SUMMARY'):
            aggregate_native(tape)
        tape = fixture()
        tape['actions'][3]['after']['cash'] += 1
        tape['actions_sha256'] = digest(tape['actions'])
        with self.assertRaisesRegex(ValueError, 'CASH_OR_PROFIT'):
            aggregate_native(tape)

    def test_missing_milestones_are_explicit_and_no_projection_is_invented(self):
        result = analyze({'owned_account': {'ledger': fixture()}, 'config': {}, 'orders': [], 'investments': [], 'costs': []})
        self.assertEqual(len(result['milestones']), 5)
        self.assertTrue(all(row['status'] == 'NOT_REACHED_WITHIN_EXECUTED_HORIZON' for row in result['milestones']))
        self.assertEqual(result['historical_billion_models_bridge_status'], 'UNBRIDGED_NATIVE_SCALE')
        self.assertTrue(result['complete_365_day_history'])
        self.assertEqual(result['trailing_365_day_collections_microUSD'], 0)

    def test_equal_starting_capital_required(self):
        first = {'seed': 8, 'arm': 'baseline', 'config': {'customer_pool': 8}, 'owned_account': {'ledger': fixture()}}
        second = copy.deepcopy(first)
        second['arm'] = 'growth'
        second['owned_account']['ledger']['config']['opening'] = 2000
        with self.assertRaisesRegex(ValueError, 'EQUAL_STARTING_CAPITAL'):
            compare([first, second])

    def test_same_hour_receipts_do_not_use_later_action_for_earlier_crossing(self):
        tape = fixture()
        tape['actions'] = tape['actions'][:3]
        previous = copy.deepcopy(tape['actions'][-1]['after'])
        for number, amount in enumerate([600_000 * 1_000_000, 500_000 * 1_000_000]):
            after = copy.deepcopy(previous)
            for key in ['collections', 'revenue', 'cash', 'profit', 'unrestrictedEarned']:
                after[key] += amount
            tape['actions'].append({'seq': len(tape['actions']), 'day': 24, 'op': 'event',
                                    'args': {'id': 'one', 'action': 'release', 'event_id': str(number)},
                                    'before': previous, 'after': after})
            previous = after
        tape.update(actions_sha256=digest(tape['actions']), summary=previous, receivables=0)
        bridge = analyze({'owned_account': {'ledger': tape}, 'config': {}, 'orders': [], 'investments': [], 'costs': []})
        crossing = bridge['milestones'][0]['revenue_attainment']
        self.assertEqual(crossing['state_microUSD']['collections'], 1_100_000 * 1_000_000)

    def test_actual_acquisition_categories_include_failed_contact_costs_once(self):
        result = {'owned_account': {'ledger': fixture()}, 'config': {},
                  'orders': [{'id': 'one', 'customer_id': 'customer', 'collection_time': 24,
                              'price': 200, 'complete_cost': 10, 'acquisition_source_plan_id': 'plan-channel'}],
                  'investments': [{'id': 'channel', 'plan_id': 'plan-channel', 'kind': 'acquisition', 'cost': 12}],
                  'costs': [{'id': 'channel', 'category': 'acquisition_contract', 'amount': 12},
                            {'id': 'outreach', 'category': 'outreach_including_failed_and_unused_slots', 'amount': 3},
                            {'id': 'qualification', 'category': 'qualification_including_lost_offers', 'amount': 5},
                            {'id': 'production', 'category': 'production_contract', 'amount': 10},
                            {'id': 'setup', 'category': 'development_integration_qualification_and_failed_search', 'amount': 10}]}
        cohorts = analyze(result)['cohorts']
        self.assertEqual(cohorts['all_paid_channel_and_exposure_cost_microUSD'], 20)
        self.assertEqual(cohorts['acquisition_cost_per_source_linked_paying_customer_microUSD'], 20)
        allocated = cohorts['whole_enterprise_cost_allocation']
        self.assertEqual(allocated['allocated_complete_cost_microUSD'], 40)
        self.assertEqual(allocated['cohorts']['first_collected']['allocated_complete_cost_microUSD'], 40)
        self.assertEqual(cohorts['investment_attribution'][0]['attributed_collections_microUSD'], 200)

    def test_shared_setup_allocated_once_including_failed_work(self):
        result = {'owned_account': {'ledger': fixture()}, 'config': {},
                  'orders': [{'id': 'one', 'customer_id': 'customer', 'collection_time': 24, 'price': 200, 'complete_cost': 10},
                             {'id': 'two', 'customer_id': 'customer', 'collection_time': None, 'price': 300, 'complete_cost': 10}],
                  'investments': [], 'costs': [{'id': 'resources', 'amount': 20, 'category': 'production_contract'},
                                             {'id': 'setup', 'amount': 20, 'category': 'development_integration_qualification_and_failed_search'}]}
        allocation = analyze(result)['cohorts']['whole_enterprise_cost_allocation']
        self.assertEqual(allocation['allocated_complete_cost_microUSD'], 40)
        self.assertEqual(allocation['cohorts']['first_collected']['shared_enterprise_cost_microUSD'], 10)
        self.assertEqual(allocation['cohorts']['noncollected']['shared_enterprise_cost_microUSD'], 10)

    def test_channel_payback_charges_pending_and_failed_attempts_before_collection(self):
        result = {'owned_account': {'ledger': fixture()}, 'config': {},
                  'orders': [{'id': 'one', 'customer_id': 'customer', 'qualified_time': 1, 'collection_time': 24,
                              'price': 200, 'complete_cost': 10, 'acquisition_source_plan_id': 'plan'},
                             {'id': 'two', 'customer_id': 'customer', 'qualified_time': 2, 'collection_time': None,
                              'price': 300, 'complete_cost': 10, 'acquisition_source_plan_id': 'plan'}],
                  'investments': [{'id': 'channel', 'plan_id': 'plan', 'kind': 'acquisition', 'purchased_time': 0, 'cost': 12}],
                  'costs': []}
        row = analyze(result)['cohorts']['investment_attribution'][0]
        self.assertEqual(row['attributed_direct_complete_cost_microUSD'], 20)
        self.assertEqual(row['all_linked_attempt_order_ids'], ['one', 'two'])
        self.assertEqual(row['attributed_scoped_contribution_microUSD'], 168)
        self.assertEqual(row['attributed_payback_hour'], 24)


if __name__ == '__main__':
    unittest.main()
