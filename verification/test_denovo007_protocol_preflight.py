import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from verification.denovo007_protocol_preflight import assess


def contract(total=89, k=10, reduction='9/10', maximum=10, claim='possible'):
    return {'schema': 'agi-alpha/shortlist-constraint007/v1', 'candidate_count': total,
            'selector': {'kind': 'tie_inclusive_top_k', 'k': k}, 'minimum_reduction': reduction,
            'maximum_retained': maximum, 'claim': claim, 'evidence_state': 'TEST_ONLY'}


class PreflightTests(unittest.TestCase):
    def test_frozen_invalid_contract_cli_refuses(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'refusal.json'
            result = subprocess.run([sys.executable, str(root/'verification/denovo007_protocol_preflight.py'), '--contract', str(root/'verification/cycle007_denovo_protocol.json'), '--candidate-count', '89', '--output', str(output)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            report = json.loads(output.read_text())
            self.assertEqual(report['selector_possible_count_interval'], [10, 89])
            self.assertEqual(report['maximum_count_from_reduction'], 8)
            self.assertFalse(report['some_selector_count_can_satisfy'])

    def test_exact_decimal_boundary_preserves_ten(self):
        result = assess(contract(total=100, reduction='0.90'))
        self.assertEqual(result['maximum_count_from_reduction'], 10)
        self.assertTrue(result['some_selector_count_can_satisfy'])
        self.assertFalse(result['all_selector_counts_satisfy'])

    def test_possible_is_not_arbitrary_tie_guarantee(self):
        self.assertTrue(assess(contract(k=1))['accepted_arithmetic_claim'])
        result = assess(contract(k=1, claim='guaranteed_for_selector_counts'))
        self.assertFalse(result['accepted_arithmetic_claim'])
        self.assertEqual(result['selector_possible_count_interval'], [1, 89])

    def test_explicit_operation_count(self):
        value = contract(claim='guaranteed_for_selector_counts')
        value['selector'] = {'kind': 'exact_count', 'count': 8}
        self.assertTrue(assess(value)['accepted_arithmetic_claim'])
        value['selector']['count'] = 9
        self.assertFalse(assess(value)['accepted_arithmetic_claim'])

    def test_no_reduction_allows_all_ties(self):
        self.assertTrue(assess(contract(k=1, reduction='0', maximum=89, claim='guaranteed_for_selector_counts'))['accepted_arithmetic_claim'])
        self.assertTrue(assess(contract(total=5, k=10, reduction='0', maximum=5, claim='guaranteed_for_selector_counts'))['accepted_arithmetic_claim'])

    def test_malformed_and_inexact_values_refused(self):
        for changes in ({'candidate_count': True}, {'minimum_reduction': 0.9}, {'minimum_reduction': 'NaN'}, {'minimum_reduction': '1.1'}, {'selector': {'kind': 'tie_inclusive_top_k', 'k': 0}}, {'selector': {'kind': 'invented'}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                assess(dict(contract(), **changes))


if __name__ == '__main__':
    unittest.main()
