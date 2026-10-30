"""Local writer exclusion and native earned-fund regression; no market claims."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from commercial.persistence import memory_engine
from commercial.single_writer import OwnedTape as DurableTape
from commercial.tape_lease import WriterLease
from vendor.alpha_claim.contracts import canonical, digest
from vendor.alpha_claim.protected_exchange import ProtectedExchange

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {'scope': 'SIMULATED', 'test': 'writer-exclusion'}


def earned_fixture():
    def validate(task):
        if task != {'numbers': [2, 3]}:
            raise ValueError('FIXTURE_CHANGED')
    def check(task, artifact):
        return {'accepted': artifact == {'sum': sum(task['numbers'])}, 'decisive': True}
    ex = memory_engine(ProtectedExchange, key=b'T' * 32, contract='writer-financial-regression',
                       validate=validate, check=check, opening=1_000_000_000, working=10_000_000)
    ex.cost('production', 10_000_000)
    ex.wallet('buyer', 100_000_000)
    ex.offer('order', 'buyer', 100_000_000, 'nonrecourse-simulated', {'numbers': [2, 3]}, 20)
    terms = {k: ex.order('order')[k] for k in ['id', 'buyer', 'price', 'rail', 'task_hash', 'contract', 'deadline']}
    ex.event('order', 'consent', 'consent', {'buyer': 'buyer', 'termsHash': digest(terms)}, 0)
    ex.event('order', 'fund', 'fund', ex.provider.issue(ex.order('order'), 'funded'), 1)
    ex.event('order', 'prepare', 'prepare', {'sum': 5}, 2)
    ex.event('order', 'release', 'release', ex.provider.issue(ex.order('order'), 'cleared'), 3)
    return ex


@unittest.skipUnless(os.name == 'posix', 'Requires the declared local POSIX runtime')
class WriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'exchange.sqlite'
        self.owners = []

    def tearDown(self):
        for owner in reversed(self.owners):
            owner.close()
        self.tmp.cleanup()

    def open(self, path=None, config=None):
        owner = DurableTape(path or self.path, CONFIG if config is None else config, canonical, json.loads)
        self.owners.append(owner)
        return owner

    def test_same_process_second_owner_refused_before_mutation(self):
        first = self.open()
        before = first.tape.read_bytes()
        with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'):
            self.open()
        self.assertEqual(first.tape.read_bytes(), before)

    def test_separate_process_second_owner_refused(self):
        first = self.open()
        code = """import json,sys
from pathlib import Path
from commercial.single_writer import OwnedTape as DurableTape
from vendor.alpha_claim.contracts import canonical
try:
    t=DurableTape(Path(sys.argv[1]),json.loads(sys.argv[2]),canonical,json.loads)
except ValueError as e:
    print(str(e)); sys.exit(0 if str(e)=='TAPE_ALREADY_OWNED' else 3)
else:
    t.close(); sys.exit(2)
"""
        r = subprocess.run([sys.executable, '-c', code, str(self.path), json.dumps(CONFIG)],
                           cwd=ROOT, capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('TAPE_ALREADY_OWNED', r.stdout)
        first.lease.assert_owner()

    def test_clean_close_reacquires_and_replays_exact_history(self):
        first = self.open(); first.append({'seq': 0, 'test': 'history'})
        raw = first.tape.read_bytes(); first.close()
        second = self.open()
        self.assertEqual(second.recovery_actions, [{'seq': 0, 'test': 'history'}])
        self.assertEqual(second.tape.read_bytes(), raw)
        second.append({'seq': 1})
        self.assertEqual(len(second.tape.read_bytes().splitlines()), 3)

    def test_crash_releases_lease_and_preserves_fsynced_action(self):
        code = """import json,sys,time
