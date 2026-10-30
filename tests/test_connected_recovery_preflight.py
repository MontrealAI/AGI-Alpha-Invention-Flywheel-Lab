import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from adaptive_enterprise.account import Account
from tests import test_connected_finance as fixture


class ConnectedRecoveryPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ConnectedFinanceTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixture.ConnectedFinanceTests.tearDownClass()

    def setUp(self):
        self.fixture = fixture.ConnectedFinanceTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def interrupt(self, boundary):
        t = self.fixture
        t.earn()
        method = 'finish' if boundary == 'finish' else 'reserve'
        original = getattr(t.account._account, method)
        def crash(*args, **kwargs):
            if boundary != 'zero':
                original(*args, **kwargs)
            raise InterruptedError(boundary)
        with patch.object(t.account._account, method, crash), self.assertRaises(InterruptedError):
            t.spend()

    def authority(self):
        parent = Path(self.fixture.tmp.name)
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in parent.glob('account.sqlite.*')
                if p.name.endswith(('.actions.jsonl', '.connected-journal.json', '.adaptive-proofs.json', '.adaptive-resolutions.json'))}

    def test_valid_zero_reserve_and_finish_tails_recover_once(self):
        for boundary in ['zero', 'reserve', 'finish']:
            with self.subTest(boundary=boundary):
                if boundary != 'zero':
                    self.fixture.tearDown(); self.fixture.setUp()
                self.interrupt(boundary)
                t = self.fixture
                t.reopen()
                self.assertEqual(t.spend()['funding'], 'EARNED')
                record = t.account.export()
                self.assertEqual(record['ledger']['summary']['expenses'], 70_000_000)
                self.assertEqual(record['ledger']['summary']['reservedInvestment'], 0)
                self.assertEqual(sum(row['op'] == 'reserve' for row in record['ledger']['actions']), 1)
                self.assertEqual(sum(row['op'] == 'finish' for row in record['ledger']['actions']), 1)
                self.assertTrue(t.account.audit()['accepted'])

    def test_extra_native_cost_at_each_pending_boundary_rejects_before_mutation(self):
        for boundary in ['zero', 'reserve', 'finish']:
            with self.subTest(boundary=boundary):
                if boundary != 'zero':
                    self.fixture.tearDown(); self.fixture.setUp()
                self.interrupt(boundary)
                t = self.fixture
                t.account._account.cost('unexpected-unlogged-cost', 123, 1)
                before = t.account._account.export()
                t.account.close()
                authoritative = self.authority()
                with self.assertRaisesRegex(ValueError, 'PENDING_CONNECTED_NATIVE_TAIL_MISMATCH'):
                    t.open()
                self.assertEqual(self.authority(), authoritative)
                with Account(t.root, t.manifest, t.path, opening=1_000_000_000,
                             working=0, contract='connected014-finance-test') as account:
                    self.assertEqual(account.export(), before)


if __name__ == '__main__':
    unittest.main()
