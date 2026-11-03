import copy
import unittest
from mechanism_harness.core import digest
from omega.observation import execute, select_panel
from omega.observation_verify import conventional_panel, conventional_execute, verify_receipt


def request():
    return {'schema': 'omega-observation/v1', 'case_id': 'unit', 'context_id': 'batch-unit',
            'hypotheses': [{'id': 'clean', 'state': [0, 0], 'accepted_actions': ['reuse']},
                           {'id': 'changed', 'state': [4, 0], 'accepted_actions': ['isolate']}],
            'sensors': [{'id': 'assay', 'coefficients': [1, 0], 'offset': 0, 'error_bound': 1,
                         'setup_cost_cents': 4, 'sample_cost_cents': 1, 'authorized': True}],
            'budget_cents': 5, 'prior_observations': [], 'inherited_recipes': []}


class ObservationTest(unittest.TestCase):
    def test_separating_measurement_is_accepted_by_independent_reference(self):
        r = request()
        self.assertEqual(select_panel(r), conventional_panel(r))
        got = execute(r, lambda name: 1)
        self.assertEqual(got, conventional_execute(r, lambda name: 1))
        self.assertEqual(got['action'], 'reuse')
        check = verify_receipt(r, got)
        self.assertTrue(check['accepted'])
        self.assertFalse(check['observation_truth_verified'])

    def test_overlap_is_unresolved_and_calls_nothing(self):
        r = request(); r['sensors'][0]['error_bound'] = 2
        calls = []
        got = execute(r, lambda name: calls.append(name))
        self.assertEqual(got['status'], 'UNRESOLVED')
        self.assertEqual(got, conventional_execute(r, lambda name: 0))
        self.assertEqual(calls, [])
        self.assertTrue(verify_receipt(r, got)['accepted'])

    def test_three_way_action_conflict_not_reduced_to_pairwise(self):
        r = request()
        r['hypotheses'] = [
            {'id': 'w0', 'state': [0, 0], 'accepted_actions': ['a', 'b']},
            {'id': 'w1', 'state': [2, 0], 'accepted_actions': ['b', 'c']},
            {'id': 'w2', 'state': [4, 0], 'accepted_actions': ['a', 'c']}]
        got = conventional_execute(r, lambda name: 1)
        self.assertEqual(got['action'], 'b')
        self.assertEqual(got['hypothesis_ids'], ['w0', 'w1'])
        self.assertEqual(got, execute(r, lambda name: 1))
        r['sensors'] = []
        self.assertEqual(conventional_panel(r)['status'], 'UNRESOLVED')

    def test_fixed_panel_can_use_complementary_sensors(self):
        r = request()
        r['hypotheses'] = [{'id': f'w{x}{y}', 'state': [x, y], 'accepted_actions': [f'a{x}{y}']}
                           for x in (0, 4) for y in (0, 4)]
        r['sensors'].append(dict(r['sensors'][0], id='other', coefficients=[0, 1]))
        r['budget_cents'] = 10
        got = execute(r, lambda name: 1 if name == 'assay' else 5)
        self.assertEqual(got, conventional_execute(r, lambda name: 1 if name == 'assay' else 5))
        self.assertEqual(got['action'], 'a04')
        self.assertTrue(verify_receipt(r, got)['accepted'])

    def test_partial_missing_result_preserves_observed_posterior_and_full_attempt_cost(self):
        r = request()
        r['hypotheses'] = [{'id': f'w{x}{y}', 'state': [x, y], 'accepted_actions': [f'a{x}{y}']}
                           for x in (0, 4) for y in (0, 4)]
        r['sensors'].append(dict(r['sensors'][0], id='other', coefficients=[0, 1]))
        r['budget_cents'] = 10
        got = execute(r, lambda name: 1 if name == 'assay' else None)
        self.assertEqual(got['status'], 'OBSERVATION_UNAVAILABLE')
        self.assertEqual(got['hypothesis_ids'], ['w00', 'w04'])
        self.assertEqual(got['incurred_cost_cents'], 10)
        self.assertEqual(got, conventional_execute(r, lambda name: 1 if name == 'assay' else None))
        self.assertTrue(verify_receipt(r, got)['accepted'])

    def test_out_of_model_is_not_safe(self):
        r = request(); got = execute(r, lambda name: 100)
        self.assertEqual(got['status'], 'OUT_OF_MODEL')
        self.assertIsNone(got['action'])
        self.assertEqual(got, conventional_execute(r, lambda name: 100))
        self.assertTrue(verify_receipt(r, got)['accepted'])

    def test_boundary_invalid_boolean_is_not_integer(self):
        r = request(); got = execute(r, lambda name: True)
        self.assertEqual(got['status'], 'INVALID_OBSERVATION')
        self.assertTrue(verify_receipt(r, got)['accepted'])
        r['budget_cents'] = True
        for solver in (select_panel, conventional_panel):
            with self.assertRaises(ValueError): solver(r)

    def test_unauthorized_sensor_never_executes(self):
        r = request(); r['sensors'][0]['authorized'] = False
        got = execute(r, lambda name: self.fail('unauthorized call'))
        self.assertEqual(got['status'], 'UNRESOLVED')
        self.assertEqual(select_panel(r), conventional_panel(r))

    def test_inheritance_is_only_exact_generic_recipe_and_ordinary_reuse_ties(self):
        r = request(); r['budget_cents'] = 1
        self.assertEqual(conventional_panel(r)['status'], 'UNRESOLVED')
        r['inherited_recipes'] = [{'sensor_id': 'assay', 'sensor_sha256': digest(r['sensors'][0])}]
        self.assertEqual(conventional_panel(r)['cost_cents'], 1)
        self.assertEqual(select_panel(r), conventional_panel(copy.deepcopy(r)))
        r['sensors'][0]['error_bound'] = 2
        for solver in (select_panel, conventional_panel):
            with self.assertRaises(ValueError): solver(r)

    def test_prior_observations_are_context_bound_and_can_avoid_new_measurement(self):
        r = request()
        r['prior_observations'] = [{'sensor_id': 'assay', 'sensor_sha256': digest(r['sensors'][0]),
                                     'context_id': r['context_id'], 'value': 0}]
        got = execute(r, lambda name: self.fail('redundant measure'))
        self.assertEqual(got['incurred_cost_cents'], 0)
        self.assertEqual(got['action'], 'reuse')
        self.assertTrue(verify_receipt(r, got)['accepted'])
        r['context_id'] = 'other-batch'
        for solver in (select_panel, conventional_panel):
            with self.assertRaises(ValueError): solver(r)

    def test_out_of_model_prior_never_calls_measurement(self):
        r = request()
        r['prior_observations'] = [{'sensor_id': 'assay', 'sensor_sha256': digest(r['sensors'][0]),
                                     'context_id': r['context_id'], 'value': 100}]
        got = execute(r, lambda name: self.fail('out-of-model called'))
        self.assertEqual(got['status'], 'OUT_OF_MODEL')
        self.assertTrue(verify_receipt(r, got)['accepted'])

    def test_tampered_cost_action_or_source_rejected(self):
        r = request(); got = execute(r, lambda name: 0)
        changes = [('incurred_cost_cents', 0), ('action', 'isolate'), ('request_sha256', 'x'),
                   ('hypothesis_ids', ['changed']), ('physical_validity', 'VERIFIED'),
                   ('panel', []), ('cost_cents', True)]
        for key, value in changes:
            bad = copy.deepcopy(got); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): verify_receipt(r, bad)

    def test_duplicate_or_fabricated_observation_rejected(self):
        r = request(); got = execute(r, lambda name: 0)
        got['observations'].append(copy.deepcopy(got['observations'][0]))
        with self.assertRaises(ValueError): verify_receipt(r, got)

    def test_arbitrarily_large_sensor_values_remain_exact(self):
        r = request(); r['hypotheses'][1]['state'][0] = 10**40
        r['sensors'][0]['error_bound'] = 10**20
        self.assertEqual(conventional_panel(r), select_panel(r))
        self.assertEqual(conventional_panel(r)['status'], 'PANEL_READY')

    def test_explicit_reference_resource_checkpoint_not_infeasibility(self):
        r = request()
        with self.assertRaisesRegex(RuntimeError, 'RESOURCE_CHECKPOINT_NOT_INFEASIBILITY'):
            conventional_panel(r, max_subsets=2)

    def test_common_action_does_not_require_state_identification(self):
        r = request()
        for w in r['hypotheses']: w['accepted_actions'].append('pause')
        got = conventional_execute(r, lambda name: self.fail('needless measurement'))
        self.assertEqual(got['action'], 'pause')
        self.assertEqual(got['panel'], [])
        self.assertTrue(verify_receipt(r, got)['accepted'])


if __name__ == '__main__': unittest.main()
