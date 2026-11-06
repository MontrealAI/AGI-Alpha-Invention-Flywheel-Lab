"""Release completeness and a real no-Git executable package check."""
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from connected_enterprise.runner import QUOTE_RELEASE_PATHS, quote_release_paths, source_paths
from connected_enterprise.finance import source_paths_for_manifest
from scripts.release_connected014 import applicable_workflows, archive_manifest

ROOT = Path(__file__).resolve().parents[1]


class QuoteReleaseTests(unittest.TestCase):
    def test_complete_optional_unit_and_partial_or_symlink_refusal(self):
        self.assertTrue(set(QUOTE_RELEASE_PATHS) <= set(source_paths(ROOT)))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(quote_release_paths(root), set())
            first = root / QUOTE_RELEASE_PATHS[0]
            first.parent.mkdir(parents=True)
            first.write_text('partial')
            with self.assertRaisesRegex(ValueError, 'COMPLETE_RELEASE_SOURCE'):
                quote_release_paths(root)
            for name in QUOTE_RELEASE_PATHS:
                p = root/name
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, p)
            self.assertEqual(quote_release_paths(root), set(QUOTE_RELEASE_PATHS))
            first.unlink()
            first.symlink_to(ROOT/QUOTE_RELEASE_PATHS[0])
            with self.assertRaisesRegex(ValueError, 'COMPLETE_RELEASE_SOURCE'):
                quote_release_paths(root)

    def test_resealed_but_incomplete_archive_is_rejected(self):
        raw = b'partial'
        name = QUOTE_RELEASE_PATHS[0]
        frozen = {'files': {}, 'sha256': hashlib.sha256(b'{}').hexdigest()}
        manifest = {'schema': 'agi-alpha/connected014-source-distribution/v1',
                    'executing_source': frozen,
                    'files': {name: hashlib.sha256(raw).hexdigest()}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'partial.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(name, raw)
                archive.writestr('SOURCE_MANIFEST.json', json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'PUBLIC_QUOTE_EXACT_RELEASE_SOURCE'):
                archive_manifest(path)

    def test_all_executed_dependencies_and_tests_trigger_same_head_gate(self):
        names = set(source_paths_for_manifest({'schema': 'genesis-commitment001/native-services/v1'}))
        names.update(QUOTE_RELEASE_PATHS)
        names.add('requirements-commercial010.txt')
        workflow = (ROOT/'.github/workflows/commitment-public-quote.yml').read_text()
        pr, push = workflow.split('  push:', 1)
        paths = lambda text: {line.strip()[3:-1] for line in text.splitlines()
                              if line.strip().startswith("- '")}
        self.assertEqual(paths(pr), paths(push))
        for name in names:
            with self.subTest(path=name):
                self.assertIn('commitment-public-quote.yml', applicable_workflows([name]))
                self.assertTrue(any(fnmatchcase(name, pattern) for pattern in paths(pr)))

    def test_distribution_inventory_runs_and_audits_without_git(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base/'source'
            for name in source_paths(ROOT):
                dest = source/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, dest)
            self.assertFalse((source/'.git').exists())
            script = source/'scripts/qualify_commitment_quote.py'
            for command in ('run', 'audit'):
                completed = subprocess.run([sys.executable, '-B', str(script), command,
                    '--output', str(base/'evidence')], cwd=source, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                receipt = json.loads(completed.stdout)
                self.assertTrue(all(row['accepted'] for row in receipt['audit'].values()))


if __name__ == '__main__':
    unittest.main()
