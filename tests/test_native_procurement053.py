import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('native_procurement053',ROOT/'scripts/run_conditional_procurement053.py')
RUNNER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(RUNNER)


class NativeProcurement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='native-procurement053-test-')
        cls.result=RUNNER.run(Path(cls.tmp.name)/'experiment')

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_each_case_is_independently_audited_and_reopens_unchanged(self):
        self.assertEqual(len(self.result['cases']),10)
        self.assertTrue(self.result['origin_audit_accepted'])
        for row in self.result['cases']:
            for key in ('native_audit_accepted','independent_audit_accepted','reopen_audit_accepted','same_account_reopen_unchanged'):
                self.assertTrue(row[key])

    def test_ordinary_control_has_identical_opportunity_and_finances(self):
        for case in RUNNER.CASES:
            rows=[r for r in self.result['cases'] if r['case']==case]
            self.assertEqual(rows[0]['summary'],rows[1]['summary'])
            self.assertEqual([o['outcome']for o in rows[0]['opportunities']],
                [o['outcome']for o in rows[1]['opportunities']])

    def test_central_broader_outcome_is_earned_funded_and_disjoint(self):
        for row in self.result['cases']:
            if row['case']!='central':continue
            first,second=row['opportunities']
            self.assertEqual(first['accepted_component_count'],1)
            self.assertEqual(second['accepted_component_count'],3)
            self.assertFalse(set(first['work_keys'])&set(second['work_keys']))
            self.assertEqual(second['invoice_funding'],'EARNED')
            self.assertTrue(row['financed_by_earnings'])
            self.assertEqual(second['outcome'],'ACCEPTED_COLLECTED')
            self.assertEqual(len(second['accepted_component_bindings']),3)

    def test_expiry_default_demand_and_cash_controls_preserve_losses(self):
        expected={'expired':'EXPIRED_BEFORE_RESERVATION','provider_default':'PROVIDER_DEFAULT_FULL_INVOICE_INCURRED',
            'no_demand':'NO_DEMAND_NO_PRODUCTION','unaffordable':'UNAFFORDABLE_NO_RESERVATION'}
        for row in self.result['cases']:
            if row['case']=='central':continue
            second=row['opportunities'][1]
            self.assertEqual(second['outcome'],expected[row['case']])
            self.assertFalse(row['financed_by_earnings'])
            self.assertEqual(row['summary']['collections'],0 if row['case']=='no_demand' else RUNNER.MODEL['primitive_price'])
            if row['case']=='provider_default':
                self.assertEqual(second['invoice_funding'],'EARNED')
                self.assertGreater(row['summary']['expenses'],RUNNER.MODEL['setup_search_development']+sum(second['invoice_components'].values()))
            else:self.assertNotIn('invoice_funding',second)


if __name__=='__main__':unittest.main()
