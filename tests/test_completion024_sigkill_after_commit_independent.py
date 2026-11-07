"""Independent fatal process interruption after native CAS commit; ephemeral fixture only.

Frozen protocol: qualification/completion024-independent/OS_KILL_AFTER_NATIVE_COMMIT_PROTOCOL.md
Never publish an authority ticket, signing key or account recovery state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest

from connected_enterprise.finance import JournalAccount
from connected_enterprise.transition_evidence import evidence_directory
from connected_enterprise.upgrades import validate_ticket
from tests.test_completion024_cas_claim_boundary_independent import (
    IndependentCASClaimBoundaryTests, OPENING, WORKING, CONTRACT,
)

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NATIVE_COMMIT_BEFORE_SIGKILL"

# The simulated owner's actual ticket goes via stdin, never argv or logs.
# The real Account method is called first; no exception or alternate write path.
CHILD = r"""
import json, os, signal, sys
from adaptive_enterprise.account import Account
from connected_enterprise.finance import JournalAccount
from connected_enterprise.transition_evidence import evidence_directory
p = json.load(sys.stdin)
real_transition = Account.source_transition
def crash_after_real_native_commit(self, ticket):
    result = real_transition(self, ticket)
    sys.stdout.write("NATIVE_COMMIT_BEFORE_SIGKILL\n")
    sys.stdout.flush()
    os.kill(os.getpid(), signal.SIGKILL)
    return result
Account.source_transition = crash_after_real_native_commit
with evidence_directory(p['store']):
    with JournalAccount.upgrade_source(
        p['source'], p['manifest'], p['path'], opening=p['opening'],
        working=p['working'], contract=p['contract'],
        authorization=p['ticket']
    ):
        sys.exit(55)
sys.exit(56)
"""


@unittest.skipUnless(os.name == "posix", "Requires SIGKILL and local POSIX writer lock")
class IndependentCASAfterNativeSIGKILL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        IndependentCASClaimBoundaryTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        IndependentCASClaimBoundaryTests.tearDownClass()

    def setUp(self):
        self.case = IndependentCASClaimBoundaryTests(
            "test_missing_cas_scope_cannot_change_signed_history")
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def test_native_committed_os_kill_reopens_exactly_once_without_liability_loss(self):
        prior, ticket, inode, _ = self.case._prepare(claim=True)
        original_actions = prior["ledger"]["actions"]
        original_summary = prior["ledger"]["summary"]
        self.assertTrue(prior["ledger"]["prospective_claims"])
        self.assertGreater(original_summary["payables"], 0)
        with evidence_directory(self.case.store):
            validated = validate_ticket(
                ticket, key=self.case.keypath.read_bytes(),
                root=self.case.new, path=self.case.path
            )
        self.assertEqual(validated["schema"], "agi-alpha/native-source-transition/v2-cas")
        payload = {
            "source": str(self.case.new), "path": str(self.case.path),
            "store": str(self.case.store), "manifest": self.case.manifest,
            "opening": OPENING, "working": WORKING, "contract": CONTRACT,
            "ticket": ticket,
        }
        proc = subprocess.Popen(
            [sys.executable, "-B", "-c", CHILD], cwd=ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                 "PYTHONPATH": str(ROOT)},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            try:
                out, _private_stderr = proc.communicate(json.dumps(payload), timeout=150)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=15)
                self.fail("FATAL_WORKER_TIMEOUT")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=15)
        # Deliberately do NOT render stderr, which might contain private paths.
        self.assertEqual(proc.returncode, -signal.SIGKILL, "EXPECTED_REAL_OS_SIGKILL")
        self.assertEqual(out.strip(), MARKER, "REAL_NATIVE_COMMIT_NOT_REACHED")

        with evidence_directory(self.case.store):
            with JournalAccount.upgrade_source(
                self.case.new, self.case.manifest, self.case.path,
                opening=OPENING, working=WORKING, contract=CONTRACT,
                authorization=ticket,
            ) as recovered:
                first = recovered.export()
                self.assertTrue(recovered.audit()["accepted"])
                tape = first["ledger"]
                self.assertEqual(tape["actions"][:len(original_actions)], original_actions)
                self.assertEqual(len(tape["actions"]), len(original_actions) + 1)
                self.assertEqual(sum(a["op"] == "source_transition"
                                     for a in tape["actions"]), 1)
                self.assertEqual(tape["summary"], original_summary)
                self.assertEqual(tape["prospective_claims"],
                                 prior["ledger"]["prospective_claims"])
                self.assertEqual(tape["summary"]["payables"], original_summary["payables"])
                self.assertEqual(tape["summary"]["collections"], original_summary["collections"])
            with JournalAccount(
                self.case.new, self.case.manifest, self.case.path,
                opening=OPENING, working=WORKING, contract=CONTRACT,
            ) as ordinary_reopen:
                self.assertEqual(ordinary_reopen.export(), first)
                self.assertTrue(ordinary_reopen.audit()["accepted"])
            signed_journal = self.case.base / "account.sqlite.connected-journal.json"
            before_rejection = signed_journal.read_bytes()
            with self.assertRaises(ValueError):
                with JournalAccount(
                    self.case.old, self.case.manifest, self.case.path,
                    opening=OPENING, working=WORKING, contract=CONTRACT,
                ):
                    self.fail("UNAUTHORIZED_DOWNGRADE_OPENED")
            self.assertEqual(signed_journal.read_bytes(), before_rejection)
        self.assertEqual(self.case.keypath.stat().st_ino, inode)
        print(json.dumps({
            "schema": "agi-alpha/independent-cas-fatal-commit/v1",
            "cases": 1, "source_transition_actions": 1,
            "native_prefix_preserved": True, "claim_and_payables_preserved": True,
            "source_downgrade_rejected": True, "signing_inode_preserved": True,
            "ordinary_reopen_and_audit": "ACCEPTED",
            "scope": "SYNTHETIC_CLAIM_ACCOUNT_ONLY_NOT_OPERATING_STATE",
        }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
