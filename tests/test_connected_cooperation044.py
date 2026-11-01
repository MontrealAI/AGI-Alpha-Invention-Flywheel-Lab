"""Small adversarial witness tests; actual native runs are separate qualification."""
import copy
import unittest
from unittest.mock import patch
from connected_enterprise.cooperation044 import attributed_component, sequence_witness, _inventory_identity, PROTOCOL


def fixture():
    first = {'id': 'first', 'job_id': 'j0', 'customer_id': 'c0', 'qualified_time': 1, 'production_time': 2,
             'acceptance_time': 3, 'collection_time': 4, 'outcome': 'SETTLED', 'price': 20,
             'complete_cost': 5, 'capacity_units': 1, 'offer': {'service_id': 'small'},
             'service_receipt': {'accepted': True}, 'capacity_source_plan_ids': []}
    second = {'id': 'second', 'job_id': 'j1', 'customer_id': 'c1', 'qualified_time': 10, 'production_time': 11,
              'acceptance_time': 12, 'collection_time': 13, 'outcome': 'SETTLED', 'price': 50,
              'complete_cost': 8, 'capacity_units': 3, 'offer': {'service_id': 'large'},
              'service_receipt': {'accepted': True, 'actual_execution_artifact_sha256': 'a'*64},
              'capacity_source_plan_ids': ['p1', 'p1'], 'joint_allocation_sha256': 'delivery', 'joint_option_id': 'sell'}
    investment = {'id': 'buy', 'plan_id': 'p1', 'cost': 6, 'purchased_time': 5, 'activation_time': 6,
                  'expiry_time': 20, 'capacity_units': 2, 'kind': 'capacity', 'funding_receipt': {'funding': 'EARNED'}}
    row = {'quantity': 2, 'invoice': 6, 'slots': 3, 'scenario_net': {'central': '34'},
           'selected_work': [{'job_id': 'j1'}], 'status': 'RESOLVED'}
    plan = {'id': 'planning', 'time': 5, 'observed_need_ids': ['c1'],
            'allocation': {'decision': {'selected': ['buy'], 'states_evaluated': 3, 'optimality_scope': 'FINITE'}},
            'capacity_recourse': {'recourse': [row]}}
    delivery = {'id': 'delivery', 'time': 10, 'allocation': {'decision': {'selected': ['sell']}}}
    choice = {'kind': 'offer', 'joint_allocation_sha256': 'delivery', 'joint_option_id': 'sell',
              'customer_id': 'c1', 'chosen': True, 'buyer_choice': 'us',
              'market_context': {'profile': {'outside_options': [{'name': 'decline'}]}}}
    return {'config': {'initial_slots': 1}, 'orders': [first, second], 'investments': [investment],
            'joint_actions': {'planning': plan, 'delivery': delivery}, 'decisions': [choice],
            'owned_account': {'ledger': {'actions': [{'op': 'reserve', 'day': 5,
                'args': {'id': 'p1', 'amount': 6}, 'before': {'available': 100, 'unrestrictedEarned': 15}}]}}}


