"""Native account/capacity boundaries on disposable, source-matched accounts.

Financial fixtures here test mechanics only. They do not replace the registered
commercial scenarios or establish actual supplier, buyer or payment behavior.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from commercial.ledger import canonical, digest
from connected_enterprise.finance import SOURCE_PATHS, audit_journal
from . import service
from .delivery import default_requests, produce
from .native import BusinessAccount, OPENING, capacity_rows

ROOT = Path(__file__).resolve().parents[2]
USD = 1_000_000
SUPPLIERS = {'shared-worker': {'units': 1, 'consent': 'AUTHORED_SIMULATED_ACCEPTANCE',
                              'common_dependency': 'fixture-local-host'}}


class NativeCommitmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='commitment001-native-')
        self.home = Path(self.temporary.name)
        self.source = self.home / 'source'
        for name in sorted(set(SOURCE_PATHS) | set(service.source_paths(ROOT))):
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.requests = default_requests()
        self.manifest = service.prepare_manifest(self.source, [
            {'id': request['id'], 'request': request,
             'delivery_path': service.DELIVERIES + request['id'] + '.json'}
            for request in self.requests])
        self.path = self.home / 'account.sqlite'
        self.manifest_file = self.home / 'manifest.json'
        self.manifest_file.write_bytes(canonical(self.manifest))
        self.business = self.open()

    def tearDown(self):
        self.business.close()
        self.temporary.cleanup()

    def open(self):
        return BusinessAccount(self.source, self.manifest, self.path,
                               contract='commitment001-boundary-fixture', suppliers=SUPPLIERS)

    def work(self, order='first', *, start=2, end=4, amount=10*USD, job='restore-first'):
        return {'capacity': {'supplier': 'shared-worker', 'start': start, 'end': end, 'units': 1},
                'costs': {'fixture-production': amount}, 'expected_net': USD,
                'job': job, 'order': order, 'buyer': 'buyer-' + order}

    def reserve(self, order='first', *, hour=1, allow_seed=True, **work_options):
        work = self.work(order, **work_options)
        return self.business.reserve_delivery('capacity-' + order,
                sum(work['costs'].values()), hour, work, allow_seed=allow_seed)

    def earn(self):
        self.assertIsNotNone(self.reserve())
        self.business.begin('restore-first', 'first', 'buyer-first', 1000*USD, 1200*USD,
                            1, 10, 12)
        self.assertTrue(self.business.deliver('restore-first', 'first', produce(self.requests[0]), 2)['accepted'])
        self.business.event('first', 'release', 10)
        self.business.account.advance_financial(13)
        self.assertGreater(self.business.account.snapshot()['summary']['unrestrictedEarned'], 0)

    def test_overlapping_capacity_cannot_spend_or_promise_twice(self):
        first = self.reserve()
        self.assertEqual(first['funding'], 'SEED')
        before = self.business.account.export()
        self.assertIsNone(self.reserve('second', start=3, end=5))
        self.assertEqual(self.business.account.export(), before)
        with self.assertRaisesRegex(ValueError, 'FUNDED_CAPACITY'):
            self.business.begin('restore-first', 'second', 'buyer-second', 1000*USD, 1200*USD, 1, 10, 12)
        self.assertEqual(self.business.account.export(), before)

    def test_half_open_adjacent_slots_are_available(self):
        self.reserve()
        self.assertIsNotNone(self.reserve('adjacent', start=4, end=6))
        self.assertEqual(len(capacity_rows(self.business.account.export())), 2)

    def test_same_id_retry_is_exactly_once_and_changed_payload_rejected(self):
        receipt = self.reserve()
        before = self.business.account.export()
        self.assertEqual(self.reserve(), receipt)
        self.assertEqual(self.business.account.export(), before)
        with self.assertRaisesRegex(ValueError, 'IDEMPOTENT_CAPACITY_CHANGED'):
            self.reserve(start=3, end=5)
        with self.assertRaisesRegex(ValueError, 'PAYLOAD_CHANGED'):
            self.reserve(amount=11*USD)
        self.assertEqual(self.business.account.export(), before)
        self.business.close()
        self.business = self.open()
        self.assertEqual(self.reserve(), receipt)
        self.assertEqual(self.business.account.export(), before)

    def test_cross_thread_handle_misuse_is_refused_without_mutation(self):
        before = self.business.account.export()
        def attempt(index):
            try:
                self.reserve('concurrent-' + str(index))
            except sqlite3.ProgrammingError:
                return 'SQLITE_THREAD_OWNERSHIP_REJECTED'
            return 'UNEXPECTED_THREAD_OPERATION'
        with ThreadPoolExecutor(max_workers=6) as pool:
            receipts = list(pool.map(attempt, range(12)))
        self.assertEqual(receipts, ['SQLITE_THREAD_OWNERSHIP_REJECTED'] * 12)
        self.assertEqual(self.business.account.export(), before)

    def test_cash_is_not_earned_and_unaffordable_action_has_no_effect(self):
        summary = self.business.account.snapshot()['summary']
        self.assertEqual(summary['cash'], OPENING)
        self.assertEqual(summary['unrestrictedEarned'], 0)
        before = self.business.account.export()
        self.assertIsNone(self.reserve(allow_seed=False))
        self.assertIsNone(self.reserve(amount=OPENING + USD))
        self.assertEqual(self.business.account.export(), before)

    def test_collected_matured_earnings_fund_distinct_successor(self):
        self.earn()
        receipt = self.reserve('successor', hour=13, start=14, end=16,
                               amount=100*USD, job='migration-next', allow_seed=False)
        self.assertEqual(receipt['funding'], 'EARNED')
        self.business.begin('migration-next', 'successor', 'buyer-successor', 700*USD, 900*USD,
                            13, 20, 22)
        self.assertTrue(self.business.deliver('migration-next', 'successor', produce(self.requests[1]), 14)['accepted'])
        self.business.event('successor', 'release', 20)
        self.business.account.advance_financial(23)
        exported = self.business.account.export()
        self.assertEqual(exported['ledger']['summary']['collections'], 1700*USD)
        self.assertEqual(exported['ledger']['summary']['reservedInvestment'], 0)
        self.assertTrue(audit_journal(exported, root=self.source, manifest=self.manifest)['accepted'])

    def test_checker_source_drift_is_rejected_without_new_debit(self):
        before = self.business.account.export()
        source = self.source / service.PREFIX / 'acceptance.py'
        original = source.read_bytes()
        try:
            source.write_bytes(original + b'\n')
            with self.assertRaises(ValueError):
                self.reserve()
        finally:
            source.write_bytes(original)
        self.assertEqual(self.business.account.export(), before)

    def test_prepared_output_tampering_invalidates_native_replay(self):
        self.earn()
        exported = self.business.account.export()
        output = self.source / self.manifest['jobs'][0]['delivery_path']
        original = output.read_bytes()
        artifact = json.loads(original)
        artifact['output_sha256'] = '0' * 64
        try:
            output.write_bytes(canonical(artifact))
            with self.assertRaisesRegex(ValueError, 'ACTUAL_DELIVERY_HASH_CHANGED'):
                audit_journal(exported, root=self.source, manifest=self.manifest)
        finally:
            output.write_bytes(original)
        self.assertTrue(audit_journal(exported, root=self.source, manifest=self.manifest)['accepted'])

    def test_other_process_cannot_open_owned_account(self):
        code = '''
import json,sys
from pathlib import Path
from campaign.genesis_commitment001.native import BusinessAccount
source,path,manifest = map(Path,sys.argv[1:])
try:
    b=BusinessAccount(source,json.loads(manifest.read_text()),path,
      contract='commitment001-boundary-fixture',suppliers={'shared-worker':{'units':1,'consent':'AUTHORED_SIMULATED_ACCEPTANCE','common_dependency':'fixture-local-host'}})
except ValueError as error:
    if 'TAPE_ALREADY_OWNED' not in str(error): raise
    print('LEASE_REJECTED')
else:
    b.close()
    raise SystemExit('UNEXPECTED_SECOND_OWNER')
'''
        before = self.business.account.export()
        completed = subprocess.run([sys.executable, '-c', code, str(self.source), str(self.path), str(self.manifest_file)],
                                   cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), 'LEASE_REJECTED')
        self.assertEqual(self.business.account.export(), before)

    @unittest.skipUnless(hasattr(signal, 'SIGKILL'), 'POSIX process crash')
    def test_sigkill_after_seed_debit_recovers_one_capacity_commitment(self):
        self._crash_and_recover('cost', earned=False)

    @unittest.skipUnless(hasattr(signal, 'SIGKILL'), 'POSIX process crash')
    def test_sigkill_after_earned_reservation_recovers_one_capacity_commitment(self):
        self._crash_and_recover('reserve', earned=True)

    @unittest.skipUnless(hasattr(signal, 'SIGKILL'), 'POSIX process crash')
    def test_sigkill_after_earned_finish_recovers_one_capacity_commitment(self):
        self._crash_and_recover('finish', earned=True)

    def _crash_and_recover(self, stage, *, earned):
        if earned:
            self.earn()
        hour, start, end = (13, 14, 16) if earned else (1, 2, 4)
        work = self.work('crashed', start=start, end=end, amount=100*USD if earned else 10*USD)
        before = self.business.account.export()
        key_path = self.path.with_name(self.path.name + '.adaptive-simulation-key')
        authority_hash = hashlib.sha256(key_path.read_bytes()).hexdigest()
        payload = self.home / 'crash-payload.json'
        payload.write_bytes(canonical({'work': work, 'hour': hour, 'earned': earned, 'stage': stage}))
        self.business.close()
        code = '''
import json,os,signal,sys
from pathlib import Path
from campaign.genesis_commitment001.native import BusinessAccount
source,path,manifest,payload = map(Path,sys.argv[1:])
p=json.loads(payload.read_text())
with BusinessAccount(source,json.loads(manifest.read_text()),path,
  contract='commitment001-boundary-fixture',suppliers={'shared-worker':{'units':1,'consent':'AUTHORED_SIMULATED_ACCEPTANCE','common_dependency':'fixture-local-host'}}) as b:
    original=getattr(b.account._account,p['stage'])
    def crash(*args,**kwargs):
        result=original(*args,**kwargs)
        marker=payload.with_suffix('.reached')
        marker.write_text(p['stage'])
        os.kill(os.getpid(),signal.SIGKILL)
        return result
    setattr(b.account._account,p['stage'],crash)
    b.reserve_delivery('capacity-crashed',sum(p['work']['costs'].values()),p['hour'],p['work'],allow_seed=not p['earned'])
raise SystemExit('CRASH_BOUNDARY_NOT_REACHED')
'''
        completed = subprocess.run([sys.executable, '-c', code, str(self.source), str(self.path), str(self.manifest_file), str(payload)],
                                   cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, -signal.SIGKILL, completed.stderr)
        self.assertEqual(payload.with_suffix('.reached').read_text(), stage)
        self.business = self.open()
        receipt = self.business.reserve_delivery('capacity-crashed', sum(work['costs'].values()), hour, work, allow_seed=not earned)
        recovered = self.business.account.export()
        self.assertEqual(hashlib.sha256(key_path.read_bytes()).hexdigest(), authority_hash)
        self.assertEqual(len([r for r in capacity_rows(recovered) if r['id'] == 'capacity-crashed']), 1)
        self.assertEqual(recovered['ledger']['summary']['expenses'] - before['ledger']['summary']['expenses'], sum(work['costs'].values()))
        self.assertEqual(recovered['ledger']['summary']['reservedInvestment'], 0)
        self.assertEqual(receipt['funding'], 'EARNED' if earned else 'SEED')
        self.assertEqual(self.business.reserve_delivery('capacity-crashed', sum(work['costs'].values()), hour, work, allow_seed=not earned), receipt)
        self.assertEqual(self.business.account.export(), recovered)
        self.assertTrue(audit_journal(recovered, root=self.source, manifest=self.manifest)['accepted'])


if __name__ == '__main__':
    unittest.main()