from pathlib import Path
from commercial.single_writer import OwnedTape as DurableTape
from vendor.alpha_claim.contracts import canonical
x=DurableTape(Path(sys.argv[1]),json.loads(sys.argv[2]),canonical,json.loads)
x.append({'seq':0,'survives':'crash'})
print('OWNED',flush=True)
time.sleep(30)
"""
        p = subprocess.Popen([sys.executable, '-c', code, str(self.path), json.dumps(CONFIG)],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import select
            self.assertTrue(select.select([p.stdout], [], [], 8)[0])
            self.assertEqual(p.stdout.readline().strip(), 'OWNED')
            with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'): self.open()
            p.kill(); p.wait(timeout=5)
            self.assertEqual(self.open().recovery_actions, [{'seq': 0, 'survives': 'crash'}])
        finally:
            if p.poll() is None: p.kill(); p.wait(timeout=5)
            p.stdout.close(); p.stderr.close()

    def test_bad_config_releases_failed_constructor(self):
        self.open().close()
        with self.assertRaisesRegex(ValueError, 'CONFIGURATION_MISMATCH'): self.open(config={'wrong': True})
        self.open().lease.assert_owner()

    def test_torn_tape_preserved_and_failed_constructor_releases(self):
        first = self.open(); first.close(); saved = first.tape.read_bytes()
        first.tape.write_bytes(saved + b'{')
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_OR_OVERSIZED'): self.open()
        self.assertEqual(first.tape.read_bytes(), saved + b'{')
        # Restore only this temporary test fixture, never historical campaign evidence.
        first.tape.write_bytes(saved)
        self.open().lease.assert_owner()

    def test_symlink_lock_refused(self):
        target = Path(self.tmp.name)/'target'; target.write_text('retain')
        self.path.with_name(self.path.name+'.writer.lock').symlink_to(target)
        with self.assertRaises(OSError): self.open()
        self.assertEqual(target.read_text(), 'retain')

    def test_directory_lock_refused(self):
        self.path.with_name(self.path.name+'.writer.lock').mkdir()
        with self.assertRaises(OSError): self.open()

    def test_fifo_lock_refused_without_blocking(self):
        os.mkfifo(self.path.with_name(self.path.name+'.writer.lock'))
        with self.assertRaisesRegex(ValueError, 'SINGLE_REGULAR_LEASE'): self.open()

    def test_hardlinked_lock_refused(self):
        target = Path(self.tmp.name)/'target'; target.write_text('retain')
        os.link(target, self.path.with_name(self.path.name+'.writer.lock'))
        with self.assertRaisesRegex(ValueError, 'SINGLE_REGULAR_LEASE'): self.open()

    def test_replaced_lock_inode_stops_append(self):
        owner = self.open(); before = owner.tape.read_bytes()
        owner.lease.path.unlink(); owner.lease.path.touch()
        with self.assertRaisesRegex(ValueError, 'LEASE_IDENTITY_CHANGED'): owner.append({'seq': 0})
        self.assertEqual(owner.tape.read_bytes(), before)

    def test_closed_owner_cannot_append_or_checkpoint(self):
        owner = self.open(); owner.close()
        with self.assertRaisesRegex(ValueError, 'NOT_OWNED'): owner.append({'seq': 0})
        with self.assertRaisesRegex(ValueError, 'NOT_OWNED'): owner.checkpoint(None, [])

    def test_forked_child_cannot_use_parent_lease(self):
        owner = self.open()
        pid = os.fork()
        if pid == 0:
            try:
                owner.append({'seq': 0, 'unauthorized_child': True})
            except ValueError:
                owner.close(); os._exit(0)
            os._exit(2)
        _, status = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        # Child close must not unlock the parent's shared open-file description.
        with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'): self.open()
        owner.append({'seq': 0, 'parent': True})

    def test_lock_inode_persists_between_owners(self):
        one = self.open(); inode = one.lease.path.stat().st_ino; one.close()
        two = self.open()
        self.assertEqual(two.lease.path.stat().st_ino, inode)

    def test_separate_accounts_can_have_separate_owners(self):
        a = self.open(); b = self.open(Path(self.tmp.name)/'other.sqlite')
        a.append({'seq': 0}); b.append({'seq': 0})
        self.assertNotEqual(a.lease.path, b.lease.path)

    def test_checkpoint_preserves_native_integrity(self):
        owner = self.open(); ex = earned_fixture()
        try:
            owner.checkpoint(ex.db, [])
            c = sqlite3.connect(':memory:')
            try:
                c.deserialize(owner.path.read_bytes())
                self.assertEqual(c.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
            finally: c.close()
            self.assertFalse(json.loads(owner.proof.read_bytes())['native_financial_algorithm_changed'])
        finally: ex.close()

    def test_native_earnings_cannot_be_reserved_twice_after_takeover(self):
        first = self.open(); ex = earned_fixture()
        try:
            self.assertEqual(ex.snapshot()['unrestrictedEarned'], 90_000_000)
            witness = ex.reserve_investment('first', 60_000_000, 10_000_000, intent_hash=digest({'first': True}))
            first.append({'seq': 0, 'id': 'first', 'cap': 60_000_000, 'value': 10_000_000,
                          'intent': digest({'first': True}), 'witness': witness})
            with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'): self.open()
        finally: ex.close(); first.close()
        second = self.open(); recovered = earned_fixture()
        try:
            for action in second.recovery_actions:
                restored = recovered.reserve_investment(action['id'], action['cap'], action['value'], intent_hash=action['intent'])
                self.assertEqual(restored, action['witness'])
            self.assertEqual(recovered.snapshot()['unrestrictedEarned'], 30_000_000)
            with self.assertRaisesRegex(ValueError, 'earned funds'):
                recovered.reserve_investment('second', 60_000_000, 10_000_000)
        finally: recovered.close()

    def test_close_is_idempotent(self):
        owner = self.open(); owner.close(); owner.close()
        self.open().lease.assert_owner()


if __name__ == '__main__': unittest.main()
