"""Legacy finance needs its own closure; active industrial services need all theirs."""
from pathlib import Path
import shutil
import tempfile
import unittest

from connected_enterprise.finance import (
    SOURCE_PATHS, INVENTORY_SOURCE_PATHS, PRODUCTION_SOURCE_PATHS,
    source_identity, source_paths_for_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


class IndustrialSourceClosureTests(unittest.TestCase):
    def copy(self, root, names):
        for name in names:
            target=root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)

    def test_legacy_finance_does_not_require_inactive_inventory_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.copy(root,SOURCE_PATHS)
            legacy={'schema':'agi-alpha/adaptive012-services/v1'}
            self.assertEqual(set(source_identity(root,legacy)['files']),set(SOURCE_PATHS))
            self.assertEqual(source_identity(root),source_identity(root,legacy))
            self.assertFalse((root/'inventory061/inputs').exists())

    def test_active_inventory_binds_nonpython_inputs_and_shared_imports(self):
        manifest={'schema':'inventory061/native-services/v1'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=set(SOURCE_PATHS)|set(INVENTORY_SOURCE_PATHS)
            self.copy(root,names-{'inventory061/inputs/brief.md'})
            with self.assertRaisesRegex(ValueError,'inventory061/inputs/brief.md'):
                source_identity(root,manifest)
            self.copy(root,['inventory061/inputs/brief.md'])
            identity=source_identity(root,manifest)
            self.assertEqual(set(identity['files']),names)
            self.assertIn('production060/acceptance.py',identity['files'])
            path=root/'inventory061/inputs/brief.md'
            path.write_bytes(path.read_bytes()+b'\n')
            self.assertNotEqual(identity,source_identity(root,manifest))

    def test_production_has_its_complete_domain_without_inventory_dependency(self):
        manifest={'schema':'production060/native-services/v1'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=set(SOURCE_PATHS)|set(PRODUCTION_SOURCE_PATHS)
            self.copy(root,names)
            self.assertEqual(set(source_identity(root,manifest)['files']),names)
            self.assertFalse(any(p.startswith('inventory061/') for p in names))
            self.assertEqual(set(source_paths_for_manifest(manifest)),names)

    def test_optional_inventory_package_is_complete_or_wholly_absent(self):
        from connected_enterprise.runner import source_paths
        from inventory061.service import SOURCES
        complete=set(source_paths(ROOT))
        self.assertTrue(set(SOURCES)<=complete)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.copy(root,complete-{'inventory061/inputs/brief.md'})
            partial=set(source_paths(root))
            self.assertFalse(any(n.startswith('inventory061/') for n in partial))
            self.assertFalse(any(n.startswith('tests/test_inventory061') for n in partial))
            with self.assertRaisesRegex(ValueError,'inventory061/inputs/brief.md'):
                source_identity(root,{'schema':'inventory061/native-services/v1'})


if __name__=='__main__':
    unittest.main()
