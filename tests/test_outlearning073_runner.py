import copy
import unittest
from unittest.mock import patch
from outlearning073 import run
from outlearning073.worlds import development_requests


class RunnerSemanticReplayTests(unittest.TestCase):
    def setUp(self):
        self.source = {'scope': 'UNSCORED_K1_DEVELOPMENT_TEST'}
        self.case = {'request': development_requests()[0], 'arm': 'retained'}
        self.record = run._build(self.case['request'], self.case['arm'], self.source)
        self.record['verification'] = run._compact(run.verify(self.case['request'], self.record['artifact']))

    def test_valid_development_construction_has_reproducible_semantics(self):
        checked = run._check_case(copy.deepcopy(self.record), self.case, self.source)
        self.assertTrue(checked['verification']['accepted'])

    def test_forged_discovery_trace_cannot_borrow_accepted_artifact(self):
        forged = copy.deepcopy(self.record)
        forged['construction_trace']['claimed_discovery'] = 'Invented after accepted output existed'
        self.assertEqual(forged['artifact'], self.record['artifact'])
        with self.assertRaises(ValueError):
            run._check_case(forged, self.case, self.source)

    def test_forged_free_probe_receipt_cannot_borrow_accepted_artifact(self):
        forged = copy.deepcopy(self.record)
        forged['probes'] = [{'actions': [], 'result': {'status': 'observed', 'cost_units': 0, 'remaining_units': 32, 'observations': [], 'effects': {'p0': 1, 'p1': 0}}}]
        forged['diagnostic_units'] = 0
        self.assertEqual(forged['artifact'], self.record['artifact'])
        with self.assertRaises(ValueError):
            run._check_case(forged, self.case, self.source)

    def test_forged_routine_identity_cannot_claim_retained_execution(self):
        forged = copy.deepcopy(self.record)
        forged['routine'] = 'unexecuted-discovery-generator:build'
        with self.assertRaises(ValueError):
            run._check_case(forged, self.case, self.source)


class RunnerNativeClaimBindingTests(unittest.TestCase):
    def test_public_snapshot_cannot_replace_independently_audited_summary(self):
        audited = {'accepted': True, 'summary': {'expenses': 100}}
        result = {'snapshot': {'summary': {'expenses': 0}}}
        with patch.object(run.native, 'audit_export', return_value=audited):
            with self.assertRaisesRegex(ValueError, 'NATIVE_SUMMARY_CLAIM_CHANGED'):
                run._audit_native_result(None, {}, {}, result, {})

    def test_valid_audit_does_not_validate_incomplete_complete_cost_claim(self):
        expense = run.economics.ECONOMIC_PLAN['sunk_research_USD_before_entry_decision'] * 1_000_000
        account = {'ledger': {'actions': []}}
        case = {'scenario': {'enter': False}, 'opening_microUSD': 100_000_000_000}
        summary = {'expenses': expense, 'profit': -expense}
        result = {'snapshot': {'summary': copy.deepcopy(summary)}, 'record_sha256': run.digest(account), 'scenario': copy.deepcopy(case['scenario']), 'opening_microUSD': case['opening_microUSD'], 'plan_sha256': run.digest(run.economics.ECONOMIC_PLAN), 'costs': [{'stage': 'K1', 'sunk_research_microUSD': expense, 'total_microUSD': expense}], 'expense_reconciliation': {'expected_microUSD': expense, 'native_microUSD': expense, 'equal': True}, 'commercial_verdict': 'NO_CONNECTED_COMMERCIAL_SUCCESS'}
        audited = {'accepted': True, 'summary': summary}
        with patch.object(run.native, 'audit_export', return_value=audited):
            self.assertEqual(run._audit_native_result(None, {}, account, result, case), audited)
        forged = copy.deepcopy(result)
        forged['snapshot']['summary']['expenses'] += 1
        inconsistent_audit = {'accepted': True, 'summary': copy.deepcopy(forged['snapshot']['summary'])}
        with patch.object(run.native, 'audit_export', return_value=inconsistent_audit):
            with self.assertRaisesRegex(ValueError, 'COMPLETE_EXPENSE_CLAIM_CHANGED'):
                run._audit_native_result(None, {}, account, forged, case)


if __name__ == '__main__':
    unittest.main()
