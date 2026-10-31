import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from commercial.terms import prospective_terms
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from enterprise.services import SOURCE_PATHS as SERVICE_SOURCE_PATHS, prepare_services
from experiments.commerce006 import PINS

ROOT = Path(__file__).resolve().parents[1]


class NativeCapitalAdverseStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='native-capital-source-')
        cls.root = Path(cls.fixture.name)
        for name in set(SOURCE_PATHS) | set(SERVICE_SOURCE_PATHS) | set(PINS):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.manifest = prepare_services(cls.root, 'services')
        cls.job = next(j for j in cls.manifest['jobs'] if j['service_id'] == 'reconciliation')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def open(self, path):
        return JournalAccount(self.root, self.manifest, path, opening=20_000_000,
                              working=0, contract='native-prospective-v1:adverse-regression')

    def settle(self, account):
        terms = prospective_terms('o', 2_000_000, 20, 2, residual=100_000,
                                  premium=10_000, coverage_limit=100_000, payout_delay_hours=2)
        account.execute('register_terms', {'id': 't', 'terms': terms}, 0)
        account.execute('wallet', {'buyer': 'b', 'amount': 2_000_000}, 0)
        account.execute('offer', {'id': 'o', 'buyer': 'b', 'price': 2_000_000,
                                 'job_id': self.job['id'], 'deadline': 10, 'terms_id': 't'}, 0)
        for action, moment in [('consent', 0), ('fund', 0), ('prepare', 1), ('release', 2)]:
            account.execute('event', {'id': 'o', 'event_id': action, 'action': action}, moment)

    def test_first_native_maturity_detects_cash_or_profit_fault_and_keeps_committed_history(self):
        for fields in [('cash',), ('profit',), ('cash', 'profit')]:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory(prefix='maturity-fault-') as tmp:
                with self.open(Path(tmp) / 'account.sqlite') as account:
                    self.settle(account)
                    execute, snapshot = account.execute, account._account.snapshot
                    committed = False
                    def observed_execute(op, args, day):
                        nonlocal committed
                        result = execute(op, args, day)
                        if op == 'mature':
                            committed = True
                        return result
                    def faulty_snapshot():
                        result = copy.deepcopy(snapshot())
                        if committed:
                            for field in fields:
                                result['summary'][field] += 1
                        return result
                    with patch.object(account, 'execute', observed_execute), \
                         patch.object(account._account, 'snapshot', faulty_snapshot), \
                         self.assertRaisesRegex(ValueError, 'MATURITY_CANNOT_CREATE_CASH_OR_PROFIT'):
                        account.advance_financial(21)
                    # The negative assertion cannot erase or retry a committed
                    # financial event. Original canonical audit remains mandatory.
                    before = account.export()
                    self.assertEqual(sum(row['op'] == 'mature' for row in before['ledger']['actions']), 1)
                    account.advance_financial(21)
                    self.assertEqual(account.export(), before)
                    self.assertTrue(account.audit()['accepted'])

    def test_reversal_keeps_distinct_claim_service_and_registered_residual(self):
        with tempfile.TemporaryDirectory(prefix='native-capital-account-') as tmp:
            path = Path(tmp) / 'account.sqlite'
            with self.open(path) as account:
                self.settle(account)
                account.execute('event', {'id': 'o', 'event_id': 'late-reversal', 'action': 'late_reversal'}, 3)
                reversed_state = account.snapshot()['summary']
                self.assertEqual(reversed_state['tailReserve'], 200_000)
                self.assertEqual(reversed_state['payables'], 0)
                self.assertTrue(reversed_state['investmentStopped'])
                account.execute('claim', {'id': 'o', 'claim_id': 'distinct-support-claim',
                                         'amount': 50_000, 'kind': 'covered'}, 4)
                claimed = account.snapshot()['summary']
                self.assertEqual((claimed['tailReserve'], claimed['payables']), (150_000, 50_000))
                account.execute('resolve_claim', {'id': 'o', 'claim_id': 'distinct-support-claim',
                                                 'settlement_id': 'pay', 'resolution': 'pay'}, 5)
                account.execute('recover_claim', {'id': 'o', 'claim_id': 'distinct-support-claim',
                                                 'settlement_id': 'recover', 'amount': 50_000, 'source_tx': 'support-recovery'}, 6)
                profit = account.snapshot()['summary']['profit']
                account.execute('mature', {'id': 'o', 'event_id': 'maturity'}, 21)
                matured = account.snapshot()['summary']
                self.assertEqual((matured['tailReserve'], matured['payables']), (100_000, 0))
                self.assertEqual(matured['profit'], profit)
                account.execute('claim', {'id': 'o', 'claim_id': 'distinct-late-support',
                                         'amount': 50_000, 'kind': 'ordinary'}, 22)
                after = account.snapshot()['summary']
                self.assertEqual((after['tailReserve'], after['payables']), (50_000, 50_000))
                self.assertTrue(after['investmentStopped'])
                self.assertEqual(after['unrestrictedEarned'], 0)
                record = account.export()
                self.assertTrue(account.audit()['accepted'])
            with self.open(path) as restored:
                self.assertEqual(restored.export(), record)
                self.assertTrue(restored.audit()['accepted'])
            self.assertTrue(audit_journal(record, root=self.root, manifest=self.manifest)['accepted'])
            forged = copy.deepcopy(record)
            forged['ledger']['summary']['tailReserve'] = 0
            with self.assertRaises(ValueError):
                audit_journal(forged, root=self.root, manifest=self.manifest)


if __name__ == '__main__':
    unittest.main()
