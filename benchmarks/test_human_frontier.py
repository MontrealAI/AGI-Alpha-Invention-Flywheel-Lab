"""Regressions for end-to-end autonomous comparison; no real service tests."""
from __future__ import annotations
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('human_frontier', ROOT / 'human_frontier.py')
assert spec and spec.loader
hf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hf)


class AutonomousBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / 'illustrative_cases.json').read_text())

    def test_four_services(self):
        self.assertEqual(len(hf.analyze(self.source)['cases']), 4)

    def test_no_human_verification_or_development_labor(self):
        result = hf.analyze(self.source)
        self.assertEqual(result['mandatory_human_verification'], 'NONE')
        self.assertTrue(all(x['agent_human_hours'] == '0' and
                            x['autonomous_operation_human_labor_usd'] == '0.00' for x in result['cases']))

    def test_every_business_phase_included(self):
        result = hf.analyze(self.source)
        self.assertEqual(set(result['autonomous_operation_includes']), set(hf.PHASES))
        for case in result['cases']:
            self.assertEqual({p['phase'] for p in case['autonomous_phase_costs']}, set(hf.PHASES))

    def test_article_production_is_four_cents(self):
        case = hf.analyze(self.source)['cases'][0]
        produce = next(p for p in case['autonomous_phase_costs'] if p['phase'] == 'production')
        self.assertEqual(produce['model_cost_usd'], '0.04')
        self.assertEqual(case['ai_workflow_model_cost_usd'], '0.25')

    def test_premium_software_production(self):
        case = hf.analyze(self.source)['cases'][2]
        produce = next(p for p in case['autonomous_phase_costs'] if p['phase'] == 'production')
        self.assertEqual(produce['model'], 'gpt-6-astra')
        self.assertEqual(produce['model_cost_usd'], '4.50')

    def test_default_hypothetical_margins_are_not_actual_sales(self):
        result = hf.analyze(self.source)
        self.assertTrue(all(float(x['conditional_ai_contribution_usd']) > 0 for x in result['cases']))
        self.assertEqual(result['actual_customer_receipts_usd'], '0')
        self.assertEqual(result['commercial_success'], 'UNESTABLISHED')
        self.assertFalse(result['all_outcomes_confirmed'])
        self.assertTrue(all(not x['quality_and_same_outcome_verified'] for x in result['cases']))

    def test_nonzero_escalation_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][2]['agent_human_hours'] = '1'
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_old_human_review_schema_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['ai_review_hours'] = '1'
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_missing_autonomous_phase_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['autonomous_phases'].pop()
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_duplicate_phase_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['autonomous_phases'][1]['name'] = 'production'
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_bad_model_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['autonomous_phases'][0]['model'] = 'pretend-model'
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_bad_api_rate_refused(self):
        x = copy.deepcopy(self.source)
        x['models']['gpt-6.1-terra']['output_usd_per_million'] = 'NaN'
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_boolean_token_count_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['autonomous_phases'][0]['input_tokens'] = True
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_missing_expense_category_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['ai_non_model_costs'].pop('warranty_and_liability_reserve_usd')
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_negative_distribution_cost_refused(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['ai_non_model_costs']['paid_distribution_usd'] = '-1'
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_no_forged_customer_sales(self):
        x = copy.deepcopy(self.source)
        x['metadata']['actual_sales'] = 1
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_no_forged_quality_confirmation(self):
        x = copy.deepcopy(self.source)
        x['metadata']['same_outcome_independently_verified'] = True
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_no_boolean_human_duration(self):
        x = copy.deepcopy(self.source)
        x['cases'][0]['human_hours'] = True
        with self.assertRaises(ValueError): hf.analyze(x)

    def test_output_reproduces_exact_reference(self):
        expected = json.loads((ROOT / 'illustrative_results.json').read_text())
        self.assertEqual(hf.analyze(self.source), expected)

    def test_cli_writes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'result.json'
            command = [sys.executable, str(ROOT / 'human_frontier.py'), '--output', str(target)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            old_bytes = target.read_bytes()
            self.assertEqual(json.loads(old_bytes)['commercial_success'], 'UNESTABLISHED')
            second = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(second.returncode, 2)
            self.assertIn('Preserve prior output', second.stderr)
            self.assertEqual(target.read_bytes(), old_bytes)


if __name__ == '__main__':
    unittest.main()
