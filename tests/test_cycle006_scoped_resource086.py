"""Deterministic, adversarial observer tests; not a repeat of cycle006 commerce."""
import errno
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'verification/cycle006_scoped_resource086.py'
spec = importlib.util.spec_from_file_location('observer086', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ScopedResource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.observer = m.Observer(self.root)

    def disappearing(self, relative, with_database=True):
        item = self.root / relative
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_bytes(b'x' * 10)
        if with_database:
            item.with_name(item.name.removesuffix('-journal')).write_bytes(b'LIVE_DB')
        old = Path.lstat
        observed = []
        def injected(p, *args, **kwargs):
            if p == item and not observed:
                observed.append(p)
                p.unlink()
            return old(p, *args, **kwargs)
        with patch.object(Path, 'lstat', injected):
            try:
                result = self.observer.sizes(self.root)
            except Exception as error:
                return error, observed
        return result, observed

    def test_all_four_registered_journals_disappear_with_database(self):
        for relative in sorted(m.ALLOWED):
            with self.subTest(relative=relative):
                result, observed = self.disappearing(relative)
                self.assertEqual(len(observed), 1)
                self.assertIsInstance(result, list)
                self.assertEqual(result, [7] * self.observer.vanished)
        self.assertEqual(self.observer.vanished, 4)

    def test_unlisted_database_journal_is_not_suppressed(self):
        result, observed = self.disappearing('artifacts/wessels-conditional-settlement/unlisted.sqlite-journal')
        self.assertEqual(len(observed), 1)
        self.assertIsInstance(result, FileNotFoundError)

    def test_missing_database_not_suppressed(self):
        result, observed = self.disappearing(sorted(m.ALLOWED)[0], False)
        self.assertEqual(len(observed), 1)
        self.assertIsInstance(result, FileNotFoundError)

    def test_symlink_database_is_not_valid_for_missing_journal(self):
        relative = sorted(m.ALLOWED)[0]
        entry = self.root / relative
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b'journal')
        entry.with_name(entry.name.removesuffix('-journal')).symlink_to('/dev/null')
        original = Path.lstat
        def vanish(p, *args, **kwargs):
            if p == entry and entry.exists():
                entry.unlink()
            return original(p, *args, **kwargs)
        with patch.object(Path, 'lstat', vanish):
            with self.assertRaisesRegex(ValueError, 'JOURNAL_WITHOUT_REGULAR_DATABASE'):
                self.observer.sizes(self.root)

    def test_permission_error_not_suppressed(self):
        entry = self.root / 'private'
        entry.write_bytes(b'abc')
        old = Path.lstat
        def inject(p, *a, **kw):
            if p == entry:
                raise PermissionError(errno.EACCES, 'denied')
            return old(p, *a, **kw)
        with patch.object(Path, 'lstat', inject):
            with self.assertRaises(PermissionError):
                self.observer.sizes(self.root)

    def test_symlink_no_follow_and_wrong_root(self):
        p = self.root / 'regular'
        p.write_bytes(b'abc')
        q = self.root / 'link'
        q.symlink_to('/dev/zero')
        self.assertEqual(sum(self.observer.sizes(self.root)), 3 + q.lstat().st_size)
        with self.assertRaises(ValueError):
            self.observer.sizes(self.root / 'not_root')

    def test_receipt_limits_still_apply(self):
        (self.root / 'x').write_bytes(b'x' * 4096)
        receipt = {'observer086': {}, 'state': 'complete', 'reason': None,
                   'waited_cpu_seconds': 0.0, 'wall_seconds': 0.0,
                   'limits': {'output_bytes': 2048, 'storage_bytes': 10000,
                              'cpu_seconds': 60, 'wall_seconds': 60}, 'output_bytes': 0}
        result = self.observer.finish(receipt, self.root)
        self.assertEqual(result['state'], 'overrun')
        self.assertEqual(result['reason'], 'final-output-file-limit')
        self.assertGreater(result['output_bytes'], 4096)

    def test_wrong_run_id_refused_before_guard_import(self):
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_RUN_ID'):
            m.prospective_run(self.root, [], self.root / 'out', self.root / 'ledger', 'wrong', {})

if __name__ == '__main__':
    unittest.main()
