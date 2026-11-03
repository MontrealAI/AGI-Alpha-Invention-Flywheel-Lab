import fcntl
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from enterprise078.transactional_data.operator import ingest
from enterprise078.transactional_data.run import fixture
from .snapshot import deliver


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root/'live.sqlite'
        self.output = self.root/'accepted'; self.events = fixture(257)
        ingest(self.source, [])
        self.writer = sqlite3.connect(self.source)
        self.addCleanup(self.writer.close)
        self.writer.executemany('INSERT INTO events VALUES(?,?,?)',
                               [(r['id'],r['account'],r['quantity']) for r in self.events])
        self.writer.commit()
        self.assertGreater(Path(str(self.source)+'-wal').stat().st_size, 0)

    def run_delivery(self):
        return deliver(self.source, self.output, 'live-commission', self.events)

    def test_live_wal(self):
        r = self.run_delivery(); self.assertTrue(r['accepted'])
        self.assertFalse(r['native_catalog_admitted'])
        self.assertEqual(r['acceptance']['unique_events'], 257)
        self.assertEqual(self.writer.execute('SELECT count(*) FROM events').fetchone()[0],257)

    def test_100000_actual_records(self):
        events = fixture(100000)
        self.writer.executemany('INSERT INTO events VALUES(?,?,?)',
                               [(r['id'],r['account'],r['quantity']) for r in events[257:]])
        self.writer.commit(); self.events = events
        self.assertEqual(self.run_delivery()['acceptance']['unique_events'],100000)

    def test_wrong_input_no_publication(self):
        self.events = self.events[:-1]
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_DOES_NOT_MATCH'): self.run_delivery()
        self.assertFalse(self.output.exists())

    def test_later_source_append_does_not_change_delivery(self):
        r = self.run_delivery()
        self.writer.execute("INSERT INTO events VALUES('later','new',19)"); self.writer.commit()
        self.assertEqual(hashlib.sha256((self.output/'delivery.sqlite').read_bytes()).hexdigest(),r['database_sha256'])
        with sqlite3.connect(self.output/'delivery.sqlite') as c:
            self.assertEqual(c.execute('SELECT count(*) FROM events').fetchone()[0],257)

    def test_interrupted_acceptance_no_publication(self):
        with patch('enterprise078.transactional_admission.snapshot.accept', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'): self.run_delivery()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.snapshot-*')))

    def test_existing_destination_preserved(self):
        self.output.mkdir(); (self.output/'keep').write_text('original')
        with self.assertRaisesRegex(ValueError,'NEW_DELIVERY'): self.run_delivery()
        self.assertEqual((self.output/'keep').read_text(),'original')

    def test_publisher_exclusion(self):
        with (self.root/'accepted.publisher.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.run_delivery()
        self.assertFalse(self.output.exists())


if __name__ == '__main__': unittest.main()
