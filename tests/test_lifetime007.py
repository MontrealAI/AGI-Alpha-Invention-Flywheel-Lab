import copy
import json
from pathlib import Path
import unittest

from inventions.lifetime007.compiler import construct, remap_operator, validate_plan
from inventions.lifetime007.execute import execute
from experiments.lifetime007 import fresh_file_spec

ROOT = Path(__file__).resolve().parents[1]


class LifetimeTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'campaign/cycle-007/LIFETIME_SPEC.json').read_text())

    def test_indivisible_finalizer_cannot_meet_both_actual_obligations(self):
        self.assertEqual(construct(self.spec, allow_factorization=False)['status'], 'INFEASIBLE_IN_GRAMMAR')
        plan = construct(self.spec)
        for domain, values in [('sqlite', ['α', 'record\n2']), ('file', ['nul\0value', ''])]:
            spec = self.spec if domain == 'sqlite' else fresh_file_spec()
            result = execute(spec, construct(spec), values)
            self.assertEqual(result['output'], values)
            self.assertIsNone(result['error'])
            self.assertTrue(result['closed'])

    def test_commit_failure_and_partial_delivery_are_distinct(self):
        plan = construct(self.spec)
        failed = execute(self.spec, plan, ['first', 'second'], 'commit')
        self.assertEqual(failed['output'], [])
        self.assertFalse(failed['committed'])
        for fault in ['mid_consume', 'mid_interrupt']:
            result = execute(self.spec, plan, ['first', 'second'], fault)
            self.assertEqual(result['output'], ['first'])
            self.assertTrue(result['committed'])
            self.assertIsNotNone(result['error'])
            self.assertEqual(sum(e['event'] == 'release' for e in result['trace']), 1)

    def test_source_mismatch_and_unsupported_invariants_refuse(self):
        plan = construct(self.spec)
        malformed = copy.deepcopy(self.spec)
        malformed['obligations']['durable_before_visible'] = 1
        with self.assertRaises(ValueError):
            construct(malformed)
        malformed = copy.deepcopy(self.spec)
        malformed['effects'][0]['operation'] = 'unknown_close'
        with self.assertRaises(ValueError):
            construct(malformed)
        stale = copy.deepcopy(self.spec)
        stale['task_id'] = 'different'
        with self.assertRaises(ValueError):
            execute(stale, plan, ['record'])

    def test_role_names_are_not_semantics_and_unsafe_split_refuses(self):
        spec = copy.deepcopy(self.spec)
        spec['effects'].reverse()
        self.assertEqual(execute(spec, construct(spec), ['same'])['output'], ['same'])
        for block in spec['blocks']:
            block['separable'] = False
        self.assertEqual(construct(spec)['status'], 'INFEASIBLE_IN_GRAMMAR')
        with self.assertRaises(ValueError):
            validate_plan(spec, construct(self.spec))

    def test_corrupt_acquired_operator_refuses(self):
        operator = copy.deepcopy(construct(self.spec)['generated_operator'])
        operator['precedence'][0].reverse()
        with self.assertRaises(ValueError):
            remap_operator(operator, self.spec, fresh_file_spec())


if __name__ == '__main__':
    unittest.main()
