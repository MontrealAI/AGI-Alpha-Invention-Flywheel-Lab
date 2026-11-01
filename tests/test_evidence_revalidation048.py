import copy
import json
from pathlib import Path
import tempfile
import unittest
from experiments import evidence_revalidation048 as e


class RevalidationTests(unittest.TestCase):
    def setUp(self):
        self.case = e.cases()[0]
        self.contract = self.case['contract']
        self.plan = e.construct(self.contract, self.case['before'])
        self.previous = e.produce(self.contract, self.case['before'], self.plan)

    def test_changed_claim_recomputed_unchanged_claims_carried(self):
        result = e.produce(self.contract, self.case['after'], self.plan, self.previous, e.digest(self.previous))
        self.assertEqual(result['evaluated'], ['distribution_manifest'])
        self.assertEqual(result['reused'], ['stable_total', 'stable_identity'])
        self.assertEqual(result['claims']['distribution_manifest']['value'], 112)
        self.assertTrue(e.audit(self.contract, self.case['after'], self.plan, result)['accepted'])

    def test_changed_all_sources_recomputes_every_claim(self):
        case = e.cases()[1]
        result = e.produce(case['contract'], case['after'], self.plan, self.previous, e.digest(self.previous))
        self.assertEqual(result['reused'], [])
        self.assertEqual(result['producer_row_visits'], 6)

    def test_missing_or_extra_sources_fail_closed(self):
        for sources in ({'changing.csv': self.case['after']['changing.csv']}, dict(self.case['after'], undeclared='x')):
            with self.assertRaisesRegex(ValueError, 'EXACT_DECLARED_SOURCE_SET_REQUIRED'):
                e.produce(self.contract, sources, self.plan)

    def test_omitted_dependency_plan_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan['dependencies']['distribution_manifest'] = []
        with self.assertRaisesRegex(ValueError, 'PLAN_CHANGED_OR_INCOMPLETE'):
            e.produce(self.contract, self.case['after'], plan)

    def test_previous_identity_and_scope_are_not_self_authority(self):
        altered = copy.deepcopy(self.previous)
        altered['claims']['stable_total']['value'] = 10000
        with self.assertRaisesRegex(ValueError, 'TRUSTED_PREVIOUS_IDENTITY_REQUIRED'):
            e.produce(self.contract, self.case['after'], self.plan, altered, e.digest(self.previous))
        with self.assertRaisesRegex(ValueError, 'TRUSTED_PREVIOUS_IDENTITY_REQUIRED'):
            e.produce(self.contract, self.case['after'], self.plan, self.previous)
        altered = copy.deepcopy(self.previous)
        altered['contract_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'PREVIOUS_SCOPE_CHANGED'):
            e.produce(self.contract, self.case['after'], self.plan, altered, e.digest(altered))

    def test_full_judge_catches_forged_reused_result_even_with_new_hash(self):
        altered = copy.deepcopy(self.previous)
        altered['claims']['stable_total']['value'] = 10000
        result = e.produce(self.contract, self.case['after'], self.plan, altered, e.digest(altered))
        with self.assertRaisesRegex(ValueError, 'AUDIT_CLAIM_MISMATCH'):
            e.audit(self.contract, self.case['after'], self.plan, result)

    def test_unsupported_transform_and_unaccounted_input_refused(self):
        for change in ('unsupported', 'omitted'):
            contract = copy.deepcopy(self.contract)
            if change == 'unsupported':
                contract['claims'][0]['kind'] = 'guess_semantics'
            else:
                contract['claims'] = contract['claims'][:1]
            with self.assertRaises(ValueError):
                e.construct(contract, self.case['after'])

    def test_noncanonical_numbers_duplicate_headers_and_bad_rows_refused(self):
        for text in ('name,bytes\na,01\n', 'bytes,bytes\n1,2\n', 'name,bytes\na,2,3\n'):
            sources = dict(self.case['after'], **{'changing.csv': text})
            with self.assertRaises(ValueError):
                e.produce(self.contract, sources, self.plan)

    def test_adverse_domain_results_are_preserved(self):
        for case in e.cases():
            result = e.produce(case['contract'], case['after'], e.construct(case['contract'], case['after']))
            self.assertTrue(e.audit(case['contract'], case['after'], e.construct(case['contract'], case['after']), result)['accepted'])
            if case['id'].startswith('manufacturing'):
                self.assertFalse(result['claims']['manufacturing_sample']['value'])
            if case['id'].startswith('measurement'):
                self.assertEqual(result['claims']['measurement_batch']['value'], -18)

    def test_complete_fixed_experiment_equal_content_and_cost_reaudit(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'study'
            frozen = e.register(output)
            result = e.run(output)
            self.assertEqual(e.verify(output)['checked_rows'], 18)
            self.assertIsNone(result['actual_profit_usd'])
            self.assertFalse(result['retained_method_advantage'])
            for case in frozen['cases']:
                rows = {row['arm']: row for row in result['rows'] if row['case'] == case['id']}
                self.assertEqual(rows['ordinary_reuse']['artifact'], rows['retained_method']['artifact'])
                self.assertEqual(rows['ordinary_reuse']['complete_lifecycle_row_visits'], rows['retained_method']['complete_lifecycle_row_visits'])
                self.assertLess(rows['full_recompute']['complete_lifecycle_row_visits'], rows['retained_method']['complete_lifecycle_row_visits'])
            with self.assertRaisesRegex(ValueError, 'FIXED_EXECUTION_ALREADY_COMPLETE'):
                e.run(output)
            result['rows'].pop()
            (output / 'RESULT.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, 'RESULT_COVERAGE_OR_CLAIMS'):
                e.verify(output)


if __name__ == '__main__':
    unittest.main()
