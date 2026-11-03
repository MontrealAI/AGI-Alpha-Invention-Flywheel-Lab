import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from .process_verify import (conventional_policy, independent_execution,
                             unfamiliar_cases, verify_policy)


def primary():
    rows = [
        ('m1', 1, 0, {'a': 10, 'b': 0, 'c': 0, 'robust': 10}),
        ('m2', 0, 1, {'a': 0, 'b': 10, 'c': 0, 'robust': 10}),
        ('m3', 1, 1, {'a': 10, 'b': 10, 'c': 0, 'robust': 10}),
        ('m4', 0, 0, {'a': 0, 'b': 0, 'c': 10, 'robust': 10})]
    return {'schema': 'omega/process-request/v1', 'name': 'Independent primary contract',
            'ambition': 'Minimum declared process yield with bounded cost.', 'currency': 'USD',
            'models': [{'id': m, 'responses': {'passive': 10, 'a': a, 'b': b}, 'yields': y}
                       for m, a, b, y in rows],
            'experiments': [{'id': 'passive', 'cost_cents': 1}, {'id': 'a', 'cost_cents': 4},
                            {'id': 'b', 'cost_cents': 5}],
            'recipes': [{'id': 'a', 'cost_cents': 18}, {'id': 'b', 'cost_cents': 20},
                        {'id': 'c', 'cost_cents': 22}, {'id': 'robust', 'cost_cents': 100}],
            'observations': [], 'target_minimum': 10, 'max_total_cost_cents': 40,
            'max_experiments': 3, 'consent': True}


class IndependentProcessTests(unittest.TestCase):
    def test_exact_optimal_primary_and_no_active(self):
        request = primary()
        plan = conventional_policy(request)
        check = verify_policy(request, plan)
        self.assertEqual(check['models_covered'], 4)
        self.assertEqual(check['worst_cost_cents'], 31)
        request['max_experiments'] = 0
        self.assertEqual(conventional_policy(request)['status'], 'NO_QUALIFIED_POLICY')

    def test_sunk_observations_are_not_charged_twice(self):
        request = primary()
        request['observations'] = [{'experiment_id': 'a', 'value': 1}]
        request['max_experiments'] = 0
        plan = conventional_policy(request)
        self.assertEqual(plan['worst_cost_cents'], 18)
        self.assertEqual(verify_policy(request, plan)['models_covered'], 2)

    def test_decline_and_unknown_observation(self):
        request = primary()
        request['consent'] = False
        declined = conventional_policy(request)
        self.assertEqual(declined['status'], 'BUYER_DECLINED')
        self.assertFalse(verify_policy(request, declined)['accepted'])
        request['consent'] = True
        request['observations'] = [{'experiment_id': 'a', 'value': 99}]
        self.assertEqual(conventional_policy(request)['status'], 'MODEL_MISMATCH')

    def test_stale_missing_branch_and_cost_reject(self):
        request = primary()
        plan = conventional_policy(request)
        changed = copy.deepcopy(request)
        changed['recipes'][0]['cost_cents'] += 1
        with self.assertRaises(ValueError):
            verify_policy(changed, plan)
        broken = copy.deepcopy(plan)
        broken['tree']['branches'].pop(next(iter(broken['tree']['branches'])))
        with self.assertRaises(ValueError):
            verify_policy(request, broken)
        broken = copy.deepcopy(plan)
        broken['worst_cost_cents'] -= 1
        with self.assertRaises(ValueError):
            verify_policy(request, broken)

    def test_wrong_recipe_cannot_borrow_other_world_yield(self):
        request = primary()
        plan = conventional_policy(request)
        plan['tree'] = {'kind': 'produce', 'recipe_id': 'a'}
        plan['worst_cost_cents'] = 18
        with self.assertRaisesRegex(ValueError, 'TARGET_FAILED'):
            verify_policy(request, plan)

    def test_invented_refusal_unknown_fields_and_bool_cost_reject(self):
        request = primary()
        plan = conventional_policy(request)
        for status in ('NO_QUALIFIED_POLICY', 'BUYER_DECLINED', 'MODEL_MISMATCH'):
            broken = {**plan, 'status': status, 'tree': None, 'worst_cost_cents': None}
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'UNSUPPORTED_REFUSAL'):
                verify_policy(request, broken)
        with self.assertRaisesRegex(ValueError, 'EXACT_FIELDS'):
            verify_policy(request, {**plan, 'universal_guarantee': True})
        with self.assertRaisesRegex(ValueError, 'EXACT_INTEGER'):
            verify_policy(request, {**plan, 'worst_cost_cents': True})

    def test_duplicate_observation_consistency_and_changed_authority(self):
        request = primary()
        request['observations'] = [{'experiment_id': 'a', 'value': 1}] * 2
        self.assertEqual(conventional_policy(request)['worst_cost_cents'], 18)
        plan = conventional_policy(request)
        request['consent'] = False
        with self.assertRaisesRegex(ValueError, 'REQUEST_BINDING'):
            verify_policy(request, plan)
        request['consent'] = True
        request['observations'].append({'experiment_id': 'a', 'value': 0})
        self.assertEqual(conventional_policy(request)['status'], 'MODEL_MISMATCH')

    def test_all_declared_worlds_independently_execute(self):
        request = primary()
        plan = conventional_policy(request)
        rows = [independent_execution(request, plan, model['responses'], model['yields'])
                for model in request['models']]
        self.assertTrue(all(row['production_accepted'] for row in rows))
        self.assertEqual(max(row['cost_cents'] for row in rows), plan['worst_cost_cents'])

    def test_omitted_alias_passes_probes_but_fails_production(self):
        request = primary()
        plan = conventional_policy(request)
        oracle = request['models'][0]
        yields = dict(oracle['yields'])
        yields['a'] = 0
        result = independent_execution(request, plan, oracle['responses'], yields)
        self.assertEqual(result['status'], 'PRODUCTION_REJECTED')
        self.assertFalse(result['production_accepted'])

    def test_unpredicted_response_never_silently_selects_recipe(self):
        request = primary()
        plan = conventional_policy(request)
        oracle = request['models'][0]
        responses = {name: 99 for name in oracle['responses']}
        result = independent_execution(request, plan, responses, oracle['yields'])
        self.assertEqual(result['status'], 'MODEL_MISMATCH')
        self.assertNotIn('recipe_id', result)

    def test_zero_cost_information_and_bool_rejection(self):
        request = primary()
        for experiment in request['experiments']:
            experiment['cost_cents'] = 0
        plan = conventional_policy(request)
        self.assertEqual(verify_policy(request, plan)['worst_cost_cents'], 22)
        request['experiments'][0]['cost_cents'] = False
        with self.assertRaises(ValueError):
            conventional_policy(request)

    def test_evaluator_authored_unfamiliar_cases_replay(self):
        cases = unfamiliar_cases()
        self.assertEqual(len(cases), 18)
        for request in cases:
            with self.subTest(request=request['name']):
                policy = conventional_policy(request)
                check = verify_policy(request, policy)
                self.assertEqual(check['accepted'], policy['status'] == 'QUALIFIED_POLICY')


