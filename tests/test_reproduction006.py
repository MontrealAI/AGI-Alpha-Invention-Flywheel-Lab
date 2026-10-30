"""Identity and immutable interruption boundaries of the real cycle-006 entry point."""
import hashlib
import importlib.util
import json
import os
import signal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'run_cycle006.py'
spec = importlib.util.spec_from_file_location('reproduction006_entrypoint', SOURCE)
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class ReproductionBoundaryTests(unittest.TestCase):
    def frozen(self, root):
        candidate = root / entry.CANDIDATE
        candidate.parent.mkdir(parents=True)
        source = root / 'instrument.py'
        source.write_text('untrusted_code_was_not_imported = True\n')
        pins = {'instrument.py': entry.sha(source)}
        candidate.write_text(json.dumps({'sources': pins}))
        pins[entry.CANDIDATE] = entry.sha(candidate)
        freeze = root / 'freeze.json'
        freeze.write_text(json.dumps({'schema': 'agi-alpha/cycle006-reproduction-freeze/v1',
            'sources': pins, 'candidate_freeze_sha256': entry.sha(candidate)}))
        return freeze, source

    def test_exact_closure_then_changed_or_symlinked_source_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze, source = self.frozen(root)
            with patch.object(entry, 'REQUIRED', {'instrument.py', entry.CANDIDATE}):
                entry.source_identity(root, freeze, entry.sha(freeze))
                source.write_text('changed\n')
                with self.assertRaisesRegex(ValueError, 'SOURCE_IDENTITY_MISMATCH'):
                    entry.source_identity(root, freeze)
                original = root / 'original.py'
                original.write_text('untrusted_code_was_not_imported = True\n')
                source.unlink(); source.symlink_to(original)
                with self.assertRaisesRegex(ValueError, 'SOURCE_IDENTITY_MISMATCH'):
                    entry.source_identity(root, freeze)

    def test_initialization_failure_keeps_marker_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze, source = self.frozen(root)
            source.write_text('changed\n')
            output = root / 'run'
            with patch.object(entry, 'ROOT', root), patch.object(entry, 'REQUIRED', {'instrument.py', entry.CANDIDATE}):
                with self.assertRaisesRegex(ValueError, 'SOURCE_IDENTITY_MISMATCH'):
                    entry.main(['--output', str(output), '--freeze', str(freeze)])
                self.assertTrue((output / 'STARTED.json').exists())
                marker = (output / 'INTERRUPTED.json').read_bytes()
                self.assertFalse((output / 'COMPLETE.json').exists())
                with self.assertRaises(FileExistsError):
                    entry.main(['--output', str(output), '--freeze', str(freeze)])
                self.assertEqual(marker, (output / 'INTERRUPTED.json').read_bytes())

    def test_signal_pending_at_successful_mkdir_keeps_interruption_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'run'
            real_mkdir = Path.mkdir
            def interrupt_after_kernel_creation(path, *args, **kwargs):
                result = real_mkdir(path, *args, **kwargs)
                if path == output:
                    os.kill(os.getpid(), signal.SIGINT)
                return result
            with patch.object(Path, 'mkdir', interrupt_after_kernel_creation):
                with self.assertRaises(KeyboardInterrupt):
                    entry.main(['--output', str(output)])
            self.assertTrue(output.is_dir())
            self.assertTrue((output / 'INTERRUPTED.json').is_file())
            self.assertFalse((output / 'COMPLETE.json').exists())

    def test_cli_refuses_symlinked_freeze_before_application_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze, unused = self.frozen(root)
            alias = root / 'alias.json'; alias.symlink_to(freeze)
            with patch.object(entry, 'ROOT', root), patch.object(entry, 'REQUIRED', {'instrument.py', entry.CANDIDATE}):
                with self.assertRaisesRegex(ValueError, 'FREEZE_SYMLINK'):
                    entry.main(['--output', str(root / 'run'), '--freeze', str(alias)])
            self.assertTrue((root / 'run/INTERRUPTED.json').is_file())

    def test_completion_exclusive_publication_and_wrong_freeze_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze, unused = self.frozen(root)
            with patch.object(entry, 'REQUIRED', {'instrument.py', entry.CANDIDATE}):
                with self.assertRaisesRegex(ValueError, 'FREEZE_IDENTITY_MISMATCH'):
                    entry.source_identity(root, freeze, '0' * 64)
            report = root / 'REPORT.json'; report.write_text('{}\n')
            entry.complete(root, report)
            original = (root / 'COMPLETE.json').read_bytes()
            with self.assertRaises(FileExistsError):
                entry.complete(root, report)
            self.assertEqual(original, (root / 'COMPLETE.json').read_bytes())
            self.assertEqual(json.loads(original)['report_sha256'], hashlib.sha256(report.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
