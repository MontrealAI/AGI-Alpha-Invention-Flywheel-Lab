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

    def test_transitive_production_sources_bind_quotes(self):
        from pathlib import Path
        from unittest.mock import patch
        from adaptive_enterprise.instruments import SOURCE_PATHS
        self.assertTrue(set(SOURCE_PATHS) <= set(candidate.DEPENDENCIES))
        original = Path.read_bytes
        for name in ('commercial/service.py', 'commercial/service_verifier.py',
                     'adaptive_enterprise/strategies.py', 'commercial/ledger.py'):
            with self.subTest(changed=name):
                def changed(path):
                    raw = original(path)
                    return raw+b'\n# changed source' if path.as_posix().endswith('/'+name) else raw
                with patch.object(Path, 'read_bytes', changed):
                    with self.assertRaisesRegex(ValueError, 'QUOTE_SOURCE_OR_INPUT_CHANGED'):
                        candidate.select(self.raw, self.quotes, now=self.now,
                                         budget_microUSD=self.budget)

    def test_provider_identifiers_cannot_collide_with_internal_steps(self):
        adversarial = ('assemble_complete', 'internal_assemble_complete',
                       'provider_00', 'provider_23', 'a'*64, 'z'*64)
        for identifier in adversarial:
            quotes = copy.deepcopy(self.quotes)
            quotes[0]['id'] = identifier
            for observations in (quotes, list(reversed(quotes))):
                with self.subTest(identifier=identifier, reversed=observations is not quotes):
                    composed = candidate.select(self.raw, observations, now=self.now,
                                                budget_microUSD=self.budget)
                    ordinary = self.ordinary(observations)
                    self.assertEqual(composed['quote_ids'], ordinary['quote_ids'])
                    self.assertEqual(composed['total_microUSD'], ordinary['total_microUSD'])
                    self.assertIn(identifier, composed['quote_ids'])
                    self.assertTrue(candidate.execute(self.raw, observations, composed,
                                                      now=self.now)['accepted'])
        # Equal-price choices must retain ORIGINAL quote-ID ordering, not input order.
        quotes = copy.deepcopy(self.quotes)
        for q, identifier in zip(quotes, ('provider_00','assemble_complete',
                'internal_assemble_complete','provider_01','provider_23','a'*64,'z'*64)):
            q['id'] = identifier
            if q['service_id'] != 'operations_bundle': q['cost_microUSD'] = 1750000
        for observations in (quotes, list(reversed(quotes))):
            composed = candidate.select(self.raw, observations, now=self.now,
                                        budget_microUSD=self.budget)
            self.assertEqual(composed['quote_ids'], self.ordinary(observations)['quote_ids'])
            self.assertTrue(candidate.execute(self.raw, observations, composed, now=self.now)['accepted'])

    def test_unaffordable_large_quote_does_not_poison_affordable_bundle(self):
        quotes = copy.deepcopy(self.quotes)
        next(q for q in quotes if q['id']=='evidence_matrix_alternate')['cost_microUSD']=10_000_010_000
        selected = candidate.select(self.raw, quotes, now=self.now, budget_microUSD=self.budget)
        self.assertEqual(selected['quote_ids'], self.ordinary(quotes)['quote_ids'])
        self.assertEqual(selected['total_microUSD'], 5_500_000)
        self.assertEqual(selected['search']['route'], 'symbolic_compose')
        self.assertTrue(candidate.execute(self.raw, quotes, selected, now=self.now)['accepted'])

    def test_exact_budget_boundaries_and_labeled_large_budget_fallback(self):
        for budget in (0, candidate.ASSEMBLY-1, candidate.ASSEMBLY, 5_499_999,
                       5_500_000, 10_000_000_000, 10_000_009_999, 10_000_010_000):
            with self.subTest(budget=budget):
                selected = candidate.select(self.raw, self.quotes, now=self.now, budget_microUSD=budget)
                ordinary = self.ordinary(budget=budget)
                for key in ('status','quote_ids','total_microUSD'):
                    self.assertEqual(selected[key], ordinary[key])
                route = ('ordinary_fallback' if budget<2_000_000 or budget//10000>1_000_000
                         else 'symbolic_compose')
                self.assertEqual(selected['search']['route'], route)
        quotes=copy.deepcopy(self.quotes)
        for q in quotes:
            q['cost_microUSD']=30_000_000_000 if q['service_id']=='operations_bundle' else 10_000_000_000
        # Primitive cover and integrated provider tie on price; fewer quotes wins.
        for budget in (30_000_249_999, 30_000_250_000):
            selected=candidate.select(self.raw, quotes, now=self.now, budget_microUSD=budget)
            ordinary=self.ordinary(quotes,budget=budget)
            for key in ('status','quote_ids','total_microUSD'):
                self.assertEqual(selected[key],ordinary[key])
            self.assertEqual(selected['search']['route'],'ordinary_fallback')
            if selected['status']=='READY':
                self.assertEqual(selected['quote_ids'],['integrated_provider'])
                self.assertTrue(candidate.execute(self.raw,quotes,selected,now=self.now)['accepted'])
        for budget in (-1, True, 1.5, '8000000', None):
            for policy in ('composed','ordinary'):
                with self.subTest(budget=budget,policy=policy), self.assertRaises(ValueError):
                    candidate.select(self.raw,self.quotes,now=self.now,budget_microUSD=budget,policy=policy)
        for cost in (0,-10000,True,1,1.5):
            quotes=copy.deepcopy(self.quotes);quotes[1]['cost_microUSD']=cost
            for policy in ('composed','ordinary'):
                with self.subTest(cost=cost,policy=policy), self.assertRaises(ValueError):
                    candidate.select(self.raw,quotes,now=self.now,budget_microUSD=40_000_000_000,policy=policy)

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
