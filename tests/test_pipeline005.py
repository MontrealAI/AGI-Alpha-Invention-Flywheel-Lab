import tempfile
import unittest
from pathlib import Path
from mechanisms import pipeline
from mechanisms.executor import admit


class PipelineTests(unittest.TestCase):
    def test_acquired_stored_retrieved_generated_path_and_equal_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, donors, graph = pipeline.example()
            result = pipeline.develop(task, donors, graph, root/'development', root/'memory')
            self.assertFalse(result['before_passed'])
            self.assertTrue(result['after_passed'])
            self.assertIsNotNone(result['retained'])
            fresh, _, target = pipeline.example('renamed-successor', True)
            scores = {mode: pipeline.reuse(fresh, donors, target, root/mode, root/'memory', mode)['passed']
                      for mode in ('inheritance', 'ordinary', 'conventional', 'removed', 'reset')}
            self.assertEqual(scores, {'inheritance': True, 'ordinary': True, 'conventional': True, 'removed': False, 'reset': False})

    def test_component_removal_cannot_fabricate_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, donors, graph = pipeline.example()
            no_mapping = pipeline.develop(task, donors, graph, root/'no-map', root/'memory', use_mapping=False)
            self.assertIsNone(no_mapping['retained'])
            no_critic = pipeline.develop(task, donors, graph, root/'no-critic', root/'memory', use_critic=False)
            self.assertFalse(no_critic['after_passed'])
            self.assertIsNone(no_critic['retained'])

    def test_unsupported_effect_composition_refuses(self):
        task, _, _ = pipeline.example()
        task['phases'].append({'id': 'second-reservation', 'kind': 'reserve', 'deps': [], 'unit': 'event'})
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_BROKER_EFFECT_CLASS'):
            admit(task)
