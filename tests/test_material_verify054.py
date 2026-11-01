import copy
import unittest
from types import SimpleNamespace

from connected_enterprise.material_verify054 import audit_plan, audit_transfer, digest, validate_order


def fixture():
    raw = {'schema': 'material054/order/v1', 'scope': 'SYNTHETIC_PUBLIC_WORKLOAD',
           'order_id': 'first', 'kerf_mm': 2, 'min_remnant_mm': 10,
           'stocks': [{'id': 'A', 'length_mm': 100, 'grade': 'steel',
                       'source_sha256': 'a' * 64, 'cost_microUSD': 30},
                      {'id': 'B', 'length_mm': 80, 'grade': 'steel',
                       'source_sha256': 'b' * 64, 'cost_microUSD': 20}],
           'pieces': [{'id': 'p1', 'length_mm': 30, 'grade': 'steel'},
                      {'id': 'p2', 'length_mm': 40, 'grade': 'steel'}]}
    source_hash = digest(raw)
    remnant = {'id': 'first:A:remnant', 'parent_stock_id': 'A', 'length_mm': 26,
               'grade': 'steel', 'cost_microUSD': 0,
               'source_sha256': digest({'input_sha256': source_hash, 'stock_id': 'A',
                                       'piece_ids': ['p1', 'p2'], 'remnant_mm': 26})}
    artifact = {'schema': 'material054/plan/v1', 'scope': raw['scope'], 'order_id': 'first',
                'input_sha256': source_hash,
                'patterns': [{'stock_id': 'A', 'piece_ids': ['p1', 'p2'],
                              'used_mm': 74, 'remnant_mm': 26}],
                'unused_stock_ids': ['B'], 'remnants': [remnant],
                'material_cost_microUSD': 30, 'consumed_mm': 74}
    return raw, artifact


