import copy
import unittest

from .evaluate import evaluate
from .study import analyze, evaluate_program, validate_case_spec
from .world import SCHEDULES, make_world, public_task


class RegisteredStudyContractTests(unittest.TestCase):
    def setUp(self):
        self.spec = make_world('economic-K1/v1/0', 'K1', 0)
        self.spec['operating_schedule'] = SCHEDULES[0]

    def test_registered_development_case_is_valid(self):
        self.assertTrue(validate_case_spec(self.spec))

    def test_easy_provider_substitution_is_rejected(self):
        changed = copy.deepcopy(self.spec)
        changed['providers'][0]['config']['compensation'] = False
        with self.assertRaisesRegex(ValueError, 'REGISTERED_WORLD_OR_SCHEDULE_CHANGED'):
            validate_case_spec(changed)

    def test_actual_schedule_cannot_be_chosen_after_result(self):
        changed = copy.deepcopy(self.spec)
        changed['operating_schedule'] = SCHEDULES[2]
        with self.assertRaisesRegex(ValueError, 'REGISTERED_WORLD_OR_SCHEDULE_CHANGED'):
            validate_case_spec(changed)

    def test_unregistered_seed_is_rejected(self):
        changed = copy.deepcopy(self.spec)
        changed['seed'] = 'favorable-replacement'
        with self.assertRaisesRegex(ValueError, 'REGISTERED_ECONOMIC_SEED_REQUIRED'):
            validate_case_spec(changed)

    def test_safe_refusal_cannot_be_native_complete_delivery(self):
        program = {'entry': 'end', 'nodes': {'end': {'finish': 'aborted', 'obligations': []}}}
        result = evaluate_program(self.spec, program)
        self.assertTrue(result['all_safe'])
        self.assertFalse(result['complete_delivery'])

    def test_missing_scored_rows_fail_before_analysis(self):
        with self.assertRaisesRegex(ValueError, 'EXACT_REGISTERED_CONFIRMATION_DENOMINATOR_REQUIRED'):
            analyze([])

    def test_operating_schedule_is_hidden_from_constructor(self):
        self.assertNotIn('operating_schedule', public_task(self.spec))

    def test_evaluation_does_not_mutate_bound_world(self):
        before = copy.deepcopy(self.spec)
        ident = self.spec['providers'][0]['id']
        program = {'entry': 'run', 'nodes': {
            'run': {'op': 'execute', 'provider': ident, 'token': 'order', 'next': {'*': 'end'}},
            'end': {'finish': 'delivered', 'obligations': []}}}
        evaluate(self.spec, program)
        self.assertEqual(before, self.spec)


if __name__ == '__main__':
    unittest.main()
