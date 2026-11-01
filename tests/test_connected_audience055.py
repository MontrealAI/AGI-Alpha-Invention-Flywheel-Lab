import copy
import unittest

from connected_enterprise.audience055 import SCHEMA, owned_customer_ids, reachability, validate_policy
from connected_enterprise.channel_menu import menu_options
from connected_enterprise.channels import ChannelBook, audit_channel_history
from connected_enterprise.engine import _buyers, default_config


def fixture(count=2, total=6):
    cfg = default_config()
    cfg.update(customer_pool=total, horizon_days=30)
    cfg['audience_policy'] = {'schema': SCHEMA, 'owned_audience_count': count}
    cfg['channel_menu_policy'] = {'schema': 'connected-channel-menu/v1', 'contract_ids': ['pilot'], 'conversion_bps': 10000}
    for terms in cfg['channels'].values():
        terms.update(owned_audience_count=count, activation_reliability_bps=10000, realization_bps=10000,
            overlap_bps=0, lead_days=2, duration_days=7)
    buyers = {f'SIM-customer-{i:03d}': {'id': f'SIM-customer-{i:03d}', 'known': i < count,
        'onboarded': False, 'active': True, 'pending_commitments': {}, 'next_need_time': 0} for i in range(total)}
    return cfg, buyers


class AudienceAdmission(unittest.TestCase):
    def test_registered_initial_and_channel_audience_have_one_definition(self):
        for count in (0, 2, 6):
            cfg, buyers = fixture(count)
            self.assertEqual(owned_customer_ids(cfg, buyers), set(sorted(buyers)[:count]))
            actual = _buyers(cfg, 13)
            self.assertEqual({b['id'] for b in actual if b['known']}, owned_customer_ids(cfg, buyers))
            book = ChannelBook(13, cfg['channels'])
            book.purchase('pilot', 0, 'paid-pilot')
            exposed = book.expose(2, list(buyers.values()))
            self.assertTrue({e['customer_id'] for e in exposed}.isdisjoint(owned_customer_ids(cfg, buyers)))
            if count == 6:self.assertEqual(exposed, [])
            self.assertEqual(audit_channel_history(book.export(), cfg['channels'], 13, list(buyers.values()))['exposure_days_checked'], 1)

    def test_legacy_owned_semantics_are_unchanged(self):
        cfg, buyers = fixture(0)
        del cfg['audience_policy']
        self.assertEqual(owned_customer_ids(cfg, buyers), set(sorted(buyers)[:4]))
        self.assertEqual(sum(b['known'] for b in _buyers(cfg, 13)), 4)

    def test_mismatch_or_fabricated_owned_count_is_rejected(self):
        cfg, _ = fixture()
        for value in (True, -1, 7):
            bad = copy.deepcopy(cfg);bad['audience_policy']['owned_audience_count'] = value
            with self.assertRaisesRegex(ValueError, 'OWNED_AUDIENCE_MUST_BE_REGISTERED_POPULATION_SUBSET'):validate_policy(bad)
        cfg['channels']['extended']['owned_audience_count'] = 4
        with self.assertRaisesRegex(ValueError, 'CHANNEL_AND_INITIAL_OWNED_AUDIENCE_MUST_MATCH'):validate_policy(cfg)

    def test_zero_and_exhausted_reach_are_not_paid_options(self):
        for count, exhausted in ((6, False), (2, True)):
            cfg, buyers = fixture(count)
            contacts = {ident: [{'day': 0}] * 3 for ident in buyers} if exhausted else {}
            row = reachability(cfg, buyers, contacts, 0, 'pilot')
            self.assertEqual(row['potential_customer_ids'], [])
            self.assertEqual(menu_options(cfg, 'competitive_growth', 0, buyers, contacts, [], [100000000], 2, []), [])

    def test_temporary_cooldown_can_be_reached_later_without_free_contacts(self):
        cfg, buyers = fixture(5)
        ident = sorted(buyers)[-1]
        row = reachability(cfg, buyers, {ident: [{'day': 0}]}, 0, 'pilot')
        self.assertEqual(row['ready_customer_ids'], [])
        self.assertEqual(row['delayed_customer_ids'], [ident])
        self.assertEqual(row['earliest_contact_day'][ident], 7)
        self.assertEqual(row['remaining_contact_capacity'], 1)
        cfg['channels']['pilot']['duration_days'] = 4
        row = reachability(cfg, buyers, {ident: [{'day': 0}]}, 0, 'pilot')
        self.assertEqual(row['blocked'][ident], 'TEMPORARILY_UNAVAILABLE_IN_WINDOW')
        self.assertEqual(menu_options(cfg, 'competitive_growth', 0, buyers, {ident: [{'day': 0}]}, [], [100000000], 2, []), [])

    def test_delayed_need_pending_work_and_active_customers_are_not_new_demand(self):
        cfg, buyers = fixture(2)
        a, b, c, d = sorted(buyers)[2:]
        buyers[a]['next_need_time'] = 6 * 24
        buyers[b]['pending_commitments'] = {'accepted-order': 100}
        buyers[c].update(onboarded=True, active=True)
        buyers[d]['next_need_time'] = 50 * 24
        row = reachability(cfg, buyers, {}, 0, 'pilot')
        self.assertEqual(row['potential_customer_ids'], [a])
        self.assertEqual(row['delayed_customer_ids'], [a])
        self.assertEqual(row['blocked'][b], 'PENDING_ORDER')
        self.assertEqual(row['blocked'][c], 'ALREADY_ACTIVE_CUSTOMER')
        self.assertEqual(row['blocked'][d], 'TEMPORARILY_UNAVAILABLE_IN_WINDOW')

    def test_hidden_budget_and_future_labels_do_not_change_admission(self):
        cfg, buyers = fixture()
        before = reachability(cfg, buyers, {}, 0, 'pilot')
        for buyer in buyers.values():buyer.update(initial_budget=0, remaining_budget=999999999999, hidden_future='unseen-refusal')
        self.assertEqual(reachability(cfg, buyers, {}, 0, 'pilot'), before)

    def test_overlapping_contracts_cannot_duplicate_a_daily_exposure(self):
        cfg, buyers = fixture(2)
        for terms in cfg['channels'].values():terms.update(slots_per_day=20, overlap_bps=10000)
        book = ChannelBook(13, cfg['channels'])
        for ident in cfg['channels']:book.purchase(ident, 0, 'paid-' + ident)
        exposed = book.expose(2, list(buyers.values()))
        self.assertEqual(len(exposed), len({row['customer_id'] for row in exposed}))
        self.assertLessEqual(len(exposed), 4)
        self.assertEqual(audit_channel_history(book.export(), cfg['channels'], 13, list(buyers.values()))['exposure_days_checked'], 1)

    def test_expired_window_and_disabled_supplier_have_no_reach(self):
        cfg, buyers = fixture()
        self.assertEqual(reachability(cfg, buyers, {}, 29, 'pilot')['potential_customer_ids'], [])
        cfg['channels']['pilot']['realization_bps'] = 0
        row = reachability(cfg, buyers, {}, 0, 'pilot')
        self.assertEqual(row['potential_customer_ids'], [])
        self.assertTrue(all(row['blocked'][ident] == 'NO_CONTRACT_REALIZATION' for ident in sorted(buyers)[2:]))


if __name__ == '__main__':unittest.main()
