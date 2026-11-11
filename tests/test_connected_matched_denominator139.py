"""Integrity139: no silently discarded registered-arm observations (analytical only)."""
import copy
import unittest

from connected_enterprise.scale import compare
from tests.test_connected_matched_market138 import pair


class MatchedDenominatorIntegrity139(unittest.TestCase):
    def test_complete_matched_denominator_reports_all_selected_observations(self):
        a, b = pair()
        c, d = pair()
        c['seed'] = d['seed'] = 139001
        result = compare([a, b, c, d])
        self.assertEqual(len(result['pairs']), 2)
        self.assertEqual(result['matched_denominator'],
                         {'baseline_businesses': 2, 'candidate_businesses': 2, 'pairs': 2})
        self.assertEqual([p['profit_delta_microUSD'] for p in result['pairs']], [0, 0])

    def test_misaligned_seed_case_or_pool_cannot_disappear_silently(self):
        for mutation in (
            lambda r: r.__setitem__('seed', 139002),
            lambda r: r.__setitem__('world', 'price_war'),
            lambda r: r['config'].__setitem__('customer_pool', 9),
        ):
            with self.subTest(mutation=mutation):
                a, b = pair()
                mutation(b)
                with self.assertRaisesRegex(ValueError, 'UNMATCHED_REQUESTED_ARM_DENOMINATOR'):
                    compare([a, b])

    def test_one_eligible_pair_does_not_mask_missing_adverse_control(self):
        a, b = pair()
        extra, candidate = pair()
        extra['seed'] = 139010
        candidate['seed'] = 139011
        with self.assertRaisesRegex(ValueError, 'UNMATCHED_REQUESTED_ARM_DENOMINATOR'):
            compare([a, b, extra, candidate])

    def test_one_eligible_pair_does_not_mask_missing_candidate(self):
        a, b = pair()
        extra, _ = pair()
        extra['seed'] = 139012
        with self.assertRaisesRegex(ValueError, 'UNMATCHED_REQUESTED_ARM_DENOMINATOR'):
            compare([a, b, extra])

    def test_unrelated_nonrequested_arm_does_not_create_false_denominator(self):
        a, b = pair()
        unrelated = copy.deepcopy(a)
        unrelated['arm'] = 'channel'
        unrelated['seed'] = 139013
        result = compare([a, b, unrelated])
        self.assertEqual(len(result['pairs']), 1)
        self.assertEqual(result['matched_denominator'],
                         {'baseline_businesses': 1, 'candidate_businesses': 1, 'pairs': 1})

    def test_no_data_or_one_requested_arm_must_not_qualify(self):
        a, b = pair()
        for results in ([], [a], [b]):
            with self.subTest(results=len(results)):
                with self.assertRaisesRegex(ValueError, 'NO_MATCHED_REQUESTED_ARM_PAIRS|UNMATCHED_REQUESTED_ARM_DENOMINATOR'):
                    compare(results)

    def test_distinct_arms_required_and_legitimate_policy_remains_comparable(self):
        a, b = pair()
        with self.assertRaisesRegex(ValueError, 'DISTINCT_COMPARISON_ARMS_REQUIRED'):
            compare([a, b], baseline='baseline', candidate='baseline')
        b['config']['strategic_policy'] = {'allocation': 'costed_policy'}
        result = compare([a, b])
        self.assertEqual(result['pairs'][0]['declared_treatment_policy_fields'], ['strategic_policy'])


if __name__ == '__main__':
    unittest.main()
