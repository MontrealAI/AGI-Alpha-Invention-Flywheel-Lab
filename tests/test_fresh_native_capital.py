import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from adaptive_enterprise.account import action_digest, audit_account
from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICES, prepare_services
from commercial.terms import prospective_terms
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal

ROOT = Path(__file__).resolve().parents[1]


class NativeCapitalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='native-capital-source-')
        cls.root = Path(cls.fixture.name)
        for name in set(SOURCE_PATHS) | set(SERVICES):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.manifest = prepare_services(cls.root, 'services')
        cls.manifest['native_engine']='prospective-v1'
        cls.jobs = [j for j in cls.manifest['jobs'] if j['service_id'] == 'reconciliation' and j['accepted']]

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-capital-account-')
        self.path = Path(self.tmp.name) / 'account.sqlite'
        self.a = self.open()

    def open(self):
        return JournalAccount(self.root, self.manifest, self.path, opening=300_000_000,
                              working=100_000_000, contract='native-prospective-v1:test')

    def tearDown(self):
        self.a.close(); self.tmp.cleanup()

    def settled(self, ident='order1', *, legacy=False, residual=0, coverage=0, premium=10_000, start=0):
        price = 100_000_000
        terms = prospective_terms(ident, price, start + 20, start + 2,
                                  residual=residual, coverage_limit=coverage,
                                  premium=premium, payout_delay_hours=2)
        if not legacy:
            self.a.execute('register_terms', {'id': ident + '-v1', 'terms': terms}, start)
        self.a.execute('wallet', {'buyer': ident + '-buyer', 'amount': price}, start)
        offer = {'id': ident, 'buyer': ident + '-buyer', 'price': price,
                 'job_id': self.jobs[0]['id'], 'deadline': start + 10}
        if not legacy:
            offer['terms_id'] = ident + '-v1'
        self.a.execute('offer', offer, start)
        for action in ['consent', 'fund', 'prepare', 'release']:
            self.a.execute('event', {'id': ident, 'action': action, 'event_id': ident + '-' + action}, start + 2)
        return terms

    def test_maturity_preserves_profit_and_releases_exactly_once(self):
        self.settled()
        before = self.a.snapshot()['summary']
        with self.assertRaisesRegex(ValueError, 'MATURITY'):
            self.a.execute('mature', {'id': 'order1', 'event_id': 'premature-attempt'}, 20)
        matured = self.a.advance_financial(21)['summary']
        self.assertEqual(before['tailReserve'] - matured['tailReserve'], 100_200_000)
        self.assertEqual(before['profit'], matured['profit'])
        export = self.a.export()
        self.a.advance_financial(21)
        self.assertEqual(self.a.export(), export)
        self.assertTrue(self.a.audit()['accepted'])

    def test_legacy_tail_is_preserved(self):
        self.settled(legacy=True)
        tail = self.a.snapshot()['summary']['tailReserve']
        self.a.advance_financial(200)
        self.assertEqual(self.a.snapshot()['summary']['tailReserve'], tail)
        with self.assertRaisesRegex(ValueError, 'LEGACY_TERMS_IMMUTABLE'):
            self.a.execute('mature', {'id': 'order1', 'event_id': 'legacy-refused'}, 200)

    def test_boundary_claim_remains_payable_after_maturity(self):
        self.settled(residual=5_000_000)
        self.a.execute('claim', {'id': 'order1', 'claim_id': 'c1', 'amount': 12_000_000, 'kind': 'disputed'}, 20)
        self.a.advance_financial(21)
        self.assertEqual(self.a.snapshot()['summary']['payables'], 12_000_000)
        self.a.execute('resolve_claim', {'id': 'order1', 'claim_id': 'c1', 'settlement_id': 'deny1', 'resolution': 'deny'}, 21)
        self.assertEqual(self.a.snapshot()['summary']['payables'], 0)
        self.assertEqual(self.a.snapshot()['summary']['tailReserve'], 5_000_000)
        self.assertTrue(self.a.audit()['accepted'])

    def test_recovery_is_collected_delayed_costed_and_bounded(self):
        self.settled(coverage=30_000_000, premium=1_000_000)
        self.a.execute('claim', {'id': 'order1', 'claim_id': 'covered1', 'amount': 20_000_000, 'kind': 'covered'}, 3)
        self.a.execute('resolve_claim', {'id': 'order1', 'claim_id': 'covered1', 'settlement_id': 'pay1', 'resolution': 'pay'}, 3)
        args = {'id': 'order1', 'claim_id': 'covered1', 'settlement_id': 'recover1', 'amount': 10_000_000, 'source_tx': 'synthetic-recovery-1'}
        with self.assertRaisesRegex(ValueError, 'DELAY'):
            self.a.execute('recover_claim', args, 4)
        self.assertEqual(self.a.snapshot()['summary']['recoveryIncome'], 0)
        args['settlement_id'] = 'valid-recovery1'
        self.a.execute('recover_claim', args, 5)
        self.a.execute('recover_claim', {**args, 'settlement_id': 'recover2', 'source_tx': 'synthetic-recovery-2'}, 5)
        self.assertEqual(self.a.snapshot()['summary']['recoveryIncome'], 20_000_000)
        self.assertTrue(self.a.audit()['accepted'])

    def test_positive_profit_does_not_spend_committed_cash_and_stale_proof_fails(self):
        self.settled()
        snap = self.a.snapshot(); self.assertGreater(snap['summary']['profit'], 0)
        self.assertIsNone(self.a.spend('too-large', 'production', snap['summary']['available'] + 1, 3, {}, 1))
        plan = {'plan_id': 'stale1', 'action_id': 'stale-action1'}
        authority = action_digest(plan, snap['state_digest'], 1, 1)
        self.a.cost('state-change', 1, 3)
        with self.assertRaisesRegex(ValueError, 'STALE_NATIVE_ACCOUNT_STATE'):
            self.a._account.reserve(plan, expected_state_digest=snap['state_digest'], authorized_digest=authority, amount=1, expected_net=1, day=3)
        self.assertGreater(self.a.snapshot()['summary']['profit'], 0)

    def test_maturity_commit_interruption_recovers_without_double_release(self):
        self.settled()
        execute = self.a._account.execute
        def crash(op, args, day):
            result = execute(op, args, day)
            if op == 'mature':
                raise InterruptedError('after native maturity commit')
            return result
        with patch.object(self.a._account, 'execute', crash), self.assertRaises(InterruptedError):
            self.a.advance_financial(21)
        self.a.close(); self.a = self.open()
        self.a.advance_financial(21)
        self.assertEqual(sum(e['op'] == 'mature' for e in self.a.export()['ledger']['actions']), 1)
        self.assertTrue(audit_account(self.a.export(), root=self.root, manifest=self.manifest)['accepted'])

    def test_public_state_tampering_and_clock_rollback_are_rejected(self):
        self.settled()
        with self.assertRaisesRegex(ValueError, 'EVENT_TIME_REGRESSION'):
            self.a.cost('rollback', 1, 1)
        forged = copy.deepcopy(self.a.export())
        forged['ledger']['prospective_orders'][0]['matured_at'] = 3
        with self.assertRaises(ValueError):
            audit_journal(forged, root=self.root, manifest=self.manifest)

    def test_unpaid_late_and_provider_default_claims_never_unlock_new_work(self):
        self.settled(residual=1_000_000,coverage=0,premium=250_000)
        before=self.a.snapshot()['summary']
        self.a.execute('claim',{'id':'order1','claim_id':'boundary','amount':2_000_000,'kind':'ordinary'},20)
        cash=self.a.snapshot()['summary']['cash'];profit=self.a.snapshot()['summary']['profit']
        self.a.advance_financial(21)
        matured=self.a.snapshot()['summary']
        self.assertEqual((matured['cash'],matured['profit'],matured['payables']),(cash,profit,2_000_000))
        self.a.execute('claim',{'id':'order1','claim_id':'late-default','amount':2_000_000,'kind':'provider_default'},22)
        stopped=self.a.snapshot()['summary']
        self.assertEqual(stopped['payables'],4_000_000)
        self.assertTrue(stopped['investmentStopped']);self.assertEqual(stopped['unrestrictedEarned'],0)
        self.assertEqual(stopped['recoveryIncome'],0)
        self.assertIsNone(self.a.spend('unsafe-seed','production',1,22,{},1,allow_seed=True))
        self.a.execute('wallet',{'buyer':'next-buyer','amount':1_000_000},22)
        with self.assertRaisesRegex(ValueError,'STOP_BLOCKS_NEW_COMMITMENT'):
            self.a.execute('offer',{'id':'next','buyer':'next-buyer','price':1_000_000,'job_id':self.jobs[1]['id'],'deadline':30},22)
        self.assertTrue(self.a.audit()['accepted'])

    def test_current_writer_prevents_competing_reservation_owner(self):
        with self.assertRaisesRegex(ValueError, 'ALREADY_OWNED'):
            self.open()
