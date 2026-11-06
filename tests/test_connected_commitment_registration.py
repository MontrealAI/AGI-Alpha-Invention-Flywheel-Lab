"""F05: unsigned case metadata cannot relabel a source-bound native account.

Fresh synthetic fixtures supply two honest buyer decisions. Adversarial copies
contain only public files: no account authority is copied, edited or regenerated.
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

from campaign.genesis_commitment001 import service
from connected_enterprise.finance import source_paths_for_manifest

ROOT = Path(service.__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def save(path, value):
    path.write_bytes(canonical(value)+b'\n')


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


def protected_public(output):
    names = ['NATIVE_EXPORT.json', 'MANIFEST.json']
    names.extend(path.relative_to(output).as_posix()
                 for path in (output/'source').rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts)
    return {name: hashlib.sha256((output/name).read_bytes()).hexdigest()
            for name in sorted(names)}


def authority_metadata(output):
    # Check that original synthetic authority was not replaced or modified;
    # never read its key or copy any of these files to an adversarial fixture.
    result = {}
    for path in (output/'private').rglob('*'):
        if path.is_file():
            metadata = path.stat()
            result[path.relative_to(output/'private').as_posix()] = (
                metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
    return result


class RegistrationContractChallenge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='commitment-registration-f05-')
        cls.home = Path(cls.temporary.name)
        cls.source = cls.home/'source'
        for name in source_paths_for_manifest({'schema': service.SCHEMA}):
            destination = cls.source/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, destination)
        cls.fixtures = {}
        for scenario, arm in [('central', 'retained'), ('no_demand', 'direct')]:
            output = cls.home/('original-'+scenario+'-'+arm)
            run = command(cls.source, 'run', '--output', output,
                          '--scenario', scenario, '--arm', arm)
            if run.returncode:
                raise RuntimeError(run.stdout+run.stderr)
            cls.fixtures[scenario] = output
        cls.original_public = {key: protected_public(path)
                               for key, path in cls.fixtures.items()}
        cls.original_authority = {key: authority_metadata(path)
                                  for key, path in cls.fixtures.items()}

    @classmethod
    def tearDownClass(cls):
        try:
            for key, original in cls.fixtures.items():
                if (protected_public(original) != cls.original_public[key]
                        or authority_metadata(original) != cls.original_authority[key]):
                    raise AssertionError('Original fixture or native authority changed')
        finally:
            cls.temporary.cleanup()

    def test_matching_native_registration_contracts_audit_and_package(self):
        for scenario, original in self.fixtures.items():
            with self.subTest(scenario=scenario):
                output = self.home/('honest-'+scenario)
                public_copy(original, output)
                self.assertFalse((output/'private').exists())
                registration = read(output/'REGISTRATION.json')
                record = read(output/'NATIVE_EXPORT.json')
                self.assertEqual(record['ledger']['config']['contract'],
                                 'commitment001-'+registration['binding'][:20])
                before = protected_public(output)
                audited = command(self.source, 'audit', '--output', output)
                self.assertEqual(audited.returncode, 0, audited.stderr)
                packaged = command(self.source, 'package', '--output', output,
                                   '--archive', self.home/(output.name+'.zip'))
                self.assertEqual(packaged.returncode, 0, packaged.stderr)
                self.assertEqual(protected_public(output), before)

    def reject_coherent_relabel(self, scenario, arm, name):
        original = self.fixtures['central']
        output = self.home/name
        public_copy(original, output)
        self.assertFalse((output/'private').exists())
        before = protected_public(output)
        record = read(output/'NATIVE_EXPORT.json')
        registration = read(output/'REGISTRATION.json')
        original_binding = registration['binding']
        native_contract = record['ledger']['config']['contract']
        self.assertEqual(native_contract, 'commitment001-'+original_binding[:20])

        # The relabeled unsigned surface is internally consistent. The buyer
        # choice comes from the other honestly executed scenario, not invented
        # preferences, and no native action/signature is changed.
        target_choice = read(self.fixtures[scenario]/'REPORT.json')['first_buyer_choice']
        registration['scenario'] = scenario
        registration['arm'] = arm
        registration['binding'] = hashlib.sha256(canonical(
            {key: value for key, value in registration.items() if key != 'binding'})).hexdigest()
        save(output/'REGISTRATION.json', registration)
        execution = read(output/'EXECUTION.json')
        execution['binding'] = registration['binding']
        execution['first_choice'] = target_choice
        save(output/'EXECUTION.json', execution)
        report = read(output/'REPORT.json')
        original_finances = report['native_summary']
        report.update(binding=registration['binding'], scenario=scenario, arm=arm,
                      first_buyer_choice=target_choice)
        save(output/'REPORT.json', report)
        self.assertNotEqual(native_contract, 'commitment001-'+registration['binding'][:20])
        self.assertEqual(report['native_summary'], original_finances)
        self.assertEqual(record['ledger']['summary'], original_finances)
        self.assertEqual(protected_public(output), before)

        audit = command(self.source, 'audit', '--output', output)
        archive = self.home/(name+'.zip')
        package = command(self.source, 'package', '--output', output, '--archive', archive)
        self.assertEqual(protected_public(output), before)
        self.assertEqual(read(output/'NATIVE_EXPORT.json')['ledger']['config']['contract'],
                         native_contract)
        for operation, result in [('audit', audit), ('package', package)]:
            with self.subTest(operation=operation):
                self.assertNotEqual(result.returncode, 0,
                                    'One signed native account was accepted as another registration')
                if operation == 'package':
                    self.assertFalse(archive.exists(), 'Relabeled account evidence was exported')

    def test_central_account_cannot_be_relabeled_no_demand(self):
        self.reject_coherent_relabel('no_demand', 'retained', 'scenario-relabel')

    def test_no_order_account_cannot_be_relabeled_as_other_arm(self):
        self.reject_coherent_relabel('central', 'direct', 'arm-relabel')

    def test_native_working_reserve_must_match_registered_initialization(self):
        original = self.home/'working-reserve-original'
        # Construct a genuine alternative ledger in a child process. Only the
        # constructor argument changes in memory; source, inputs, records and
        # signatures stay authentic. $1 is reserved, not spent or reseeded.
        producer = r'''
from pathlib import Path
import sys
from campaign.genesis_commitment001 import native, runner
output = Path(sys.argv[1])
actual = native.JournalAccount
def reserve(*args, **kwargs):
    if kwargs['working'] != 0:
        raise ValueError('CONTROL_WORKING_ARGUMENT_CHANGED')
    kwargs['working'] = 1_000_000
    return actual(*args, **kwargs)
native.JournalAccount = reserve
try:
    runner.run(output, scenario='central', arm='retained')
except ValueError as exc:
    if str(exc) != 'REGISTERED_WORKING_CAPITAL_CHANGED' or not all(
            (output/name).is_file() for name in
            ('REGISTRATION.json', 'MANIFEST.json', 'NATIVE_EXPORT.json', 'REPORT.json')):
        raise
'''
        env = {**os.environ, 'PYTHONPATH': str(self.source),
               'PYTHONDONTWRITEBYTECODE': '1'}
        produced = subprocess.run([sys.executable, '-c', producer, str(original)],
                                  cwd=self.source, env=env, text=True, capture_output=True)
        self.assertEqual(produced.returncode, 0, produced.stdout+produced.stderr)
        output = self.home/'working-reserve-public'
        public_copy(original, output)
        self.assertFalse((output/'private').exists())
        record = read(output/'NATIVE_EXPORT.json')
        registration = read(output/'REGISTRATION.json')
        self.assertEqual(record['ledger']['config']['working'], 1_000_000)
        self.assertEqual(record['ledger']['config']['opening'], 100_000_000_000)
        self.assertEqual(record['ledger']['config']['contract'],
                         'commitment001-'+registration['binding'][:20])
        before = protected_public(output)
        # A clean native checker must accept this legitimate alternative before
        # the campaign checker rejects its undeclared initialization policy.
        native_check = r'''
from pathlib import Path
import json, sys
from connected_enterprise.finance import audit_journal
output = Path(sys.argv[1])
read = lambda name: json.loads((output/name).read_text())
print(json.dumps(audit_journal(read('NATIVE_EXPORT.json'),
    root=output/'source', manifest=read('MANIFEST.json'))))
'''
        checked = subprocess.run([sys.executable, '-c', native_check, str(output)],
                                 cwd=self.source, env=env, text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertTrue(json.loads(checked.stdout)['accepted'])
        audit = command(self.source, 'audit', '--output', output)
        archive = self.home/'working-reserve-public.zip'
        package = command(self.source, 'package', '--output', output, '--archive', archive)
        self.assertEqual(protected_public(output), before)
        for operation, result in [('audit', audit), ('package', package)]:
            with self.subTest(operation=operation):
                self.assertNotEqual(result.returncode, 0,
                                    'Undeclared native working reserve was accepted')
                self.assertIn('REGISTERED_WORKING_CAPITAL_CHANGED', result.stderr)
                if operation == 'package':
                    self.assertFalse(archive.exists(), 'Undeclared reserve evidence was exported')


if __name__ == '__main__':
    unittest.main()
