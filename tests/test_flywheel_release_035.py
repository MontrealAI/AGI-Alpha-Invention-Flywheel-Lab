"""Canonical release inventory, clean extracted invocation and fail-closed identity."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from connected_enterprise.runner import identity, source_paths

ROOT = Path(__file__).resolve().parents[1]


class ReleasedWheel(unittest.TestCase):
    def extracted(self, temp):
        archive = Path(temp) / 'source.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            for name in source_paths(ROOT):
                out.write(ROOT / name, name)
        dest = Path(temp) / 'extracted'
        with zipfile.ZipFile(archive) as source:
            source.extractall(dest)
        return dest

    def test_actual_extracted_cli_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            extracted = self.extracted(temp)
            expected = identity(ROOT)['sha256']
            self.assertEqual(identity(extracted)['sha256'], expected)
            receipt = Path(temp) / 'receipt.json'
            result = subprocess.run([sys.executable, '-I', str(extracted / 'scripts/qualify_released_wheel035.py'),
                '--expected-source', expected, '--output', str(receipt)], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            proof = json.loads(receipt.read_text())
            self.assertTrue(proof['accepted'])
            self.assertEqual(proof['stage_count'], 48)
            self.assertFalse(proof['funding_authority'])

    def test_missing_wheel_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            extracted = self.extracted(temp)
            (extracted / 'flywheel_wheel/coupling.py').unlink()
            with self.assertRaisesRegex(ValueError, 'FLYWHEEL_WHEEL_SOURCE_DEPENDENCY_MISSING'):
                identity(extracted)

    def test_absent_optional_wheel_keeps_legacy_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            extracted = self.extracted(temp)
            shutil.rmtree(extracted / 'flywheel_wheel')
            self.assertFalse(any(name.startswith('flywheel_wheel/') for name in source_paths(extracted)))

    def test_tampered_source_fails_with_compact_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            extracted = self.extracted(temp)
            expected = identity(extracted)['sha256']
            with (extracted / 'flywheel_wheel/render.py').open('a') as stream:
                stream.write('\n# modified\n')
            receipt = Path(temp) / 'receipt.json'
            result = subprocess.run([sys.executable, '-I', str(extracted / 'scripts/qualify_released_wheel035.py'),
                '--expected-source', expected, '--output', str(receipt)], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 1)
            proof = json.loads(receipt.read_text())
            self.assertFalse(proof['accepted'])
            self.assertNotIn(str(extracted), receipt.read_text())
            self.assertEqual(proof['failure_type'], 'ValueError')


if __name__ == '__main__':
    unittest.main()
