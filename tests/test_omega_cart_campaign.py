"""Pilot-only campaign integrity, complete attempt costs and equal-content controls."""
import copy
from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest.mock import patch

from mechanism_harness import cart_campaign as campaign
from mechanism_harness.market_cases import market as original_market

PILOT = ((1337, 'substitute'), (1338, 'competitive'))


@contextmanager
def pilot():
    def small(seed, family):
        return original_market(seed, family, width=2)
    with patch.object(campaign, 'CASES', PILOT), patch.object(campaign, 'market', side_effect=small):
        yield


class CampaignIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with pilot():
            cls.report = campaign.execute()
            cls.report['source'] = campaign.source_identity()

    def test_declared_cases_all_preserved(self):
        self.assertEqual(self.report['registered_case_ids'], [list(x) for x in PILOT])
        self.assertEqual(len(self.report['cases']), 2)
        self.assertTrue(self.report['all_synthesized_programs_verified'])

    def test_equal_content_gets_equal_constraints(self):
        for row in self.report['cases']:
            self.assertTrue(row['equal_content_same_logical_run'])
            self.assertEqual(row['expected_gain_over_equal_content_reuse_cents'], '0')
        self.assertFalse(self.report['beats_equal_content_reuse'])

    def test_successor_reports_acquisition_and_ablation(self):
        first, second = self.report['cases']
        self.assertFalse(first['successor_ablation']['is_successor'])
        self.assertTrue(second['successor_ablation']['is_successor'])
        self.assertEqual(second['successor_ablation']['prior_acquisition_rows'],
                         first['runs']['inherited']['total_rows_built'])
        self.assertTrue(second['successor_ablation']['cold_verified'])
        self.assertTrue(second['successor_ablation']['ordinary_equal_content_verified'])

    def test_noentry_and_copycat_are_feasible(self):
        for row in self.report['cases']:
            self.assertEqual(row['runs']['nonentry']['verification']['expected_contribution_cents'], '0')
            self.assertTrue(all(c['declined'] for c in row['copycat_choices']))

    def test_intact_replay(self):
        with pilot():
            self.assertTrue(campaign.audit(self.report)['accepted'])

    def test_dropped_case_and_arm_rejected(self):
        changed = copy.deepcopy(self.report)
        changed['cases'].pop()
        with pilot(), self.assertRaisesRegex(ValueError, 'DENOMINATOR'):
            campaign.audit(changed)
        changed = copy.deepcopy(self.report)
        del changed['cases'][0]['runs']['full_control']
        with pilot(), self.assertRaisesRegex(ValueError, 'ARM_CHANGED'):
            campaign.audit(changed)

    def test_changed_cost_total_rejected(self):
        changed = copy.deepcopy(self.report)
        changed['total_rows_built']['inherited'] -= 1
        with pilot(), self.assertRaisesRegex(ValueError, 'REPLAY_CHANGED'):
            campaign.audit(changed)

    def test_source_tamper_rejected(self):
        changed = copy.deepcopy(self.report)
        changed['source']['mechanism_harness/cart_program.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            campaign.audit(changed)

    def test_failed_attempts_remain_in_totals(self):
        # Financially relevant regression: an unresolved constructor must not
        # vanish from the measured discovery-cost denominator.
        original = campaign.synthesize
        calls = 0
        def unresolved(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                result = copy.deepcopy(result)
                result['program'] = None
                result['status'] = 'UNRESOLVED'
            return result
        with pilot(), patch.object(campaign, 'synthesize', side_effect=unresolved):
            report = campaign.execute(PILOT[:1])
        self.assertEqual(report['completed_cases'], 0)
        self.assertFalse(report['all_synthesized_programs_verified'])
        self.assertGreater(report['total_rows_built']['inherited'], 0)
        self.assertEqual(report['total_rows_built']['inherited'],
                         report['cases'][0]['runs']['inherited']['total_rows_built'])
        self.assertIsNone(report['cases'][0]['memory_after'])


if __name__ == '__main__':
    unittest.main()
