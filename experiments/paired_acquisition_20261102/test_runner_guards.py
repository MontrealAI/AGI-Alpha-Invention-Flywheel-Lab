"""Integrity failures must precede scientific execution and preserve evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class SourceIntegrity(unittest.TestCase):
    def test_tampered_constructor_is_refused_before_import_and_output_is_exclusive(self):
        source = Path(__file__).resolve().parent
        manifest = source / 'SOURCE_MANIFEST.json'
        expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'experiments' / source.name
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', 'evidence'))
            with (target / 'instrument.py').open('a') as handle:
                handle.write('\nraise RuntimeError("TAMPERED_CODE_MUST_NOT_EXECUTE")\n')
            output = root / 'receipt'
            command = [sys.executable, '-m', f'experiments.{source.name}.run',
                       '--output', str(output), '--expected-freeze-sha256', expected,
                       '--source-commit', '0' * 40, '--execution-label', 'integrity-negative-only']
            run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(run.returncode, 0)
            failure = json.loads((output / 'FAILURE.json').read_text())
            self.assertIn('frozen source differs: instrument.py', failure['error'])
            self.assertFalse(failure['scientific_execution_started'])
            self.assertFalse(failure['source_integrity_after_attempt'])
            self.assertEqual(failure['denominators_remain_registered'],
                             {'bulk': 80, 'spatial': 12, 'controls': 8, 'limitations': 4})
            self.assertFalse((output / 'SCIENCE.json').exists())
            original = {p.name: p.read_bytes() for p in output.iterdir()}
            retry = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual(original, {p.name: p.read_bytes() for p in output.iterdir()})


if __name__ == '__main__':
    unittest.main()
