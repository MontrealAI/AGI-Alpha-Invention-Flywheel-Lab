import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from adaptive_enterprise.account import Account, audit_account
from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICES, prepare_services
from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS
from connected_enterprise.upgrades import authorize_upgrade

ROOT = Path(__file__).resolve().parents[1]
BASE = '10bdb2c5787f95158642b068756ba30b58140562'
CONTRACT = 'connected014-ordinary-legacy-owned'


class NativeSourceUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='native-upgrade-sources-')
        cls.old = Path(cls.fixture.name) / 'pinned-old'
        cls.old.mkdir()
        from tests.connected_legacy_fixture import materialize
        materialize(ROOT,BASE,cls.old)
        cls.manifest = prepare_services(cls.old, 'services')
        (cls.old / 'MANIFEST.json').write_text(json.dumps(cls.manifest))
        cls.new = Path(cls.fixture.name) / 'new'
        cls.new.mkdir()
        for name in set(SOURCE_PATHS) | set(SERVICES):
            target = cls.new / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        shutil.copytree(cls.old / 'services', cls.new / 'services')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-upgrade-account-')
        self.path = Path(self.tmp.name) / 'same-account.sqlite'
        code = '''import json,sys
from connected_enterprise.finance import JournalAccount
root,path,contract=sys.argv[1:]; m=json.load(open(root+'/MANIFEST.json'))
with JournalAccount(root,m,path,opening=500000000,working=100000000,contract=contract) as a:
 job=next(j for j in m['jobs'] if j['service_id']=='reconciliation' and j['accepted'])
 a.execute('wallet',{'buyer':'legacy-buyer','amount':100000000},0)
 a.execute('offer',{'id':'legacy-order','buyer':'legacy-buyer','price':100000000,'job_id':job['id'],'deadline':10},0)
 for action in ['consent','fund','prepare','release']: a.execute('event',{'id':'legacy-order','action':action,'event_id':'legacy-'+action},2)
 a.cost('legacy-incurred-cost',5000000,2)
 print(json.dumps(a.export()))
'''
        done = subprocess.run([sys.executable, '-c', code, str(self.old), str(self.path), CONTRACT],
                              cwd=self.old, env={**os.environ, 'PYTHONPATH': str(self.old)},
                              text=True, capture_output=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.original = json.loads(done.stdout)
        self.a = None

    def tearDown(self):
        if self.a is not None:
            self.a.close()
        self.tmp.cleanup()

    def authorize(self, ident='upgrade-1'):
        return authorize_upgrade(historical_root=self.old, target_root=self.new,
                                 manifest=self.manifest, path=self.path, opening=500_000_000,
                                 working=100_000_000, contract=CONTRACT,
                                 expected_state_digest=self.original['snapshot']['state_digest'], ident=ident, day=3)

    def upgrade(self, ticket):
        return JournalAccount.upgrade_source(self.new, self.manifest, self.path,
                                            opening=500_000_000, working=100_000_000,
                                            contract=CONTRACT, authorization=ticket)

    def reopen(self):
        return JournalAccount(self.new, self.manifest, self.path, opening=500_000_000,
                              working=100_000_000, contract=CONTRACT)

    def test_pristine_old_verifier_transition_preserves_account_money_and_obligations(self):
        ticket = self.authorize()
        original_key_identity = self.path.with_name(self.path.name + '.adaptive-simulation-key').stat().st_ino
        self.a = self.upgrade(ticket)
        record = self.a.export()
        self.assertEqual(record['ledger']['summary'], self.original['ledger']['summary'])
        self.assertEqual(record['ledger']['actions'][:-1], self.original['ledger']['actions'])
        self.assertEqual(record['connected_journal']['source_history'][0]['body']['prior_envelope']['body'], self.original['connected_journal'])
        self.assertEqual(self.path.with_name(self.path.name + '.adaptive-simulation-key').stat().st_ino, original_key_identity)
        self.assertEqual(self.a.snapshot()['summary']['tailReserve'], 100_200_000)
        self.a.cost('post-upgrade-cost', 7, 4)
        self.assertTrue(audit_account(self.a.export(), root=self.new, manifest=self.manifest)['accepted'])
        before = self.a.export(); self.a.close(); self.a = self.reopen()
        self.assertEqual(self.a.export(), before)

    def test_unauthorized_upgrade_tamper_and_branch_fork_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_OR_AUTHORITY_CHANGED'):
            self.reopen()
        ticket = self.authorize()
        fork = self.authorize('fork-authorization')
        tampered = copy.deepcopy(ticket); tampered['body']['counter'] = 2
        with self.assertRaisesRegex(ValueError, 'SIGNATURE_MISMATCH'):
            self.upgrade(tampered)
        self.a = self.upgrade(ticket)
        with self.assertRaisesRegex(ValueError, 'ALREADY_OWNED'):
            self.upgrade(fork)
        self.a.close(); self.a = None
        with self.assertRaisesRegex(ValueError, 'RETRY_AUTHORIZATION_CHANGED'):
            self.upgrade(fork)
        self.a = self.reopen()

    def test_interruption_before_native_transition_recovers_signed_intent_once(self):
        ticket = self.authorize()
        with patch.object(Account, 'source_transition', side_effect=InterruptedError('before native transition')), self.assertRaises(InterruptedError):
            self.upgrade(ticket)
        self.a = self.reopen()
        self.assertEqual(sum(e['op'] == 'source_transition' for e in self.a.export()['ledger']['actions']), 1)
        self.assertEqual(self.a.snapshot()['summary'], self.original['ledger']['summary'])
        self.assertTrue(self.a.audit()['accepted'])

    def test_direct_native_upgrade_bypass_and_public_proof_tamper_fail(self):
        ticket = self.authorize(); self.a = self.upgrade(ticket)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_SOURCE_UPGRADE_ENTRYPOINT'):
            self.a.execute('source_transition', {}, 4)
        forged = copy.deepcopy(self.a.export())
        forged['source_transitions']['upgrade-1']['body']['prior_record']['ledger']['summary']['tailReserve'] = 0
        with self.assertRaises(ValueError):
            audit_account(forged, root=self.new, manifest=self.manifest)

    def test_portable_historical_verifier_resolves_without_changing_signed_ticket(self):
        ticket = self.authorize(); self.a = self.upgrade(ticket)
        destination = self.new / 'historical-source-versions' / ticket['body']['from_source']['sha256']
        destination.parent.mkdir(exist_ok=True)
        shutil.move(str(self.old), destination)
        try:
            self.assertTrue(self.a.audit()['accepted'])
            self.assertEqual(self.a.export()['source_transitions']['upgrade-1'], ticket)
        finally:
            shutil.move(str(destination), self.old)

    def test_interruption_after_native_commit_and_missing_authority_fail_closed(self):
        ticket = self.authorize()
        original = Account.source_transition
        def crash(account, authorization):
            original(account, authorization)
            raise InterruptedError('after source transition commit')
        with patch.object(Account, 'source_transition', crash), self.assertRaises(InterruptedError):
            self.upgrade(ticket)
        self.a = self.reopen()
        self.assertEqual(sum(e['op'] == 'source_transition' for e in self.a.export()['ledger']['actions']), 1)
        authority = self.a.journal_path.read_bytes()
        self.a.journal_path.unlink()
        try:
            with self.assertRaisesRegex(ValueError, 'SOURCE_AUTHORITY_MISSING'):
                self.a._account.cost('bypass-after-loss', 1, 4)
        finally:
            self.a.journal_path.write_bytes(authority)
        self.assertTrue(self.a.audit()['accepted'])

    def test_stale_signed_upgrade_cannot_replace_advanced_old_checkpoint(self):
        ticket = self.authorize()
        code = '''import json,sys
from connected_enterprise.finance import JournalAccount
r,p,c=sys.argv[1:];m=json.load(open(r+'/MANIFEST.json'))
with JournalAccount(r,m,p,opening=500000000,working=100000000,contract=c) as a: a.cost('after-ticket',1,3)
'''
        done = subprocess.run([sys.executable, '-c', code, str(self.old), str(self.path), CONTRACT],
                              cwd=self.old, env={**os.environ, 'PYTHONPATH': str(self.old)},
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        journal = self.path.with_name(self.path.name + '.connected-journal.json')
        before = journal.read_bytes()
        with self.assertRaisesRegex(ValueError, 'PRIOR_AUTHORITY_CHANGED'):
            self.upgrade(ticket)
        self.assertEqual(journal.read_bytes(), before)

    def test_pristine_old_code_cannot_downgrade_new_financial_history(self):
        ticket = self.authorize(); self.a = self.upgrade(ticket)
        self.a.cost('new-version-financial-event', 11, 4)
        self.a.close(); self.a = None
        tape_path = self.path.with_name(self.path.name + '.actions.jsonl')
        before = tape_path.read_bytes()
        code = '''import json,sys
from connected_enterprise.finance import JournalAccount
r,p,c=sys.argv[1:];m=json.load(open(r+'/MANIFEST.json'))
with JournalAccount(r,m,p,opening=500000000,working=100000000,contract=c): pass
'''
        done = subprocess.run([sys.executable, '-c', code, str(self.old), str(self.path), CONTRACT],
                              cwd=self.old, env={**os.environ, 'PYTHONPATH': str(self.old)},
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(tape_path.read_bytes(), before)
        self.a = self.reopen()
        self.assertTrue(self.a.audit()['accepted'])

    def test_two_writers_racing_transition_commit_exactly_once(self):
        ticket = self.authorize()
        barrier = threading.Barrier(2); release = threading.Event(); finished = threading.Event()
        attempts = []
        def writer():
            barrier.wait(timeout=10)
            account = None
            try:
                account = self.upgrade(ticket)
                attempts.append('COMMITTED')
            except ValueError as error:
                attempts.append(str(error))
            finally:
                if len(attempts) == 2:
                    finished.set()
                if account is not None:
                    release.wait(timeout=20)
                    account.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(writer) for _ in range(2)]
            try:
                self.assertTrue(finished.wait(timeout=20))
                self.assertEqual(attempts.count('COMMITTED'), 1)
                self.assertTrue(any('ALREADY_OWNED' in x for x in attempts))
            finally:
                release.set()
            for future in futures:
                future.result(timeout=10)
        self.a = self.reopen()
        self.assertEqual(sum(e['op'] == 'source_transition' for e in self.a.export()['ledger']['actions']), 1)
        self.assertEqual(self.a.snapshot()['summary'], self.original['ledger']['summary'])
