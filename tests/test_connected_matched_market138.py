"""Preregistered adversarial external-world parity for observer compare (138)."""
import copy
import unittest

from connected_enterprise.scale import compare
from tests.test_connected_scale import fixture


def pair():
    """Toy observer fixture; never a qualified native simulation or customer."""
    original = {
        'seed': 138001, 'world': 'central', 'arm': 'baseline',
        'config': {
            'customer_pool': 8, 'arrival_bps': 7000, 'value_bps': 10000,
            'setup_cost': 100, 'profit_tax_bps': 2000,
            'channels': {'pilot': {'price_microUSD': 100, 'activation_bps': 9000}},
            'complete_offer_policy': {'buyer_profiles': ['same-declared-market']},
        },
        'source': {'sha256': 'a' * 64, 'services': ['declared-reconciliation']},
        'owned_account': {'ledger': fixture()},
    }
    challenger = copy.deepcopy(original)
    challenger['arm'] = 'growth'
    return original, challenger


class MatchedMarketIntegrity138(unittest.TestCase):
    def test_identical_external_world_keeps_baseline_comparison(self):
        a, b = pair()
        result = compare([a, b])
        self.assertEqual(len(result['pairs']), 1)
        record = result['pairs'][0]
        self.assertEqual(record['profit_delta_microUSD'], 0)
        self.assertEqual(record['collections_delta_microUSD'], 0)
        self.assertEqual(record['declared_treatment_policy_fields'], [])
        self.assertEqual(len(record['matched_external_configuration_sha256']), 64)
        self.assertEqual(len(record['matched_source_sha256']), 64)

    def test_cannot_select_a_winner_by_changing_demand_or_buyer_values(self):
        for field, value in (('arrival_bps', 10000), ('value_bps', 20000)):
            with self.subTest(field=field):
                a, b = pair()
                b['config'][field] = value
                with self.assertRaisesRegex(ValueError, 'UNMATCHED_EXTERNAL_MARKET'):
                    compare([a, b])

    def test_cannot_hide_complete_costs_or_contract_or_prospective_terms(self):
        for change in (
            lambda config: config.__setitem__('setup_cost', 1),
            lambda config: config.__setitem__('profit_tax_bps', 0),
            lambda config: config['channels']['pilot'].__setitem__('price_microUSD', 1),
            lambda config: config['complete_offer_policy'].__setitem__('buyer_profiles', ['different']),
            lambda config: config.__setitem__('prospective_policy', {'term': 'discount'}),
        ):
            with self.subTest(change=change):
                a, b = pair()
                change(b['config'])
                with self.assertRaisesRegex(ValueError, 'UNMATCHED_EXTERNAL_MARKET'):
                    compare([a, b])

    def test_declared_policy_treatment_does_not_change_external_environment(self):
        a, b = pair()
        a['config']['strategic_policy'] = {'rank': 'ordinary'}
        b['config']['strategic_policy'] = {'rank': 'challenger'}
        b['config']['channel_menu_policy'] = {'sequence': 'trial'}
        result = compare([a, b])['pairs'][0]
        self.assertEqual(result['declared_treatment_policy_fields'],
                         ['channel_menu_policy', 'strategic_policy'])
        self.assertEqual(result['profit_delta_microUSD'], 0)

    def test_source_missing_on_one_side_or_different_rejected(self):
        a, b = pair()
        b['source']['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'UNMATCHED_SOURCE'):
            compare([a, b])
        a, b = pair()
        b.pop('source')
        with self.assertRaisesRegex(ValueError, 'UNMATCHED_SOURCE'):
            compare([a, b])

    def test_legacy_minimal_equal_config_fixture_remains_readable(self):
        a, b = pair()
        a.pop('source')
        b.pop('source')
        a['config'] = {'customer_pool': 8}
        b['config'] = {'customer_pool': 8}
        self.assertIsNone(compare([a, b])['pairs'][0]['matched_source_sha256'])

    def test_missing_external_config_rejected(self):
        a, b = pair()
        b.pop('config')
        with self.assertRaisesRegex(ValueError, 'MATCHED_EXTERNAL_CONFIGURATION_REQUIRED'):
            compare([a, b])


if __name__ == '__main__':
    unittest.main()
