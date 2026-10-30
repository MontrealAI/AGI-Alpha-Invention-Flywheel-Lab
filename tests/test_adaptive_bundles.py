import copy
import unittest
from unittest.mock import patch

from adaptive_enterprise.bundles import PROMISE, audit_bundle, build_bundle
from adaptive_enterprise.instruments import produce, synthetic_raw


def bundle_order(index=0):
    components = []
    for service_id in ['reconciliation', 'kpi_variance', 'evidence_matrix']:
        raw = synthetic_raw(service_id, index)
        artifact = produce(raw, 'canonical' if index < 8 else 'generated_schema')
        components.append({'job_id': raw['order_id'], 'service_id': service_id, 'raw_order': raw, 'artifact': artifact})
    return {'order_id': 'adaptive012-operations_bundle-' + str(index), 'service_id': 'operations_bundle',
            'scope': 'SYNTHETIC_PUBLIC_WORKLOAD', 'currency': 'USD', 'components': components,
            'work_keys': [component['job_id'] for component in components]}


class AdaptiveBundleTests(unittest.TestCase):
    def test_actual_bundle_runs_three_shared_component_contracts(self):
        order = bundle_order()
        calls = []
        def production(raw, method):
            calls.append((raw['service_id'], raw['order_id']))
            return produce(raw, method)
        with patch('adaptive_enterprise.instruments.produce', side_effect=production):
            artifact = build_bundle(order)
        self.assertEqual(len(calls), 3)
        self.assertEqual({service for service, _ in calls}, {'reconciliation', 'kpi_variance', 'evidence_matrix'})
        self.assertEqual(artifact['work_keys'], order['work_keys'])
        self.assertEqual(len(set(artifact['work_keys'])), 3)
        self.assertEqual(artifact['promise'], PROMISE)
        checked = audit_bundle(order, artifact)
        self.assertTrue(checked['accepted'])
        self.assertEqual(len(checked['component_acceptance']), 3)
        self.assertTrue(all(item['accepted'] for item in checked['component_acceptance']))

    def test_bundle_checker_never_calls_the_producer(self):
        order = bundle_order(1)
        artifact = build_bundle(order)
        with patch('adaptive_enterprise.instruments.produce', side_effect=AssertionError('checker called producer')):
            self.assertTrue(audit_bundle(order, artifact)['accepted'])

    def test_generated_schema_component_is_real_executable_work(self):
        order = bundle_order(9)
        self.assertNotEqual(order['components'][0]['artifact']['plan']['mapping']['invoices']['id'], 'id')
        artifact = build_bundle(order)
        self.assertTrue(audit_bundle(order, artifact)['accepted'])

    def test_duplicate_work_or_component_service_refused(self):
        for mode in ['work', 'service', 'same-job', 'missing']:
            order = bundle_order()
            if mode == 'work':
                order['work_keys'][1] = order['work_keys'][0]
            elif mode == 'service':
                order['components'][1]['service_id'] = 'reconciliation'
            elif mode == 'same-job':
                order['components'][1] = copy.deepcopy(order['components'][0])
                order['work_keys'][1] = order['work_keys'][0]
            else:
                order['components'].pop()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build_bundle(order)

    def test_source_identity_and_prepared_content_must_match_reexecution(self):
        order = bundle_order()
        order['components'][0]['raw_order']['order_id'] = 'different-source'
        with self.assertRaises(ValueError):
            build_bundle(order)
        order = bundle_order()
        order['components'][0]['artifact']['useful_outcome']['totals']['matched_invoice_cents'] += 1
        with self.assertRaisesRegex(ValueError, 'COMPONENT_REEXECUTION_MISMATCH'):
            build_bundle(order)

    def test_rehashed_unsupported_output_is_rejected_by_independent_component_checker(self):
        order = bundle_order()
        artifact = build_bundle(order)
        changed = copy.deepcopy(artifact['components'][2]['artifact'])
        changed['useful_outcome']['rows'][0]['value'] = 'Unsupported capability'
        order['components'][2]['artifact'] = copy.deepcopy(changed)
        artifact['components'][2]['artifact'] = changed
        self.assertFalse(audit_bundle(order, artifact)['accepted'])

    def test_staged_readiness_cannot_be_relabelled_as_complete_bundle(self):
        order = bundle_order()
        raw = synthetic_raw('reconciliation', 15)
        staged = produce(raw, 'staged_readiness')
        order['components'][0] = {'job_id': raw['order_id'], 'service_id': 'reconciliation', 'raw_order': raw, 'artifact': staged}
        order['work_keys'][0] = raw['order_id']
        with self.assertRaisesRegex(ValueError, 'FULL_BUNDLE_CANNOT_INCLUDE_STAGED_COMPONENT'):
            build_bundle(order)

    def test_missing_extra_reordered_and_altered_components_are_rejected(self):
        order = bundle_order()
        original = build_bundle(order)
        for mode in ['missing', 'extra', 'reordered', 'work-key', 'promise', 'scope']:
            artifact = copy.deepcopy(original)
            if mode == 'missing':
                artifact['components'].pop()
            elif mode == 'extra':
                artifact['components'].append(copy.deepcopy(artifact['components'][0]))
            elif mode == 'reordered':
                artifact['components'].reverse()
            elif mode == 'work-key':
                artifact['work_keys'][0] = 'a-new-independent-sale'
            elif mode == 'promise':
                artifact['promise'] = 'Guaranteed customer profit'
            else:
                artifact['outcome_scope'] = 'intake_readiness'
            with self.subTest(mode=mode):
                self.assertFalse(audit_bundle(order, artifact)['accepted'])

    def test_unknown_fields_and_unapproved_scope_are_rejected(self):
        order = bundle_order()
        artifact = build_bundle(order)
        artifact['extra_claim'] = 'Unverified outcome'
        self.assertFalse(audit_bundle(order, artifact)['accepted'])
        order['scope'] = 'PRIVATE_CUSTOMER'
        with self.assertRaises(ValueError):
            build_bundle(order)


if __name__ == '__main__':
    unittest.main()
