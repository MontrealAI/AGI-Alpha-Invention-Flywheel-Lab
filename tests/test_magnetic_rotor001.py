"""Frozen safety and scope checks for source gate 001. No network in tests."""
from __future__ import annotations

from hashlib import md5
from io import BytesIO
import stat
import unittest
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

from research.magnetic_rotor001 import gate


def fixture(files, *, compression=ZIP_DEFLATED):
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=compression) as archive:
        for name, body in files:
            archive.writestr(name, body)
    return buffer.getvalue()


class MagneticSourceGateTests(unittest.TestCase):
    def test_one_verified_member(self):
        data = fixture([("data/force.csv", "x,y\n1,2\n"), ("data/distance.txt", "0 1")])
        found = gate.inspect_source(data, require_published_md5=False)
        self.assertEqual(found["file_count"], 2)
        self.assertEqual(found["compressed_bytes"], len(data))
        self.assertEqual(found["source_sha256_measured"], gate.sha256(data).hexdigest())
        self.assertEqual(found["status"], "SOURCE_ACCESS_GATE_PASS_PHYSICAL_UTILITY_HOLD")
        self.assertFalse(found["force_curve_interpreted"])
        self.assertFalse(found["physical_hold_slide_accepted"])
        self.assertEqual(found["deployment"], "NO_DEPLOY")
        self.assertEqual(found["rights_for_commercial_use"], "UNVERIFIED")
        self.assertFalse(found["native_financial_account_opened"])

    def test_published_digest_rejects_any_other_zip(self):
        data = fixture([("data.csv", "42")])
        if md5(data).hexdigest() == gate.EXPECTED_MD5:
            self.fail("test fixture unexpectedly equals published archive")
        with self.assertRaisesRegex(gate.SourceGateError, "MD5_MISMATCH"):
            gate.inspect_source(data)

    def test_traversal_name_rejected(self):
        for name in ("../escape.csv", "data/../../escape", "/root.txt", "C:/disk/file.txt", "a\\b.txt", "a/./b.txt", "a//b.txt"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(gate.SourceGateError, "UNSAFE"):
                    gate.inspect_source(fixture([(name, "x")]), require_published_md5=False)

    def test_casefold_duplicate_rejected(self):
        with self.assertRaisesRegex(gate.SourceGateError, "DUPLICATE"):
            gate.inspect_source(fixture([("X.csv", "a"), ("x.csv", "b")]), require_published_md5=False)

    def test_unix_symlink_rejected(self):
        info = ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(gate.SourceGateError, "SYMLINK"):
            gate.inspect_source(fixture([(info, "../target")]), require_published_md5=False)

    def test_broken_archive_rejected(self):
        with self.assertRaisesRegex(gate.SourceGateError, "ZIP_CORRUPT"):
            gate.inspect_source(b"not a zip", require_published_md5=False)

    def test_crc_changed_without_rewriting_directory_rejected(self):
        data = bytearray(fixture([("p.txt", "ORIGINAL")], compression=ZIP_STORED))
        offset = data.find(b"ORIGINAL")
        self.assertGreater(offset, 0)
        data[offset] ^= 1
        with self.assertRaisesRegex(gate.SourceGateError, "ZIP_CORRUPT"):
            gate.inspect_source(bytes(data), require_published_md5=False)

    def test_nested_archive_opaque(self):
        inner = fixture([("real.csv", "z")])
        outer = fixture([("data.zip", inner)])
        report = gate.inspect_source(outer, require_published_md5=False)
        self.assertEqual(report["opaque_nested_archive_count"], 1)
        self.assertEqual(report["file_count"], 1)
        self.assertFalse(report["force_curve_interpreted"])

    def test_excessive_members_rejected(self):
        with self.assertRaisesRegex(gate.SourceGateError, "ZIP_MEMBER_COUNT"):
            gate.inspect_source(
                fixture([(f"x{i:04d}.txt", "") for i in range(gate.MAX_MEMBERS + 1)]),
                require_published_md5=False
            )

    def test_empty_archive_rejected(self):
        with self.assertRaisesRegex(gate.SourceGateError, "ZIP_MEMBER_COUNT"):
            gate.inspect_source(fixture([]), require_published_md5=False)

    def test_transfer_limit_enforced_before_zip_parse(self):
        with self.assertRaisesRegex(gate.SourceGateError, "SOURCE_SIZE"):
            gate.inspect_source(b"x" * (gate.MAX_TRANSFER + 1), require_published_md5=False)

    def test_compression_bomb_rejected(self):
        with self.assertRaisesRegex(gate.SourceGateError, "ZIP_MEMBER_RATIO"):
            gate.inspect_source(fixture([("repetitive.txt", "0" * (5 * 1024 * 1024))]), require_published_md5=False)

    def test_no_implicit_revenue_or_calibration_claim(self):
        result = gate.inspect_source(fixture([("observations.csv", "1,2")]), require_published_md5=False)
        self.assertEqual(result["real_earnings"], 0)
        self.assertEqual(result["buyer_demand"], "UNKNOWN")
        self.assertFalse(result["physical_hold_slide_accepted"])


if __name__ == "__main__":
    unittest.main()
