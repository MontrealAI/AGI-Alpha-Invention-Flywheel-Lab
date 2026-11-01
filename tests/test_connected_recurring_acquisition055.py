import copy
from fractions import Fraction
import unittest
from connected_enterprise.compounding055 import configuration
from connected_enterprise.recurring_acquisition055 import forecast
from connected_enterprise.startup_acquisition048 import preflight
from connected_enterprise.engine import _offer_menu


def fixture(world='friction'):
    cfg = configuration(world)
    buyers = {f'SIM-customer-{i:03d}': {'id': f'SIM-customer-{i:03d}', 'known': i < 4,
        'onboarded': False, 'active': True, 'pending_commitments': {}, 'next_need_time': 0,
        'outside_spend': 0, 'our_settled_spend': 0, 'service_index': i % 3} for i in range(12)}
    jobs = {row['job_id']: {'job': {'id': row['job_id'], 'accepted': True,
        'service_id': 'reconciliation', 'work_keys': ['source-' + row['job_id']]},
        'artifact': {'method': 'canonical', 'outcome_scope': 'complete_outcome'}}
        for requests in cfg['recurring_request_policy']['requests'].values() for row in requests}
    return cfg, buyers, jobs


class RecurringAcquisition055(unittest.TestCase):
    def result(self, cfg, buyers, jobs, **kwargs):
        return forecast(cfg, buyers, {}, 0, 'pilot', cfg['initial_slots'], jobs=jobs, **kwargs)

    def test_no_missing_invalid_incomplete_or_wrong_service_can_enable_access(self):
        cfg, buyers, jobs = fixture()
        self.assertIsNotNone(self.result(cfg, buyers, jobs))
        self.assertIsNone(self.result(cfg, buyers, None))
        for field, value in (('accepted', False), ('service_id', 'evidence_matrix')):
            changed = copy.deepcopy(jobs)
            for entry in changed.values():entry['job'][field] = value
            self.assertIsNone(self.result(cfg, buyers, changed))
            self.assertEqual(preflight(cfg, buyers, changed, _offer_menu), [])
        for entry in jobs.values():entry['artifact']['outcome_scope'] = 'component_only'
        self.assertEqual(preflight(cfg, buyers, jobs, _offer_menu), [])

    def test_shared_source_work_is_not_recredited_as_a_new_complete_outcome(self):
        cfg, buyers, jobs = fixture()
        for entry in jobs.values():entry['job']['work_keys'] = ['one-shared-input']
        self.assertIsNone(self.result(cfg, buyers, jobs))
        self.assertEqual(preflight(cfg, buyers, jobs, _offer_menu), [])

    def test_no_possible_public_win_refuses_before_startup_planning(self):
        cfg, buyers, jobs = fixture('commodity')
        self.assertIsNone(self.result(cfg, buyers, jobs))
        self.assertEqual(preflight(cfg, buyers, jobs, _offer_menu), [])
        cfg, buyers, jobs = fixture()
        cfg['arrival_bps'] = 0
        self.assertEqual(preflight(cfg, buyers, jobs, _offer_menu), [])

    def test_first_evaluation_and_all_channel_attempts_survive_conversion_haircut(self):
        cfg, buyers, jobs = fixture()
        cfg['startup_acquisition_policy']['conversion_bps'] = 10000
        full = self.result(cfg, buyers, jobs)
        cfg['startup_acquisition_policy']['conversion_bps'] = 1000
        low = self.result(cfg, buyers, jobs)
        self.assertEqual(low['amounts_fraction']['initial_qualification'], full['amounts_fraction']['initial_qualification'])
        self.assertGreater(Fraction(low['amounts_fraction']['initial_qualification']), 0)
        self.assertEqual(low['channel_attempt_outreach_microUSD'], full['channel_attempt_outreach_microUSD'])
        self.assertLess(Fraction(low['amounts_fraction']['collections']), Fraction(full['amounts_fraction']['collections']))

    def test_owned_concurrent_work_is_in_cash_envelope_and_shared_cost_charged_once(self):
        cfg, buyers, jobs = fixture()
        full = self.result(cfg, buyers, jobs)
        counts = full['all_buyer_future_planning_days']
        self.assertTrue(all(counts[ident] > 0 for ident in sorted(buyers)[:4]))
        expected = sum(counts.values()) * (cfg['exposure_cost'] + cfg['qualification_cost'])
        expected += full['channel_attempt_outreach_microUSD'] + full['maintenance_allocation_microUSD']
        self.assertEqual(full['future_operating_cash_lock'], expected)
        self.assertEqual(full['maintenance_allocation_microUSD'], 364 * cfg['maintenance_daily'])
        changed = copy.deepcopy(cfg)
        for ident in sorted(buyers)[:4]:
            changed['recurring_request_policy']['requests'][ident] = []
            changed['complete_offer_policy']['requested_jobs'][ident] = []
        empty = self.result(changed, buyers, jobs)
        self.assertLess(empty['future_operating_cash_lock'], full['future_operating_cash_lock'])

    def test_used_or_outside_consumed_requests_do_not_reenter_the_forecast(self):
        cfg, buyers, jobs = fixture()
        first = [requests[0]['job_id'] for ident, requests in cfg['recurring_request_policy']['requests'].items() if ident in sorted(buyers)[4:]]
        self.assertIsNone(self.result(cfg, buyers, jobs, consumed_jobs=first))
        self.assertIsNone(self.result(cfg, buyers, jobs, used_jobs=first))
        ident = sorted(buyers)[4]
        all_requests = [row['job_id'] for row in cfg['recurring_request_policy']['requests'][ident]]
        remaining = self.result(cfg, buyers, jobs, consumed_jobs=all_requests)
        self.assertNotIn(ident, {row['customer_id'] for row in remaining['public_offers']})

    def test_private_labels_budgets_and_future_draws_do_not_change_selection(self):
        cfg, buyers, jobs = fixture()
        original = self.result(cfg, buyers, jobs)
        for buyer in buyers.values():buyer.update(remaining_budget=0, initial_budget=1, hidden_future='default', private_atom=999)
        self.assertEqual(self.result(cfg, buyers, jobs), original)

    def test_unmodeled_recourse_contract_cannot_create_a_positive_option(self):
        cfg, buyers, jobs = fixture()
        cfg['refusal_recourse_policy'] = {'scope': 'extra_unmodeled_daily_fees'}
        self.assertIsNone(self.result(cfg, buyers, jobs))
        self.assertEqual(preflight(cfg, buyers, jobs, _offer_menu), [])

    def test_longer_windows_fail_closed_until_the_method_supports_them(self):
        cfg, buyers, jobs = fixture()
        cfg['recurring_request_policy']['requests']['SIM-customer-004'][0]['expiry_hour'] += 24
        with self.assertRaisesRegex(ValueError, 'AT_MOST_SEVEN_DAY_REQUEST_WINDOWS'):
            self.result(cfg, buyers, jobs)


if __name__ == '__main__':unittest.main()
