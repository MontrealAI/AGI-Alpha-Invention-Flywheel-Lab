"""Frozen independent competing OS-writer CAS transition: ephemeral simulated account only.

Protocol: qualification/completion024-independent/RACING_WRITER_PROTOCOL.md.
No account, signer or canonical financial source is modified by this test.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from connected_enterprise.finance import JournalAccount
from connected_enterprise.transition_evidence import evidence_directory
import tests.test_completion024_cas_claim_boundary_independent as fixture

ROOT = Path(__file__).resolve().parents[1]

# The signed simulated authorization travels ONLY through subprocess stdin,
# never an argument, artifact or ordinary test diagnostic. The workers disclose
# a tiny fixed status vocabulary and no private bytes.
WORKER = r"""
import json, pathlib, sys, time
from connected_enterprise.finance import JournalAccount
from connected_enterprise.transition_evidence import evidence_directory
p = json.loads(sys.stdin.read())
barrier = pathlib.Path(p['barrier'])
stop = time.monotonic() + 30
while not barrier.is_file():
    if time.monotonic() >= stop:
        print('BARRIER_TIMEOUT'); sys.exit(41)
    time.sleep(0.01)
try:
    with evidence_directory(p['store']):
        with JournalAccount.upgrade_source(
            p['new'], p['manifest'], p['path'], opening=p['opening'],
            working=p['working'], contract=p['contract'],
            authorization=p['ticket']) as account:
            if not account.audit()['accepted']:
                print('AUDIT_REFUSED'); sys.exit(42)
    print('OWNER_ACCEPTED')
except ValueError as exc:
    if str(exc) == 'TAPE_ALREADY_OWNED':
        print('CONTENDED')
        sys.exit(31)
    print('OTHER_VALUE_REFUSAL')
    sys.exit(43)
except Exception:
    print('UNEXPECTED_WORKER_FAILURE')
    sys.exit(44)
"""


@unittest.skipUnless(os.name == 'posix', 'requires explicit POSIX account lease')
class IndependentCrossProcessCASRace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.IndependentCASClaimBoundaryTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixture.IndependentCASClaimBoundaryTests.tearDownClass()

    def setUp(self):
        self.case = fixture.IndependentCASClaimBoundaryTests(
            'test_missing_cas_scope_cannot_change_signed_history')
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_two_simultaneous_os_processes_cannot_fork_claim_or_source(self):
        before, ticket, key_inode, _ = self.case._prepare(claim=True)
        ledger_before = before['ledger']['actions']
        self.assertTrue(before['ledger']['prospective_claims'])
        journal = self.case.base / 'account.sqlite.connected-journal.json'
        before_journal_hash = hashlib.sha256(journal.read_bytes()).hexdigest()
        start = self.case.base / 'BEGIN_TWO_WRITERS'
        payload = {
            'new': str(self.case.new), 'path': str(self.case.path),
            'store': str(self.case.store), 'barrier': str(start),
            'manifest': self.case.manifest, 'opening': fixture.OPENING,
            'working': fixture.WORKING, 'contract': fixture.CONTRACT,
            'ticket': ticket,
        }
        wire = json.dumps(payload)
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPATH': str(ROOT)}
        workers = []
        results = []
        try:
            for _ in range(2):
                proc = subprocess.Popen(
                    [sys.executable, '-B', '-c', WORKER], cwd=ROOT,
                    env=env, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                workers.append(proc)
                # Write the private synthetic authority to stdin, not argv.
                proc.stdin.write(wire)
                proc.stdin.close()
            start.write_text('release simultaneously\n')
            for proc in workers:
                try:
                    proc.wait(timeout=150)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
                    self.fail('OS_WRITER_HUNG')
                stdout = proc.stdout.read().strip()
                stderr = proc.stderr.read()
                # Do not print stderr: it may contain private temporary paths.
                self.assertFalse(stderr if proc.returncode in (0, 31) else False,
                                 'WORKER_STDERR_NOT_EMPTY')
                results.append((proc.returncode, stdout))
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=10)
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
        self.assertTrue(any(code == 0 for code, _ in results), results)
        self.assertTrue(all((code, status) in
                            {(0, 'OWNER_ACCEPTED'), (31, 'CONTENDED')}
                            for code, status in results), results)

        with evidence_directory(self.case.store):
            with JournalAccount(self.case.new, self.case.manifest, self.case.path,
                                opening=fixture.OPENING, working=fixture.WORKING,
                                contract=fixture.CONTRACT) as account:
                exported = account.export()
                actions = exported['ledger']['actions']
                self.assertEqual(actions[:len(ledger_before)], ledger_before)
                self.assertEqual(sum(row['op'] == 'source_transition' for row in actions), 1)
                self.assertEqual(exported['ledger']['prospective_claims'],
                                 before['ledger']['prospective_claims'])
                self.assertEqual(exported['ledger']['summary']['payables'],
                                 before['ledger']['summary']['payables'])
                self.assertTrue(account.audit()['accepted'])
            # The old version must not regain custody of the same account.
            old_bytes = journal.read_bytes()
            with self.assertRaises(ValueError):
                with JournalAccount(self.case.old, self.case.manifest, self.case.path,
                                    opening=fixture.OPENING, working=fixture.WORKING,
                                    contract=fixture.CONTRACT):
                    self.fail('OLD_SOURCE_TAKEOVER_NOT_REJECTED')
            self.assertEqual(journal.read_bytes(), old_bytes)
        self.assertEqual(self.case.keypath.stat().st_ino, key_inode)
        self.assertNotEqual(hashlib.sha256(journal.read_bytes()).hexdigest(),
                            before_journal_hash)
        print(json.dumps({'schema': 'agi-alpha/independent-cas-race/v1',
                          'exactly_one_source_transition': True,
                          'old_native_prefix_preserved': True,
                          'original_claim_preserved': True,
                          'old_source_downgrade_rejected': True,
                          'key_inode_preserved': True,
                          'writer_results': sorted(s for _, s in results),
                          'scope': 'EPHEMERAL_SIMULATION_NOT_ORIGINAL_ACCOUNT'},
                         sort_keys=True))


if __name__ == '__main__':
    unittest.main()
