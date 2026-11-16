"""Protocol checks only; never claim these are model qualification."""
import hashlib
import json
from pathlib import Path
import unittest
from scripts.qualify_quote_workflow_007 import strategy_parameters, ordinary
from bridge.workflow_strategies import call_limit

PRODUCT = Path(__file__).resolve().parents[1]

class QuoteTrial007Tests(unittest.TestCase):
    def test_frozen_cases_and_contract_unchanged(self):
        old_path = PRODUCT/'evidence/LOCAL-QUOTE-PROTOCOL-006.json'
        old = json.loads(old_path.read_text())
        new = json.loads((PRODUCT/'evidence/LOCAL-QUOTE-PROTOCOL-007.json').read_text())
        for key in old.keys() - {'schema', 'purpose', 'registered_at', 'finite_inference_budget'}:
            self.assertEqual(new[key], old[key], key)
        expected_budget = dict(old['finite_inference_budget'], max_output_tokens_per_call=2048)
        self.assertEqual(new['finite_inference_budget'], expected_budget)
        self.assertEqual(new['strategy_comparison']['original_protocol_sha256'], hashlib.sha256(old_path.read_bytes()).hexdigest())

    def test_equal_call_allocation_with_different_role_allocation(self):
        for strategy, iterations in [('actor-critic', 2), ('single-model', 4)]:
            config = strategy_parameters(strategy)
            self.assertEqual(config['max_iterations'], iterations)
            self.assertEqual(call_limit(config), 4)

    def test_unknown_strategy_refused(self):
        with self.assertRaises(ValueError):
            strategy_parameters('unbounded')

    def test_ordinary_control_preserves_all_expected_outputs(self):
        protocol = json.loads((PRODUCT/'evidence/LOCAL-QUOTE-PROTOCOL-007.json').read_text())
        for case in protocol['manufacturing_cases'] + protocol['lab_cases']:
            self.assertEqual(ordinary(case['input']), case['expected'])

if __name__ == '__main__':
    unittest.main()
