import copy
import unittest

from . import fabric as f
from . import reference as r
from .run import run


class FabricTests(unittest.TestCase):
    def setUp(self):
        self.blocks, self.operand = f.fixture(3)
        self.plan = f.construct('gram')
        self.cache, _ = f.encode(self.blocks, self.plan)
        self.binding, self.returns = f.execute(self.cache, self.plan)

    def test_exhaustive_contract_and_successor(self):
        result = run()
        self.assertEqual(result['exhaustive']['linear'], {'subsets': 128, 'correct': 99, 'refused': 29})
        self.assertEqual(result['exhaustive']['gram'], {'subsets': 128, 'correct': 29, 'refused': 99})
        self.assertEqual(result['successor']['retained'], result['successor']['equal_content_ordinary'])
        self.assertFalse(result['two_domain_loss_coded_gram_feasible'])

    def test_strong_conventional_coded_matches(self):
        for kind in ['linear', 'gram']:
            self.assertEqual(f.construct(kind)['worker_units'], r.conventional_coded(kind)['worker_units'])

    def test_replication_beats_quadratic_coding(self):
        self.assertEqual(r.replication()['worker_units'], 6)
        self.assertEqual(f.construct('linear')['worker_units'], 5)
        self.assertEqual(f.construct('gram')['worker_units'], 8)

    def test_insufficient_and_total_loss(self):
        for subset in [[], self.returns[:4]]:
            with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_RETURNS'):
                f.decode(subset, self.plan, self.binding)

    def test_duplicate_workers(self):
        with self.assertRaisesRegex(ValueError, 'UNIQUE_DECLARED'):
            f.decode(self.returns[:4] + [self.returns[0]], self.plan, self.binding)

    def test_changed_job(self):
        bad = copy.deepcopy(self.returns)
        bad[0]['binding'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'JOB_BINDING_CHANGED'):
            f.decode(bad, self.plan, self.binding)

    def test_cache_invalidation(self):
        for mutation in ['input', 'field', 'bytes']:
            bad = copy.deepcopy(self.cache)
            if mutation == 'input':
                bad['input'] = 'changed'
            elif mutation == 'field':
                bad['field'] = 17
            else:
                bad['shards'][next(iter(bad['shards']))]['matrix'][0][0] += 1
            with self.assertRaisesRegex(ValueError, 'CACHE_'):
                f.encode(self.blocks, self.plan, bad)

    def test_cache_is_not_authentication(self):
        bad = copy.deepcopy(self.cache)
        row = bad['shards'][next(iter(bad['shards']))]
        row['matrix'][0][0] += 1
        row['sha256'] = f.digest(row['matrix'])
        cached, _ = f.encode(self.blocks, self.plan, bad)
        binding, returns = f.execute(cached, self.plan)
        self.assertFalse(r.accept(self.blocks, 'gram', None, f.decode(returns, self.plan, binding)))

    def test_original_affine_fixture_is_a_favorable_degree_region(self):
        blocks, _ = f.fixture(3, affine=True)
        cache, _ = f.encode(blocks, self.plan)
        binding, returns = f.execute(cache, self.plan)
        low_degree = [f.combine([v['value'] for v in returns[:3]],
            f.weights([v['x'] for v in returns[:3]], x)) for x in [1, 2, 3]]
        self.assertTrue(r.accept(blocks, 'gram', None, low_degree))

    def test_canonical_inputs_and_outputs(self):
        bad = copy.deepcopy(self.blocks)
        bad[0][0][0] = True
        with self.assertRaisesRegex(ValueError, 'CANONICAL_FIELD'):
            f.encode(bad, self.plan)
        for value in [-1, f.P, True]:
            bad = copy.deepcopy(self.returns)
            bad[0]['value'][0][0] = value
            with self.assertRaisesRegex(ValueError, 'CANONICAL_RETURN'):
                f.decode(bad, self.plan, self.binding)

    def test_undeclared_worker_and_changed_operation(self):
        bad = copy.deepcopy(self.returns)
        bad[0]['x'] = 99
        with self.assertRaisesRegex(ValueError, 'UNIQUE_DECLARED'):
            f.decode(bad, self.plan, self.binding)
        bad_plan = copy.deepcopy(self.plan)
        bad_plan['threshold'] = 3
        with self.assertRaisesRegex(ValueError, 'CURRENT_OPERATION'):
            f.decode(self.returns, bad_plan, self.binding)


if __name__ == '__main__':
    unittest.main()
