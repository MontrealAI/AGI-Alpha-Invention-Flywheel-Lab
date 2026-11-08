"""Finite adversarial file-descriptor custody checks; see frozen 099 protocol.

All source content here is synthetic and local. No keys, network, buyers, cash or
government webpage bytes. Cases are deterministic, not timing-sensitive.
"""
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from research.regulatory_portable_audit098 import _read_regular


class FDCustody099(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root = Path(self.d.name)
        self.path = self.root / "document.html"
        self.path.write_bytes(b"trusted synthetic content")
        self.victim = self.root / "other.html"
        self.victim.write_bytes(b"untrusted replacement synthetic content")

    def test_F0_regular_file_reads_exact(self):
        self.assertEqual(_read_regular(self.path, 1024), b"trusted synthetic content")

    def test_F1_final_symlink_rejected(self):
        self.path.unlink()
        self.path.symlink_to(self.victim)
        with self.assertRaises((ValueError, OSError)):
            _read_regular(self.path, 1024)

    def test_F1_swap_to_symlink_after_first_lstat_rejected(self):
        real_lstat = Path.lstat
        switched = [False]
        target = self.path

        def swap_after_first_stat(p):
            value = real_lstat(p)
            if p == target and not switched[0]:
                switched[0] = True
                target.unlink()
                target.symlink_to(self.victim)
            return value

        with patch.object(Path, "lstat", swap_after_first_stat):
            with self.assertRaises((ValueError, OSError)):
                _read_regular(self.path, 1024)
        self.assertTrue(switched[0])

    def test_F2_named_pipe_refused_without_read(self):
        self.path.unlink()
        os.mkfifo(self.path)
        with self.assertRaises((ValueError, OSError)):
            _read_regular(self.path, 1024)

    def test_F3_post_open_path_change_detected(self):
        original = Path.lstat
        calls = [0]
        target = self.path

        def replace_at_postcheck(p):
            if p == target:
                calls[0] += 1
                if calls[0] == 2:
                    target.unlink()
                    target.symlink_to(self.victim)
            return original(p)

        with patch.object(Path, "lstat", replace_at_postcheck):
            with self.assertRaises((ValueError, OSError)):
                _read_regular(self.path, 1024)
        self.assertEqual(calls[0], 2, "A second named-path identity check is required")

    def test_F4_empty_and_oversized_rejected(self):
        self.path.write_bytes(b"")
        with self.assertRaises((ValueError, OSError)):
            _read_regular(self.path, 1024)
        self.path.write_bytes(b"b" * 1025)
        with self.assertRaises((ValueError, OSError)):
            _read_regular(self.path, 1024)

    def test_F4_bounded_binary_bytes_unchanged(self):
        value = b"binary\x00and\xffbytes"
        self.path.write_bytes(value)
        self.assertEqual(_read_regular(self.path, len(value)), value)


if __name__ == "__main__":
    unittest.main()
