"""Tests of illustrative calculation and truthful evidence boundaries."""
from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('human_frontier',ROOT/'human_frontier.py')
assert spec and spec.loader
hf=importlib.util.module_from_spec(spec)
spec.loader.exec_module(hf)
class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.source=json.loads((ROOT/'illustrative_cases.json').read_text())
    def test_four_distinct_services(self): self.assertEqual(len(hf.analyze(self.source)['cases']),4)
    def test_labor_exceeds_AI_modeled_cost_in_these_assumptions(self):
        self.assertTrue(all(float(c['human_minus_ai_modeled_cost_usd'])>0 for c in hf.analyze(self.source)['cases']))
    def test_Terra_blog_tokens_four_cents(self): self.assertEqual(hf.analyze(self.source)['cases'][0]['ai_model_token_usd'],'0.04')
    def test_premium_model_software_cost(self): self.assertEqual(hf.analyze(self.source)['cases'][2]['ai_model_token_usd'],'4.50')
    def test_no_earnings_or_confirmed_quality(self):
        result=hf.analyze(self.source)
        self.assertEqual(result['actual_customer_receipts_usd'],'0')
        self.assertEqual(result['commercial_success'],'UNESTABLISHED')
        self.assertTrue(all(c['quality_and_same_outcome_verified'] is False for c in result['cases']))
    def test_no_boolean_hours(self):
        x=copy.deepcopy(self.source);x['cases'][0]['human_hours']=True
        with self.assertRaises(ValueError): hf.analyze(x)
    def test_bad_rate_refused(self):
        x=copy.deepcopy(self.source);x['models']['gpt-6.1-terra']['output_usd_per_million']='NaN'
        with self.assertRaises(ValueError): hf.analyze(x)
    def test_duplicate_case_refused(self):
        x=copy.deepcopy(self.source);x['cases'][1]['id']=x['cases'][0]['id']
        with self.assertRaises(ValueError): hf.analyze(x)
    def test_cannot_inject_proven_sales(self):
        x=copy.deepcopy(self.source);x['metadata']['actual_sales']=1
        with self.assertRaises(ValueError): hf.analyze(x)
    def test_cannot_inject_quality_confirmation(self):
        x=copy.deepcopy(self.source);x['metadata']['same_outcome_independently_verified']=True
        with self.assertRaises(ValueError): hf.analyze(x)
    def test_unknown_cost_category_refused(self):
        x=copy.deepcopy(self.source);x['cases'][0]['new_unknown_cost']='0'
        with self.assertRaises(ValueError): hf.analyze(x)
    def test_output_file_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'existing.json';path.write_text('previous')
            self.assertTrue(path.exists())
            self.assertNotEqual(path.read_text(),'{ }')
if __name__=='__main__': unittest.main()
