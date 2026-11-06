"""F03: exported public delivery evidence must match its executed native turn.

All mutations target detached public copies of fresh synthetic fixtures. The
native export, source-prepared deliveries and financial report remain unchanged;
these probes do not forge a native ledger or claim altered economic results.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from campaign.genesis_commitment001 import service
from connected_enterprise.finance import source_paths_for_manifest

ROOT = Path(service.__file__).resolve().parents[2]
PUBLIC_RECEIPTS = ('FIRST_ARTIFACT.json', 'FIRST_ACCEPTANCE.json',
                   'SUCCESSOR_ARTIFACT.json', 'SUCCESSOR_ACCEPTANCE.json')


def command(source, *arguments):
    return subprocess.run(
        [sys.executable, '-m', 'campaign.genesis_commitment001.runner',
         *map(str, arguments)], cwd=source, text=True, capture_output=True,
        env={**os.environ, 'PYTHONPATH': str(source), 'PYTHONDONTWRITEBYTECODE': '1'})


def public_copy(original, destination):
    destination.mkdir()
    for path in original.iterdir():
        if path.name == 'private':
            continue
        if path.is_dir():
            shutil.copytree(path, destination/path.name,
                            ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copyfile(path, destination/path.name)


def protected_hashes(output):
    """Only public records; never inspect or copy account recovery authority."""
    names = ['NATIVE_EXPORT.json', 'REPORT.json', 'MANIFEST.json',
             'REGISTRATION.json', 'EXECUTION.json']
    names.extend(path.relative_to(output).as_posix()
                 for path in (output/'source').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    return {name: hashlib.sha256((output/name).read_bytes()).hexdigest()
            for name in sorted(names)}


class PublicCommitmentReceiptChallenge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='commitment-public-f03-')
        cls.home = Path(cls.temporary.name)
        cls.source = cls.home/'source'
        for name in source_paths_for_manifest({'schema': service.SCHEMA}):
            target = cls.source/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
        cls.fixtures = {}
        cases = [('favorable_envelope', arm) for arm in ('retained', 'direct')]
        cases += [(scenario, 'retained') for scenario in
                  ('central', 'bad_output', 'shared_shock', 'cost_stress')]
        for scenario, arm in cases:
            output = cls.home/('original-'+scenario+'-'+arm)
            result = command(cls.source, 'run', '--output', output,
                             '--scenario', scenario, '--arm', arm)
            if result.returncode:
                raise RuntimeError(result.stdout+result.stderr)
            cls.fixtures[(scenario, arm)] = output
        cls.original_hashes = {key: protected_hashes(path)
                               for key, path in cls.fixtures.items()}

    @classmethod
    def tearDownClass(cls):
        try:
            for key, output in cls.fixtures.items():
                if protected_hashes(output) != cls.original_hashes[key]:
                    raise AssertionError('Original synthetic fixture was changed')
        finally:
            cls.temporary.cleanup()

    def test_honest_positive_and_adverse_public_packages_remain_auditable(self):
        expected = {
            'favorable_envelope': set(PUBLIC_RECEIPTS),
            'central': set(),
            'bad_output': {'FIRST_ARTIFACT.json', 'FIRST_ACCEPTANCE.json'},
            'shared_shock': {'FIRST_ARTIFACT.json'},
            'cost_stress': {'FIRST_ARTIFACT.json', 'FIRST_ACCEPTANCE.json'},
        }
        for (scenario, arm), original in self.fixtures.items():
            with self.subTest(scenario=scenario, arm=arm):
                output = self.home/('honest-'+scenario+'-'+arm)
                public_copy(original, output)
                self.assertFalse((output/'private').exists())
                self.assertEqual({name for name in PUBLIC_RECEIPTS
                                  if (output/name).exists()}, expected[scenario])
                before = protected_hashes(output)
                audited = command(self.source, 'audit', '--output', output)
                self.assertEqual(audited.returncode, 0, audited.stderr)
                archive = self.home/(output.name+'.zip')
                packaged = command(self.source, 'package', '--output', output,
                                   '--archive', archive)
                self.assertEqual(packaged.returncode, 0, packaged.stderr)
                extracted = self.home/(output.name+'-extracted')
                with zipfile.ZipFile(archive) as zipped:
                    self.assertFalse(any('private' in Path(name).parts
                                         or name.endswith('.adaptive-simulation-key')
                                         for name in zipped.namelist()))
                    zipped.extractall(extracted)
                checked = command(extracted/'source', 'audit', '--output', extracted)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(protected_hashes(output), before)
                self.assertEqual(protected_hashes(extracted), before)

    def rejection_probes(self, mutation):
        for arm in ('retained', 'direct'):
            original = self.fixtures[('favorable_envelope', arm)]
            for filename in PUBLIC_RECEIPTS:
                output = self.home/(mutation+'-'+arm+'-'+filename[:-5].lower())
                public_copy(original, output)
                self.assertFalse((output/'private').exists())
                before = protected_hashes(output)
                target = output/filename
                outside = None
                if mutation == 'contradictory':
                    value = json.loads(target.read_text())
                    if 'ARTIFACT' in filename:
                        value['request_id'] = 'FRESH-F03-CONTRADICTORY-PUBLIC-ID'
                    else:
                        value['accepted'] = not value['accepted']
                    target.write_text(json.dumps(value))
                elif mutation == 'malformed':
                    target.write_bytes(b'{FRESH-F03-MALFORMED-JSON')
                elif mutation == 'missing':
                    target.unlink()
                elif mutation == 'symlink':
                    outside = self.home/(output.name+'-outside.json')
                    outside.write_bytes(target.read_bytes())
                    outside_before = outside.read_bytes()
                    target.unlink()
                    target.symlink_to(outside)
                else:
                    raise AssertionError('Unregistered mutation')
                audited = command(self.source, 'audit', '--output', output)
                archive = self.home/(output.name+'.zip')
                packaged = command(self.source, 'package', '--output', output,
                                   '--archive', archive)
                self.assertEqual(protected_hashes(output), before)
                if outside is not None:
                    self.assertEqual(outside.read_bytes(), outside_before)
                for operation, result in [('audit', audited), ('package', packaged)]:
                    with self.subTest(arm=arm, file=filename, mutation=mutation,
                                      operation=operation):
                        self.assertNotEqual(result.returncode, 0,
                                            'Changed public evidence was accepted')
                        if operation == 'package':
                            self.assertFalse(archive.exists(),
                                             'Rejected evidence left an export archive')

    def test_valid_but_contradictory_public_receipts_are_rejected(self):
        self.rejection_probes('contradictory')

    def test_malformed_public_receipts_are_rejected(self):
        self.rejection_probes('malformed')

    def test_missing_public_receipts_are_rejected(self):
        self.rejection_probes('missing')

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlink boundary')
    def test_symlink_public_receipts_are_rejected(self):
        self.rejection_probes('symlink')


if __name__ == '__main__':
    unittest.main()
