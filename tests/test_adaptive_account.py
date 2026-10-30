import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from adaptive_enterprise.account import Account, action_digest, audit_account
from commercial.ledger import TapeExchange, digest
from commercial.single_writer import SingleWriterExchange
from enterprise.services import SOURCE_PATHS, prepare_services

ROOT = Path(__file__).resolve().parents[1]
OPENING = 1_000_000_000


def _open(root, manifest, path):
    return Account(root, manifest, path, opening=OPENING, working=0, contract='adaptive-account-test')


def _plan(ident='next-delivery'):
    return {'plan_id': ident, 'action_id': ident + '-action', 'customer_id': 'synthetic-buyer',
            'service_id': 'reconciliation', 'source_hashes': {},
            'scenario_net_cash_microUSD': {'ordinary': 10_000_000, 'adverse': -15_000_000}}


def _reserve_worker(root, manifest, path, state, start, queue, ident):
    start.wait(20)
    try:
        with _open(root, manifest, path) as account:
            plan = _plan(ident)
            authorized = action_digest(plan, state, 60_000_000, 10_000_000)
            account.reserve(plan, expected_state_digest=state, authorized_digest=authorized,
                            amount=60_000_000, expected_net=10_000_000, day=1)
            queue.put(('reserved', ident))
    except ValueError as exc:
        queue.put(('rejected', str(exc)))


def _crash_worker(root, manifest, path, connection):
    account = _open(root, manifest, path)
    account.cost('acknowledged-before-crash', 7_000_000, 1)
    connection.send(account.snapshot())
    connection.close()
    os._exit(17)


def _crash_reservation_worker(root, manifest, path, state, connection):
    account = _open(root, manifest, path)
    plan = _plan('crashed-reservation')
    authorized = action_digest(plan, state, 60_000_000, 10_000_000)
    account.reserve(plan, expected_state_digest=state, authorized_digest=authorized,
                    amount=60_000_000, expected_net=10_000_000, day=1)
    connection.send(account.snapshot())
    connection.close()
    os._exit(19)


class AdaptiveAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='adaptive012-account-fixture-')
        cls.root = Path(cls.fixture.name)
        for name in SOURCE_PATHS:
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.manifest = prepare_services(cls.root, 'services')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='adaptive012-account-test-')
        self.path = Path(self.tmp.name) / 'account.sqlite'

    def tearDown(self):
        self.tmp.cleanup()

    def open(self):
        return _open(self.root, self.manifest, self.path)

    def earn(self, account):
        job = next(j for j in self.manifest['jobs'] if j['service_id'] == 'reconciliation')
        account.execute('wallet', {'buyer': 'buyer-wallet', 'amount': 100_000_000}, 0)
        account.execute('offer', {'id': 'accepted-service', 'buyer': 'buyer-wallet', 'price': 100_000_000,
                                  'job_id': job['id'], 'deadline': 100}, 0)
        for action in ['consent', 'fund', 'prepare', 'release']:
            account.execute('event', {'id': 'accepted-service', 'action': action, 'event_id': action}, 0)
        account.cost('complete-original-cost', 10_000_000, 0)
        self.assertEqual(account.snapshot()['summary']['unrestrictedEarned'], 90_000_000)

    def reserve(self, account, ident='next-delivery', state=None, amount=60_000_000):
        plan = _plan(ident)
        state = account.snapshot()['state_digest'] if state is None else state
        authorized = action_digest(plan, state, amount, 10_000_000)
        return account.reserve(plan, expected_state_digest=state, authorized_digest=authorized,
                               amount=amount, expected_net=10_000_000, day=1)

    def test_native_earned_reserve_finish_and_public_audit(self):
        with self.open() as account:
            self.earn(account)
            self.reserve(account)
            before = account.snapshot()
            self.assertEqual(before['summary']['reservedInvestment'], 60_000_000)
            account.finish('next-delivery', 40_000_000, 'a' * 64, 2)
            after = account.snapshot()
            self.assertEqual(after['summary']['expenses'], 50_000_000)
            self.assertEqual(after['summary']['unrestrictedEarned'], 50_000_000)
            self.assertEqual(after['summary']['reservedInvestment'], 0)
            record = account.export()
            self.assertTrue(account.audit()['accepted'])
        self.assertEqual(audit_account(record, root=self.root, manifest=self.manifest)['state_bound_reservations'], 1)

    def test_seed_and_future_receipts_do_not_finance_reservation(self):
        with self.open() as account:
            with self.assertRaisesRegex(ValueError, 'earned funds'):
                self.reserve(account)
            self.assertEqual(account.snapshot()['summary']['collections'], 0)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 0)

    def test_stale_state_or_modified_authorization_rejected(self):
        with self.open() as account:
            self.earn(account)
            state = account.snapshot()['state_digest']
            account.cost('new-obligation', 1, 1)
            with self.assertRaisesRegex(ValueError, 'STALE_NATIVE'):
                self.reserve(account, state=state)
            plan = _plan()
            current = account.snapshot()['state_digest']
            signature = action_digest(plan, current, 60_000_000, 10_000_000)
            plan['service_id'] = 'changed-after-authorization'
            with self.assertRaisesRegex(ValueError, 'AUTHORIZED_ACTION'):
                account.reserve(plan, expected_state_digest=current, authorized_digest=signature,
                                amount=60_000_000, expected_net=10_000_000, day=1)

    def test_plan_amount_and_later_obligations_cannot_be_underreserved(self):
        with self.open() as account:
            self.earn(account)
            state = account.snapshot()['state_digest']
            plan = dict(_plan(), reserve_amount=70_000_000)
            with self.assertRaisesRegex(ValueError, 'RESERVATION_AMOUNT_MISMATCH'):
                action_digest(plan, state, 60_000_000, 10_000_000)
            plan = dict(_plan(), upfront_cost=40_000_000, worst_later_reserve=30_000_000)
            with self.assertRaisesRegex(ValueError, 'LATER_OBLIGATIONS'):
                action_digest(plan, state, 60_000_000, 10_000_000)
            proof = action_digest(plan, state, 70_000_000, 10_000_000)
            account.reserve(plan, expected_state_digest=state, authorized_digest=proof,
                            amount=70_000_000, expected_net=10_000_000, day=1)
            self.assertEqual(account.snapshot()['summary']['unrestrictedEarned'], 20_000_000)

    def test_later_obligation_early_finish_and_tampered_invoice_refused(self):
        with self.open() as account:
            self.earn(account)
            execution = {'kind': 'capacity', 'source_sha256': 'a' * 64}
            option = {'id': 'capacity', 'kind': 'capacity', 'upfront_cost': 40_000_000,
                      'later_liabilities': {'ordinary': 30_000_000}, 'execution': execution}
            plan = dict(_plan(), selected_options=[option], upfront_cost=40_000_000,
                        worst_later_reserve=30_000_000, reserve_amount=70_000_000, expected_net=10_000_000)
            state = account.snapshot()['state_digest']
            account.reserve(plan, expected_state_digest=state,
                            authorized_digest=action_digest(plan, state, 70_000_000, 10_000_000),
                            amount=70_000_000, expected_net=10_000_000, day=1)
            with self.assertRaisesRegex(ValueError, 'RESOLUTION_REQUIRED'):
                account.finish(plan['plan_id'], 40_000_000, 'c' * 64, 2)
            with self.assertRaisesRegex(ValueError, 'OBLIGATION_AWARE'):
                account.execute('finish', {'id': plan['plan_id'], 'amount': 40_000_000, 'artifact_sha256': 'c' * 64}, 2)
            receipt = {'schema': 'agi-alpha/adaptive012-obligation-resolution/v1', 'plan_id': plan['plan_id'],
                       'resolved_at_day': 2, 'native_actions_sha256': account.snapshot()['actions_sha256'],
                       'work_artifact_sha256': 'c' * 64, 'upfront_incurred_microUSD': 40_000_000,
                       'later_incurred_microUSD': 30_000_000, 'unused_reserve_microUSD': 0, 'deliveries': [],
                       'growth': [{'option_id': 'capacity', 'execution_sha256': digest(execution), 'prepaid_support_microUSD': 30_000_000}]}
            altered = copy.deepcopy(receipt); altered['growth'][0]['execution_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'SOURCE_OR_INVOICE'):
                account.finish(plan['plan_id'], 70_000_000, 'c' * 64, 2, obligation_receipt=altered)
            account.finish(plan['plan_id'], 70_000_000, 'c' * 64, 2, obligation_receipt=receipt)
            self.assertEqual(account.snapshot()['summary']['unrestrictedEarned'], 20_000_000)
            self.assertTrue(account.audit()['accepted'])
        with self.open() as account:
            account.finish(plan['plan_id'], 70_000_000, 'c' * 64, 2, obligation_receipt=receipt)
            self.assertTrue(account.audit()['accepted'])

    def test_accepted_fee_invoice_requires_native_prepare_and_keeps_pending_principal_protected(self):
        with self.open() as account:
            self.earn(account)
            job = [j for j in self.manifest['jobs'] if j['service_id'] == 'reconciliation'][1]
            execution = {'kind': 'delivery', 'job_id': job['id'], 'customer_id': 'second-customer',
                         'payment_bps': 290, 'payment_fixed_microUSD': 300_000, 'onboarding_microUSD': 500_000}
            option = {'id': 'delivery', 'kind': 'delivery', 'upfront_cost': 10_000_000,
                      'later_liabilities': {'ordinary': 3_700_000}, 'execution': execution}
            plan = dict(_plan(), selected_options=[option], upfront_cost=10_000_000,
                        worst_later_reserve=3_700_000, reserve_amount=13_700_000, expected_net=10_000_000)
            state = account.snapshot()['state_digest']
            account.reserve(plan, expected_state_digest=state,
                            authorized_digest=action_digest(plan, state, 13_700_000, 10_000_000),
                            amount=13_700_000, expected_net=10_000_000, day=1)
            account.execute('wallet', {'buyer': 'second-wallet', 'amount': 100_000_000}, 1)
            account.execute('offer', {'id': 'second-order', 'buyer': 'second-wallet', 'price': 100_000_000,
                                      'job_id': job['id'], 'deadline': 100}, 1)
            for action in ['consent', 'fund']:
                account.execute('event', {'id': 'second-order', 'event_id': 'second-' + action, 'action': action}, 1)
            receipt = {'schema': 'agi-alpha/adaptive012-obligation-resolution/v1', 'plan_id': plan['plan_id'],
                       'resolved_at_day': 1, 'native_actions_sha256': account.snapshot()['actions_sha256'],
                       'work_artifact_sha256': 'd' * 64, 'upfront_incurred_microUSD': 10_000_000,
                       'later_incurred_microUSD': 3_700_000, 'unused_reserve_microUSD': 0, 'growth': [],
                       'deliveries': [{'option_id': 'delivery', 'job_id': job['id'], 'order_id': 'second-order',
                                       'artifact_sha256': job['artifact_sha256'], 'customer_id': 'second-customer',
                                       'outcome': 'NATIVE_ACCEPTED', 'payment_fee_microUSD': 3_200_000, 'onboarding_microUSD': 500_000}]}
            with self.assertRaisesRegex(ValueError, 'ACCEPTANCE_AND_PROTECTION'):
                account.finish(plan['plan_id'], 13_700_000, 'd' * 64, 1, obligation_receipt=receipt)
            account.execute('event', {'id': 'second-order', 'event_id': 'second-prepare', 'action': 'prepare'}, 1)
            receipt['native_actions_sha256'] = account.snapshot()['actions_sha256']
            account.finish(plan['plan_id'], 13_700_000, 'd' * 64, 1, obligation_receipt=receipt)
            self.assertEqual(account.snapshot()['summary']['custodyReserve'], 100_000_000)
            self.assertTrue(account.audit()['accepted'])

    def test_idempotent_cost_reserve_finish_and_resume(self):
        with self.open() as account:
            self.earn(account)
            state = account.snapshot()['state_digest']
            self.reserve(account, state=state)
            sequence = account.snapshot()['sequence']
            self.reserve(account, state=state)
            self.assertEqual(account.snapshot()['sequence'], sequence)
            account.finish('next-delivery', 30_000_000, 'b' * 64, 2)
            account.finish('next-delivery', 30_000_000, 'b' * 64, 2)
            expected = account.snapshot()
        with self.open() as account:
            account.finish('next-delivery', 30_000_000, 'b' * 64, 2)
            self.assertEqual(account.snapshot(), expected)
            with self.assertRaisesRegex(ValueError, 'PAYLOAD_CHANGED'):
                account.finish('next-delivery', 31_000_000, 'b' * 64, 2)
            account.cost('later-support', 3, 3)
            seq = account.snapshot()['sequence']
            account.cost('later-support', 3, 3)
            self.assertEqual(account.snapshot()['sequence'], seq)

    def test_mandatory_namespace_rejects_legacy_unguarded_callers(self):
        with self.open():
            with self.assertRaisesRegex(ValueError, 'MANDATORY_WRITER'):
                TapeExchange(self.path, root=self.root, manifest=self.manifest,
                             opening=OPENING, working=0, contract='adaptive-account-test')
        with self.assertRaisesRegex(ValueError, 'MANDATORY_WRITER'):
            TapeExchange(self.path, root=self.root, manifest=self.manifest,
                         opening=OPENING, working=0, contract='adaptive-account-test', durable=False)
        with self.assertRaisesRegex(ValueError, 'ACCOUNT_FACADE'):
            SingleWriterExchange(self.path, root=self.root, manifest=self.manifest,
                                 opening=OPENING, working=0, contract='adaptive-account-test')
        with self.assertRaisesRegex(ValueError, 'MANDATORY_WRITER'):
            TapeExchange(Path(self.tmp.name) / 'new-adaptive.sqlite', root=self.root,
                         manifest={'schema': 'agi-alpha/adaptive012-services/v1'},
                         opening=OPENING, working=0, contract='new')

    def test_unqualified_direct_reservation_entrypoint_refused(self):
        with self.open() as account:
            with self.assertRaisesRegex(ValueError, 'STATE_BOUND_RESERVE'):
                account.execute('reserve', {'id': 'unbound', 'amount': 1,
                                           'expected_net_value': 1, 'intent_sha256': 'a' * 64}, 0)

    def test_competing_processes_cannot_double_reserve_same_earnings(self):
        with self.open() as account:
            self.earn(account)
            state = account.snapshot()['state_digest']
        context = multiprocessing.get_context('spawn')
        start, queue = context.Event(), context.Queue()
        processes = [context.Process(target=_reserve_worker, args=(str(self.root), self.manifest, str(self.path), state, start, queue, 'reserve-' + str(i))) for i in range(2)]
        for process in processes:
            process.start()
        start.set()
        outcomes = [queue.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(30)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(sum(row[0] == 'reserved' for row in outcomes), 1, outcomes)
        self.assertEqual(sum(row[0] == 'rejected' for row in outcomes), 1, outcomes)
        with self.open() as account:
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 60_000_000)
            self.assertEqual(account.snapshot()['summary']['unrestrictedEarned'], 30_000_000)
            self.assertEqual(len(account.export()['ledger']['investments']), 1)

    def test_interrupted_owner_takeover_replays_acknowledged_action_once(self):
        with self.open() as account:
            self.earn(account)
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe(False)
        process = context.Process(target=_crash_worker, args=(str(self.root), self.manifest, str(self.path), child))
        process.start(); child.close()
        self.assertTrue(parent.poll(30))
        expected = parent.recv()
        process.join(30)
        self.assertEqual(process.exitcode, 17)
        with self.open() as account:
            self.assertEqual(account.snapshot(), expected)
            account.cost('acknowledged-before-crash', 7_000_000, 1)
            self.assertEqual(account.snapshot(), expected)
            self.assertEqual(account.snapshot()['summary']['collections'], 100_000_000)

    def test_interrupted_reservation_commit_retries_without_duplicate_funding(self):
        with self.open() as account:
            self.earn(account)
            state = account.snapshot()['state_digest']
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe(False)
        process = context.Process(target=_crash_reservation_worker,
                                  args=(str(self.root), self.manifest, str(self.path), state, child))
        process.start(); child.close()
        self.assertTrue(parent.poll(30))
        expected = parent.recv(); process.join(30)
        self.assertEqual(process.exitcode, 19)
        with self.open() as account:
            self.assertEqual(account.snapshot(), expected)
            self.reserve(account, ident='crashed-reservation', state=state)
            self.assertEqual(account.snapshot(), expected)
            self.assertEqual(len(account.export()['ledger']['investments']), 1)
            self.assertTrue(account.audit()['accepted'])

    def test_precommit_proof_survives_interruption_without_spending(self):
        with self.open() as account:
            self.earn(account)
            state = account.snapshot()['state_digest']
            original = account._owner.execute
            def interrupted(*args, **kwargs):
                raise InterruptedError('before native reservation; proof already durable')
            account._owner.execute = interrupted
            with self.assertRaises(InterruptedError):
                self.reserve(account, state=state)
            account._owner.execute = original
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 0)
        with self.open() as account:
            self.reserve(account, state=state)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 60_000_000)
            self.assertEqual(len(account.export()['ledger']['investments']), 1)

    def test_local_mac_entropy_does_not_change_native_financial_replay(self):
        with self.open() as first:
            self.earn(first); self.reserve(first)
            left = first.export()
        alternative = Path(self.tmp.name) / 'second.sqlite'
        with _open(self.root, self.manifest, alternative) as second:
            self.earn(second); self.reserve(second)
            right = second.export()
        self.assertEqual(left['ledger'], right['ledger'])
        self.assertNotEqual(left['action_proofs']['next-delivery']['signature'], right['action_proofs']['next-delivery']['signature'])

    def test_signed_proof_and_public_state_binding_tampering_rejected(self):
        with self.open() as account:
            self.earn(account); self.reserve(account)
            record = account.export()
        changed = copy.deepcopy(record)
        changed['action_proofs']['next-delivery']['body']['expected_state_digest'] = '0' * 64
        with self.assertRaises(ValueError):
            audit_account(changed, root=self.root, manifest=self.manifest)
        proof = self.path.with_name(self.path.name + '.adaptive-proofs.json')
        records = json.loads(proof.read_bytes())
        records['next-delivery']['signature'] = '0' * 64
        proof.write_text(json.dumps(records))
        with self.assertRaisesRegex(ValueError, 'SIGNATURE_MISMATCH'):
            self.open()

    def test_explicit_distributed_storage_and_aliases_refused(self):
        for storage in ['nfs', 'distributed', 'unknown']:
            with self.subTest(storage=storage), self.assertRaisesRegex(ValueError, 'LOCAL_POSIX'):
                Account(self.root, self.manifest, self.path, opening=OPENING, storage=storage)
        target = Path(self.tmp.name) / 'target'
        target.touch()
        alias = Path(self.tmp.name) / 'alias.sqlite'
        alias.symlink_to(target)
        with self.assertRaises(ValueError):
            _open(self.root, self.manifest, alias)
        with patch('adaptive_enterprise.account.Path.read_text', return_value='1 0 0:1 / / rw - nfs4 server:/volume rw\n'):
            with self.assertRaisesRegex(ValueError, 'DISTRIBUTED_OR_UNKNOWN'):
                self.open()

    def test_hardlinked_tape_alias_refused(self):
        with self.open():
            pass
        source = self.path.with_name(self.path.name + '.actions.jsonl')
        alias = Path(self.tmp.name) / 'other.sqlite.actions.jsonl'
        os.link(source, alias)
        with self.assertRaisesRegex(ValueError, 'SINGLE_REGULAR_ACCOUNT'):
            TapeExchange(Path(self.tmp.name) / 'other.sqlite', root=self.root, manifest=self.manifest,
                         opening=OPENING, working=0, contract='adaptive-account-test')

    def test_adaptive_services_settle_through_owned_native_audit(self):
        from adaptive_enterprise.instruments import SOURCE_PATHS as ADAPTIVE_SOURCES, prepare_services as prepare_adaptive
        root = Path(self.tmp.name) / 'adaptive-source'
        for name in ADAPTIVE_SOURCES:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        manifest = prepare_adaptive(root, 'services')
        with _open(root, manifest, self.path) as account:
            account.execute('wallet', {'buyer': 'adaptive-buyer', 'amount': 300_000_000}, 0)
            for i, service in enumerate(['reconciliation', 'kpi_variance', 'evidence_matrix']):
                job = next(j for j in manifest['jobs'] if j['service_id'] == service)
                ident = 'adaptive-service-' + str(i)
                account.execute('offer', {'id': ident, 'buyer': 'adaptive-buyer', 'price': 100_000_000,
                                          'job_id': job['id'], 'deadline': 100}, 0)
                for action in ['consent', 'fund', 'prepare', 'release']:
                    account.execute('event', {'id': ident, 'action': action, 'event_id': ident + '-' + action}, 0)
            self.assertEqual(account.snapshot()['summary']['collections'], 300_000_000)
            self.reserve(account)
            self.assertTrue(account.audit()['accepted'])


if __name__ == '__main__':
    unittest.main()
