import copy
import unittest
from connected_enterprise.recurring055 import SCHEMA, consumed_job_ids, public_candidate, request_ids, validate_policy


def fixture():
    requests = {'SIM-customer-000': [
        {'job_id': 'period-one', 'release_hour': 24, 'expiry_hour': 48},
        {'job_id': 'period-two', 'release_hour': 72, 'expiry_hour': 96}],
        'SIM-customer-001': []}
    profile = {'id': 'public-recurrence', 'services': ['reconciliation'],
        'price_grids': {'reconciliation': [20_000_000, 40_000_000]},
        'atoms': [{'weight_bps': 5000, 'budget_microUSD': 30_000_000,
                   'values': {'reconciliation': 60_000_000}},
                  {'weight_bps': 5000, 'budget_microUSD': 100_000_000,
                   'values': {'reconciliation': 80_000_000}}],
        'outside_options': []}
    return {'horizon_days': 4, 'customer_pool': 2,
        'complete_offer_policy': {'schema': 'connected-complete-offer-market/v1',
            'selection': 'menu', 'profiles': [profile],
            'requested_jobs': {buyer: [row['job_id'] for row in rows] for buyer, rows in requests.items()}},
        'recurring_request_policy': {'schema': SCHEMA, 'jobs_per_service': 32,
            'chunk_size': 7, 'requests': requests}}


class RecurringPublicRequests055(unittest.TestCase):
    def test_released_expired_consumed_and_exhausted_windows(self):
        cfg = fixture()
        self.assertEqual(validate_policy(cfg), cfg['recurring_request_policy'])
        for moment, expected in [(0, []), (23, []), (24, ['period-one']),
                                 (47, ['period-one']), (48, []), (71, []),
                                 (72, ['period-two']), (95, ['period-two']), (96, [])]:
            self.assertEqual(request_ids(cfg, 'SIM-customer-000', moment), expected)
        self.assertEqual(request_ids(cfg, 'SIM-customer-000', 24, ['period-one']), [])
        self.assertEqual(request_ids(cfg, 'SIM-customer-000', 24, (), {'period-one'}), [])
        self.assertEqual(request_ids(cfg, 'SIM-customer-001', 24), [])

    def test_public_information_only_and_exact_affordability(self):
        cfg = fixture()
        buyer = {'id': 'SIM-customer-000', 'outside_spend': 50_000_000,
                 'our_settled_spend': 20_000_000, 'pending_commitments': {'old': 10_000_000}}
        self.assertTrue(public_candidate(cfg, buyer, 24))
        for hidden in [{'remaining_budget': 0, 'initial_budget': 0, 'seed': 1, 'case': 'adverse'},
                       {'remaining_budget': 10**30, 'initial_budget': 10**30, 'seed': 999,
                        'case': 'central', 'hidden_future': ['success']}]:
            changed = {**buyer, **hidden}
            self.assertEqual(public_candidate(cfg, changed, 24), public_candidate(cfg, buyer, 24))
        buyer['outside_spend'] += 1
        self.assertFalse(public_candidate(cfg, buyer, 24))
        buyer['outside_spend'] = 0
        self.assertFalse(public_candidate(cfg, buyer, 48))

    def test_outside_purchase_consumes_once_but_refusal_does_not(self):
        cfg = fixture()
        decline = {'kind': 'offer', 'time': 24, 'customer_id': 'SIM-customer-000',
                   'request_job_id': 'period-one', 'buyer_choice': 'decline'}
        outside = {**decline, 'time': 25, 'buyer_choice': 'self_service', 'outside_spend': 0}
        self.assertEqual(consumed_job_ids(cfg, [decline]), set())
        self.assertEqual(consumed_job_ids(cfg, [decline, outside]), {'period-one'})
        self.assertEqual(consumed_job_ids(cfg, [decline, outside], before=25), set())
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            consumed_job_ids(cfg, [outside, {**outside, 'time': 26}])
        self.assertEqual(consumed_job_ids(cfg, [{**outside, 'buyer_choice': 'us'}]), {'period-one'})

    def test_unknown_wrong_buyer_expired_or_unbound_decision_rejected(self):
        cfg = fixture()
        decision = {'kind': 'outside_choice', 'time': 24, 'customer_id': 'SIM-customer-000',
                    'request_job_id': 'period-one', 'buyer_choice': 'human'}
        for changes in [{'request_job_id': None}, {'customer_id': 'SIM-customer-001'},
                        {'time': 48}, {'request_job_id': 'not-admitted'}]:
            with self.assertRaises(ValueError):
                consumed_job_ids(cfg, [{**decision, **changes}])

    def test_duplicate_overlap_population_or_admission_tampering_rejected(self):
        mutators = [
            lambda c: c['recurring_request_policy'].update(extra=True),
            lambda c: c['recurring_request_policy'].update(jobs_per_service=31),
            lambda c: c['recurring_request_policy'].update(chunk_size=True),
            lambda c: c['recurring_request_policy']['requests']['SIM-customer-000'][1].update(job_id='period-one'),
            lambda c: c['recurring_request_policy']['requests']['SIM-customer-000'][1].update(release_hour=47),
            lambda c: c['recurring_request_policy']['requests']['SIM-customer-000'][1].update(expiry_hour=97),
            lambda c: c['recurring_request_policy']['requests'].pop('SIM-customer-001'),
            lambda c: c['complete_offer_policy']['requested_jobs']['SIM-customer-000'].reverse(),
        ]
        for mutate in mutators:
            cfg = fixture()
            mutate(cfg)
            with self.assertRaises(ValueError):
                validate_policy(cfg)
        cfg = fixture()
        cfg['recurring_request_policy']['requests']['SIM-customer-001'] = [
            {'job_id': 'period-one', 'release_hour': 0, 'expiry_hour': 24}]
        cfg['complete_offer_policy']['requested_jobs']['SIM-customer-001'] = ['period-one']
        with self.assertRaisesRegex(ValueError, 'UNIQUE_GLOBAL'):
            validate_policy(cfg)


if __name__ == '__main__':
    unittest.main()
