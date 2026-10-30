import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from commercial.ledger import TapeExchange, audit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'campaign/commercial-010/service/executed-002/manifest.json'


class MemoryPersistence010Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_bytes())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='commercial010-io-verification-')
        self.path = Path(self.tmp.name) / 'exchange.sqlite'

    def tearDown(self):
        self.tmp.cleanup()

    def open(self):
        return TapeExchange(self.path, root=ROOT, manifest=self.manifest,
                            opening=1_000_000_000, working=0, contract='io-only-regression-010')

    def test_native_memory_checkpoint_integrity_and_durable_restart(self):
        ex = self.open()
        self.assertTrue(all(not r[2] for r in ex.ex.db.execute('PRAGMA database_list')))
        self.assertFalse(self.path.exists())
        ex.execute('cost', {'id': 'one', 'amount': 10}, 0)
        before = ex.export()
        ex.close()
        db = sqlite3.connect('file:' + str(self.path) + '?mode=ro', uri=True)
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        db.close()
        reopened = self.open()
        self.assertEqual(reopened.export(), before)
        reopened.execute('cost', {'id': 'two', 'amount': 11}, 1)
        self.assertEqual(reopened.ex.snapshot()['expenses'], 21)
        self.assertEqual(reopened.ex.snapshot()['unrestrictedEarned'], 0)
        reopened.close()
        proof = json.loads(self.path.with_name(self.path.name + '.persistence.json').read_bytes())
        self.assertEqual(proof['action_count'], 2)
        self.assertEqual(proof['checkpoint_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertFalse(proof['native_financial_algorithm_changed'])

    def test_corrupt_checkpoint_is_preserved_and_rebuilt_from_checked_tape(self):
        ex = self.open()
        ex.execute('cost', {'id': 'one', 'amount': 10}, 0)
        expected = ex.export()
        ex.close()
        broken = b'broken checkpoint bytes preserved verbatim'
        self.path.write_bytes(broken)
        recovered = self.open()
        self.assertEqual(recovered.export(), expected)
        recovered.close()
        preserved = self.path.with_name(self.path.name + '.corrupt-' + hashlib.sha256(broken).hexdigest())
        self.assertEqual(preserved.read_bytes(), broken)
        db = sqlite3.connect('file:' + str(self.path) + '?mode=ro', uri=True)
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        db.close()

    def test_torn_tape_and_rebound_configuration_fail_without_discarding_evidence(self):
        ex = self.open()
        ex.execute('cost', {'id': 'one', 'amount': 10}, 0)
        ex.close()
        tape = self.path.with_name(self.path.name + '.actions.jsonl')
        raw = tape.read_bytes()
        tape.write_bytes(raw + b'{"torn":')
        with self.assertRaises(ValueError):
            self.open()
        self.assertEqual(tape.read_bytes(), raw + b'{"torn":')
        tape.write_bytes(raw)
        with self.assertRaises(ValueError):
            TapeExchange(self.path, root=ROOT, manifest=self.manifest, opening=2_000_000_000,
                         working=0, contract='io-only-regression-010')

    def test_old_frozen_financial_tape_replays_identically_through_memory_engine(self):
        old = ROOT / 'campaign/commercial-010/market-development-001/qualified_differentiation/RESULT.json'
        result = json.loads(old.read_bytes())
        checked = audit(result['ledger'], root=ROOT, manifest=self.manifest,
                        expected_actions_sha256=result['ledger']['actions_sha256'])
        self.assertEqual(checked['summary'], result['ledger']['summary'])
        self.assertEqual(checked['orders'], result['ledger']['orders'])
        self.assertEqual(checked['investments'], result['ledger']['investments'])


if __name__ == '__main__':
    unittest.main()
