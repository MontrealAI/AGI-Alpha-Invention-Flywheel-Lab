import copy
import hashlib
from pathlib import Path
import random
import unittest

from mechanisms.construct import construct, conventional, evaluate_policy, interpret, reframe, validate, validate_task


def task(names=('r-93', 'x-11', 'y-70', 'c-42')):
    return {'id': 'typed-example', 'phases': [
        {'id': names[0], 'kind': 'reserve', 'deps': [], 'unit': 'event'},
        {'id': names[1], 'kind': 'measurement', 'deps': [names[0]], 'unit': 'event'},
        {'id': names[2], 'kind': 'adaptation', 'deps': [names[1]], 'unit': 'event'},
        {'id': names[3], 'kind': 'commit', 'deps': [names[2]], 'unit': 'event'}]}


class Construct005(unittest.TestCase):
    def test_mapping_obligation_changes_executable_scope(self):
        target = task()
        baseline = construct(target)
        one = construct(target, [{'kind': 'protect', 'phase_ids': ['x-11']}])
        other = construct(target, [{'kind': 'protect', 'phase_ids': ['y-70']}])
        self.assertEqual(baseline['program']['protected'], [])
        self.assertNotEqual(one['program'], other['program'])
        self.assertFalse(interpret({'task': target, 'program': baseline['program'], 'interrupt_at': 'x-11'})['interrupted_marker'])
        self.assertTrue(interpret({'task': target, 'program': one['program'], 'interrupt_at': 'x-11'})['interrupted_marker'])
        self.assertFalse(interpret({'task': target, 'program': other['program'], 'interrupt_at': 'x-11'})['interrupted_marker'])

    def test_complementary_protection_and_atomic_publication(self):
        target = task()
        obligations = [{'kind': 'protect', 'phase_ids': ['c-42']}, {'kind': 'atomic_publish', 'phase_ids': ['c-42']}]
        result = construct(target, obligations)
        program = result['program']
        outcome = interpret({'task': target, 'program': program, 'interrupt_at': 'c-42', 'interrupt_stage': 'during'})
        self.assertTrue(outcome['interrupted_marker'])
        self.assertFalse(outcome['partial_publication'])
        self.assertFalse(outcome['complete_exists'])
        for component in ('protected', 'atomic'):
            removed = copy.deepcopy(program)
            removed[component] = []
            failed = interpret({'task': target, 'program': removed, 'interrupt_at': 'c-42', 'interrupt_stage': 'during'})
            self.assertFalse(failed['interrupted_marker']) if component == 'protected' else self.assertTrue(failed['complete_exists'])

    def test_arbitrary_labels_and_permutation_use_graph_not_factorials(self):
        phases = []
        for i in range(30):
            phases.append({'id': 'unrelated-' + str(97 - i), 'kind': 'reserve' if i == 0 else ('commit' if i == 29 else 'generic'),
                           'deps': [] if i == 0 else [phases[-1]['id']], 'unit': 'event'})
        target = {'id': 'larger-dag', 'phases': phases}
        expected = [p['id'] for p in phases]
        random.Random(5).shuffle(phases)
        result = construct(target, [{'kind': 'protect', 'phase_ids': expected[1:]}], max_candidates=4)
        self.assertEqual(result['status'], 'constructed')
        self.assertEqual(result['program']['order'], expected)
        self.assertLessEqual(result['candidate_count'], 4)

    def test_operator_instantiates_new_target_and_obeys_match_bound(self):
        operator = {'language': 'event-plan-rewrite/v1', 'rules': [
            {'match': {'kind': 'measurement', 'unit': 'event'}, 'emit': {'kind': 'protect', 'phase_ids': ['$match']}}], 'max_matches': 1}
        result = construct(task(('fresh-0', 'fresh-9', 'fresh-3', 'fresh-5')), operator=operator)
        self.assertEqual(result['program']['protected'], ['fresh-9'])
        self.assertEqual(result['operator_trace']['matches'], 1)
        poisoned = copy.deepcopy(operator)
        poisoned['rules'][0]['emit']['judge'] = 'accept'
        with self.assertRaises(ValueError):
            construct(task(), operator=poisoned)

    def test_compensation_is_derived_from_resource_causality(self):
        target = task()
        program = construct(target, [{'kind': 'compensate', 'phase_ids': ['y-70']}])['program']
        self.assertEqual(program['compensations'], {'y-70': ['r-93']})
        receipt = interpret({'task': target, 'program': program, 'interrupt_at': 'y-70'})
        self.assertEqual(receipt['compensated'], ['r-93'])
        with self.assertRaises(ValueError):
            construct(target, [{'kind': 'compensate', 'phase_ids': ['x-11'], 'resource_phase_ids': ['y-70']}])

    def test_invalid_graphs_and_resource_exhaustion_are_explicit(self):
        target = task()
        target['phases'][0]['deps'] = ['c-42']
        with self.assertRaisesRegex(ValueError, 'CYCLIC'):
            validate_task(target)
        target = task()
        target['phases'][1]['unit'] = 'kg'
        with self.assertRaisesRegex(ValueError, 'UNIT'):
            validate_task(target)
        result = construct(task(), [{'kind': 'protect', 'phase_ids': ['x-11']}], max_candidates=1)
        self.assertEqual(result['status'], 'exhausted')
        self.assertIsNone(result['program'])

    def test_conventional_control_satisfies_same_interruption_spec(self):
        target = task()
        program = conventional(target)
        for phase in ('x-11', 'y-70', 'c-42'):
            result = interpret({'task': target, 'program': program, 'interrupt_at': phase, 'interrupt_stage': 'during'})
            self.assertTrue(result['interrupted_marker'])
            self.assertFalse(result['complete_exists'])

    def test_interpreter_executes_under_actual_seccomp(self):
        from flywheel import sandbox
        source = Path(__file__).resolve().parents[1] / 'mechanisms/construct.py'
        target = task()
        program = construct(target, [{'kind': 'protect', 'phase_ids': ['x-11']}])['program']
        receipt = sandbox.run(source, 'interpret', {'task': target, 'program': program, 'interrupt_at': 'x-11'}, hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(receipt['worker']['confinement'], 'linux-seccomp-default-deny')
        self.assertTrue(receipt['worker']['result']['interrupted_marker'])

    def test_crossed_policy_and_tool_sets_keep_same_acceptance_interface(self):
        target = task()
        obligations = [{'kind': 'protect', 'phase_ids': ['x-11', 'y-70', 'c-42']},
                       {'kind': 'atomic_publish', 'phase_ids': ['c-42']}]
        outcomes = {}
        for policy in ('old', 'new'):
            for name, capabilities in [('old_tools', ['protect']), ('new_tools', ['protect', 'atomic_publish'])]:
                built = evaluate_policy(target, policy, capabilities, obligations, max_candidates=64)
                self.assertEqual(built['status'], 'constructed')
                self.assertEqual(built['acceptance'], 'UNASSESSED_EXTERNAL_SPECIFICATION_REQUIRED')
                self.assertLessEqual(built['candidate_count'], 64)
                receipt = interpret({'task': target, 'program': built['program'], 'interrupt_at': 'c-42', 'interrupt_stage': 'during'})
                outcomes[(policy, name)] = receipt
                self.assertEqual(receipt['complete_exists'], name == 'old_tools')
                self.assertTrue(receipt['interrupted_marker'])
        self.assertEqual(outcomes[('old', 'new_tools')]['complete_exists'], outcomes[('new', 'new_tools')]['complete_exists'])

    def test_policy_search_comparison_executes_actual_old_generator(self):
        target = task()
        nodes = target['phases']
        for i in range(4):
            phase = {'id': 'extra-' + str(i), 'kind': 'compute', 'unit': 'event', 'deps': [nodes[-2]['id']]}
            nodes[-1]['deps'] = [phase['id']]
            nodes.insert(-1, phase)
        target['phases'] = list(reversed(nodes))
        obligations = [{'kind': 'protect', 'phase_ids': [p['id'] for p in nodes if p['kind'] != 'reserve']},
                       {'kind': 'atomic_publish', 'phase_ids': [p['id'] for p in nodes if p['kind'] == 'commit']}]
        old = evaluate_policy(target, 'old', ['protect', 'atomic_publish'], obligations, 64)
        new = evaluate_policy(target, 'new', ['protect', 'atomic_publish'], obligations, 64)
        self.assertIn('actual old permutations', old['attempts'][0]['origin'])
        self.assertIn('extends original <=7 representation', old['adapter_scope'])
        self.assertEqual(old['status'], 'exhausted')
        self.assertEqual(old['candidate_count'], 64)
        self.assertEqual(new['status'], 'constructed')
        self.assertLess(new['candidate_count'], old['candidate_count'])

    def test_reframing_changes_method_without_dropping_objective(self):
        objective = {'source_identities': {'mechanisms/construct.py': 'a' * 64},
                     'full_checks': ['source-pin', 'portable-execution'],
                     'service_obligations': ['Operate from source archive without Git history'],
                     'safety_obligations': ['No new network or credentials']}
        first = reframe(objective, {'provenance_assumption': 'git_history'}, ['verified_snapshot'])
        self.assertFalse(first['snapshot_receipt_supported'])
        self.assertTrue(all(item['status'] == 'refused' for item in first['alternatives']))
        receipt = {'verified': True, 'objective_sha256': first['objective_sha256'],
                   'source_identities': objective['source_identities'],
                   'checks': {name: True for name in objective['full_checks']}}
        changed = reframe(objective, {'provenance_assumption': 'git_history'}, ['verified_snapshot'], receipt)
        self.assertEqual(changed['objective_sha256'], first['objective_sha256'])
        self.assertEqual(changed['objective'], objective)
        self.assertEqual([x['representation'] for x in changed['alternatives'] if x['status'] == 'admitted'], ['verified_snapshot'])
        forged = copy.deepcopy(receipt)
        forged['checks']['portable-execution'] = False
        rejected = reframe(objective, {}, ['verified_snapshot'], forged)
        self.assertFalse(rejected['snapshot_receipt_supported'])


if __name__ == '__main__':
    unittest.main()
