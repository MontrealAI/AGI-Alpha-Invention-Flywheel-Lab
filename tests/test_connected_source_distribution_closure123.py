"""Source-distribution developer test closure 123; no account, signer or network."""
import unittest
from pathlib import Path

from connected_enterprise.runner import source_paths
from scripts.qualify_connected014 import TEST_ONLY_INPUTS, with_test_source_closure


ROOT = Path(__file__).resolve().parents[1]


class SourceDistributionDeveloperClosure123(unittest.TestCase):
    def test_actual_canonical_test_inventory_includes_both_original_test_consumers(self):
        original = set(source_paths(ROOT))
        self.assertTrue(set(TEST_ONLY_INPUTS).issubset(original))
        included = with_test_source_closure(original)
        for required in TEST_ONLY_INPUTS.values():
            for name in required:
                with self.subTest(name=name):
                    self.assertIn(name, included)
                    path = ROOT / name
                    self.assertTrue(path.is_file())
                    self.assertFalse(path.is_symlink())

    def test_only_dependencies_of_present_tests_are_added(self):
        dependent_guard, dependent_release = TEST_ONLY_INPUTS
        both = with_test_source_closure({dependent_guard, dependent_release})
        only_guard = with_test_source_closure({dependent_guard})
        only_release = with_test_source_closure({dependent_release})
        neither = with_test_source_closure({'some/other_test.py'})
        self.assertEqual(both, {dependent_guard, dependent_release, *TEST_ONLY_INPUTS[dependent_guard], *TEST_ONLY_INPUTS[dependent_release]})
        self.assertEqual(only_guard, {dependent_guard, *TEST_ONLY_INPUTS[dependent_guard]})
        self.assertEqual(only_release, {dependent_release, *TEST_ONLY_INPUTS[dependent_release]})
        self.assertEqual(neither, {'some/other_test.py'})

    def test_source_closure_is_idempotent_and_does_not_add_private_state(self):
        selected = with_test_source_closure(TEST_ONLY_INPUTS)
        self.assertEqual(selected, with_test_source_closure(selected))
        self.assertTrue(all('key' not in path.lower() or not path.endswith('.adaptive-simulation-key')
                            for path in selected))
        self.assertTrue(all('.sqlite' not in path for path in selected))


if __name__ == '__main__':
    unittest.main()
