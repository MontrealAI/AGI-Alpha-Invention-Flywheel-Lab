"""Frozen public quote arithmetic and actual local delivery; no market proof."""
import copy
import unittest

from adaptive_enterprise.bundles import audit_bundle
from adaptive_enterprise.instruments import produce, synthetic_raw
from connected_enterprise import conditional_procurement053 as candidate
from connected_enterprise.procurement_verify053 import ordinary_select, audit_selection


def raw_bundle():
    components = []
    for service in candidate.SERVICES:
        raw = synthetic_raw(service, 0, 53)
        components.append(dict(job_id=raw['order_id'], service_id=service,
                               raw_order=raw, artifact=produce(raw, 'canonical')))
    return dict(order_id='procurement053-test', service_id='operations_bundle',
                scope='SYNTHETIC_PUBLIC_WORKLOAD', currency='USD', components=components,
                work_keys=[c['job_id'] for c in components])


class ProcurementTests(unittest.TestCase):
    def setUp(self):
        self.raw = raw_bundle()
        self.quotes = candidate.fixture_quotes(self.raw)
        self.now = 24
        self.budget = 8_000_000

    def ordinary(self, quotes=None, now=None, budget=None):
        return ordinary_select(self.quotes if quotes is None else quotes, candidate.SERVICES,
            self.now if now is None else now, self.budget if budget is None else budget, candidate.ASSEMBLY)

    def audit(self, result, quotes=None, now=None):
        return audit_selection(result, self.quotes if quotes is None else quotes, candidate.SERVICES,
            self.now if now is None else now, self.budget, candidate.ASSEMBLY)

    def test_primary_complete_cost_matches_candidate(self):
        expected = self.ordinary()
        self.assertEqual(expected['total_microUSD'], 5_500_000)
        self.assertEqual(len(expected['quote_ids']), 3)
        result = candidate.select(self.raw, self.quotes, now=24, budget_microUSD=self.budget)
        for field in expected: self.assertEqual(result[field], expected[field])
        self.assertTrue(self.audit(result)['accepted'])

    def test_integrated_supplier_and_tie_are_not_excluded(self):
        for cost in (4_000_000, 5_250_000):
            quotes = copy.deepcopy(self.quotes)
            quotes[-1]['cost_microUSD'] = cost
            ordinary = self.ordinary(quotes)
            self.assertEqual(ordinary['quote_ids'], ['integrated_provider'])
            selected = candidate.select(self.raw, quotes, now=24, budget_microUSD=self.budget)
            for field in ordinary: self.assertEqual(selected[field], ordinary[field])

    def test_supplier_ties_ids_and_observation_order(self):
        quotes = copy.deepcopy(self.quotes)
        for q in quotes:
            if q['id'].endswith('_alternate'): q['cost_microUSD'] = 1_750_000
        selected = self.ordinary(list(reversed(quotes)))
        self.assertTrue(all(x.endswith('_alternate') for x in selected['quote_ids']))
        composed = candidate.select(self.raw, quotes, now=24, budget_microUSD=self.budget)
        self.assertEqual(composed['quote_ids'], selected['quote_ids'])

    def test_expiry_availability_and_boundary(self):
        expired = candidate.fixture_quotes(self.raw, 'expired')
        self.assertEqual(self.ordinary(expired)['status'], 'NO_COMPLETE_AFFORDABLE_BUNDLE')
        self.assertEqual(self.ordinary(now=0)['status'], 'READY')
        self.assertEqual(self.ordinary(now=72)['status'], 'NO_COMPLETE_AFFORDABLE_BUNDLE')
        quotes = copy.deepcopy(self.quotes)
        for q in quotes:
            if q['service_id'] in ('evidence_matrix', 'operations_bundle'): q['available'] = False
        self.assertEqual(self.ordinary(quotes)['status'], 'NO_COMPLETE_AFFORDABLE_BUNDLE')
        self.assertEqual(self.ordinary(budget=5_500_000)['status'], 'READY')
        self.assertEqual(self.ordinary(budget=5_499_999)['status'], 'NO_COMPLETE_AFFORDABLE_BUNDLE')

    def test_forged_incomplete_cost_and_stale_selection(self):
        selected = self.ordinary()
        for mutation in (lambda x: x['quote_ids'].pop(),
                         lambda x: x.update(total_microUSD=1),
                         lambda x: x['quote_ids'].append(x['quote_ids'][0]),
                         lambda x: x.update(total_microUSD=True),
                         lambda x: x.update(now=72)):
            bad = copy.deepcopy(selected); mutation(bad)
            self.assertFalse(self.audit(bad)['accepted'])
        self.assertFalse(self.audit(selected, now=72)['accepted'])
        refusal = dict(status='NO_COMPLETE_AFFORDABLE_BUNDLE', quote_ids=[], total_microUSD=None)
        self.assertFalse(self.audit(refusal)['accepted'])

    def test_all_outputs_execute_and_missing_component_rejects(self):
        selected = candidate.select(self.raw, self.quotes, now=24, budget_microUSD=self.budget)
        delivered = candidate.execute(self.raw, self.quotes, selected, now=24)
        self.assertTrue(delivered['accepted'])
        self.assertEqual({r['service_id'] for r in delivered['completed_components']}, set(candidate.SERVICES))
        broken = copy.deepcopy(delivered['artifact']); broken['components'].pop()
        self.assertFalse(audit_bundle(self.raw, broken)['accepted'])
        default = candidate.execute(self.raw, self.quotes, selected, now=24, default_service='kpi_variance')
        self.assertFalse(default['accepted']); self.assertIsNone(default['artifact'])
        self.assertEqual(default['failure'], 'LOCAL_AUTHORED_PROVIDER_DEFAULT')

    def test_invalid_quotes_and_goal_reject(self):
        for field, value in (('available', 1), ('cost_microUSD', True), ('cost_microUSD', -1),
                             ('valid_until', True), ('source_sha256', 'invalid')):
            quotes = copy.deepcopy(self.quotes); quotes[0][field] = value
            with self.assertRaises(ValueError): self.ordinary(quotes)
        with self.assertRaises(ValueError):
            ordinary_select(self.quotes, ['reconciliation'], 24, self.budget, candidate.ASSEMBLY)
        quotes = copy.deepcopy(self.quotes); quotes[1]['id'] = quotes[0]['id']
        with self.assertRaises(ValueError): self.ordinary(quotes)


if __name__ == '__main__': unittest.main()