class Cooperation044Tests(unittest.TestCase):
    def setUp(self): self.r = fixture()
    def test_sequence_is_bound_to_prospective_decisions(self):
        w = sequence_witness(self.r)
        self.assertEqual(w['component']['net_attributed_contribution_microUSD'], 36)
        self.assertEqual(w['prospective_decisions']['successor_decision_id'], 'delivery')
    def test_repeated_capacity_unit_ids_charge_invoice_once(self):
        self.assertEqual(attributed_component(self.r, {'p1'})['all_enabler_invoices_microUSD'], 6)
    def test_linked_negative_settlement_counts(self):
        o = copy.deepcopy(self.r['orders'][1]); o.update(id='loss', price=1, complete_cost=40)
        self.r['orders'].append(o)
        self.assertEqual(attributed_component(self.r, {'p1'})['net_attributed_contribution_microUSD'], -3)
        self.assertIsNone(sequence_witness(self.r))
    def test_uncollected_order_counts_cost_not_quote(self):
        o = copy.deepcopy(self.r['orders'][1]); o.update(id='bad', price=999, complete_cost=40, outcome='REFUNDED', collection_time=None)
        self.r['orders'].append(o)
        self.assertEqual(attributed_component(self.r, {'p1'})['net_attributed_contribution_microUSD'], -4)
    def test_transitive_component_counts_other_losses_and_all_invoices(self):
        i = copy.deepcopy(self.r['investments'][0]); i.update(id='other', plan_id='p2', cost=7)
        self.r['investments'].append(i)
        self.r['orders'][1]['acquisition_source_plan_id'] = 'p2'
        o = copy.deepcopy(self.r['orders'][1]); o.update(id='loss', price=0, complete_cost=20, capacity_source_plan_ids=[])
        self.r['orders'].append(o)
        c = attributed_component(self.r, {'p1'})
        self.assertEqual(c['all_enabler_invoices_microUSD'], 13)
        self.assertEqual(c['net_attributed_contribution_microUSD'], 9)
    def test_missing_required_plan_rejected(self):
        self.r['orders'][1]['acquisition_source_plan_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'MISSING_NATIVE_ENABLER'): attributed_component(self.r, {'p1'})
    def test_duplicate_plan_rejected(self):
        self.r['investments'].append(copy.deepcopy(self.r['investments'][0]))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'): attributed_component(self.r, {'p1'})
    def test_seed_funding_not_relabelled_earnings(self):
        self.r['investments'][0]['funding_receipt']['funding'] = 'SEED'
        with self.assertRaisesRegex(ValueError, 'EARNED'): sequence_witness(self.r)
    def test_positive_profit_without_earned_liquidity_cannot_fund(self):
        self.r['owned_account']['ledger']['actions'][0]['before']['unrestrictedEarned'] = 5
        with self.assertRaisesRegex(ValueError, 'LIQUIDITY'): sequence_witness(self.r)
    def test_insufficient_available_cash_cannot_fund(self):
        self.r['owned_account']['ledger']['actions'][0]['before']['available'] = 5
        with self.assertRaisesRegex(ValueError, 'LIQUIDITY'): sequence_witness(self.r)
    def test_invoice_must_match_actual_reservation(self):
        self.r['owned_account']['ledger']['actions'][0]['args']['amount'] = 3
        with self.assertRaisesRegex(ValueError, 'LIQUIDITY'): sequence_witness(self.r)
    def test_future_collection_cannot_finance_past_purchase(self):
        self.r['orders'][0]['collection_time'] = 7
        self.assertIsNone(sequence_witness(self.r))
    def test_unaccepted_first_work_is_not_a_profitable_predecessor(self):
        self.r['orders'][0]['service_receipt']['accepted'] = False
        self.assertIsNone(sequence_witness(self.r))
    def test_unaccepted_successor_refused(self):
        self.r['orders'][1]['service_receipt']['accepted'] = False
        self.assertIsNone(sequence_witness(self.r))
    def test_expired_capacity_refused(self):
        self.r['investments'][0]['expiry_time'] = 11
        self.assertIsNone(sequence_witness(self.r))
    def test_not_yet_active_capacity_refused(self):
        self.r['investments'][0]['activation_time'] = 11
        self.assertIsNone(sequence_witness(self.r))
    def test_same_capacity_does_not_establish_changed_constraint(self):
        self.r['orders'][1]['capacity_units'] = 1
        self.assertIsNone(sequence_witness(self.r))
    def test_missing_prior_decision_refused(self):
        del self.r['joint_actions']['planning']
        with self.assertRaisesRegex(ValueError, 'PREINVESTMENT'): sequence_witness(self.r)
    def test_unplanned_successor_not_a_prospective_link(self):
        self.r['joint_actions']['planning']['capacity_recourse']['recourse'][0]['selected_work'][0]['job_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'PROSPECTIVE'): sequence_witness(self.r)
    def test_missing_delivery_selection_refused(self):
        self.r['joint_actions']['delivery']['allocation']['decision']['selected'] = []
        with self.assertRaisesRegex(ValueError, 'DELIVERY_SELECTION'): sequence_witness(self.r)
    def test_buyer_refusal_preserved(self):
        self.r['decisions'][0]['chosen'] = False
        with self.assertRaisesRegex(ValueError, 'VOLUNTARY'): sequence_witness(self.r)
    def test_only_cpu_telemetry_exempt_from_matched_inventory(self):
        a = {'jobs': [{'id': 'x', 'input_sha256': 'a'}], 'resource_receipt': {'process_cpu_seconds': .1, 'model_calls': 0}}
        b = copy.deepcopy(a); b['resource_receipt']['process_cpu_seconds'] = .2
        self.assertEqual(_inventory_identity(a), _inventory_identity(b))
        b['jobs'][0]['input_sha256'] = 'b'
        self.assertNotEqual(_inventory_identity(a), _inventory_identity(b))
    def test_billing_and_calls_not_discarded_from_inventory(self):
        a = {'resource_receipt': {'model_calls': 0}}; b = {'resource_receipt': {'model_calls': 1}}
        self.assertNotEqual(_inventory_identity(a), _inventory_identity(b))
    def test_invalid_cpu_rejected(self):
        with self.assertRaises(ValueError): _inventory_identity({'resource_receipt': {'process_cpu_seconds': float('nan')}})
    def test_inherited_extra_catalogue_service_does_not_break_request_mapping(self):
        from connected_enterprise.cooperation044 import configuration
        from connected_enterprise.engine import default_config
        manifest = {'jobs': [{'id': 'extra-job', 'service_id': 'operations_bundle'}]}
        with patch('connected_enterprise.engine.fresh_account_config', return_value=(default_config(), manifest)):
            cfg, unchanged = configuration(manifest, 'central', 'earned_capacity')
        self.assertEqual(cfg['complete_offer_policy']['requested_jobs']['SIM-customer-000'], ['extra-job'])
        self.assertEqual(unchanged, manifest)
    def test_no_demand_zeros_values_without_removing_outside_options(self):
        from connected_enterprise.cooperation044 import configuration
        from connected_enterprise.engine import default_config
        with patch('connected_enterprise.engine.fresh_account_config', return_value=(default_config(), {'jobs': []})):
            cfg, _ = configuration({'jobs': []}, 'no_demand', 'earned_capacity')
        for p in cfg['complete_offer_policy']['profiles']:
            self.assertTrue(p['outside_options'])
            self.assertTrue(all(v == 0 for v in p['atoms'][0]['values'].values()))
    def test_protocol_discloses_finite_exposed_comparison(self):
        self.assertEqual(PROTOCOL['evidence_role'], 'EXPOSED_DEVELOPMENT_NOT_FRESH_CONFIRMATION')
        self.assertEqual(PROTOCOL['opening_microUSD'], 100000000000)


if __name__ == '__main__': unittest.main()
