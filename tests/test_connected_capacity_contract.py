import copy
import unittest

from connected_enterprise.verify import _check_investments


class CapacityContractChecks(unittest.TestCase):
    def fixture(self):
        receipt = {'plan_id': 'paid-capacity', 'funding': 'EARNED', 'day': 24}
        request = {'operation': 'spend', 'id': 'capacity-1', 'kind': 'capacity_contract',
                   'amount': 8_000_000, 'day': 24, 'expected_net': 10_000_000,
                   'work': {'units_per_day': 1, 'lead_hours': 24, 'duration_hours': 48}}
        investment = {'id': 'capacity-1', 'plan_id': 'paid-capacity', 'kind': 'capacity',
                      'purchased_time': 24, 'activation_time': 48, 'expiry_time': 96,
                      'cost': 8_000_000, 'funding_receipt': receipt, 'predicted_net': 10_000_000}
        result = {'investments': [investment], 'config': {'capacity_lead_hours': 24,
                  'capacity_duration_hours': 48, 'initial_slots': 1, 'maximum_slots': 2,
                  'supplier_outage_start_day': -1, 'supplier_outage_days': 0},
                  'channels': {'contacts': {}}, 'buyers': [{'id': 'owned-buyer'}],
                  'owned_account': {'connected_journal': {'entries': [{'request': request, 'receipt': receipt}]}}}
        tape = {'actions': [{'op': 'reserve', 'args': {'id': 'paid-capacity'}, 'day': 24,
                             'before': {'unrestrictedEarned': 20_000_000}},
                            {'op': 'finish', 'args': {'id': 'paid-capacity', 'amount': 8_000_000}, 'day': 24}]}
        orders = {'order': {'customer_id': 'owned-buyer', 'qualified_time': 48, 'production_time': 50,
                            'capacity_source_plan_id': 'paid-capacity', 'outcome': 'SETTLED'}}
        return result, tape, orders

    def check(self, result, tape, orders):
        return _check_investments(result, tape, orders)

    def test_valid_financed_lifetime_and_actual_use_pass(self):
        self.assertEqual(self.check(*self.fixture()), {'productive_investments_checked': 1,
                                                      'settled_capability_uses_checked': 1})

    def test_early_activation_extended_or_missing_expiry_reject(self):
        for field, value in [('activation_time', 24), ('expiry_time', 100096), ('expiry_time', None)]:
            result, tape, orders = self.fixture(); result['investments'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'CAPACITY_LIFETIME|CAPACITY_EXPIRY'):
                self.check(result, tape, orders)

    def test_purchase_time_cannot_move_away_from_native_invoice(self):
        result, tape, orders = self.fixture()
        result['investments'][0].update(purchased_time=25, activation_time=49, expiry_time=97)
        with self.assertRaisesRegex(ValueError, 'CAPACITY_PURCHASE_NOT_BOUND'):
            self.check(result, tape, orders)

    def test_financed_terms_must_be_typed_positive_and_frozen(self):
        for field in ['lead_hours', 'duration_hours', 'units_per_day']:
            for value in [None, True, 0, -1, '24', 24.0, 999]:
                result, tape, orders = self.fixture()
                result['owned_account']['connected_journal']['entries'][0]['request']['work'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.check(result, tape, orders)
        for field in ['capacity_lead_hours', 'capacity_duration_hours']:
            result, tape, orders = self.fixture(); result['config'][field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(result, tape, orders)

    def test_request_identity_kind_amount_and_day_remain_bound(self):
        for field, value in [('id', 'other'), ('kind', 'free-capacity'), ('amount', 1), ('day', 23), ('day', True)]:
            result, tape, orders = self.fixture()
            result['owned_account']['connected_journal']['entries'][0]['request'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'CAPACITY_PURCHASE_NOT_BOUND|CAPACITY_FINANCED_PURCHASE_TIME'):
                self.check(result, tape, orders)
        result, tape, orders = self.fixture(); tape['actions'][0]['day'] = 23
        with self.assertRaisesRegex(ValueError, 'CAPACITY_PURCHASE_NOT_BOUND'):
            self.check(result, tape, orders)


if __name__ == '__main__':
    unittest.main()
