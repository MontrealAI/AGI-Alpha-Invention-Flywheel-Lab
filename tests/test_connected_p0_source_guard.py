"""Adversarial synthetic preflight tests; no original Account or private keys."""
import tempfile
import unittest
from pathlib import Path
from tools.p0_source_guard import checked_path, inspect, load_registry


class JoinPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.a, self.b, self.c = (self.root / name for name in 'abc')
        for p in (self.a, self.b, self.c):
            (p / 'connected_enterprise').mkdir(parents=True)
        self.files(self.a, {'a.py': 'a', 'shared.py': 'old', 'production.py': 'p', 'inventory.py': 'i'})
        self.files(self.b, {'b.py': 'b', 'shared.py': 'new'})
        self.files(self.c, {'a.py': 'a', 'b.py': 'b', 'shared.py': 'resolved', 'production.py': 'p', 'inventory.py': 'i'})
        self.registry(self.a, "SOURCE_PATHS = ('a.py', 'shared.py')\nPRODUCTION_SOURCE_PATHS = ('production.py',)\nINVENTORY_SOURCE_PATHS = ('inventory.py',)\ndef source_paths_for_manifest(x):\n return 'flexibility063/native-services/v1'\n")
        self.registry(self.b, "SOURCE_PATHS = ('b.py', 'shared.py')\n")
        self.registry(self.c, "SOURCE_PATHS = ('a.py', 'b.py', 'shared.py')\nPRODUCTION_SOURCE_PATHS = ('production.py',)\nINVENTORY_SOURCE_PATHS = ('inventory.py',)\ndef source_paths_for_manifest(x):\n return 'flexibility063/native-services/v1'\n")

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, root, files):
        for name, text in files.items():
            (root / name).write_text(text)

    def registry(self, root, text):
        (root / 'connected_enterprise/finance.py').write_text(text)

    def test_complete_union_preserves_optional_routes_and_fingerprints_changed_shared(self):
        v = inspect(self.a, self.b, self.c)
        self.assertTrue(v['registry_complete'])
        self.assertEqual(v['union_source_count'], 3)
        self.assertEqual([x['path'] for x in v['shared_financial_paths_with_different_bytes']], ['shared.py'])
        self.assertTrue(v['semantic_review_and_authenticated_account_migration_required'])

    def test_loss_of_main_or_transition_authority_detected(self):
        self.registry(self.c, "SOURCE_PATHS = ('a.py', 'shared.py')\n")
        v = inspect(self.a, self.b, self.c)
        self.assertFalse(v['registry_complete'])
        self.assertEqual(v['missing_main_or_transition_financial_paths'], ['b.py'])

    def test_loss_of_manifest_optional_source_detected(self):
        self.registry(self.c, "SOURCE_PATHS = ('a.py', 'b.py', 'shared.py')\n")
        v = inspect(self.a, self.b, self.c)
        self.assertFalse(v['registry_complete'])
        self.assertEqual(v['missing_main_optional_service_paths']['INVENTORY_SOURCE_PATHS'], ['inventory.py'])
        self.assertEqual(v['missing_main_optional_service_paths']['PRODUCTION_SOURCE_PATHS'], ['production.py'])
        self.assertEqual(v['missing_main_manifest_routes'], ['flexibility063/native-services/v1'])

    def test_symlink_and_traversal_refused(self):
        (self.c / 'bad.py').symlink_to(self.c / 'a.py')
        with self.assertRaisesRegex(ValueError, 'P0_SYMLINK_SOURCE_REFUSED'):
            checked_path(self.c, 'bad.py')
        for name in ('../a.py', '/tmp/x', 'bad\\slash.py'):
            with self.assertRaisesRegex(ValueError, 'P0_INVALID_SOURCE_PATH'):
                checked_path(self.c, name)

    def test_dynamic_registry_cannot_execute_or_pass(self):
        self.registry(self.b, "SOURCE_PATHS = __import__('os').system('echo not executed')\n")
        with self.assertRaisesRegex(ValueError, 'P0_NONLITERAL_REGISTRY'):
            load_registry(self.b)

    def test_missing_pinned_files_refused(self):
        (self.b / 'b.py').unlink()
        with self.assertRaisesRegex(ValueError, 'P0_MISSING_SOURCE:b.py'):
            inspect(self.a, self.b, self.c)


    def test_late_registry_writes_cannot_hide_missing_source_dependencies(self):
        baseline = (self.c / 'connected_enterprise/finance.py').read_text()
        cases = (
            ("SOURCE_PATHS += ('ghost.py',)", 'SOURCE_PATHS'),
            ("del SOURCE_PATHS", 'SOURCE_PATHS'),
            ("if True:\n SOURCE_PATHS = ('a.py',)", 'SOURCE_PATHS'),
            ("def mutate():\n global SOURCE_PATHS\n SOURCE_PATHS = ('a.py',)", 'SOURCE_PATHS'),
            ("SOURCE_PATHS: tuple = ('a.py',)", 'SOURCE_PATHS'),
            ("INVENTORY_SOURCE_PATHS += ('ghost.py',)", 'INVENTORY_SOURCE_PATHS'),
        )
        for addition, registry in cases:
            with self.subTest(addition=addition):
                self.registry(self.c, baseline + '\n' + addition + '\n')
                with self.assertRaisesRegex(ValueError, 'P0_REGISTRY_REBIND_OR_DYNAMIC_WRITE:' + registry):
                    inspect(self.a, self.b, self.c)
        self.registry(self.c, baseline)
        self.assertTrue(inspect(self.a, self.b, self.c)['registry_complete'])


if __name__ == '__main__':
    unittest.main()
