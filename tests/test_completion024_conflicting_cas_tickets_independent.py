"""Frozen conflicting signed CAS tickets across two OS writers.

This is a candidate-only, ephemeral financial-integrity test. See the
previously committed CONFLICTING_TICKETS_PROTOCOL.md. No original account
or owner implementation is accessed or changed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from connected_enterprise.finance import JournalAccount
from connected_enterprise.operations import _copy_source, _copy_inputs
from connected_enterprise.transition_evidence import evidence_directory, ticket_body
from connected_enterprise.upgrades import authorize_upgrade
import tests.test_completion024_cas_claim_boundary_independent as fixture

ROOT = Path(__file__).resolve().parents[1]

# Synthetic signed tickets are delivered only via stdin, never command line,
# artifact, shell trace or worker stdout. All stdout is a fixed status word.
WORKER = r"""
import json,pathlib,sys,time
from connected_enterprise.finance import JournalAccount
from connected_enterprise.transition_evidence import evidence_directory
p=json.loads(sys.stdin.read())
stop=time.monotonic()+30
while not pathlib.Path(p['barrier']).is_file():
 if time.monotonic()>stop:
  print('BARRIER_TIMEOUT');sys.exit(41)
 time.sleep(0.01)
try:
 with evidence_directory(p['store']):
  with JournalAccount.upgrade_source(
      p['target'],p['manifest'],p['path'],opening=p['opening'],
      working=p['working'],contract=p['contract'],authorization=p['ticket']) as a:
   if not a.audit()['accepted']:
    print('AUDIT_REFUSED');sys.exit(42)
 print('ACCEPTED')
except ValueError:
 print('REFUSED');sys.exit(31)
except BaseException:
 print('UNEXPECTED');sys.exit(44)
