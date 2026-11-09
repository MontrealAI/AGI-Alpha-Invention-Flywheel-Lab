"""Exposed demo acceptance; not new commercial confirmation."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from interpret import build, render
from verify import verify

FIXTURE=Path(__file__).with_name('demo.csv')

class InterpreterTests(unittest.TestCase):
    def test_source_bound_independent_demo(self):
        report=build(FIXTURE,sample_role='EXPOSED_DEMO',review_status='UNVERIFIED',population_frame='UNKNOWN')
        self.assertEqual(report['status'],'UNQUALIFIED_DEMONSTRATION')
        self.assertEqual(report['groups']['region-a']['scored'],2)
        self.assertEqual(report['groups']['region-b']['fn'],1)
        self.assertIsNone(report['population_prevalence_estimate'])
        self.assertIsNone(report['actual_revenue_usd'])
        with TemporaryDirectory() as td:
            p=Path(td)/'receipt.json';p.write_text(json.dumps(report))
            self.assertTrue(verify(FIXTURE,p))

    def test_renders_offline_explicit_limits(self):
        report=build(FIXTURE,sample_role='EXPOSED_DEMO',review_status='UNVERIFIED',population_frame='UNKNOWN')
        h=render(report)
        self.assertIn('not validated population estimation',h)
        self.assertIn(report['input_sha256'],h)
        self.assertNotIn('<script',h)

    def test_rejects_duplicated_case_instead_of_inflating_evidence(self):
        with TemporaryDirectory() as td:
            p=Path(td)/'f.csv';p.write_text(FIXTURE.read_text()+FIXTURE.read_text().splitlines()[1]+'\n')
            with self.assertRaisesRegex(ValueError,'UNIQUE_CASE_ID'):
                build(p,sample_role='EXPOSED_DEMO',review_status='UNVERIFIED',population_frame='UNKNOWN')

    def test_rejects_labeled_csv_tampering_and_receipt_forgery(self):
        report=build(FIXTURE,sample_role='EXPOSED_DEMO',review_status='UNVERIFIED',population_frame='UNKNOWN')
        with TemporaryDirectory() as td:
            p=Path(td)/'receipt.json'
            bad=copy.deepcopy(report);bad['groups']['region-b']['fn']=0;p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'COUNTS_CHANGED'):verify(FIXTURE,p)
            p.write_text(json.dumps(report))
            badcsv=Path(td)/'f.csv';badcsv.write_text(FIXTURE.read_text().replace('region-b','region-c'))
            with self.assertRaisesRegex(ValueError,'ORIGINAL_INPUT_CHANGED'):verify(badcsv,p)

    def test_no_certification_without_label_review_and_heldout_role(self):
        with self.assertRaisesRegex(ValueError,'EXACT_EVIDENCE_ROLE'):
            build(FIXTURE,sample_role='ASSUMED_WIN',review_status='UNVERIFIED',population_frame='UNKNOWN')
        report=build(FIXTURE,sample_role='FROZEN_HELDOUT',review_status='UNVERIFIED',population_frame='DOCUMENTED')
        self.assertEqual(report['status'],'UNQUALIFIED_DEMONSTRATION')
        report=build(FIXTURE,sample_role='FROZEN_HELDOUT',review_status='INDEPENDENTLY_REVIEWED',population_frame='UNKNOWN')
        self.assertEqual(report['status'],'BOUNDED_HELDOUT_DIAGNOSTIC')
        self.assertIsNone(report['population_bias_certification'])

if __name__=='__main__':unittest.main()
