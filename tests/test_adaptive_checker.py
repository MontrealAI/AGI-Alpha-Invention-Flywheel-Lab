import copy
from pathlib import Path
import unittest

from adaptive_enterprise.checkers import audit_delivery, identity, READINESS_PROMISE
from commercial.service import reconcile


def example():
    raw = {'order_id': 'independent-check-012', 'service_id': 'reconciliation',
           'scope': 'SYNTHETIC_PUBLIC_WORKLOAD', 'currency': 'USD', 'source_order': None,
           'tables': {'invoices': [{'x': 'I1', 'y': 'C', 'z': '10.01'}, {'x': 'I2', 'y': 'C', 'z': '20.02'}],
                      'payments': [{'a': 'P1', 'b': 'C', 'c': '10.01', 'd': ['I1']}, {'a': 'P2', 'b': 'C', 'c': '20.02', 'd': ['I2']}]},
           'units': {'invoices': {'z': 'USD'}, 'payments': {'c': 'USD'}}}
    normalized = {'order_id': raw['order_id'], 'scope': raw['scope'], 'currency': 'USD', 'require_complete': False,
                  'invoices': [{'id': 'I1', 'customer': 'C', 'amount_cents': 1001}, {'id': 'I2', 'customer': 'C', 'amount_cents': 2002}],
                  'payments': [{'id': 'P1', 'customer': 'C', 'amount_cents': 1001, 'invoice_refs': ['I1']}, {'id': 'P2', 'customer': 'C', 'amount_cents': 2002, 'invoice_refs': ['I2']}]}
    plan = {'schema': 'adaptive012/intake-plan/v1', 'service_id': 'reconciliation', 'status': 'READY',
            'mapping': {'invoices': {'id': 'x', 'customer': 'y', 'amount_cents': 'z'},
                        'payments': {'id': 'a', 'customer': 'b', 'amount_cents': 'c', 'invoice_refs': 'd'}},
            'units': {'invoices': 'USD', 'payments': 'USD'},
            'constraints': ['preserve_source_rows', 'explicit_money_units', 'unique_record_identity', 'referential_customer_consistency'],
            'search': {'candidates_tested': 1, 'candidate_count': 30, 'operation_count': 4, 'retained_constraints_used': []}, 'failure': None}
    artifact = {'order_id': raw['order_id'], 'service_id': 'reconciliation', 'scope': raw['scope'], 'currency': 'USD',
                'outcome_scope': 'complete_outcome', 'method': 'generated_schema', 'plan': plan,
                'normalized_input': normalized, 'useful_outcome': reconcile(normalized)}
    return raw, artifact


class AdaptiveCheckerTests(unittest.TestCase):
    def test_independent_checked_conversion_and_outcome(self):
        raw, artifact = example()
        self.assertTrue(audit_delivery('reconciliation', raw, artifact)['accepted'])
        self.assertEqual(artifact['normalized_input']['invoices'][0]['amount_cents'], 1001)

    def test_source_mapping_and_normalization_tampering_refused(self):
        raw, original = example()
        for kind in ['unit', 'row', 'customer', 'claim', 'method', 'constraints']:
            artifact = copy.deepcopy(original)
            if kind == 'unit':
                artifact['plan']['units']['invoices'] = 'cents'
            elif kind == 'row':
                artifact['normalized_input']['invoices'].pop()
            elif kind == 'customer':
                artifact['normalized_input']['payments'][0]['customer'] = 'Unknown'
            elif kind == 'claim':
                artifact['useful_outcome']['totals']['matched_invoice_cents'] += 1
            elif kind == 'method':
                artifact['method'] = 'canonical'
            else:
                artifact['plan']['constraints'] = []
            with self.subTest(kind=kind):
                self.assertFalse(audit_delivery('reconciliation', raw, artifact)['accepted'])

    def test_real_missing_units_support_only_explicit_readiness(self):
        raw, artifact = example()
        raw['units'] = {'invoices': {}, 'payments': {}}
        artifact.update(outcome_scope='intake_readiness', method='staged_readiness', normalized_input=None)
        artifact['plan'].update(status='BLOCKED', mapping=None, units={}, failure='MISSING_TYPED_MAPPING_OR_FACTS')
        artifact['useful_outcome'] = {'order_id': raw['order_id'], 'source_rows': {'invoices': 2, 'payments': 2},
                                     'missing_or_ambiguous': ['MISSING_TYPED_MAPPING_OR_FACTS'], 'production_ready': False,
                                     'promised_outcome': READINESS_PROMISE, 'source_sha256': identity(raw)}
        self.assertTrue(audit_delivery('reconciliation', raw, artifact)['accepted'])
        artifact['useful_outcome']['production_ready'] = True
        self.assertFalse(audit_delivery('reconciliation', raw, artifact)['accepted'])

    def test_fabricated_missing_units_failure_refused(self):
        raw, artifact = example()
        artifact.update(outcome_scope='intake_readiness', method='staged_readiness', normalized_input=None)
        artifact['plan'].update(status='BLOCKED', mapping=None, units={}, failure='MISSING_TYPED_MAPPING_OR_FACTS')
        artifact['useful_outcome'] = {'order_id': raw['order_id'], 'source_rows': {'invoices': 2, 'payments': 2},
                                     'missing_or_ambiguous': ['MISSING_TYPED_MAPPING_OR_FACTS'], 'production_ready': False,
                                     'promised_outcome': READINESS_PROMISE, 'source_sha256': identity(raw)}
        result = audit_delivery('reconciliation', raw, artifact)
        self.assertFalse(result['accepted'])
        self.assertTrue(any('FABRICATED_INTAKE_BLOCKER' in error for error in result['errors']))

    def test_blocker_reason_is_independently_bound(self):
        raw, artifact = example()
        raw['units'] = {'invoices': {}, 'payments': {}}
        artifact.update(outcome_scope='intake_readiness', method='staged_readiness', normalized_input=None)
        artifact['plan'].update(status='BLOCKED', mapping=None, units={}, failure='AMBIGUOUS_MAPPING')
        artifact['useful_outcome'] = {'order_id': raw['order_id'], 'source_rows': {'invoices': 2, 'payments': 2},
                                     'missing_or_ambiguous': ['AMBIGUOUS_MAPPING'], 'production_ready': False,
                                     'promised_outcome': READINESS_PROMISE, 'source_sha256': identity(raw)}
        self.assertFalse(audit_delivery('reconciliation', raw, artifact)['accepted'])

    def test_extra_unsupported_claim_and_private_scope_refused(self):
        raw, artifact = example()
        artifact['certification'] = 'Unsupported'
        self.assertFalse(audit_delivery('reconciliation', raw, artifact)['accepted'])
        raw, artifact = example()
        raw['scope'] = 'PRIVATE_CUSTOMER'
        self.assertFalse(audit_delivery('reconciliation', raw, artifact)['accepted'])

    def test_no_producer_or_strategy_import(self):
        source = (Path(__file__).resolve().parents[1] / 'adaptive_enterprise/checkers.py').read_text()
        self.assertNotIn('from adaptive_enterprise.instruments', source)
        self.assertNotIn('from adaptive_enterprise.strategies', source)


if __name__ == '__main__':
    unittest.main()
