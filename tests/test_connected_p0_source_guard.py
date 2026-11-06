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
        self.registry(self.a, "SOURCE_PATHS = ('a.py', 'shared.py')\nPRODUCTION_SOURCE_PATHS = ('production.py',)\nINVENTORY_SOURCE_PATHS = ('inventory.py',)\ndef source_paths_for_manifest(manifest):\n schema = manifest.get('schema') if isinstance(manifest, dict) else None\n if schema == 'flexibility063/native-services/v1':\n  return SOURCE_PATHS + tuple(source_paths(None))\n if schema == 'public-portfolio-20261102/native-services/v2':\n  return SOURCE_PATHS + tuple(source_paths(None))\n return SOURCE_PATHS\n")
        self.registry(self.b, "SOURCE_PATHS = ('b.py', 'shared.py')\n")
        self.registry(self.c, "SOURCE_PATHS = ('a.py', 'b.py', 'shared.py')\nPRODUCTION_SOURCE_PATHS = ('production.py',)\nINVENTORY_SOURCE_PATHS = ('inventory.py',)\ndef source_paths_for_manifest(manifest):\n schema = manifest.get('schema') if isinstance(manifest, dict) else None\n if schema == 'flexibility063/native-services/v1':\n  return SOURCE_PATHS + tuple(source_paths(None))\n if schema == 'public-portfolio-20261102/native-services/v2':\n  return SOURCE_PATHS + tuple(source_paths(None))\n return SOURCE_PATHS\n")

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
        self.assertEqual(v['missing_main_manifest_routes'], ['flexibility063/native-services/v1', 'public-portfolio-20261102/native-services/v2'])

    def test_v2_route_loss_rejected_despite_complete_static_source_lists(self):
        path = self.c / 'connected_enterprise/finance.py'
        path.write_text(path.read_text().replace(
            " if schema == 'public-portfolio-20261102/native-services/v2':\n  return SOURCE_PATHS + tuple(source_paths(None))\n", ""))
        result = inspect(self.a, self.b, self.c)
        self.assertFalse(result['registry_complete'])
        self.assertEqual(result['missing_main_manifest_routes'],
                         ['public-portfolio-20261102/native-services/v2'])
        self.assertEqual(result['missing_main_or_transition_financial_paths'], [])

    def test_inert_v2_literal_cannot_masquerade_as_dispatch(self):
        path = self.c / 'connected_enterprise/finance.py'
        path.write_text(path.read_text().replace(
            " if schema == 'public-portfolio-20261102/native-services/v2':\n  return SOURCE_PATHS + tuple(source_paths(None))\n",
            " documentation = 'public-portfolio-20261102/native-services/v2'\n"))
        result = inspect(self.a, self.b, self.c)
        self.assertFalse(result['registry_complete'])
        self.assertIn('public-portfolio-20261102/native-services/v2',
                      result['missing_main_manifest_routes'])

    def test_v2_base_only_placeholder_is_not_a_service_route(self):
        path = self.c / 'connected_enterprise/finance.py'
        path.write_text(path.read_text().replace(
            " if schema == 'public-portfolio-20261102/native-services/v2':\n"
            "  return SOURCE_PATHS + tuple(source_paths(None))\n",
            " if schema == 'public-portfolio-20261102/native-services/v2':\n"
            "  return SOURCE_PATHS\n"))
        result = inspect(self.a, self.b, self.c)
        self.assertFalse(result['registry_complete'])
        self.assertEqual(result['missing_main_manifest_routes'],
                         ['public-portfolio-20261102/native-services/v2'])

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


class PairedAcquisitionReleaseClosureTests(unittest.TestCase):
    def registered(self):
        import json
        root = Path(__file__).resolve().parents[1]
        folder = 'experiments/paired_acquisition_20261102'
        manifest = json.loads((root / folder / 'SOURCE_MANIFEST.json').read_text())
        self.assertEqual(len(manifest['files']), 16)
        extras = ('SOURCE_MANIFEST.json', 'README.md', 'FIVE_ROUTE_STATUS.md',
                  'INDEPENDENT_REVIEW.md', 'ECONOMIC_REVIEW.md',
                  'evidence/SCIENCE.json', 'evidence/ECONOMICS.json',
                  'evidence/ECONOMIC_INPUTS.json', 'evidence/RETAINED_INTERFACE.json',
                  'evidence/SUMMARY.json', 'evidence/EXECUTION.json',
                  'evidence/LOCAL_TESTS.json')
        required = {folder + '/' + name for name in (*manifest['files'], *extras)}
        required.add('.github/workflows/paired-acquisition-20261102.yml')
        self.assertEqual(len(required), 29)
        return root, required

    def test_current_release_inventory_keeps_independent_study_and_workflow(self):
        from connected_enterprise.runner import source_paths
        root, required = self.registered()
        self.assertTrue(all((root / name).is_file() for name in required))
        self.assertEqual(sorted(required - set(source_paths(root))), [])

    def test_missing_economic_receipt_refuses_release_source_inventory(self):
        from unittest.mock import patch
        from connected_enterprise.runner import source_paths
        root, required = self.registered()
        target = root / 'experiments/paired_acquisition_20261102/evidence/ECONOMICS.json'
        self.assertIn(target.relative_to(root).as_posix(), required)
        original = Path.is_file
        def absent(path):
            return False if path == target else original(path)
        with patch.object(Path, 'is_file', absent):
            with self.assertRaisesRegex(ValueError, 'PAIRED_ACQUISITION_SOURCE_DEPENDENCY_MISSING'):
                source_paths(root)



if __name__ == '__main__':
    unittest.main()
