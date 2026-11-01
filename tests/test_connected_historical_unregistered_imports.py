"""Key-free synthetic import trust-boundary tests; no historical accounts or secrets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connected_enterprise import upgrades


class UnregisteredHistoricalImports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='historical-import-guard-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'inspected.py').write_text("RESULT='APPROVED'\n")

    def test_native_import_shadow_and_executable_archives_rejected(self):
        approved = upgrades.source_inventory(self.root)
        self.assertIn('inspected.py', approved)
        for suffix in upgrades._UNREGISTERED_IMPORT_SUFFIXES:
            with self.subTest(suffix=suffix):
                unknown = self.root / ('inspected' + suffix)
                try:
                    unknown.write_bytes(b'unsigned-synthetic-not-a-real-native-module')
                    with self.assertRaisesRegex(ValueError, 'UNREGISTERED_HISTORICAL_EXECUTABLE_REFUSED'):
                        upgrades.source_inventory(self.root)
                finally:
                    unknown.unlink()

    def test_sourceless_bytecode_denied_but_old_cache_isolated(self):
        cache = self.root / '__pycache__'
        cache.mkdir()
        (cache / 'inspected.cpython-311.pyc').write_bytes(b'untrusted-cache')
        self.assertIn('inspected.py', upgrades.source_inventory(self.root))
        self.assertEqual(upgrades._run_pinned_historical_python(self.root,
                         "import inspected;print(inspected.RESULT)", {}).stdout.strip(), 'APPROVED')
        direct = self.root / 'inspected.pyc'
        direct.write_bytes(b'untrusted-sourceless-code')
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_HISTORICAL_EXECUTABLE_REFUSED'):
            upgrades.source_inventory(self.root)

    def test_child_preflight_still_rejects_if_parent_precheck_is_bypassed(self):
        (self.root / 'inspected.so').write_bytes(b'unsigned-synthetic-native-file')
        with patch.object(upgrades, '_reject_unregistered_python_executables'):
            result = upgrades._run_pinned_historical_python(self.root, "print('CODE_RAN')", {})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('UNREGISTERED_HISTORICAL_EXECUTABLE_REFUSED', result.stderr)
        self.assertNotIn('CODE_RAN', result.stdout)

    def test_isolated_python_startup_does_not_import_historical_sitecustomize(self):
        marker = self.root / 'unexpected-startup-execution'
        (self.root / 'sitecustomize.py').write_text("from pathlib import Path\nPath("+repr(str(marker))+").write_text('unexpected')\n")
        result = upgrades._run_pinned_historical_python(self.root,
                          'import sys;print(sys.flags.isolated)', {})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '1')
        self.assertFalse(marker.exists())

    def test_symlinked_import_directory_is_refused(self):
        path = self.root / 'reexport'
        try:
            path.symlink_to(self.root, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest('symlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'HISTORICAL_SOURCE_SYMLINK_REFUSED'):
            upgrades.source_inventory(self.root)


if __name__ == '__main__':
    unittest.main()
