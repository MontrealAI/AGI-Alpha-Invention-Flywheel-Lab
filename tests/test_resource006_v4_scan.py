"""Narrow live-output scan regressions; no resource-cap changes."""
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from experiments import resource006_v4 as monitor


class ResourceScanTests(unittest.TestCase):
    def test_vanished_entry_does_not_hide_surviving_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keep, gone = root / 'keep', root / 'sqlite-journal'
            keep.write_bytes(b'1234567')
            gone.write_bytes(b'x')
            entries = [gone, keep]
            gone.unlink()
            with patch.object(Path, 'rglob', return_value=iter(entries)):
                self.assertEqual(monitor._usage(root), 7)

    def test_stable_files_and_links_count_without_following_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'nested').mkdir()
            (root / 'nested' / 'data').write_bytes(b'12345')
            (root / 'link').symlink_to('nested')
            (root / 'dangling').symlink_to('absent')
            os.mkfifo(root / 'pipe')
            expected = 5 + len('nested') + len('absent')
            self.assertEqual(monitor._usage(root), expected)

    def test_permission_and_io_errors_propagate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = root / 'unreadable'
            for error in (PermissionError(errno.EACCES, 'denied'), OSError(errno.EIO, 'bad device')):
                with self.subTest(error=error), patch.object(Path, 'rglob', return_value=iter([entry])), patch.object(Path, 'lstat', side_effect=error):
                    with self.assertRaises(type(error)):
                        monitor._usage(root)

    def test_terminal_scan_retains_file_and_total_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'large').write_bytes(b'x' * 4096)
            for total, single, reason in ((2048, 2048, 'final-aggregate-output-storage-limit'), (16384, 2048, 'final-output-file-limit')):
                receipt = {'state': 'complete', 'wall_seconds': 0, 'waited_cpu_seconds': 0,
                           'limits': {'storage_bytes': total, 'output_bytes': single, 'cpu_seconds': 1, 'wall_seconds': 1}}
                result = monitor._final_receipt(receipt, root)
                self.assertEqual(result['state'], 'overrun')
                self.assertEqual(result['reason'], reason)
                self.assertGreater(result['output_bytes'], 4096)

    def test_terminal_scan_skips_only_vanished_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'keep').write_bytes(b'x' * 4096)
            entries = [root / 'gone', root / 'keep']
            receipt = {'state': 'complete', 'wall_seconds': 0, 'waited_cpu_seconds': 0,
                       'limits': {'storage_bytes': 2048, 'output_bytes': 2048, 'cpu_seconds': 1, 'wall_seconds': 1}}
            with patch.object(Path, 'rglob', return_value=iter(entries)):
                self.assertEqual(monitor._final_receipt(receipt, root)['state'], 'overrun')

if __name__ == '__main__':
    unittest.main()
