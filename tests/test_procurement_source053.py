"""Opt-in source closure units AND mandatory real frozen-copy/extraction check."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from connected_enterprise import runner

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = 'connected_enterprise/conditional_procurement053.py'
REQUIRED = {
    TRIGGER, 'connected_enterprise/procurement_verify053.py',
    'mechanism_harness/__init__.py', 'mechanism_harness/core.py',
    'scripts/run_conditional_procurement053.py',
    'campaign/conditional-procurement-053/PROTOCOL.json',
    'tests/test_packet_geometry051.py', 'tests/test_procurement053.py',
    'tests/test_native_procurement053.py', 'tests/test_procurement_source053.py',
    'docs/harness/CONDITIONAL_PROCUREMENT053.md',
    '.github/workflows/conditional-procurement053.yml',
}


class ProcurementSourceTests(unittest.TestCase):
    def test_optional_absence_preserves_inventory_unit(self):
        # Unit isolation is NOT source qualification; the integration test below
        # uses the actual inventory and an actual frozen/extracted source tree.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'baseline.py').write_text('# baseline\n')
            with patch.object(runner, 'inherited_paths', return_value=['baseline.py']):
                self.assertEqual(runner.source_paths(root), ['baseline.py'])

    def test_complete_and_every_missing_dependency_unit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in REQUIRED:
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('# unit placeholder, never executed\n')
            with patch.object(runner, 'inherited_paths', return_value=[]):
                self.assertTrue(REQUIRED <= set(runner.source_paths(root)))
                for name in sorted(REQUIRED-{TRIGGER}):
                    path = root/name; content = path.read_bytes(); path.unlink()
                    try:
                        with self.subTest(missing=name), self.assertRaisesRegex(
                                ValueError, 'CONDITIONAL_PROCUREMENT_SOURCE_DEPENDENCY_MISSING'):
                            runner.source_paths(root)
                    finally:
                        path.write_bytes(content)

    def test_real_freeze_zip_extract_identity_and_runner(self):
        before = runner.identity(ROOT)
        self.assertTrue(REQUIRED <= set(before['files']))
        with tempfile.TemporaryDirectory(prefix='procurement053-source-') as folder:
            base = Path(folder); frozen = base/'frozen'; extracted = base/'extracted'
            # freeze is source/config registration only: no accounts or sales.
            with patch.object(runner, 'ROOT', ROOT):
                runner.freeze(frozen, smoke=True)
            saved = json.loads((frozen/'FROZEN.json').read_text())
            self.assertEqual(saved['source'], before)
            self.assertEqual(runner.identity(frozen/'source'), before)
            archive = base/'source.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                for name in sorted(before['files']):
                    z.write(frozen/'source'/name, name)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(set(z.namelist()), set(before['files']))
                z.extractall(extracted)
            self.assertEqual(runner.identity(extracted), before)
            for name in REQUIRED:
                self.assertEqual(hashlib.sha256((extracted/name).read_bytes()).hexdigest(), before['files'][name])
            command = subprocess.run([sys.executable, 'scripts/run_conditional_procurement053.py', '--help'],
                cwd=extracted, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(command.returncode, 0, command.stderr)
            self.assertIn('usage:', command.stdout)
            imported = subprocess.run([sys.executable, '-c',
                'from connected_enterprise import runner, conditional_procurement053, procurement_verify053; '
                'from pathlib import Path; print(runner.identity(Path.cwd())["sha256"])'],
                cwd=extracted, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(imported.stdout.strip(), before['sha256'])
        self.assertEqual(runner.identity(ROOT), before)


if __name__ == '__main__': unittest.main()
