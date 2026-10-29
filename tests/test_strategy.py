import tempfile
import unittest
from pathlib import Path
from flywheel.strategy import synthesize, interpret, validate, discover
from flywheel.evidence_executor import execute


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.task = {'id': 'test', 'phases': ['reserve', 'start', 'work', 'complete'], 'dependencies': [['reserve', 'start'], ['start', 'work'], ['work', 'complete']]}

    def test_constraint_changes_executed_scope(self):
        original = synthesize(self.task, [])
        repair = synthesize(self.task, [{'status': 'established', 'kind': 'protect_phase', 'phase': 'start'}])
        with tempfile.TemporaryDirectory() as temp:
            first = execute(self.task, original['program'], Path(temp)/'first', 'start')
            second = execute(self.task, repair['program'], Path(temp)/'second', 'start')
            self.assertFalse(first['interrupted_marker'])
            self.assertTrue(second['interrupted_marker'])
            self.assertFalse((Path(temp)/'second'/'COMPLETE.json').exists())
            with self.assertRaises(FileExistsError):
                execute(self.task, repair['program'], Path(temp)/'second')
            final = execute(self.task, repair['program'], Path(temp)/'commit', 'complete')
            self.assertTrue(final['interrupted_marker'])
            self.assertFalse((Path(temp)/'commit'/'COMPLETE.json').exists())
            self.assertTrue((Path(temp)/'commit'/'PENDING_COMPLETE.json').exists())

    def test_unadjudicated_critique_and_bad_effects_refused(self):
        with self.assertRaises(ValueError):
            synthesize(self.task, [{'status': 'unresolved', 'kind': 'protect_phase', 'phase': 'start'}])
        with self.assertRaises(ValueError):
            validate(self.task, {'body': ['reserve', '../escape'], 'protected_from': 0})

    def test_new_composition_retains_correctness(self):
        task = {'id': 'publication', 'phases': ['reserve', 'manifest', 'build', 'publish', 'complete'], 'dependencies': [['manifest', 'build'], ['build', 'publish'], ['publish', 'complete']]}
        candidate = synthesize(task, [], inherited={'operator': 'protect_initialization', 'language': 'bounded-evidence/v1'})
        self.assertEqual(candidate['program']['body'], task['phases'])
        for phase in task['phases'][1:]:
            self.assertTrue(interpret({'task': task, 'program': candidate['program'], 'interrupt_at': phase})['interrupted_marker'])

    def test_structural_matching_units_and_causality(self):
        target = {'id': 'target', 'nodes': [{'id': 'a', 'kind': 'guard', 'unit': 'event'}, {'id': 'b', 'kind': 'effect', 'unit': 'event'}], 'relations': [['a', 'protects', 'b']], 'conditions': {'failure': 'exception'}}
        donor = {'id': 'donor', 'nodes': [{'id': 'x', 'kind': 'guard', 'unit': 'event'}, {'id': 'y', 'kind': 'effect', 'unit': 'event'}], 'relations': [['x', 'protects', 'y']], 'conditions': {'failure': 'exception'}}
        self.assertTrue(discover([donor], target)[0]['applicable'])
        donor['relations'] = [['y', 'protects', 'x']]
        self.assertFalse(discover([donor], target)[0]['applicable'])
        donor['relations'] = [['x', 'protects', 'y']]
        donor['nodes'][0]['unit'] = 'second'
        self.assertFalse(discover([donor], target)[0]['applicable'])