"""


@unittest.skipUnless(os.name == "posix", "requires POSIX filesystem leases")
class ConflictingSignedCASWriters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.IndependentCASClaimBoundaryTests.setUpClass()
        cls.alt = fixture.IndependentCASClaimBoundaryTests.root / "alternate"
        _copy_source(ROOT, cls.alt)
        _copy_inputs(fixture.IndependentCASClaimBoundaryTests.old, cls.alt,
                     fixture.IndependentCASClaimBoundaryTests.manifest)
        target = cls.alt / "connected_enterprise" / "finance.py"
        target.write_bytes(target.read_bytes() +
                           b"\n# Alternative forward source identity fixture, no rule change.\n")

    @classmethod
    def tearDownClass(cls):
        fixture.IndependentCASClaimBoundaryTests.tearDownClass()

    def setUp(self):
        self.case = fixture.IndependentCASClaimBoundaryTests(
            "test_missing_cas_scope_cannot_change_signed_history")
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_two_valid_conflicting_forward_tickets_cannot_fork_one_account(self):
        old, first, original_key_inode, _ = self.case._prepare(claim=True)
        prior_actions = old["ledger"]["actions"]
        self.assertTrue(old["ledger"]["prospective_claims"])
        second = authorize_upgrade(
            historical_root=self.case.old, target_root=self.alt,
            manifest=self.case.manifest, path=self.case.path,
            opening=fixture.OPENING, working=fixture.WORKING,
            contract=fixture.CONTRACT,
            expected_state_digest=old["snapshot"]["state_digest"],
            ident="boundary-cas-conflicting-alternative", day=20,
            transition_format="v2-cas", evidence_root=self.case.store)

        with evidence_directory(self.case.store):
            a, b = ticket_body(first), ticket_body(second)
        self.assertEqual(a["from_source"], b["from_source"])
        self.assertEqual(a["expected_state_digest"], b["expected_state_digest"])
        self.assertNotEqual(a["to_source"]["sha256"], b["to_source"]["sha256"])
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(a["counter"], b["counter"])

        before_key_inode = self.case.keypath.stat().st_ino
        self.assertEqual(before_key_inode, original_key_inode)
        barrier = self.case.base / "RELEASE_TWO_DIFFERENT_TICKETS"
        journal = self.case.base / "account.sqlite.connected-journal.json"
        before_hash = hashlib.sha256(journal.read_bytes()).hexdigest()
        env = {**os.environ, "PYTHONPATH": str(ROOT),
               "PYTHONDONTWRITEBYTECODE": "1"}
        requests = ((self.case.new, first), (self.alt, second))
        workers = []
        outcomes = []
        try:
            for target, ticket in requests:
                payload = {
                    "barrier": str(barrier), "target": str(target),
                    "store": str(self.case.store), "path": str(self.case.path),
                    "manifest": self.case.manifest, "opening": fixture.OPENING,
                    "working": fixture.WORKING, "contract": fixture.CONTRACT,
                    "ticket": ticket,
                }
                worker = subprocess.Popen(
                    [sys.executable, "-B", "-c", WORKER], cwd=ROOT, env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True)
                workers.append(worker)
                worker.stdin.write(json.dumps(payload))
                worker.stdin.close()
            barrier.write_text("release\n")
            for worker in workers:
                try:
                    worker.wait(timeout=150)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=10)
                    self.fail("CONFLICTING_CAS_WRITER_HUNG")
                stdout = worker.stdout.read().strip()
                stderr = worker.stderr.read()
                self.assertFalse(stderr if worker.returncode in (0, 31) else False,
                                 "CONFIDENTIAL_WORKER_STDERR_NOT_EMPTY")
                self.assertIn((worker.returncode, stdout),
                              {(0, "ACCEPTED"), (31, "REFUSED")},
                              "UNEXPECTED_WORKER_RESULT")
                outcomes.append((worker.returncode, stdout))
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait(timeout=10)
                for stream in (worker.stdout, worker.stderr):
                    if stream is not None:
                        stream.close()

        self.assertEqual(sorted(outcomes),
                         [(0, "ACCEPTED"), (31, "REFUSED")])
        winner_index = next(i for i, result in enumerate(outcomes)
                            if result == (0, "ACCEPTED"))
        winner_source, _ = requests[winner_index]
        loser_source, loser_ticket = requests[1 - winner_index]

        with evidence_directory(self.case.store):
            with JournalAccount(winner_source, self.case.manifest,
                                self.case.path, opening=fixture.OPENING,
                                working=fixture.WORKING,
                                contract=fixture.CONTRACT) as opened:
                replay = opened.export()
                self.assertTrue(opened.audit()["accepted"])
                self.assertEqual(replay["ledger"]["actions"][:len(prior_actions)],
                                 prior_actions)
                self.assertEqual(
                    sum(row["op"] == "source_transition"
                        for row in replay["ledger"]["actions"]), 1)
                self.assertEqual(replay["ledger"]["prospective_claims"],
                                 old["ledger"]["prospective_claims"])
                self.assertEqual(replay["ledger"]["summary"]["payables"],
                                 old["ledger"]["summary"]["payables"])
            winning_journal = journal.read_bytes()
            with self.assertRaises(ValueError):
                with JournalAccount.upgrade_source(
                    loser_source, self.case.manifest, self.case.path,
                    opening=fixture.OPENING, working=fixture.WORKING,
                    contract=fixture.CONTRACT, authorization=loser_ticket):
                    self.fail("SIGNED_CONFLICTING_FORK_ACCEPTED")
            self.assertEqual(journal.read_bytes(), winning_journal)
            with self.assertRaises(ValueError):
                with JournalAccount(self.case.old, self.case.manifest,
                                    self.case.path, opening=fixture.OPENING,
                                    working=fixture.WORKING,
                                    contract=fixture.CONTRACT):
                    self.fail("ORIGINAL_SOURCE_DOWNGRADE_ACCEPTED")
            self.assertEqual(journal.read_bytes(), winning_journal)

        self.assertEqual(self.case.keypath.stat().st_ino, before_key_inode)
        self.assertNotEqual(before_hash, hashlib.sha256(journal.read_bytes()).hexdigest())
        print(json.dumps({
            "schema": "agi-alpha/independent-conflicting-cas-tickets/v1",
            "distinct_authentic_forward_source_versions": True,
            "one_winner_one_refusal": True,
            "native_transition_count": 1,
            "original_native_prefix_and_claim_preserved": True,
            "winning_account_audited": True,
            "losing_ticket_replay_refused": True,
            "old_source_downgrade_refused": True,
            "same_simulation_key_inode": True,
            "scope": "ONE_EPHEMERAL_SIMULATED_ACCOUNT_ONLY",
        }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
