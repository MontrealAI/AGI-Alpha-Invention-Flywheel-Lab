"""Offline, adversarial tests for frozen EIT192 live-archive metadata protocol."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile, ZIP_STORED

from tools.eit_live_source192 import choose_target, qualify_archive, Refusal
from tools.eit_live_source192 import TARGET
from tools.eit_zip_metadata192 import parse_appledouble


MEMBER = "__MACOSX/A/._x.mat"


def apple_double(payload=b"RES"):
    # Real AppleDouble-v2 signature with observed original macOS filler variant.
    header = struct.pack(">II16sH", 0x00051607, 0x00020000, b"Mac OS X        ", 1)
    descriptor = struct.pack(">III", 2, 38, len(payload))
    return header + descriptor + payload


class Source192LiveTests(unittest.TestCase):
    def test_exact_record_list_schema(self):
        record = {"id": 24120439, "files": [
            {"key": TARGET, "size": 42, "checksum": "md5:" + "a" * 32},
            {"key": "different.zip", "size": 6, "checksum": "md5:" + "b" * 32},
        ]}
        self.assertEqual(choose_target(record), (42, "a" * 32))

    def test_exact_record_dict_schema(self):
        record = {"id": "24120439", "files": {"entries": {
            TARGET: {"key": TARGET, "size": 5, "checksum": "md5:" + "C" * 32},
        }}}
        self.assertEqual(choose_target(record), (5, "c" * 32))

    def test_malformed_manifest_fails_no_fallback(self):
        valid = {"id": 24120439, "files": [
            {"key": TARGET, "size": 5, "checksum": "md5:" + "c" * 32}]}
        for altered in (
            dict(valid, id=24120440),
            dict(valid, files=[]),
            dict(valid, files=valid["files"] * 2),
            dict(valid, files=[dict(valid["files"][0], size=0)]),
            dict(valid, files=[dict(valid["files"][0], checksum="sha256:123")]),
            dict(valid, files=[dict(valid["files"][0], checksum="md5:" + "g" * 32)]),
        ):
            with self.assertRaises(Refusal):
                choose_target(altered)

    def test_full_zip_crc_and_genuine_mat_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source.zip"
            raw = apple_double()
            with ZipFile(src, "w", ZIP_STORED) as z:
                z.writestr("A/x.mat", b"source-is-raw-never-executed")
                z.writestr(MEMBER, raw)
            result = qualify_archive(
                src, historical_member=MEMBER,
                historical_sha=hashlib.sha256(raw).hexdigest(),
                historical_header=raw[:16].hex())
            self.assertEqual(result["genuine_matlab_candidates"], ["A/x.mat"])
            self.assertEqual(result["all_original_entry_count"], 2)
            self.assertTrue(result["full_zip_crc_validated"])
            self.assertTrue(result["sidecars"][0]["counterpart_present"])
            self.assertFalse(result["semantic_matlab_inventory_completed"])

    def test_failure_is_not_silently_repaired_by_picking_other_member(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source.zip"
            raw = apple_double()
            with ZipFile(src, "w") as z:
                z.writestr("A/x.mat", b"original-mat")
                z.writestr(MEMBER, raw)
            sha = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(Refusal, "SHA_CHANGED"):
                qualify_archive(src, historical_member=MEMBER,
                                historical_sha="0" * 64,
                                historical_header=raw[:16].hex())
            with self.assertRaisesRegex(Refusal, "HEADER_CHANGED"):
                qualify_archive(src, historical_member=MEMBER,
                                historical_sha=sha, historical_header="00" * 16)
            with self.assertRaisesRegex(Refusal, "SIDECAR_ABSENT"):
                qualify_archive(src)

    def test_crc_tamper_detected_before_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source.zip"
            raw = apple_double()
            with ZipFile(src, "w", ZIP_STORED) as z:
                z.writestr("A/x.mat", b"123456789-unique-payload")
                z.writestr(MEMBER, raw)
            data = src.read_bytes()
            self.assertEqual(data.count(b"123456789-unique-payload"), 1)
            src.write_bytes(data.replace(b"123456789-unique-payload",
                                         b"999999999-unique-payload"))
            with self.assertRaises(Exception) as error:
                qualify_archive(src, historical_member=MEMBER,
                                historical_sha=hashlib.sha256(raw).hexdigest(),
                                historical_header=raw[:16].hex())
            self.assertIsInstance(error.exception, Refusal)
            self.assertIn("EIT192_ZIP_CRC_FAILURE", str(error.exception))

    def test_bounded_uncompressed_member_with_signed_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source.zip"
            raw = apple_double()
            with ZipFile(src, "w") as z:
                z.writestr("A/x.mat", b"oversized")
                z.writestr(MEMBER, raw)
            with mock.patch("tools.eit_live_source192.MAX_MEMBER", 5):
                with self.assertRaisesRegex(Refusal, "MEMBER_SIZE_UNSAFE"):
                    qualify_archive(src, historical_member=MEMBER,
                                    historical_sha=hashlib.sha256(raw).hexdigest(),
                                    historical_header=raw[:16].hex())

    def test_typed_metadata_does_not_accept_arbitrary_filler(self):
        raw = bytearray(apple_double())
        raw[8] = ord("x")
        with self.assertRaisesRegex(Refusal, "FILLER_UNKNOWN"):
            parse_appledouble(raw)


if __name__ == "__main__":
    unittest.main()
