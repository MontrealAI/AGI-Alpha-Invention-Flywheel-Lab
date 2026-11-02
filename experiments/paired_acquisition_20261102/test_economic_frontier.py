"""Authored arithmetic/guard fixtures, not scientific or market confirmation."""
import copy
import unittest

from .economic_frontier import METHODS, RESOURCES, SCHEMA, compare


def fixture():
    resources = {
        'light_frames': 2, 'light_readings': 4, 'dark_frames': 0,
        'dark_readings': 0, 'blank_frames': 0, 'specimen_exposures': 2,
        'source_photons': 100, 'specimen_photons': 50,
        'elapsed_seconds': 2, 'swap_operations': 1,
    }
    choices = []
    for method in METHODS:
        use = dict(resources)
        if method == 'single_read':
            use.update(light_frames=1, light_readings=2, specimen_exposures=1,
                       elapsed_seconds=1, swap_operations=0)
        elif method == 'independent_calibration':
            use.update(blank_frames=1, specimen_exposures=1,
                       specimen_photons=25, swap_operations=0)
        choices.append({
            'method': method, 'quality': 'accepted',
            'quality_receipt_sha256': 'a' * 64,
            'rights_and_capacity': 'admitted', 'resources': use,
            'other_cash_cost_usd': 3, 'other_opportunity_cost_usd': 0,
            'complete_episode_cost_scope': True,
        })
    return {
        'schema': SCHEMA, 'case_id': 'authored-arithmetic-fixture',
        'scientific_contract_sha256': 'b' * 64,
        'permission_contract_sha256': 'c' * 64,
        'budgets': {key: 'unbounded' for key in RESOURCES},
        'cash_usd_per_unit': {key: int(key == 'light_frames') for key in RESOURCES},
        'opportunity_usd_per_unit': {key: 0 for key in RESOURCES},
        'price_basis': 'AUTHORED_UNIT_FIXTURE; not observed prices, demand or physical acquisition.',
        'choices': choices, 'available_cash_usd': 15, 'protected_cash_usd': 10,
        'prior_campaign_cost_usd': None,
        'offer_hypothesis': {'buyer_gross_value_usd': 10,
                             'buyer_adoption_cost_usd': 0,
                             'buyer_outside_surplus_usd': 0,
                             'provider_hurdle_usd': 0},
    }


class EconomicFrontierTests(unittest.TestCase):
    def test_unknown_costs_do_not_become_free_or_financeable(self):
        document = fixture()
        for key in ('cash_usd_per_unit', 'opportunity_usd_per_unit'):
            document[key] = {resource: None for resource in RESOURCES}
        for choice in document['choices']:
            choice.update(other_cash_cost_usd=None, other_opportunity_cost_usd=None)
        result = compare(document)
        for choice in result['choices'].values():
            self.assertIsNone(choice['complete_episode_cost_usd'])
            self.assertEqual(choice['conditional_cash_feasibility'], 'unresolved')
            self.assertEqual(choice['offer_state'], 'HOLD')
        paired = result['break_even_inequalities'][-1]
        self.assertTrue(paired['stipulated_protocol_cost_tie'])
        self.assertIsNone(paired['complete_cost_delta_usd'])
        self.assertIsNone(result['non_entry']['prior_campaign_cost_usd'])

    def test_specimen_budget_refuses_pair_despite_equal_light_frame_budget(self):
        document = fixture()
        document['budgets'].update(light_frames=2, specimen_exposures=1)
        result = compare(document)
        self.assertEqual(result['choices']['independent_calibration']['budget'], 'within_declared_budget')
        for method in ('paired_swap', 'ordinary_paired_swap'):
            self.assertEqual(result['choices'][method]['offer_state'], 'REFUSE')
            self.assertNotIn(method, result['conditional_resource_pareto_frontier'])

    def test_ordinary_same_observation_cost_handicap_is_rejected(self):
        document = fixture()
        document['choices'][-1]['resources']['light_frames'] = 3
        with self.assertRaisesRegex(ValueError, 'MATCHED_ORDINARY_PAIR'):
            compare(document)

    def test_positive_price_interval_does_not_fund_protected_cash(self):
        document = fixture()
        document['available_cash_usd'] = 14
        result = compare(document)['choices']['paired_swap']
        self.assertEqual(result['complete_episode_cost_usd'], '5')
        self.assertEqual(result['conditional_offer_price_interval_usd'], ['5', '10'])
        self.assertEqual(result['required_cash_including_protection_usd'], '15')
        self.assertEqual(result['conditional_cash_feasibility'], 'refused_insufficient_cash')
        self.assertEqual(result['offer_state'], 'REFUSE')

    def test_failed_quality_keeps_attempt_cost_and_nonentry_delivers_nothing(self):
        document = fixture()
        document['choices'][0]['quality'] = 'refused'
        result = compare(document)
        self.assertEqual(result['choices']['single_read']['cash_cost']['total_usd'], '4')
        self.assertEqual(result['choices']['single_read']['offer_state'], 'REFUSE')
        self.assertFalse(result['non_entry']['delivers_required_measurement'])
        self.assertEqual(result['non_entry']['incremental_acquisition_cash_cost_usd'], '0')
        self.assertIn('paired_swap', result['conditional_resource_pareto_frontier'])
        self.assertIn('ordinary_paired_swap', result['conditional_resource_pareto_frontier'])
        for key in ('native_account_executed', 'actual_offer_sent', 'authority_granted', 'commercial_profit_qualified'):
            self.assertFalse(result[key])

    def test_outside_option_and_invalid_prices_cannot_be_repaired_silently(self):
        document = fixture()
        document['offer_hypothesis']['buyer_outside_surplus_usd'] = 11
        result = compare(document)
        self.assertTrue(all(c['offer_state'] == 'REFUSE' for c in result['choices'].values()))
        for invalid in (-1, float('nan'), True):
            altered = copy.deepcopy(document)
            altered['cash_usd_per_unit']['light_frames'] = invalid
            with self.assertRaisesRegex(ValueError, 'NONNEGATIVE_FINITE_NUMBER_REQUIRED'):
                compare(altered)


if __name__ == '__main__':
    unittest.main()