class IndependentMaterialVerifierTests(unittest.TestCase):
    def test_exact_plan_accepted(self):
        raw, artifact = fixture()
        self.assertTrue(audit_plan(raw, artifact)['accepted'])

    def test_malformed_and_forged_plans_rejected(self):
        alterations = [
            lambda a: a.update(extra=True),
            lambda a: a.update(material_cost_microUSD=True),
            lambda a: a.update(consumed_mm=73),
            lambda a: a.update(material_cost_microUSD=29),
            lambda a: a.update(input_sha256='f' * 64),
            lambda a: a['patterns'][0].update(piece_ids=['p1']),
            lambda a: a['patterns'][0].update(piece_ids=['p1', 'p1']),
            lambda a: a['patterns'][0].update(piece_ids=['p2', 'p1']),
            lambda a: a['patterns'][0].update(used_mm=75),
            lambda a: a['patterns'][0].update(remnant_mm=-1),
            lambda a: a['patterns'].append(copy.deepcopy(a['patterns'][0])),
            lambda a: a['unused_stock_ids'].append('A'),
            lambda a: a['unused_stock_ids'].append('B'),
            lambda a: a['remnants'][0].update(length_mm=27),
            lambda a: a['remnants'][0].update(cost_microUSD=False),
            lambda a: a['remnants'][0].update(source_sha256='c' * 64),
            lambda a: a['remnants'].clear(),
            lambda a: a['remnants'].append(copy.deepcopy(a['remnants'][0])),
        ]
        for mutation in alterations:
            with self.subTest(mutation=mutation):
                raw, artifact = fixture()
                mutation(artifact)
                self.assertFalse(audit_plan(raw, artifact)['accepted'])

    def test_bool_and_duplicate_sources_rejected(self):
        mutations = [lambda r: r.update(kerf_mm=True),
                     lambda r: r.update(min_remnant_mm=False),
                     lambda r: r['stocks'][0].update(length_mm=True),
                     lambda r: r['stocks'][0].update(cost_microUSD=False),
                     lambda r: r['stocks'][0].update(source_sha256='A' * 64),
                     lambda r: r['pieces'][0].update(length_mm=True),
                     lambda r: r['pieces'].append(copy.deepcopy(r['pieces'][0])),
                     lambda r: r['stocks'].append(copy.deepcopy(r['stocks'][0]))]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                raw, _ = fixture()
                mutation(raw)
                with self.assertRaises(ValueError):
                    validate_order(raw)

    def test_grade_and_overcut_independently_rejected(self):
        for changes in [{'grade': 'aluminum'}, {'length_mm': 99}]:
            raw, artifact = fixture()
            raw['pieces'][0].update(changes)
            artifact['input_sha256'] = digest(raw)
            self.assertFalse(audit_plan(raw, artifact)['accepted'])

    def successor(self):
        raw, artifact = fixture()
        child = copy.deepcopy(raw)
        child['order_id'] = 'second'
        child['stocks'] = [{k: v for k, v in artifact['remnants'][0].items()
                            if k != 'parent_stock_id'}, copy.deepcopy(raw['stocks'][1])]
        child['pieces'] = [{'id': 'q1', 'length_mm': 20, 'grade': 'steel'}]
        return raw, artifact, child

    def test_exact_remnant_and_unused_stock_transfer(self):
        self.assertTrue(audit_transfer(*self.successor())['accepted'])

    def test_bad_transfers_rejected(self):
        mutations = [lambda c: c['stocks'][0].update(length_mm=27),
                     lambda c: c['stocks'][0].update(id='first:fake:remnant'),
                     lambda c: c['stocks'][0].update(id='renamed-with-known-hash'),
                     lambda c: c['stocks'][0].update(source_sha256='f' * 64),
                     lambda c: c['stocks'][1].update(length_mm=81),
                     lambda c: c.update(order_id='first')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                raw, artifact, child = self.successor()
                mutation(child)
                self.assertFalse(audit_transfer(raw, artifact, child)['accepted'])
        raw, artifact, child = self.successor()
        child['stocks'].append(copy.deepcopy(raw['stocks'][0]))
        self.assertFalse(audit_transfer(raw, artifact, child)['accepted'])

    def test_corrupt_parent_cannot_authorize_transfer(self):
        raw, artifact, child = self.successor()
        artifact['consumed_mm'] = 0
        self.assertFalse(audit_transfer(raw, artifact, child)['accepted'])

    def test_fresh_external_stock_allowed(self):
        raw, artifact, child = self.successor()
        child['stocks'].append({'id': 'fresh', 'length_mm': 200, 'grade': 'steel',
                                'source_sha256': 'e' * 64, 'cost_microUSD': 60})
        self.assertTrue(audit_transfer(raw, artifact, child)['accepted'])

    def test_bad_unserializable_inputs_fail_closed(self):
        raw, artifact = fixture()
        artifact['patterns'] = {1, 2}
        receipt = audit_plan(raw, artifact)
        self.assertFalse(receipt['accepted'])
        self.assertIsNone(receipt['artifact_sha256'])

    def test_native_successor_gate_rejects_missing_or_unreleased_parent(self):
        # Source-only exercise of the native adapter: no account or files opened.
        from commercial.ledger import TapeExchange
        for parent_state in [None, 'offered', 'consented', 'funded', 'verified', 'cancelled']:
            with self.subTest(parent_state=parent_state):
                exchange = TapeExchange.__new__(TapeExchange)
                exchange._adaptive_writer = None
                exchange.persistence = None
                exchange.last_day = 0
                exchange.manifest = {'schema': 'agi-alpha/material054-services/v1'}
                exchange.jobs = {'next': {'job': {'parent_job_id': 'parent'}}}
                exchange.actions = ([] if parent_state is None else [
                    {'op': 'offer', 'args': {'job_id': 'parent', 'id': 'parent-sale'}}])
                exchange.ex = SimpleNamespace(snapshot=lambda: {}, order=lambda _: {'state': parent_state})
                with self.assertRaisesRegex(ValueError, 'MATERIAL_PARENT_NOT_RELEASED'):
                    exchange.execute('offer', {'id': 'next-sale', 'buyer': 'buyer',
                                             'price': 1_000_000, 'job_id': 'next', 'deadline': 10}, 0)

    def test_native_material_job_cannot_be_offered_twice(self):
        from commercial.ledger import TapeExchange
        exchange = TapeExchange.__new__(TapeExchange)
        exchange._adaptive_writer = None
        exchange.persistence = None
        exchange.last_day = 0
        exchange.manifest = {'schema': 'agi-alpha/material054-services/v1'}
        exchange.jobs = {'job': {'job': {'parent_job_id': None}}}
        exchange.actions = [{'op': 'offer', 'args': {'job_id': 'job', 'id': 'old-sale'}}]
        exchange.ex = SimpleNamespace(snapshot=lambda: {})
        with self.assertRaisesRegex(ValueError, 'MATERIAL_JOB_ALREADY_COMMITTED'):
            exchange.execute('offer', {'id': 'new-sale', 'buyer': 'buyer',
                                     'price': 1_000_000, 'job_id': 'job', 'deadline': 10}, 0)

    def test_ordinary_sequence_uses_its_own_first_cycle_remnants(self):
        from connected_enterprise.material054 import ordinary_milp, successor_order, textbook_order
        from connected_enterprise.material_cycle054 import USD, economics
        first = textbook_order()
        first_plan = ordinary_milp(first)
        second = successor_order(first_plan)
        second_plan = ordinary_milp(second)
        self.assertTrue(audit_plan(first, first_plan)['accepted'])
        self.assertTrue(audit_plan(second, second_plan)['accepted'])
        self.assertTrue(audit_transfer(first, first_plan, second)['accepted'])
        self.assertEqual(first_plan['material_cost_microUSD'], 1170 * USD)
        self.assertEqual(second_plan['material_cost_microUSD'], 0)
        self.assertEqual(economics(second, second_plan, budget=100 * USD,
                                   value=130 * USD, fixed_cost=8 * USD)['buyer_choice'], 'BUY')

    def test_empty_inventory_and_demand_are_explicit_solver_outcomes(self):
        from connected_enterprise.material054 import solve
        raw, _ = fixture()
        raw['stocks'] = []
        artifact, work = solve(raw)
        self.assertIsNone(artifact)
        self.assertEqual(work['verdict'], 'NO_AVAILABLE_STOCK')
        raw, _ = fixture()
        raw['pieces'] = []
        artifact, work = solve(raw)
        self.assertTrue(audit_plan(raw, artifact)['accepted'])
        self.assertEqual(work['verdict'], 'EMPTY_DEMAND')

    def test_pattern_preprocessing_has_an_explicit_candidate_window(self):
        from connected_enterprise.material054 import patterns
        raw, _ = fixture()
        shared_window = [1]
        with self.assertRaisesRegex(RuntimeError, 'STATE_WINDOW_EXHAUSTED: pattern enumeration'):
            patterns(raw, raw['stocks'][0], shared_window)
        self.assertEqual(shared_window[0], -1)

    def test_realizable_outside_salvage_defeats_positive_fixed_cost_offer(self):
        from connected_enterprise.material054 import ordinary_milp, textbook_order
        from connected_enterprise.material_cycle054 import USD, economics
        first = textbook_order()
        artifact = ordinary_milp(first)
        decision = economics(first, artifact, budget=1500 * USD, value=1500 * USD,
                             outside_salvage=70 * USD, fixed_cost=30 * USD)
        self.assertIsNone(decision['price_microUSD'])
        self.assertEqual(decision['buyer_choice'], 'NO_PURCHASE_FROM_US')
        self.assertIn('supplier retains', decision['residual_title_terms'])


if __name__ == '__main__':
    unittest.main()
