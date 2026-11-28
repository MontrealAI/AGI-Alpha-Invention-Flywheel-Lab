"""Canonical CLI audit-to-use regression; test-owned fixture, never owner custody.

Both adversarial tests assert the safety invariant, not the historical failure.
An unchanged release is expected to fail until the integration owner repairs it.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import resource
import time

ROOT = Path(__file__).resolve().parents[1]
DELTA = 123456789
# Executed only in a disposable public-copy test. No source changes, no signer,
# no mocked audit/scale/ledger. Interpose immediately after audit receipt write.
HOOK = r'''
from pathlib import Path
import json
from connected_enterprise import runner
original_write = runner.write
def after_receipt(path, value):
    original_write(path, value)
    p = Path(path)
    if p.name != 'PACKAGE_AUDIT.json' or not value.get('accepted'):
        return
    for q in sorted((p.parent / 'worlds').glob('*/RESULT.json')):
        row = json.loads(q.read_text())
        if row['arm'] == 'growth':
            row['owned_account']['ledger']['summary']['profit'] += 123456789
            q.write_text(json.dumps(row))
            print('TEST_PUBLIC_COPY_MUTATION_AFTER_ACCEPTED_AUDIT', file=__import__('sys').stderr)
            return
    raise AssertionError('TEST_GROWTH_ARM_REQUIRED')
runner.write = after_receipt
'''
# Comparison uses the actual frozen-source child. Inject the hook into that
# child, leaving dispatch, source verification, native audit and compare intact.
DRIVER = r'''
import subprocess, sys
from connected_enterprise import runner
hook = sys.argv[1]
command = sys.argv[2]
args = sys.argv[3:]
if command == 'comparison':
    original_call = subprocess.call
    def child(argv, *a, **kw):
        assert argv[1] == '-c' and 'runner import comparison' in argv[2]
        return original_call([*argv[:2], hook + '\n' + argv[2], *argv[3:]], *a, **kw)
    runner.subprocess.call = child
else:
    exec(hook, {})
sys.argv = ['connected_enterprise', command, *args]
raise SystemExit(runner.main())
'''


class AuditSnapshot302(unittest.TestCase):
    @classmethod
    def invoke(cls, cwd, *args, injected=False):
        command = ([sys.executable, '-c', DRIVER, HOOK, *args] if injected
                   else [sys.executable, '-m', 'connected_enterprise', *args])
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        code = None
        try:
            p = subprocess.run(command, cwd=cwd,
                               env={**os.environ, 'PYTHONPATH': str(cwd), 'PYTHONDONTWRITEBYTECODE': '1'},
                               capture_output=True, text=True)
            code = p.returncode
            return p
        finally:
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            print(json.dumps({'command': args[0], 'injected': injected, 'exit': code,
                              'wall_seconds': time.monotonic()-start,
                              'waited_child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime}),
                  file=sys.stderr, flush=True)

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='snapshot302-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        private = cls.root / 'fixture'
        archive = cls.root / 'fixture.zip'
        for args in [('run', '--smoke', '--output', str(private)),
                     ('package', '--output', str(private), '--archive', str(archive))]:
            p = cls.invoke(ROOT, *args)
            if p.returncode:
                raise AssertionError('FIXTURE_COMMAND_FAILED: ' + args[0] + '; exit ' + str(p.returncode))
        cls.public = cls.root / 'public'
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None or any(n.endswith('.adaptive-simulation-key') or '.sqlite' in n for n in z.namelist()):
                raise AssertionError('TEST_REQUIRES_KEY_FREE_FIXTURE')
            z.extractall(cls.public)
        # No further operations on the private test fixture. Test exclusively
        # against copies of the existing canonical key-free package.
        p = cls.invoke(cls.public / 'source', 'audit', '--output', str(cls.public))
        if p.returncode or not json.loads(p.stdout)['accepted']:
            raise AssertionError('PUBLIC_FIXTURE_AUDIT_FAILED')
        p = cls.invoke(cls.public / 'source', 'comparison', '--output', str(cls.public))
        if p.returncode:
            raise AssertionError('PUBLIC_FIXTURE_COMPARISON_FAILED')
        cls.baseline = json.loads(p.stdout)
        if not cls.baseline['audit']['accepted'] or not cls.baseline['pairs']:
            raise AssertionError('AUDITED_MATCHED_FIXTURE_REQUIRED')

    def copy(self, name):
        dest = self.root / name
        shutil.copytree(self.public, dest)
        return dest

    def reject_mutated_source(self, dest):
        p = self.invoke(dest / 'source', 'audit', '--output', str(dest))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('WORLD_RESULT_INDEX_BINDING_CHANGED', p.stderr)

    def test_comparison_must_not_consume_unaudited_profit(self):
        dest = self.copy('comparison')
        p = self.invoke(dest / 'source', 'comparison', '--output', str(dest), injected=True)
        self.assertIn('TEST_PUBLIC_COPY_MUTATION_AFTER_ACCEPTED_AUDIT', p.stderr)
        self.reject_mutated_source(dest)
        # Reject or use the already verified snapshot; never accept a mixed one.
        if p.returncode == 0:
            got = json.loads(p.stdout)
            self.assertTrue(got['audit']['accepted'])
            self.assertEqual(got['pairs'], self.baseline['pairs'], 'Comparison consumed unaudited result data')

    def test_package_must_not_publish_unauditable_snapshot(self):
        dest = self.copy('package')
        archive = self.root / 'adversarial.zip'
        p = self.invoke(dest / 'source', 'package', '--output', str(dest), '--archive', str(archive), injected=True)
        self.assertIn('TEST_PUBLIC_COPY_MUTATION_AFTER_ACCEPTED_AUDIT', p.stderr)
        self.reject_mutated_source(dest)
        if p.returncode:
            self.assertFalse(archive.exists(), 'Rejected package left a public archive')
        else:
            extracted = self.root / 'adversarial-extracted'
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                z.extractall(extracted)
            check = self.invoke(extracted / 'source', 'audit', '--output', str(extracted))
            self.assertEqual(check.returncode, 0, 'Package returned success for an unauditable snapshot')
            self.assertTrue(json.loads(check.stdout)['accepted'])


if __name__ == '__main__':
    unittest.main()
