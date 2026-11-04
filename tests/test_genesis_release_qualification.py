"""Small fixtures exercise sealing/receipts; no full release or runtime claim."""
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile

from scripts import qualify_genesis_release as q


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='genesis-release-test-', dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        # The local sandbox itself has .git markers; model an extracted temp root.
        exists = Path.exists
        ancestors = {p / '.git' for p in self.root.parents}
        outside_git = patch.object(Path, 'exists', lambda p: False if p in ancestors else exists(p))
        outside_git.start()
        self.addCleanup(outside_git.stop)
        self.name = 'genesis_enterprise/native.py'
        (self.source / 'genesis_enterprise').mkdir()
        (self.source / self.name).write_text('# fixture\n')
        files = {self.name: q.sha(self.source / self.name)}
        self.native = {'files': files, 'sha256': hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        self.manifest = {'schema': 'agi-alpha/connected014-source-distribution/v1', 'files': files, 'executing_source': self.native}
        q.write(self.source / 'SOURCE_MANIFEST.json', self.manifest)
        self.archive = self.root / 'source.zip'
        self.pack()
        self.patches = [patch('connected_enterprise.runner.genesis_release_paths', return_value={self.name}),
                        patch('connected_enterprise.runner.GENESIS_RELEASE_PATHS', (self.name,)),
                        patch('genesis_enterprise.native.source_files', return_value=[self.name])]
        for mock in self.patches:
            mock.start()
            self.addCleanup(mock.stop)
        self.commit = 'a' * 40

    def pack(self):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name in (self.name, 'SOURCE_MANIFEST.json'):
                archive.write(self.source / name, name)

    def receipt(self):
        return dict(schema=q.SCHEMA, accepted=True, source_commit=self.commit,
            source_sha256=self.native['sha256'], source_archive_sha256=q.sha(self.archive),
            native_source=self.native, native_source_sha256=self.native['sha256'], actual_release_download=False,
            no_git_execution=True, source_files_unchanged=True, completed_resume_export_unchanged=True,
            native_audit_accepted=True, public_audit_accepted=True, native_export_sha256='c' * 64,
            public_export='public', commands=[dict(stage=stage, command=['python', *args], returncode=0,
                stdout_sha256='d' * 64, stderr_sha256='e' * 64)
                for stage, args in q.command_actions(self.root / 'engineering-account', self.root / 'public')])

    def test_exact_source(self):
        self.assertEqual(q.verify_source(self.source, self.archive), (self.manifest, self.native))

    def test_changed_member(self):
        (self.source / self.name).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'EXTRACTED_SOURCE_CHANGED'):
            q.verify_source(self.source, self.archive)

    def test_extra_file(self):
        (self.source / 'extra.py').write_text('')
        with self.assertRaisesRegex(ValueError, 'EXACT_EXTRACTED'):
            q.verify_source(self.source, self.archive)

    def test_symlink_and_traversal(self):
        (self.root / 'link').symlink_to(self.source, target_is_directory=True)
        for path in (self.root / 'link', self.source / '..' / 'source'):
            with self.assertRaises(ValueError):
                q.verify_source(path, self.archive)

    def test_checkout_refused(self):
        (self.source / '.git').mkdir()
        with self.assertRaisesRegex(ValueError, 'NOT_CHECKOUT'):
            q.verify_source(self.source, self.archive)

    def test_archive_tampering(self):
        (self.source / self.name).write_text('tampered')
        self.pack()
        with self.assertRaisesRegex(ValueError, 'SOURCE_MEMBER_HASH_CHANGED'):
            q.verify_source(self.source, self.archive)

    def test_unsafe_archive_members(self):
        for name, mode in [('../outside', 0o100644), ('link', 0o120777)]:
            self.pack()
            with zipfile.ZipFile(self.archive, 'a') as archive:
                item = zipfile.ZipInfo(name)
                item.external_attr = mode << 16
                archive.writestr(item, b'outside')
            with self.assertRaisesRegex(ValueError, 'UNSAFE_OR_PRIVATE'):
                q.verify_source(self.source, self.archive)

    def test_incomplete_closure(self):
        with patch('connected_enterprise.runner.genesis_release_paths', return_value={'missing.py'}):
            with self.assertRaisesRegex(ValueError, 'COMPLETE_GENESIS_RELEASE'):
                q.verify_source(self.source, self.archive)

    def test_valid_receipt(self):
        receipt = self.receipt()
        self.assertEqual(q.validate_receipt(receipt, self.manifest, q.sha(self.archive), self.commit), receipt)

    def test_receipt_tampering(self):
        changes = {'accepted': 1, 'source_commit': 'b' * 40,
                   'source_archive_sha256': 'x', 'native_source_sha256': 'x',
                   'completed_resume_export_unchanged': False, 'public_audit_accepted': False,
                   'native_audit_accepted': False, 'actual_release_download': 1, 'commands': []}
        for key, value in changes.items():
            with self.subTest(key=key):
                receipt = self.receipt()
                receipt[key] = value
                with self.assertRaises(ValueError):
                    q.validate_receipt(receipt, self.manifest, q.sha(self.archive), self.commit)
        for key, value in [('returncode', True), ('stage', 'skip'), ('stdout_sha256', 'bad')]:
            receipt = self.receipt()
            receipt['commands'][2][key] = value
            with self.assertRaises(ValueError):
                q.validate_receipt(receipt, self.manifest, q.sha(self.archive), self.commit)

    def test_download_binding(self):
        path = self.root / 'download.json'
        value = dict(schema='agi-alpha/connected014-actual-release-download/v1', actual_release_download=True,
                     source_commit=self.commit, tag='connected014-' + self.commit, source_sha256=self.native['sha256'],
                     files={'connected014-source.zip': q.sha(self.archive)})
        q.write(path, value)
        self.assertEqual(q.validate_download(path, self.manifest, q.sha(self.archive), self.commit), q.sha(path))
        for key, changed in [('actual_release_download', False), ('source_commit', 'b'*40), ('files', {})]:
            bad = dict(value, **{key: changed})
            q.write(path, bad)
            with self.assertRaises(ValueError):
                q.validate_download(path, self.manifest, q.sha(self.archive), self.commit)

    def test_no_checkout_fallback(self):
        with self.assertRaisesRegex(ValueError, 'EXECUTE_HELPER'):
            q.qualify(self.source, self.archive, self.root / 'out', self.commit)

    def test_failure_preserves_state_and_receipt(self):
        output = self.root / 'out'
        def fail(*args):
            account = output / 'engineering-account'
            account.mkdir()
            (account / 'recovery').write_text('retain')
            raise RuntimeError('failed')
        with patch.object(q, 'ROOT', self.source), patch.object(q, 'verify_source', side_effect=fail):
            with self.assertRaises(RuntimeError):
                q.qualify(self.source, self.archive, output, self.commit)
        self.assertEqual((output / 'engineering-account/recovery').read_text(), 'retain')
        self.assertIs(q.read(output / 'QUALIFICATION.json')['accepted'], False)
        with patch.object(q, 'ROOT', self.source):
            with self.assertRaises(FileExistsError):
                q.qualify(self.source, self.archive, output, self.commit)

    def exercise_mocked(self, changed_resume=False):
        output = self.root / 'out'
        def run(command, cwd, log, deadline, rows):
            self.assertEqual(cwd, self.source)
            stage = log.name.split('-', 1)[1]
            result = {'accepted': True, 'complete': True, 'native_audit_accepted': True}
            operation = output / 'engineering-account'
            public = output / 'public'
            if stage == 'source-identity':
                result = self.native
            if stage == 'pilot':
                (operation / 'public').mkdir(parents=True)
                q.write(operation / 'SOURCE.json', self.native)
                (operation / 'public/native-export.json').write_bytes(b'{"ledger":[]}')
            if stage == 'resume' and changed_resume:
                (operation / 'public/native-export.json').write_bytes(b'{"ledger":[1]}')
            if stage == 'export':
                (public / 'public').mkdir(parents=True)
                q.write(public / 'SOURCE.json', self.native)
                (public / 'public/native-export.json').write_bytes((operation / 'public/native-export.json').read_bytes())
                result['contains_recovery_authority'] = False
            q.write(log.with_suffix('.stdout'), result)
            log.with_suffix('.stderr').write_text('')
            rows.append({'returncode': 0})
        with patch.object(q, 'ROOT', self.source), patch.object(q, 'runtime_versions', return_value={}), \
                patch.object(q, 'run_command', side_effect=run):
            return q.qualify(self.source, self.archive, output, self.commit)

    def test_mocked_complete_sequence(self):
        result = self.exercise_mocked()
        self.assertIs(result['accepted'], True)
        self.assertIs(result['actual_release_download'], False)
        self.assertEqual([r['stage'] for r in result['commands']],
                         ['source-identity', 'pilot', 'resume', 'audit', 'export', 'public-audit'])

    def test_resume_must_preserve_export_bytes(self):
        with self.assertRaisesRegex(ValueError, 'COMPLETED_RESUME_CHANGED'):
            self.exercise_mocked(changed_resume=True)
        self.assertIs(q.read(self.root / 'out/QUALIFICATION.json')['accepted'], False)
        self.assertTrue((self.root / 'out/engineering-account/SOURCE.json').exists())

    def test_probe_checks_runtime_origins_after_closure_imports(self):
        root = Path(__file__).resolve().parents[1]
        clean = subprocess.run([sys.executable, '-B', '-c', q.PROBE], cwd=root, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertIn('adaptive_enterprise/account.py', json.loads(clean.stdout)['files'])
        for package in ('adaptive_enterprise', 'vendor', 'production060'):
            prelude = ("import sys, types; m = types.ModuleType('" + package + ".foreign'); "
                       "m.__file__ = '/outside/foreign.py'; sys.modules[m.__name__] = m;\n")
            result = subprocess.run([sys.executable, '-B', '-c', prelude + q.PROBE],
                                    cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('EXTRACTED_MODULE_ORIGIN_REQUIRED:' + package + '.foreign', result.stderr)

    def test_commands_exercise_connected_optional_shim(self):
        actions = q.command_actions(self.root / 'engineering-account', self.root / 'public')
        for stage, args in actions[1:]:
            self.assertEqual(args[:2], ['-m', 'connected_enterprise.genesis'])

    def test_runtime_pins(self):
        (self.source / 'requirements-commercial010.txt').write_text('cryptography==50.0.2\n')
        versions = {**q.NUMERICAL_PINS, 'cryptography': '50.0.2'}
        with patch.object(q.importlib.metadata, 'version', side_effect=versions.__getitem__):
            self.assertEqual(q.runtime_versions(self.source)['dependencies'], versions)
        with patch.object(q.importlib.metadata, 'version', return_value='wrong'):
            with self.assertRaisesRegex(ValueError, 'PINNED_DEPENDENCY'):
                q.runtime_versions(self.source)


if __name__ == '__main__':
    unittest.main()
