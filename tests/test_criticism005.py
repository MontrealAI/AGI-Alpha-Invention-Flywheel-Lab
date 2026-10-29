import copy
import unittest

from mechanisms.construct import construct, interpret
from mechanisms.criticism import adjudicate, critique, derive, digest, instrument_spec, response


SOURCE = 'a' * 64
SPEC = {'effect_scope': 'exclusive_local_output', 'invariants': [
    {'id': 'failure_has_evidence', 'kind': 'mark_after_reservation'},
    {'id': 'success_is_never_partial', 'kind': 'no_commit_on_failure'}]}


def task_for(labels):
    return {'id': 'changed-labels', 'phases': [
        {'id': labels[0], 'kind': 'reserve', 'deps': [], 'unit': 'event'},
        {'id': labels[1], 'kind': 'action', 'deps': [labels[0]], 'unit': 'event'},
        {'id': labels[2], 'kind': 'action', 'deps': [labels[1]], 'unit': 'event'},
        {'id': labels[3], 'kind': 'commit', 'deps': [labels[2]], 'unit': 'event'}]}


def observed(task, candidate, failure, stage='before'):
    return interpret({'task': task, 'program': candidate, 'interrupt_at': failure, 'interrupt_stage': stage}) | {'interrupt_stage': stage}


