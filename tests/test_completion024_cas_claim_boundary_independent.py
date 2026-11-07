"""Frozen 2026-11-07 synthetic CAS claim-boundary qualification; no owner account access."""
import tempfile
import unittest
from pathlib import Path

from adaptive_enterprise.instruments import prepare_services
from commercial.terms import prospective_terms
from connected_enterprise.finance import JournalAccount
from connected_enterprise.operations import _copy_source, _copy_inputs
from connected_enterprise.transition_evidence import evidence_directory
from connected_enterprise.upgrades import authorize_upgrade

ROOT = Path(__file__).resolve().parents[1]
OPENING = 500_000_000
WORKING = 100_000_000
PRICE = 100_000_000
CLAIM = 20_000_000
RESIDUAL = 5_000_000
CONTRACT = 'independent-cas-claim-boundary-20261107'


class IndependentCASClaimBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_case = tempfile.TemporaryDirectory(prefix='cas-claim-sources-')
        cls.root = Path(cls.source_case.name)
        cls.old = cls.root / 'before'
        cls.new = cls.root / 'after'
        _copy_source(ROOT, cls.old)
        cls.manifest = prepare_services(cls.old, 'services', cohort_seed=2610312203)
        _copy_source(ROOT, cls.new)
        _copy_inputs(cls.old, cls.new, cls.manifest)
        path = cls.new / 'connected_enterprise' / 'finance.py'
        path.write_bytes(path.read_bytes() + b'\n# Explicit forward source-version test fixture.\n')

    @classmethod
    def tearDownClass(cls):
        cls.source_case.cleanup()

    def setUp(self):
        self.account_case = tempfile.TemporaryDirectory(prefix='cas-claim-account-')
        self.base = Path(self.account_case.name)
        self.path = self.base / 'account.sqlite'
        self.keypath = self.base / 'account.sqlite.adaptive-simulation-key'
        self.store = self.base / 'TRANSITION_EVIDENCE'
        self.store.mkdir(mode=0o700)

    def tearDown(self):
        self.account_case.cleanup()

    def _prepare(self, claim):
        with JournalAccount(self.old, self.manifest, self.path, opening=OPENING,
                            working=WORKING, contract=CONTRACT) as a:
            job = next(j for j in self.manifest['jobs']
                       if j['service_id'] == 'reconciliation' and j['accepted'])
            terms = prospective_terms('cas-boundary-order', PRICE, 20, 2,
                                      residual=RESIDUAL, premium=1_000_000,
                                      coverage_limit=50_000_000, deductible=10_000_000,
                                      payout_delay_hours=2)
            a.execute('register_terms', {'id': 'cas-terms', 'terms': terms}, 0)
            a.execute('wallet', {'buyer': 'buyer', 'amount': PRICE}, 0)
            a.execute('offer', {'id': 'cas-boundary-order', 'buyer': 'buyer',
                                'price': PRICE, 'job_id': job['id'],
                                'deadline': 10, 'terms_id': 'cas-terms'}, 0)
            for op in ('consent', 'fund', 'prepare', 'release'):
                a.execute('event', {'id': 'cas-boundary-order', 'action': op,
                                    'event_id': 'cas-' + op}, 2)
            a.cost('original-complete-service', 10_000_000, 2)
            boundary_before = a.snapshot()['summary'].copy()
            a.advance_financial(20)  # Boundary is inclusive for claims.
            if claim:
                a.execute('claim', {'id': 'cas-boundary-order', 'claim_id': 'cas-claim',
                                    'amount': CLAIM, 'kind': 'covered'}, 20)
            prior = a.export()
        inode = self.keypath.stat().st_ino
        ticket = authorize_upgrade(historical_root=self.old, target_root=self.new,
                                   manifest=self.manifest, path=self.path, opening=OPENING,
                                   working=WORKING, contract=CONTRACT,
                                   expected_state_digest=prior['snapshot']['state_digest'],
                                   ident='boundary-cas-forward', day=20,
                                   transition_format='v2-cas', evidence_root=self.store)
        self.assertEqual(ticket['body']['schema'], 'agi-alpha/native-source-transition/v2-cas')
        self.assertTrue(list(self.store.iterdir()))
        return prior, ticket, inode, boundary_before

    def _open_forward(self, ticket):
        return JournalAccount.upgrade_source(self.new, self.manifest, self.path,
                                             opening=OPENING, working=WORKING,
                                             contract=CONTRACT, authorization=ticket)

    def test_inclusive_boundary_claim_survives_cas_and_is_not_silently_paid(self):
        prior, ticket, inode, _ = self._prepare(claim=True)
        with evidence_directory(self.store):
            with self._open_forward(ticket) as a:
                now = a.advance_financial(21)['summary']
                self.assertEqual(now['payables'], CLAIM)
                self.assertGreaterEqual(now['tailReserve'], RESIDUAL)
                self.assertEqual(now['cash'], prior['ledger']['summary']['cash'])
                self.assertEqual(a.export()['ledger']['prospective_claims'],
                                 prior['ledger']['prospective_claims'])
                self.assertEqual(a.export()['ledger']['actions'][:len(prior['ledger']['actions'])],
                                 prior['ledger']['actions'])
                self.assertTrue(a.audit()['accepted'])
                a.execute('resolve_claim', {'id': 'cas-boundary-order', 'claim_id': 'cas-claim',
                                            'settlement_id': 'cas-pay', 'resolution': 'pay'}, 22)
                before_collection = a.snapshot()['summary']
                a.execute('recover_claim', {'id': 'cas-boundary-order', 'claim_id': 'cas-claim',
                                            'settlement_id': 'cas-collection', 'amount': 10_000_000,
                                            'source_tx': 'local-fixture-collected-recovery'}, 24)
                recovered = a.snapshot()['summary']
                self.assertEqual(recovered['cash'] - before_collection['cash'], 10_000_000)
                self.assertEqual(recovered['recoveryIncome'], 10_000_000)
                self.assertTrue(a.audit()['accepted'])
                final = a.export()
            with JournalAccount(self.new, self.manifest, self.path, opening=OPENING,
                                working=WORKING, contract=CONTRACT) as reopened:
                self.assertEqual(reopened.export(), final)
                self.assertTrue(reopened.audit()['accepted'])
        self.assertEqual(self.keypath.stat().st_ino, inode)

    def test_unclaimed_expiry_preserves_large_late_claim_as_breach_and_payable(self):
        # New amendment explicitly replaces original failed blanket-refusal hypothesis.
        prior, ticket, inode, _ = self._prepare(claim=False)
        with evidence_directory(self.store):
            with self._open_forward(ticket) as a:
                early = a.snapshot()['summary'].copy()
                self.assertEqual(a.advance_financial(20)['summary'], early)
                mature = a.advance_financial(21)['summary']
                self.assertEqual(mature['cash'], early['cash'])
                self.assertEqual(mature['profit'], early['profit'])
                self.assertEqual(mature['tailReserve'], RESIDUAL)
                self.assertEqual(a.advance_financial(21)['summary'], mature)
                a.execute('claim', {'id': 'cas-boundary-order', 'claim_id': 'large-late-claim',
                                    'amount': CLAIM, 'kind': 'covered'}, 21)
                after = a.snapshot()['summary']
                self.assertEqual(after['cash'], mature['cash'])
                self.assertEqual(after['profit'], mature['profit'] - CLAIM)
                self.assertEqual(after['payables'], mature['payables'] + CLAIM)
                self.assertTrue(after['investmentStopped'])
                self.assertEqual(after['recoveryIncome'], 0)
                self.assertTrue(a.audit()['accepted'])
                self.assertEqual(a.export()['ledger']['actions'][:len(prior['ledger']['actions'])],
                                 prior['ledger']['actions'])
        self.assertEqual(self.keypath.stat().st_ino, inode)

    def test_late_claim_within_permanent_residual_is_payable_not_refused(self):
        prior, ticket, inode, _ = self._prepare(claim=False)
        with evidence_directory(self.store):
            with self._open_forward(ticket) as a:
                mature = a.advance_financial(21)['summary']
                self.assertEqual(mature['tailReserve'], RESIDUAL)
                a.execute('claim', {'id': 'cas-boundary-order', 'claim_id': 'covered-residual',
                                    'amount': 3_000_000, 'kind': 'covered'}, 21)
                after = a.snapshot()['summary']
                self.assertEqual(after['cash'], mature['cash'])
                self.assertEqual(after['profit'], mature['profit'] - 3_000_000)
                self.assertEqual(after['payables'], mature['payables'] + 3_000_000)
                self.assertEqual(after['tailReserve'], mature['tailReserve'] - 3_000_000)
                self.assertFalse(after['investmentStopped'])
                self.assertEqual(after['recoveryIncome'], 0)
                self.assertTrue(a.audit()['accepted'])
                self.assertEqual(a.export()['ledger']['actions'][:len(prior['ledger']['actions'])],
                                 prior['ledger']['actions'])
        self.assertEqual(self.keypath.stat().st_ino, inode)

    def test_missing_cas_scope_cannot_change_signed_history(self):
        _, ticket, inode, _ = self._prepare(claim=True)
        journal = self.base / 'account.sqlite.connected-journal.json'
        original = journal.read_bytes()
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_TRANSITION_EVIDENCE_SCOPE'):
            with self._open_forward(ticket):
                self.fail('unscoped CAS must never authorize upgrade')
        self.assertEqual(journal.read_bytes(), original)
        self.assertEqual(self.keypath.stat().st_ino, inode)


if __name__ == '__main__':
    unittest.main()
