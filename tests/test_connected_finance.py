import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services

ROOT = Path(__file__).resolve().parents[1]


class ConnectedFinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='connected014-finance-source-')
        cls.root = Path(cls.fixture.name)
        for name in sorted(set(SOURCE_PATHS) | set(SERVICE_PATHS)):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.manifest = prepare_services(cls.root, 'services')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='connected014-finance-test-')
        self.path = Path(self.tmp.name) / 'account.sqlite'
        self.account = self.open()

    def tearDown(self):
        self.account.close()
        self.tmp.cleanup()

    def open(self):
        return JournalAccount(self.root, self.manifest, self.path, opening=1_000_000_000,
                              working=0, contract='connected014-finance-test')

    def earn(self):
        job = next(j for j in self.manifest['jobs'] if j['service_id'] == 'reconciliation')
        self.account.execute('wallet', {'buyer': 'buyer', 'amount': 100_000_000}, 0)
        self.account.execute('offer', {'id': 'first-order', 'buyer': 'buyer', 'price': 100_000_000,
                                      'job_id': job['id'], 'deadline': 100}, 0)
        for action in ['consent', 'fund', 'prepare', 'release']:
            self.account.execute('event', {'id': 'first-order', 'action': action, 'event_id': action}, 0)
        self.account.cost('complete-original-cost', 10_000_000, 0)

    def spend(self, **changes):
        args = dict(ident='resource-1', kind='production_contract', amount=60_000_000,
                    day=1, work={'source': 'contract-1', 'units': 2}, expected_net=10_000_000)
        args.update(changes)
        return self.account.spend(**args)

    def reopen(self):
        self.account.close()
        self.account = self.open()

    def test_earned_contract_is_state_bound_obligation_resolved_and_exactly_once(self):
        self.earn()
        receipt = self.spend()
        self.assertEqual(receipt['funding'], 'EARNED')
        self.assertEqual(receipt['prepaid_support_microUSD'], 10_000)
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 70_000_000)
        self.assertEqual(self.account.snapshot()['summary']['reservedInvestment'], 0)
        before = self.account.export()
        self.assertEqual(self.spend(), receipt)
        self.assertEqual(self.account.export(), before)
        self.reopen()
        self.assertEqual(self.spend(), receipt)
        checked = self.account.audit()
        self.assertTrue(checked['accepted'])
        self.assertEqual(checked['source_bound_resource_spend_microUSD'], 60_000_000)
        exported = self.account.export()
        self.assertNotIn('key', exported['connected_journal'])
        self.assertEqual(exported['obligation_resolutions'][receipt['plan_id']]['later_incurred_microUSD'], 10_000)

    def test_startup_contract_source_drift_rejects_before_financial_mutation(self):
        before = self.account.export()
        path = self.root / 'connected_enterprise/startup_acquisition048.py'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'CONNECTED_FINANCE_SOURCE_CHANGED'):
                self.spend(allow_seed=True)
            with self.assertRaisesRegex(ValueError, 'CONNECTED_FINANCE_SOURCE_CHANGED'):
                self.account.cost('unrelated-after-source-drift', 1, 0)
        finally:
            path.write_bytes(original)
        self.assertEqual(self.account.export(), before)

    def test_future_income_does_not_fund_and_seed_requires_explicit_flag(self):
        before = self.account.export()
        self.assertIsNone(self.spend())
        self.assertEqual(self.account.export(), before)
        receipt = self.spend(allow_seed=True)
        self.assertEqual(receipt['funding'], 'SEED')
        self.assertIsNone(receipt['plan_id'])
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 60_000_000)
        self.assertTrue(self.account.audit()['accepted'])
        self.assertIsNone(self.spend(ident='unfunded', amount=2_000_000_000, allow_seed=True))

    def test_changed_duplicate_payload_refused_without_further_spending(self):
        self.earn(); self.spend()
        before = self.account.export()
        for changes in [{'amount': 1}, {'work': {'source': 'different'}}, {'day': 2},
                        {'kind': 'different'}, {'expected_net': 999}, {'allow_seed': True}]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'PAYLOAD_CHANGED'):
                self.spend(**changes)
        self.assertEqual(self.account.export(), before)

    def test_reserve_committed_then_interrupted_recovers_same_plan(self):
        self.earn()
        reserve = self.account._account.reserve
        def crash(*args, **kwargs):
            reserve(*args, **kwargs)
            raise InterruptedError('after native reservation commit')
        with patch.object(self.account._account, 'reserve', crash), self.assertRaises(InterruptedError):
            self.spend()
        self.assertEqual(self.account.snapshot()['summary']['reservedInvestment'], 60_000_000)
        self.reopen()
        receipt = self.spend()
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 70_000_000)
        self.assertEqual(self.account.snapshot()['summary']['reservedInvestment'], 0)
        self.assertEqual(sum(row['op'] == 'reserve' for row in self.account.export()['ledger']['actions']), 1)
        self.assertEqual(self.spend(), receipt)

    def test_finish_committed_then_interrupted_replay_survives_advanced_state(self):
        self.earn()
        finish = self.account._account.finish
        def crash(*args, **kwargs):
            finish(*args, **kwargs)
            raise InterruptedError('after native finish commit')
        with patch.object(self.account._account, 'finish', crash), self.assertRaises(InterruptedError):
            self.spend()
        self.reopen()
        self.account.cost('later-independent-resource', 123, 2)
        receipt = self.spend()
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 70_000_123)
        self.assertEqual(sum(row['op'] == 'finish' for row in self.account.export()['ledger']['actions']), 1)
        self.assertEqual(self.spend(), receipt)

    def test_seed_cost_commit_before_ack_is_recovered_without_double_charge(self):
        cost = self.account._account.cost
        def crash(*args, **kwargs):
            cost(*args, **kwargs)
            raise InterruptedError('after native cost commit')
        with patch.object(self.account._account, 'cost', crash), self.assertRaises(InterruptedError):
            self.spend(allow_seed=True)
        self.reopen()
        self.assertEqual(self.spend(allow_seed=True)['funding'], 'SEED')
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 60_000_000)

    def _abrupt_process(self, method):
        self.earn()
        self.account.close()
        manifest_path = Path(self.tmp.name) / 'manifest.json'
        manifest_path.write_text(json.dumps(self.manifest))
        code = """import json,os,sys
from connected_enterprise.finance import JournalAccount
root,path,manifest,method=sys.argv[1:]
account=JournalAccount(root,json.loads(open(manifest).read()),path,opening=1000000000,working=0,contract='connected014-finance-test')
original=getattr(account._account,method)
def crash(*args,**kwargs):
 original(*args,**kwargs)
 os._exit(17)
setattr(account._account,method,crash)
account.spend('resource-1','production_contract',60000000,1,{'source':'contract-1','units':2},10000000)
"""
        done = subprocess.run([sys.executable, '-c', code, str(self.root), str(self.path), str(manifest_path), method],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 17, done.stderr)
        self.account = self.open()
        self.assertEqual(self.spend()['funding'], 'EARNED')
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 70_000_000)
        self.assertEqual(self.account.snapshot()['summary']['reservedInvestment'], 0)
        self.assertTrue(self.account.audit()['accepted'])

    def test_abrupt_process_exit_after_reserve_recovers_one_expense(self):
        self._abrupt_process('reserve')

    def test_abrupt_process_exit_after_finish_recovers_one_expense(self):
        self._abrupt_process('finish')

    def test_native_operation_commit_before_ack_returns_original_prefix_snapshot(self):
        execute = self.account._account.execute
        def crash(*args, **kwargs):
            execute(*args, **kwargs)
            raise InterruptedError('after native action commit')
        with patch.object(self.account._account, 'execute', crash), self.assertRaises(InterruptedError):
            self.account.cost('exact-resource', 7, 0)
        self.reopen()
        self.account.cost('later-resource', 11, 1)
        original = self.account.cost('exact-resource', 7, 0)
        self.assertEqual(original['summary']['expenses'], 7)
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 18)
        self.assertEqual(original['sequence'], 1)

    def test_competing_owner_cannot_open_live_account(self):
        with self.assertRaisesRegex(ValueError, 'ALREADY_OWNED'):
            self.open()

    def test_source_drift_and_public_receipt_tampering_fail_closed(self):
        self.earn(); self.spend()
        record = self.account.export()
        forged = copy.deepcopy(record)
        entry = next(e for e in forged['connected_journal']['entries'] if e['request']['operation'] == 'spend')
        entry['receipt']['work_sha256'] = '0' * 64
        from commercial.ledger import digest
        forged['connected_journal_sha256'] = digest(forged['connected_journal'])
        with self.assertRaisesRegex(ValueError, 'RECEIPT_CHANGED'):
            audit_journal(forged, root=self.root, manifest=self.manifest)
        path = self.root / 'connected_enterprise/finance.py'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                self.account.snapshot()
        finally:
            path.write_bytes(original)

    def test_private_wal_tamper_is_rejected_on_reopen(self):
        self.spend(allow_seed=True)
        self.account.close()
        path = self.path.with_name(self.path.name + '.connected-journal.json')
        record = json.loads(path.read_text())
        record['body']['entries'][0]['receipt']['amount'] = 1
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'SIGNATURE_MISMATCH'):
            self.open()

    def test_operating_checkpoint_preserves_state_and_accepts_native_advancement(self):
        state = {'queue': [{'id': 'plan-1', 'time': 24}], 'buyers': [{'id': 'buyer', 'active': True}],
                 'current': {'event': {'id': 'plan-1'}}, 'last_time': 0}
        checkpoint = self.account.seal_checkpoint(state)
        self.account.cost('committed-after-checkpoint-before-event-ack', 7, 0)
        self.assertEqual(self.account.verify_checkpoint(checkpoint), state)
        self.reopen()
        self.assertEqual(self.account.verify_checkpoint(checkpoint), state)
        self.assertNotIn('key', checkpoint['body'])
        self.assertEqual(checkpoint['body']['native_sequence'], 0)
        self.assertEqual(self.account.snapshot()['summary']['expenses'], 7)

    def test_operating_queue_buyer_current_and_time_tampering_rejected(self):
        state = {'queue': [{'id': 'plan-1', 'time': 24}], 'buyers': [{'id': 'buyer', 'active': True}],
                 'current': {'event': {'id': 'plan-1'}}, 'last_time': 0}
        checkpoint = self.account.seal_checkpoint(state)
        changes = [('queue', []), ('buyers', [{'id': 'buyer', 'active': False}]),
                   ('current', None), ('last_time', 99)]
        for field, value in changes:
            forged = copy.deepcopy(checkpoint)
            forged['body']['state'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'CHECKPOINT_SIGNATURE'):
                self.account.verify_checkpoint(forged)

    def test_checkpoint_from_another_account_key_or_contract_is_rejected(self):
        checkpoint = self.account.seal_checkpoint({'queue': []})
        other = JournalAccount(self.root, self.manifest, Path(self.tmp.name) / 'other.sqlite',
                               opening=1_000_000_000, working=0, contract='other-enterprise')
        try:
            with self.assertRaisesRegex(ValueError, 'CHECKPOINT_SIGNATURE'):
                other.verify_checkpoint(checkpoint)
        finally:
            other.close()

    def test_valid_checkpoint_refuses_native_tape_rollback(self):
        before = copy.deepcopy(self.account._account.export())
        self.account.cost('acknowledged-resource', 7, 0)
        checkpoint = self.account.seal_checkpoint({'queue': []})
        with patch.object(self.account._account, 'export', lambda: before):
            with self.assertRaisesRegex(ValueError, 'CHECKPOINT_NATIVE_PREFIX'):
                self.account.verify_checkpoint(checkpoint)

    def test_public_audit_requires_every_native_action_to_be_journaled(self):
        self.earn(); self.spend()
        for dropped in [0, -1]:
            forged = copy.deepcopy(self.account.export())
            forged['connected_journal']['entries'].pop(dropped)
            from commercial.ledger import digest
            forged['connected_journal_sha256'] = digest(forged['connected_journal'])
            with self.subTest(dropped=dropped), self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
                audit_journal(forged, root=self.root, manifest=self.manifest)

    def test_public_audit_requires_journal_native_causal_order(self):
        self.earn(); self.spend()
        forged = copy.deepcopy(self.account.export())
        forged['connected_journal']['entries'][:2] = reversed(forged['connected_journal']['entries'][:2])
        from commercial.ledger import digest
        forged['connected_journal_sha256'] = digest(forged['connected_journal'])
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
            audit_journal(forged, root=self.root, manifest=self.manifest)

    def test_public_audit_rejects_direct_native_writer_bypass(self):
        self.account.cost('journaled-cost', 7, 0)
        self.account._account.cost('unclaimed-native-cost', 11, 1)
        record = self.account.export()
        self.assertEqual(record['ledger']['summary']['expenses'], 18)
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
            audit_journal(record, root=self.root, manifest=self.manifest)
        self.account.close()
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
            self.open()

    def test_new_journal_write_requires_current_complete_native_audit(self):
        self.account._account.cost('bypassed-journal', 11, 0)
        before = self.account.export()
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
            self.account.cost('cannot-continue-from-invalid-state', 7, 1)
        self.assertEqual(self.account.export(), before)
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
            self.spend(allow_seed=True)
        self.assertEqual(self.account.export(), before)

    def test_recovery_refuses_signed_unsupported_native_request_before_mutation(self):
        self.account._entry('native:cancel_investment:stale',
                            {'operation': 'execute', 'op': 'cancel_investment', 'args': {'id': 'stale'}, 'day': 0})
        before = self.account._account.export()
        self.account.close()
        with self.assertRaisesRegex(ValueError, 'CONNECTED_RESOURCE_COMMITMENT_ENTRYPOINT_REQUIRED'):
            self.open()
        from adaptive_enterprise.account import Account
        with Account(self.root, self.manifest, self.path, opening=1_000_000_000,
                     working=0, contract='connected014-finance-test') as native:
            self.assertEqual(native.export(), before)

    def test_public_audit_rejects_duplicate_native_claim(self):
        self.account.cost('actual-cost', 7, 0)
        forged = copy.deepcopy(self.account.export())
        forged['connected_journal']['entries'].append(copy.deepcopy(forged['connected_journal']['entries'][0]))
        from commercial.ledger import digest
        forged['connected_journal_sha256'] = digest(forged['connected_journal'])
        with self.assertRaisesRegex(ValueError, 'COMPLETE_UNIQUE_CONNECTED_JOURNAL_REQUIRED'):
            audit_journal(forged, root=self.root, manifest=self.manifest)

    def test_public_audit_prohibits_commitment_operations_in_execute_entries(self):
        self.account.cost('actual-cost', 7, 0)
        from commercial.ledger import digest
        for operation in ['reserve', 'finish', 'cancel_investment']:
            forged = copy.deepcopy(self.account.export())
            forged['connected_journal']['entries'][0]['request']['op'] = operation
            forged['connected_journal_sha256'] = digest(forged['connected_journal'])
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'CONNECTED_RESOURCE_COMMITMENT_ENTRYPOINT_REQUIRED'):
                audit_journal(forged, root=self.root, manifest=self.manifest)

    def test_export_is_detached_from_live_native_authority(self):
        self.account.cost('actual-resource', 7, 0)
        exported = self.account.export()
        exported['ledger']['actions'][0]['args']['amount'] = 1
        exported['ledger']['config']['opening'] = 2
        self.assertEqual(self.account.export()['ledger']['actions'][0]['args']['amount'], 7)
        self.assertEqual(self.account.export()['ledger']['config']['opening'], 1_000_000_000)
        self.assertTrue(self.account.audit()['accepted'])


if __name__ == '__main__':
    unittest.main()
