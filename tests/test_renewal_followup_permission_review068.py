import unittest
from dataclasses import replace
from connected_enterprise.renewable_market068 import MICRO, Scenario, cases, simulate


class FollowupPermissionReview068(unittest.TestCase):
    def run_months(self, bps, months=3):
        return simulate(replace(Scenario(), months=months, followup_permission_bps=bps))

    def test_zero_followup_rights_never_contact_refusers_again(self):
        r = self.run_months(0)['rows']
        self.assertGreater(r[0]['cold_contacts'], 0)
        for x in r:
            self.assertEqual(x['followup_contacts'], 0)
            self.assertEqual(x['warm_followup_pending'], 0)
            self.assertEqual(x['followup_rights_assumed_new'], 0)
            self.assertEqual(x['followup_rights_denied_new'], x['cold_contacts']-x['new_cold'])
            self.assertEqual(x['followup_permission_author_assumption_bps'], 0)
            self.assertEqual(sum(x[k] for k in ('active_customers', 'never_contacted',
                'warm_followup_pending', 'dormant_eligible', 'dormant_unavailable',
                'exhausted_contact_rights')), x['eligible_organizations'])

    def test_legacy_all_rights_explicit_and_same_month_economics(self):
        full = self.run_months(10000)['rows']
        zero = self.run_months(0)['rows']
        self.assertEqual(full[0]['cold_contacts'], zero[0]['cold_contacts'])
        self.assertEqual(full[0]['new_cold'], zero[0]['new_cold'])
        self.assertEqual(full[0]['closing_cash_micro'], zero[0]['closing_cash_micro'])
        self.assertEqual(full[0]['followup_rights_assumed_new'],
                         full[0]['cold_contacts']-full[0]['new_cold'])
        self.assertEqual(full[0]['followup_rights_denied_new'], 0)
        self.assertGreater(full[1]['followup_contacts'], 0)
        self.assertEqual(zero[1]['followup_contacts'], 0)

    def test_partial_rights_have_exact_integer_permission_denominator(self):
        x = self.run_months(5000, 1)['rows'][0]
        declined = x['cold_contacts']-x['new_cold']
        self.assertEqual(x['followup_rights_assumed_new'], declined//2)
        self.assertEqual(x['followup_rights_denied_new'], declined-declined//2)
        self.assertEqual(x['warm_followup_pending'], declined//2)

    def test_rights_scope_changes_bound_input_and_is_not_observed_consent(self):
        full = self.run_months(10000)
        none = self.run_months(0)
        self.assertNotEqual(full['input_sha256'], none['input_sha256'])
        self.assertIn('CONDITIONAL_AGGREGATE', full['evidence'])
        self.assertTrue(any('not permission' in note for note in full['qualification_limitations']))

    def test_invalid_permission_bps_rejected(self):
        with self.assertRaises(ValueError):
            self.run_months(10001)
        with self.assertRaises(ValueError):
            self.run_months(-1)

    def test_registered_no_followup_stress_not_relabelled_as_paid_commerce(self):
        result = cases()
        self.assertIn('no_followup_rights', result['cases'])
        self.assertEqual(result['claim'], 'SENSITIVITY_ONLY_NOT_NATIVE_BUSINESS_EXECUTION')
        self.assertIsNone(result['cases']['small_100k_no_extra_finance']['first_3b_month'])


if __name__ == '__main__':
    unittest.main()