class IndependentSessionReviewTests(unittest.TestCase):
    def test_reopen_rejects_corrupt_metadata_scope_and_route(self):
        from .process import BuyerSession
        from mechanism_harness.core import canonical
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'session.sqlite'
            with BuyerSession(path, primary()):
                pass
            with sqlite3.connect(path) as database:
                meta = json.loads(database.execute('SELECT value FROM meta WHERE id=1').fetchone()[0])
                meta['schema'] = 'UNRECOGNIZED'
                meta['route']['model_api_calls'] = 123
                database.execute('UPDATE meta SET value=? WHERE id=1', (canonical(meta),))
            with self.assertRaises(ValueError):
                with BuyerSession(path):
                    pass

    def test_reopen_rejects_unknown_event_fields(self):
        from .process import BuyerSession
        from mechanism_harness.core import canonical
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'session.sqlite'
            with BuyerSession(path, primary()) as session:
                session.act('first', 'observe', experiment_id='a', value=1)
            with sqlite3.connect(path) as database:
                event = json.loads(database.execute('SELECT request FROM events WHERE id=?', ('first',)).fetchone()[0])
                event['unknown'] = True
                database.execute('UPDATE events SET request=? WHERE id=?', (canonical(event), 'first'))
            with self.assertRaises(ValueError):
                with BuyerSession(path):
                    pass

    def test_duplicate_action_revalidates_receipt_while_session_open(self):
        from .process import BuyerSession
        from mechanism_harness.core import canonical
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'session.sqlite'
            with BuyerSession(path, primary()) as session:
                session.act('first', 'observe', experiment_id='a', value=1)
                with sqlite3.connect(path) as database:
                    receipt = json.loads(database.execute('SELECT receipt FROM events WHERE id=?', ('first',)).fetchone()[0])
                    receipt['status'], receipt['yield'] = 'ACCEPTED', 999
                    database.execute('UPDATE events SET receipt=? WHERE id=?', (canonical(receipt), 'first'))
                with self.assertRaises(ValueError):
                    session.act('first', 'observe', experiment_id='a', value=1)


if __name__ == '__main__':
    unittest.main()
