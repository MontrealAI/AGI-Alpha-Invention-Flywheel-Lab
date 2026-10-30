import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package009_under_test', ROOT / 'scripts/package_consequential009.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class ArchiveIntegrityTests(unittest.TestCase):
    def archive(self, base, pairs, corrupt=None):
        contents = dict(pairs)
        manifest = {'source_commit': None, 'files': {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} for name, raw in contents.items()}}
        if corrupt is not None:
            manifest['files'][corrupt]['sha256'] = '0' * 64
        path = base / 'input.zip'
        with zipfile.ZipFile(path, 'x') as stream:
            for name, raw in pairs:
                stream.writestr(name, raw)
            stream.writestr('DOWNLOAD_MANIFEST.json', json.dumps(manifest))
        return path

    def test_alias_witness_and_fresh_variants_refuse_before_any_extraction(self):
        variants = [('proof.txt', './proof.txt'), ('nested/proof.txt', 'nested//proof.txt'),
                    ('nested/proof.txt', 'nested/./proof.txt')]
        for first, second in variants:
            with self.subTest(names=[first, second]), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                path = self.archive(base, [(first, b'first'), (second, b'overwrite')])
                destination = base / 'extracted'
                with self.assertRaisesRegex(ValueError, 'UNSAFE_ARCHIVE_NAMES'):
                    package.extract(path, destination)
                self.assertFalse(destination.exists())

    def test_file_directory_prefix_conflicts_refuse_in_both_orders(self):
        for entries in [[('node', b'file'), ('node/leaf.txt', b'leaf')], [('node/leaf.txt', b'leaf'), ('node', b'file')]]:
            with self.subTest(order=[n for n, _ in entries]), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                path = self.archive(base, entries)
                destination = base / 'extracted'
                with self.assertRaisesRegex(ValueError, 'ARCHIVE_FILE_PREFIX_CONFLICT'):
                    package.extract(path, destination)
                self.assertFalse(destination.exists())

    def test_last_member_hash_failure_cannot_leave_partial_verified_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path = self.archive(base, [('first.txt', b'valid'), ('nested/last.txt', b'tampered')], 'nested/last.txt')
            destination = base / 'extracted'
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_BYTE_MISMATCH'):
                package.extract(path, destination)
            self.assertFalse(destination.exists())

    def fixture_source(self, root):
        names = ['AGENTS.md', 'CHARTER.md', 'FIRST_CAMPAIGN.md', 'THIRD_PARTY.md',
                 'scripts/package_consequential009.py', 'scripts/build_consequential009_paper.py',
                 'REPRODUCING_CONSEQUENTIAL009.md', 'payload.bin']
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('exact test bytes: ' + name).encode())
        freeze = root / 'campaign/consequential-009/SOURCE_FREEZE.json'
        freeze.parent.mkdir(parents=True)
        freeze.write_text(json.dumps({'files': {'payload.bin': hashlib.sha256((root / 'payload.bin').read_bytes()).hexdigest()}}))

    def test_worktree_pack_round_trip_has_explicit_null_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / 'source'
            self.fixture_source(source)
            archive = base / 'package.zip'
            with patch.object(package, 'ROOT', source):
                packed = package.pack(archive, 'WORKTREE')
            result = package.extract(archive, base / 'extracted')
            self.assertIsNone(packed['source_commit'])
            self.assertIsNone(result['source_commit'])
            self.assertEqual((source / 'payload.bin').read_bytes(), (base / 'extracted/payload.bin').read_bytes())
            self.assertEqual(result['files_verified'] + 1, packed['files'])

    def test_claimed_commit_with_different_git_bytes_refuses_before_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / 'source'
            self.fixture_source(source)
            archive = base / 'package.zip'
            unrelated_tree = b'100644 blob ' + b'0' * 40 + b'\tAGENTS.md\0'
            with patch.object(package, 'ROOT', source), patch.object(package.subprocess, 'check_output', return_value=unrelated_tree):
                with self.assertRaisesRegex(ValueError, 'CLAIMED_COMMIT_DOES_NOT_CONTAIN_EXACT_PACKAGED_BYTES'):
                    package.pack(archive, 'a' * 40)
            self.assertFalse(archive.exists())


class PublisherMainQualificationTests(unittest.TestCase):
    def test_actual_workflow_predicate_rejects_later_green_grid_branch(self):
        workflow = (ROOT / '.github/workflows/consequential009.yml').read_text()
        expression = next(line.strip().split('=', 1)[1].strip() for line in workflow.splitlines() if line.strip().startswith('runs = [r for r in data['))
        executable = compile(ast.parse(expression, mode='eval'), '<actual-workflow-run-filter>', 'eval')
        source = '1' * 40
        failed_main = {'id': 101, 'head_sha': source, 'event': 'push', 'head_branch': 'main', 'status': 'completed', 'conclusion': 'failure'}
        green_grid = {**failed_main, 'id': 102, 'head_branch': 'campaign/grid-screen-cycle-1', 'conclusion': 'success'}
        current = eval(executable, {'__builtins__': {}, 'data': {'workflow_runs': [failed_main, green_grid]}, 'sha': source})
        self.assertEqual(current, [failed_main])
        self.assertEqual(max(current, key=lambda row: row['id'])['conclusion'], 'failure')
        no_main = eval(executable, {'__builtins__': {}, 'data': {'workflow_runs': [green_grid]}, 'sha': source})
        self.assertEqual(no_main, [])
        self.assertIn('event=push&branch=main', workflow)


if __name__ == '__main__':
    unittest.main()