class CriticismTests(unittest.TestCase):
    def setUp(self):
        self.task = task_for(['lease-A', 'measure-Q', 'reconcile-17', 'publish-Z'])
        self.candidate = construct(self.task)['program']

    def test_witness_location_drives_executable_repair_at_multiple_labels(self):
        for labels in (['lease-A', 'measure-Q', 'reconcile-17', 'publish-Z'], ['custody', 'mix', 'verify', 'seal']):
            task = task_for(labels)
            candidate = construct(task)['program']
            for failure in labels[1:3]:
                witness = observed(task, candidate, failure)
                objection = critique(task, candidate, witness, SPEC, SOURCE)[0]
                decision = adjudicate(objection, lambda t, c, p: observed(t, c, p))
                obligations = derive(decision, task)
                self.assertEqual(decision['status'], 'established')
                self.assertEqual(obligations[0]['phase_ids'], [failure])
                self.assertEqual(obligations[0]['kind'], 'protect')
                repair = construct(task, obligations)
                self.assertEqual(repair['status'], 'constructed')
                fresh = observed(task, repair['program'], failure)
                self.assertTrue(fresh['interrupted_marker'])
                self.assertEqual(critique(task, repair['program'], fresh, SPEC, SOURCE)[0]['status'], 'no_defect')
                self.assertEqual(objection['bindings']['execution_sha256'], digest(witness))

    def test_partial_publication_yields_complementary_atomic_repair(self):
        phase = self.task['phases'][-1]['id']
        witness = observed(self.task, self.candidate, phase, 'during')
        objections = critique(self.task, self.candidate, witness, SPEC, SOURCE)
        obligations = []
        for objection in objections:
            decision = adjudicate(objection, lambda t, c, p: observed(t, c, p, 'during'))
            obligations += derive(decision, self.task)
        self.assertEqual({o['kind'] for o in obligations}, {'protect', 'atomic_publish'})
        repair = construct(self.task, obligations)['program']
        fresh = observed(self.task, repair, phase, 'during')
        self.assertTrue(fresh['interrupted_marker'])
        self.assertFalse(fresh['partial_publication'])
        self.assertEqual(critique(self.task, repair, fresh, SPEC, SOURCE)[0]['status'], 'no_defect')

    def test_harmless_pre_reservation_interrupt_is_not_a_defect(self):
        failure = self.task['phases'][0]['id']
        witness = observed(self.task, self.candidate, failure)
        objection = critique(self.task, self.candidate, witness, SPEC, SOURCE)[0]
        self.assertEqual(objection['status'], 'no_defect')
        decision = adjudicate(objection, lambda t, c, p: observed(t, c, p))
        self.assertEqual(decision['status'], 'no_defect')
        self.assertEqual(derive(decision, self.task), [])

    def test_objection_is_refuted_if_independent_run_does_not_fail(self):
        failure = self.task['phases'][1]['id']
        protected = construct(self.task, [{'kind': 'protect', 'phase_ids': [failure]}])['program']
        false_witness = observed(self.task, protected, failure) | {'interrupted_marker': False, 'state': 'UNMARKED'}
        objection = critique(self.task, protected, false_witness, SPEC, SOURCE)[0]
        decision = adjudicate(objection, lambda t, c, p: observed(t, c, p))
        self.assertEqual(decision['status'], 'refuted')
        self.assertEqual(derive(decision, self.task), [])

    def test_wrong_reproduction_location_is_unresolved_not_a_refutation(self):
        failure = self.task['phases'][1]['id']
        objection = critique(self.task, self.candidate, observed(self.task, self.candidate, failure), SPEC, SOURCE)[0]
        decision = adjudicate(objection, lambda t, c, p: observed(t, c, None))
        self.assertEqual(decision['status'], 'unresolved')
        self.assertEqual(decision['reason'], 'REPRODUCTION_PROCEDURE_MISMATCH')

    def test_missing_conflicting_unknown_and_stale_evidence_refuse(self):
        failure = self.task['phases'][1]['id']
        valid = observed(self.task, self.candidate, failure)
        for witness in ({}, valid | {'failed_phase': self.task['phases'][2]['id']}, valid | {'directory_created': False}):
            objection = critique(self.task, self.candidate, witness, SPEC, SOURCE)[0]
            decision = adjudicate(objection, lambda t, c, p: valid)
            self.assertEqual(decision['status'], 'unresolved')
            self.assertEqual(derive(decision, self.task), [])
        objection = critique(self.task, self.candidate, valid, SPEC, SOURCE)[0]
        for stale in ('candidate_sha256', 'task_sha256', 'specification_sha256', 'source_identity_sha256'):
            decision = adjudicate(objection, lambda t, c, p: valid | {stale: '0' * 64})
            self.assertEqual(decision['status'], 'unresolved')
        unknown = copy.deepcopy(SPEC)
        unknown['invariants'].append({'id': 'unsupported-science', 'kind': 'unproven_physical_effect'})
        self.assertEqual(critique(self.task, self.candidate, valid, unknown, SOURCE)[0]['status'], 'unresolved')

    def test_candidate_mutation_and_tampered_record_cannot_drive_repair(self):
        failure = self.task['phases'][1]['id']
        objection = critique(self.task, self.candidate, observed(self.task, self.candidate, failure), SPEC, SOURCE)[0]
        original = copy.deepcopy(self.candidate)
        def modifying_reproducer(t, c, p):
            c['protected'] = [p]
            return observed(t, c, p)
        decision = adjudicate(objection, modifying_reproducer)
        self.assertEqual(decision['status'], 'unresolved')
        self.assertEqual(original, self.candidate)
        objection['issue']['phase_ids'] = ['invented']
        self.assertEqual(adjudicate(objection, lambda t, c, p: {})['reason'], 'OBJECTION_IDENTITY_MISMATCH')
        decision['status'] = 'established'
        with self.assertRaisesRegex(ValueError, 'ADJUDICATION_IDENTITY_MISMATCH'):
            derive(decision, self.task)

    def test_unrepairable_commit_before_later_failure_keeps_objective(self):
        failure = self.task['phases'][1]['id']
        witness = observed(self.task, self.candidate, failure) | {'terminal_visible': True}
        atomic = [o for o in critique(self.task, self.candidate, witness, SPEC, SOURCE) if o['issue']['kind'] == 'no_commit_on_failure'][0]
        decision = adjudicate(atomic, lambda t, c, p: witness)
        self.assertEqual(decision['status'], 'established')
        with self.assertRaisesRegex(ValueError, 'UNREPAIRABLE_IN_DECLARED_LANGUAGE'):
            derive(decision, self.task)

    def test_compensation_obligation_names_failure_and_reserved_resource(self):
        failure = self.task['phases'][2]['id']
        spec = {'invariants': [{'id': 'release-custody', 'kind': 'release_after_failure'}]}
        witness = observed(self.task, self.candidate, failure)
        objection = critique(self.task, self.candidate, witness, spec, SOURCE)[0]
        decision = adjudicate(objection, lambda t, c, p: observed(t, c, p))
        obligation = derive(decision, self.task)[0]
        self.assertEqual(obligation['phase_ids'], [failure])
        self.assertEqual(obligation['resource_phase_ids'], [self.task['phases'][0]['id']])
        repaired = construct(self.task, [obligation])['program']
        self.assertEqual(observed(self.task, repaired, failure)['compensated'], [self.task['phases'][0]['id']])

    def test_specification_conflict_and_absent_source_are_not_overridden(self):
        witness = observed(self.task, self.candidate, self.task['phases'][1]['id'])
        conflict = {'invariants': [{'id': 'one', 'kind': 'mark_after_reservation', 'required_state': 'COMPLETE'}]}
        self.assertEqual(critique(self.task, self.candidate, witness, conflict, SOURCE)[0]['status'], 'unresolved')
        self.assertEqual(critique(self.task, self.candidate, witness, SPEC, None)[0]['status'], 'unresolved')

    def missing_effect_case(self):
        failure = self.task['phases'][1]['id']
        spec = {'invariants': [{'id': 'reproduce-input', 'kind': 'required_effect_available',
                                'effect': 'source_bound_historical_materialization'}]}
        witness = observed(self.task, self.candidate, failure) | {'effect_observations': [
            {'phase_id': failure, 'effect': 'source_bound_historical_materialization', 'available': False,
             'input_sha256': 'b' * 64, 'error': {'type': 'FileNotFoundError', 'message': 'Required historical source is unavailable in the declared archive.'}}]}
        objection = critique(self.task, self.candidate, witness, spec, SOURCE)[0]
        decision = adjudicate(objection, lambda t, c, p: copy.deepcopy(witness))
        return spec, witness, objection, decision

    def test_missing_effect_produces_falsifiable_instrument_spec_not_built_claim(self):
        spec, witness, objection, decision = self.missing_effect_case()
        self.assertEqual(decision['status'], 'established')
        self.assertEqual(decision['next_action'], 'needs_instrument')
        with self.assertRaisesRegex(ValueError, 'UNREPAIRABLE_IN_DECLARED_LANGUAGE'):
            derive(decision, self.task)
        result = response(decision, self.task, ['protect', 'atomic_publish', 'compensate'])
        self.assertEqual(result['status'], 'needs_instrument')
        self.assertEqual(result['obligations'], [])
        instrument = result['instrument_specification']
        self.assertEqual(instrument['requirements'][0]['kind'], 'provide_effect')
        self.assertEqual(instrument['requirements'][0]['input_sha256'], 'b' * 64)
        self.assertEqual(instrument['preserved_objective']['specification'], spec)
        self.assertEqual(instrument['bindings']['execution_sha256'], digest(witness))
        self.assertEqual(instrument['bindings']['reproduced_witness_sha256'], digest(witness))
        self.assertFalse(instrument['built'])
        self.assertFalse(instrument['verified'])
        self.assertFalse(instrument['preserved_objective']['may_change_judge'])
        self.assertIn('unchanged independent specification', instrument['operational_falsifier']['procedure'])

    def test_missing_measurement_cannot_change_judge_or_establish_defect(self):
        objection = critique(self.task, self.candidate, {}, SPEC, SOURCE)[0]
        decision = adjudicate(objection, lambda t, c, p: {})
        instrument = instrument_spec(decision, self.task, [])
        self.assertEqual(instrument['status'], 'needs_instrument')
        self.assertEqual(instrument['instrument_kind'], 'measurement')
        self.assertFalse(instrument['defect_established'])
        self.assertEqual(instrument['preserved_objective']['specification_sha256'], digest(SPEC))
        self.assertFalse(instrument['preserved_objective']['may_weaken_thresholds'])
        with self.assertRaisesRegex(ValueError, 'AVAILABLE_EFFECTS_SCHEMA'):
            instrument_spec(decision, self.task, {'effects': [], 'new_judge': 'accept everything'})

    def test_missing_effect_requires_actual_source_bound_error_and_same_input(self):
        spec, witness, objection, decision = self.missing_effect_case()
        invalid = copy.deepcopy(witness)
        invalid['effect_observations'][0].pop('error')
        self.assertEqual(critique(self.task, self.candidate, invalid, spec, SOURCE)[0]['status'], 'unresolved')
        stale = copy.deepcopy(witness)
        stale['effect_observations'][0]['input_sha256'] = 'c' * 64
        self.assertEqual(adjudicate(objection, lambda t, c, p: stale)['reason'], 'REPRODUCTION_EFFECT_INPUT_MISMATCH')
        changed_task = copy.deepcopy(self.task)
        changed_task['id'] = 'different-objective'
        with self.assertRaisesRegex(ValueError, 'STALE_TASK_OR_OBJECTION_APPLICABILITY'):
            instrument_spec(decision, changed_task, [])

    def test_existing_effect_routes_to_real_repair_not_unnecessary_instrument(self):
        failure = self.task['phases'][1]['id']
        objection = critique(self.task, self.candidate, observed(self.task, self.candidate, failure), SPEC, SOURCE)[0]
        decision = adjudicate(objection, lambda t, c, p: observed(t, c, p))
        result = response(decision, self.task, ['protect'])
        self.assertEqual(result['status'], 'repair_obligations')
        self.assertEqual(result['obligations'][0]['kind'], 'protect')
        self.assertIsNone(result['instrument_specification'])
        absent = response(decision, self.task, [])
        self.assertEqual(absent['status'], 'needs_instrument')
        self.assertEqual(absent['instrument_specification']['missing_effects'], ['protect'])


if __name__ == '__main__':
    unittest.main()
