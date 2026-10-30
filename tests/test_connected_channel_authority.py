import copy
import json
import unittest

from commercial.ledger import digest
from connected_enterprise.channels import ChannelBook, default_contracts
from connected_enterprise.verify import _check_customer_lifecycle, check_channels


class SeededChannelAuthority(unittest.TestCase):
    def fixture(self, seed=1, reliability=10000, realization=10000, lead=1, duration=5, retries=1, delay=2, days=None):
        terms = default_contracts(); terms['pilot'].update(activation_reliability_bps=reliability, realization_bps=realization,
            lead_days=lead, duration_days=duration, prepaid_retry_attempts=retries, retry_delay_days=delay,
            failure_credit_bps=2500, contact_cooldown_days=0, max_contacts_per_customer=100)
        buyers = [{'id': 'customer-' + str(i).zfill(2)} for i in range(10)]
        book = ChannelBook(seed, terms); bought = book.purchase('pilot', 0, 'paid-plan')
        for day in (range(10) if days is None else days):book.expose(day, buyers)
        investments = [{'plan_id': 'paid-plan', 'kind': 'acquisition', 'cost': bought['invoice_microUSD'],
                        'purchased_time': 0, 'activation_time': lead * 24, 'expiry_time': (lead + duration) * 24}]
        return book.export(), investments, buyers, terms

    def forged(self, field):
        channels, investments, buyers, terms = self.fixture(days=[0, 1])
        terms['pilot'][field] = 0
        channels['instances']['paid-plan']['terms'][field] = 0
        channels['purchase_receipts']['paid-plan']['terms'][field] = 0
        channels['binding_sha256'] = digest({'seed': 1, 'contracts': terms})
        return channels, investments, buyers, terms

    def test_forged_zero_reliability_activation_cannot_grant_reach(self):
        channels, investments, buyers, terms = self.forged('activation_reliability_bps')
        self.assertEqual(channels['exposures_by_day']['1']['realized_exposures'], 2)
        with self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
            check_channels(channels, investments, buyers, contracts=terms, seed=1)

    def test_forged_zero_realization_cannot_grant_reach(self):
        channels, investments, buyers, terms = self.forged('realization_bps')
        with self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
            check_channels(channels, investments, buyers, contracts=terms, seed=1)

    def test_valid_seeded_activation_retry_failure_and_expiry_replays(self):
        for seed in [1, 2, 3]:
            for reliability in [0, 5000, 10000]:
                with self.subTest(seed=seed, reliability=reliability):
                    channels, investments, buyers, terms = self.fixture(seed=seed, reliability=reliability)
                    self.assertEqual(check_channels(channels, investments, buyers, contracts=terms, seed=seed)['paid_channel_contracts_checked'], 1)
        for lead, duration, retries, delay, days in [(0, 1, 2, 1, [0, 1]), (2, 2, 3, 3, [0, 9]), (2, 8, 3, 2, [0, 3, 9, 10])]:
            with self.subTest(lead=lead, duration=duration, days=days):
                channels, investments, buyers, terms = self.fixture(reliability=0, lead=lead, duration=duration, retries=retries, delay=delay, days=days)
                check_channels(channels, investments, buyers, contracts=terms, seed=1)

    def test_forged_retry_or_credit_cannot_serve_as_activation_authority(self):
        channels, investments, buyers, terms = self.fixture(reliability=0)
        for field, value in [('activation_attempts', 0), ('failure_credit_due_microUSD', 0), ('state', 'ACTIVE')]:
            forged = copy.deepcopy(channels); forged['instances']['paid-plan'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
                check_channels(forged, investments, buyers, contracts=terms, seed=1)
        forged = copy.deepcopy(channels)
        retry = next(row for row in forged['events'] if row['kind'] == 'CHANNEL_ACTIVATION_FAILED_RETRY_SCHEDULED')
        retry['next_retry_day'] += 1
        with self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
            check_channels(forged, investments, buyers, contracts=terms, seed=1)

    def test_seeded_audience_order_and_shared_contact_limits_are_authoritative(self):
        channels, investments, buyers, terms = self.fixture()
        forged = copy.deepcopy(channels)
        first = next(row for row in forged['events'] if row['kind'] == 'POTENTIAL_CUSTOMER_EXPOSED')
        first['customer_id'] = buyers[-1]['id']
        with self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
            check_channels(forged, investments, buyers, contracts=terms, seed=1)
        self.assertEqual(check_channels(json.loads(json.dumps(channels)), investments, buyers, contracts=terms, seed=1),
                         check_channels(channels, investments, buyers, contracts=terms, seed=1))

    def test_shared_overlap_dedup_and_supplier_tranches_replay(self):
        terms = default_contracts()
        for values in terms.values():values.update(activation_reliability_bps=10000, realization_bps=10000, overlap_bps=10000)
        buyers = [{'id': 'customer-' + str(i).zfill(2)} for i in range(10)]
        book = ChannelBook(3, terms); investments = []
        for plan, contract in [('a', 'pilot'), ('b', 'pilot'), ('c', 'extended')]:
            receipt = book.purchase(contract, 0, plan)
            investments.append({'plan_id': plan, 'kind': 'acquisition', 'cost': receipt['invoice_microUSD'], 'purchased_time': 0,
                'activation_time': receipt['activation_day'] * 24, 'expiry_time': receipt['expiry_day'] * 24})
        for day in range(6):book.expose(day, buyers)
        check_channels(book.export(), investments, buyers, contracts=terms, seed=3)

    def test_business_calendar_rejects_extra_missing_and_noncanonical_days(self):
        for days in [{'0': {}, '1': {}, '2': {}}, {'0': {}}, {'0': {}, '01': {}}]:
            result = {'config': {'horizon_days': 2}, 'seed': 1, 'channels': {'exposures_by_day': days}}
            with self.subTest(days=sorted(days)), self.assertRaisesRegex(ValueError, 'CHANNEL_EXPOSURE_DAYS_DIFFER_FROM_FROZEN_HORIZON'):
                _check_customer_lifecycle(result)

    def test_unbound_seed_or_contracts_cannot_claim_full_channel_audit(self):
        channels, investments, buyers, terms = self.fixture()
        for kwargs in [{}, {'contracts': terms}, {'seed': 1}]:
            with self.subTest(kwargs=sorted(kwargs)), self.assertRaisesRegex(ValueError, 'FROZEN_CHANNEL_CONTRACTS_AND_SEED_REQUIRED'):
                check_channels(channels, investments, buyers, **kwargs)


if __name__ == '__main__':unittest.main()
