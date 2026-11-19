"""EIT192 offline, deterministic, no-source-download adversarial unit tests."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

from tools.eit_zip_metadata192 import Refusal, classify_zip, parse_appledouble, write_once


def sidecar(*payloads):
    count = len(payloads)
    end = 26 + 12 * count
    header = struct.pack(">II16sH", 0x00051607, 0x00020000, b"\0" * 16, count)
    table = b"".join(
        struct.pack(">III", i + 1, end + sum(map(len, payloads[:i])), len(payload))
        for i, payload in enumerate(payloads)
    )
    return header + table + b"".join(payloads)


def make_zip(members):
    temp = tempfile.TemporaryDirectory()
    path = Path(temp.name) / "source.zip"
    with ZipFile(path, "w") as archive:
        for name, value in members:
            archive.writestr(name, value)
    return temp, path


class AppleDouble192Tests(unittest.TestCase):
    def test_valid_single_and_multiple_descriptors(self):
        for values in [(b"hello",), (b"hello", b"world")]:
            self.assertEqual(len(parse_appledouble(sidecar(*values))), len(values))

    def test_magic_or_version_mismatch(self):
        good = sidecar(b"abc")
        for raw in (b"\0" * 4 + good[4:], good[:4] + b"\0" * 4 + good[8:]):
            with self.assertRaisesRegex(Refusal, "NOT_APPLEDOUBLE"):
                parse_appledouble(raw)

    def test_short_header_and_descriptor_table(self):
        for raw in (b"\0" * 12, sidecar(b"abc")[:34]):
            with self.assertRaises(Refusal):
                parse_appledouble(raw)

    def test_filler_count_and_duplicate_entry_ids(self):
        good = bytearray(sidecar(b"aa", b"bb"))
        for pos, replacement in ((8, b"x"), (25, b"\x00")):
            bad = good.copy()
            bad[pos:pos + 1] = replacement
            with self.assertRaises(Refusal):
                parse_appledouble(bad)
        duplicate = good.copy()
        duplicate[38:42] = duplicate[26:30]
        with self.assertRaisesRegex(Refusal, "DUPLICATE"):
            parse_appledouble(duplicate)

    def test_macos_zip_exact_appledouble_filesystem_field(self):
        # Original failed chest member begins with this documented macOS ZIP
        # AppleDouble-v2 header. Whole member validation remains separate.
        raw = bytearray(sidecar(b"resource", b"attributes"))
        raw[8:24] = b"Mac OS X        "
        self.assertEqual(raw[:16].hex(), "00051607000200004d6163204f532058")
        entries = parse_appledouble(bytes(raw))
        self.assertEqual(len(entries), 2)
        self.assertEqual([entry["length"] for entry in entries], [8, 10])
        temp, path = make_zip([
            ("A/target.mat", b"real-MAT-parser-must-examine-this"),
            ("__MACOSX/A/._target.mat", bytes(raw)),
        ])
        try:
            receipt = classify_zip(path)
            self.assertEqual(receipt["genuine_matlab_candidates"], ["A/target.mat"])
            self.assertEqual(len(receipt["sidecars"]), 1)
            self.assertTrue(receipt["sidecars"][0]["counterpart_present"])
        finally:
            temp.cleanup()
        for replacement in (b"Mac OS X       x", b"mac OS X        ",
                            b"Mac OS X\0\0\0\0\0\0\0\0", b"Mac OS X        "[:-1] + b"\0"):
            bad = raw.copy()
            bad[8:24] = replacement
            with self.assertRaisesRegex(Refusal, "FILLER_UNKNOWN"):
                parse_appledouble(bytes(bad))

    def test_descriptor_range_and_overlap(self):
        good = bytearray(sidecar(b"ab", b"cd"))
        bad = good.copy()
        bad[30:34] = struct.pack(">I", 0xFFFFFFFE)
        with self.assertRaisesRegex(Refusal, "OUTSIDE"):
            parse_appledouble(bad)
        overlapping = good.copy()
        overlapping[42:46] = struct.pack(">I", 51)
        with self.assertRaisesRegex(Refusal, "OVERLAPPING"):
            parse_appledouble(overlapping)

    def test_oversize_metadata_rejected(self):
        with self.assertRaisesRegex(Refusal, "TOO_LARGE"):
            parse_appledouble(b"\0" * (16 * 1024 * 1024 + 1))

    def test_real_matlab_is_never_silently_dropped(self):
        temp, path = make_zip([
            ("A/Source.mat", b"invalid-but-genuine-mat"),
            ("__MACOSX/A/._Source.mat", sidecar(b"fork")),
        ])
        try:
            report = classify_zip(path)
            self.assertEqual(report["genuine_matlab_candidates"], ["A/Source.mat"])
            self.assertEqual(report["sidecars"][0]["intended_counterpart"], "A/Source.mat")
            self.assertTrue(report["sidecars"][0]["counterpart_present"])
            self.assertEqual(report["decision"], "HOLD_NO_DEPLOY_NO_BID")
        finally:
            temp.cleanup()

    def test_orphan_sidecar_disclosed(self):
        temp, path = make_zip([("__MACOSX/A/._orphan.mat", sidecar(b"abc"))])
        try:
            self.assertFalse(classify_zip(path)["sidecars"][0]["counterpart_present"])
        finally:
            temp.cleanup()

    def test_malformed_metadata_rejected(self):
        temp, path = make_zip([("__MACOSX/._file.mat", b"not-appledouble")])
        try:
            with self.assertRaises(Refusal):
                classify_zip(path)
        finally:
            temp.cleanup()

    def test_wrong_directory_dot_underscore_not_filtered(self):
        temp, path = make_zip([("dir/._data.mat", b"bogus")])
        try:
            self.assertEqual(classify_zip(path)["genuine_matlab_candidates"], ["dir/._data.mat"])
        finally:
            temp.cleanup()

    def test_unrecognized_macosx_member_rejected(self):
        temp, path = make_zip([("__MACOSX/regular.mat", b"text")])
        try:
            with self.assertRaisesRegex(Refusal, "UNRECOGNIZED"):
                classify_zip(path)
        finally:
            temp.cleanup()

    def test_path_traversal_and_backslash_rejected(self):
        for name in ("../x.mat", "A/../x.mat", "\\x.mat", "A\\x.mat"):
            temp, path = make_zip([(name, b"data")])
            try:
                with self.assertRaisesRegex(Refusal, "UNSAFE_MEMBER_PATH"):
                    classify_zip(path)
            finally:
                temp.cleanup()

    def test_duplicate_casefold_rejected(self):
        temp, path = make_zip([("A.mat", b"one"), ("a.MAT", b"two")])
        try:
            with self.assertRaisesRegex(Refusal, "DUPLICATE_CASEFOLDED"):
                classify_zip(path)
        finally:
            temp.cleanup()

    def test_noncanonical_unicode_rejected(self):
        temp, path = make_zip([("cafe\u0301.mat", b"data")])
        try:
            with self.assertRaisesRegex(Refusal, "NONCANONICAL_UNICODE"):
                classify_zip(path)
        finally:
            temp.cleanup()

    def test_symlink_rejected(self):
        info = ZipInfo("fake.mat")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        temp, path = make_zip([(info, b"elsewhere")])
        try:
            with self.assertRaisesRegex(Refusal, "NONREGULAR_MEMBER"):
                classify_zip(path)
        finally:
            temp.cleanup()

    def test_receipt_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "receipt.json"
            write_once(target, {"accepted": False})
            self.assertEqual(json.loads(target.read_text()), {"accepted": False})
            with self.assertRaisesRegex(Refusal, "RECEIPT_EXISTS"):
                write_once(target, {"accepted": True})


if __name__ == "__main__":
    unittest.main()
