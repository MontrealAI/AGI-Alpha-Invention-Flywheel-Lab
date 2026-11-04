"""Public-evidence operation decisions; no new confirmation market exposure."""
import copy
from fractions import Fraction
import unittest
from unittest.mock import patch

from mechanism_harness import cart_campaign as campaign, cart_decision as decision
from mechanism_harness import cart_program as program
from mechanism_harness.market_cases import market


class PublicOperatingGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = ((1337, 'substitute'),)
        cls.study = campaign.execute(cls.cases)
        cls.study['source'] = campaign.source_identity()

    def select(self):
        with patch.object(campaign, 'CASES', self.cases):
            return decision.select(self.study)

    def test_decision_is_public_replayable_and_preserves_all_sunk_work(self):
        receipt = self.select()
        with patch.object(campaign, 'CASES', self.cases):
            self.assertTrue(decision.verify(self.study, receipt)['accepted'])
        selected = receipt['decisions'][0]
        verified = [x for x in selected['candidates'] if x['eligible']]
        self.assertEqual(Fraction(selected['expected_contribution_cents']),
                         max(Fraction(x['expected_contribution_cents']) for x in verified))
        self.assertEqual(receipt['sunk_study_work']['construction_rows_by_arm'], self.study['total_rows_built'])
        self.assertIsNone(receipt['unknown_complete_lifecycle_cost_usd'])
        chosen = decision.selected_program(self.study, receipt, 0)
        self.assertTrue(program.verify(self.study['cases'][0]['market'], chosen)['accepted'])

    def test_changed_decision_or_sunk_cost_cannot_pass(self):
        receipt = self.select()
        for field in ('decision', 'sunk'):
            altered = copy.deepcopy(receipt)
            if field == 'decision':altered['decisions'][0]['selected_arm'] = 'nonentry'
            else:altered['sunk_study_work']['construction_rows_by_arm']['inherited'] = 0
            with patch.object(campaign, 'CASES', self.cases), self.assertRaisesRegex(ValueError, 'PUBLIC_OPERATING_DECISION_CHANGED'):
                decision.verify(self.study, altered)

    def test_zero_contribution_declines_before_private_observation(self):
        m = market(1338, 'substitute', width=2)
        null = program.null_program(m)
        case = {'market': m, 'runs': {name: {'program': null, 'total_rows_built': 3,
                    'deviation_checks': 4} for name in decision.CANDIDATES}}
        selected = decision._decision(case)
        self.assertEqual(selected['action'], 'NONENTRY')
        self.assertEqual(selected['selected_arm'], 'nonentry')
        self.assertEqual(set(selected['contribution_ties']), set(decision.CANDIDATES))

    def test_work_ties_keep_tradeoffs_without_inventing_dollar_prices(self):
        case = copy.deepcopy(self.study['cases'][0])
        chosen = case['runs']['full_control']['program']
        self.assertGreater(Fraction(program.verify(case['market'], chosen)['expected_contribution_cents']), 0)
        for name in decision.CANDIDATES:
            if name != 'nonentry':
                case['runs'][name].update(program=chosen, total_rows_built=100, deviation_checks=100)
        case['runs']['bundle'].update(total_rows_built=1, deviation_checks=3)
        case['runs']['full_control'].update(total_rows_built=3, deviation_checks=1)
        selected = decision._decision(case)
        self.assertEqual(selected['workload_frontier'], ['bundle', 'full_control'])
        self.assertEqual(selected['selected_arm'], 'bundle')
        self.assertTrue(selected['lexical_tie_break_used'])

    def test_no_program_is_not_eligible_even_with_attractive_metadata(self):
        case = copy.deepcopy(self.study['cases'][0])
        case['runs']['inherited']['program'] = None
        selected = decision._decision(case)
        row = next(x for x in selected['candidates'] if x['arm'] == 'inherited')
        self.assertFalse(row['eligible'])
        self.assertIsNone(row['expected_contribution_cents'])


if __name__ == '__main__':unittest.main()
