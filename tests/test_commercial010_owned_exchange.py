"""Integration against the real commercial owner, not a mock ledger."""
import json
from pathlib import Path
import tempfile
import unittest

from commercial.single_writer import SingleWriterExchange

ROOT = Path(__file__).resolve().parents[1]


class OwnedExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT/'campaign/commercial-010/service/executed-002/manifest.json').read_bytes())

    def open(self, path, opening=1_000_000_000):
        return SingleWriterExchange(path, root=ROOT, manifest=self.manifest,
                                    opening=opening, working=0, contract='owned-exchange-integration')

    def test_competing_owner_refused_then_replays_on_takeover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'exchange.sqlite'
            with self.open(path) as first:
                first.execute('cost', {'id': 'one', 'amount': 10}, 0)
                expected = first.export()
                with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'):
                    self.open(path)
                self.assertEqual(first.export(), expected)
            with self.open(path) as second:
                self.assertEqual(second.export(), expected)
                second.execute('cost', {'id': 'two', 'amount': 11}, 1)
                self.assertEqual(second.snapshot()['expenses'], 21)
                self.assertEqual(second.snapshot()['unrestrictedEarned'], 0)

    def test_invalid_native_constructor_releases_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'exchange.sqlite'
            with self.open(path): pass
            with self.assertRaises(ValueError): self.open(path, opening=2_000_000_000)
            with self.open(path) as restored:
                self.assertEqual(restored.snapshot()['expenses'], 0)

    def test_closed_facade_refuses_new_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self.open(Path(tmp)/'exchange.sqlite')
            ex.close(); ex.close()
            with self.assertRaisesRegex(ValueError, 'NOT_OWNED'):
                ex.execute('cost', {'id': 'late', 'amount': 10}, 0)


if __name__ == '__main__': unittest.main()
