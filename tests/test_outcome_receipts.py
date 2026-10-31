"""Only publication-boundary checks; native useful-output audit is reused."""
import copy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'scripts/outcome_receipts.py'
spec = importlib.util.spec_from_file_location('outcome_receipts', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OutcomeReceipts(unittest.TestCase):
    def setUp(self):
        service = {'accepted': True, 'outcome_scope': 'complete_outcome',
                   **dict.fromkeys(('actual_execution_artifact_sha256',
                                    'native_delivered_artifact_sha256',
                                    'useful_outcome_sha256'), 'a' * 64)}
        order = {'id': 'o1', 'job_id': 'j1', 'offer': {'service_id': 'reconciliation'},
                 'outcome': 'SETTLED', 'qualified_time': 0, 'production_time': 1,
                 'acceptance_time': 2, 'collection_time': 3, 'service_receipt': service}
        self.result = {'scope': 'CONDITIONAL_SIMULATION', 'complete': True, 'source': {'sha256': 'b' * 64}, 'orders': [order], 'accepted_jobs': 1, 'paid_jobs': 1}
        self.audit = {'accepted': True, 'scope': 'NATIVE_FINANCIAL_AND_OPERATING_SEMANTICS',
                      'verifier_source_sha256': 'c' * 64, 'source_sha256': 'b' * 64,
                      'verifier_matches_world_source_snapshot': True, 'orders_reexecuted': 1}

    def test_paid_accepted_and_rejected_are_distinct(self):
        refund = copy.deepcopy(self.result['orders'][0])
        refund.update(id='o2', outcome='REFUNDED', collection_time=None)
        rejected = copy.deepcopy(refund)
        rejected.update(id='o3', outcome='QUALITY_REJECTED', acceptance_time=None,
                        service_receipt={'accepted': False})
        self.result['orders'].extend([refund, rejected])
        self.result['accepted_jobs'] = 2
        self.audit['orders_reexecuted'] = 2
        receipt = module.customer_outcomes(self.result, self.audit)
        self.assertEqual((receipt['production_attempts'], receipt['useful_outputs_accepted'],
                          receipt['paid_outputs']), (3, 2, 1))
        self.assertEqual(receipt['orders'][2]['outcome'], 'QUALITY_REJECTED')
        self.assertIsNone(receipt['orders'][2]['useful_outcome_sha256'])

    def test_missing_hash_and_contradictory_collection_rejected(self):
        for mutate in (lambda o: o['service_receipt'].pop('useful_outcome_sha256'),
                       lambda o: o.update(outcome='REFUNDED'),
                       lambda o: o.update(outcome='QUALITY_REJECTED')):
            result = copy.deepcopy(self.result)
            mutate(result['orders'][0])
            with self.assertRaises(ValueError):
                module.customer_outcomes(result, self.audit)

    def test_no_partial_or_failed_audit_success_receipt(self):
        for key, value in [('complete', False), ('complete', None)]:
            result = copy.deepcopy(self.result)
            result[key] = value
            with self.assertRaises(ValueError):
                module.customer_outcomes(result, self.audit)
        with self.assertRaises(ValueError):
            module.customer_outcomes(self.result, {**self.audit, 'accepted': False})

    def test_projection_does_not_export_authority_or_inputs(self):
        self.result['owned_account'] = {'private_key': 'DO_NOT_EXPORT'}
        self.result['orders'][0]['service_receipt']['artifact'] = {'input': 'DO_NOT_EXPORT'}
        self.assertNotIn('DO_NOT_EXPORT', str(module.customer_outcomes(self.result, self.audit)))


if __name__ == '__main__':
    unittest.main()
