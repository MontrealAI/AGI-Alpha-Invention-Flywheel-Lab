"""Negative transport tests for the frozen Governance Portable141 research contract."""
from __future__ import annotations

import hashlib
import io
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from scripts.package_governance_impact141 import FILES, build, verify


COMMIT = "ee103269e64b0ca37fadea6747a283f7937d2624"


def sha(value):
    return hashlib.sha256(value).hexdigest()


class Portable141(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.archive = self.home / "package.zip"
        self.receipt = self.home / "receipt.json"
        self.repo = Path(__file__).resolve().parents[1]
        self.record = build(self.repo, self.archive, self.receipt, COMMIT)

    def valid_verify(self, path=None, **changes):
        opts = {
            "expected_sha256": self.record["archive_sha256"],
            "expected_manifest_sha256": self.record["manifest_sha256"],
            "expected_commit": COMMIT,
        }
        opts.update(changes)
        return verify(path or self.archive, **opts)

    def mutate(self, changes, extra=None):
        with zipfile.ZipFile(self.archive) as z:
            entries = [(i, z.read(i)) for i in z.infolist()]
        target = self.home / "mutated.zip"
        with zipfile.ZipFile(target, "w") as z:
            for info, data in entries:
                if info.filename not in changes:
                    z.writestr(info, data)
                elif changes[info.filename] is not None:
                    z.writestr(info, changes[info.filename])
            if extra is not None:
                name, data, mode = extra
                info = zipfile.ZipInfo(name)
                info.external_attr = mode << 16
                z.writestr(info, data)
        return target

    def test_clean_portable_extract_and_create_only(self):
        clean = self.home / "clean"
        result = self.valid_verify(extract=clean)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["file_count"], len(FILES) + 1)
        self.assertEqual(set(json.loads((clean / "MANIFEST.json").read_text())["files"]),
                         set(FILES))
        for path in FILES:
            self.assertEqual((clean / path).read_bytes(), (self.repo / path).read_bytes())
        with self.assertRaises(FileExistsError):
            self.valid_verify(extract=clean)
        with self.assertRaises(FileExistsError):
            build(self.repo, self.archive, self.receipt, COMMIT)

    def test_deterministic_archive(self):
        two = self.home / "two.zip"
        receipt = self.home / "two.json"
        other = build(self.repo, two, receipt, COMMIT)
        self.assertEqual(self.archive.read_bytes(), two.read_bytes())
        self.assertEqual(self.record, other)

    def test_invalid_external_or_commit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EXTERNAL_ARCHIVE_DIGEST_MISMATCH"):
            self.valid_verify(expected_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "VALID_COMMIT_REQUIRED"):
            self.valid_verify(expected_commit="wrong")
        with self.assertRaisesRegex(ValueError, "INVALID_PACKAGE_MANIFEST"):
            self.valid_verify(expected_commit="0" * 40)
        with self.assertRaisesRegex(ValueError, "EXTERNAL_MANIFEST_DIGEST_MISMATCH"):
            self.valid_verify(expected_manifest_sha256="0" * 64)

    def test_modified_source_rejected_even_when_zip_rehashed(self):
        name = "products/governance_impact140/engine.py"
        with zipfile.ZipFile(self.archive) as z:
            changed = z.read(name) + b"\n# hostile edit\n"
        target = self.mutate({name: changed})
        with self.assertRaisesRegex(ValueError, "ARCHIVE_SOURCE_HASH_MISMATCH"):
            self.valid_verify(target, expected_sha256=sha(target.read_bytes()))

    def test_path_traversal_rejected(self):
        target = self.mutate({}, extra=("../outside", b"oops", stat.S_IFREG | 0o644))
        with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE_PATH"):
            self.valid_verify(target, expected_sha256=sha(target.read_bytes()))

    def test_duplicate_archive_member_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            target = self.mutate({}, extra=(FILES[0], b"duplicate", stat.S_IFREG | 0o644))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ARCHIVE_MEMBER"):
            self.valid_verify(target, expected_sha256=sha(target.read_bytes()))

    def test_symlink_member_rejected(self):
        target = self.mutate({}, extra=("link", b"bad", stat.S_IFLNK | 0o777))
        with self.assertRaisesRegex(ValueError, "ARCHIVE_SYMLINK_FORBIDDEN"):
            self.valid_verify(target, expected_sha256=sha(target.read_bytes()))

    def test_missing_or_extra_member_rejected(self):
        target = self.mutate({FILES[0]: None})
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_ARCHIVE"):
            self.valid_verify(target, expected_sha256=sha(target.read_bytes()))
        target = self.mutate({}, extra=("untrusted.dat", b"oops", stat.S_IFREG | 0o644))
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_ARCHIVE_MEMBER"):
            self.valid_verify(target, expected_sha256=sha(target.read_bytes()))

    def test_no_private_source_or_native_ledger_in_allowlist(self):
        self.assertEqual(set(FILES), {
            "campaign/governance-portable141/PROTOCOL.md",
            "campaign/public-demand140/EVIDENCE_RECONCILIATION_20261112.md",
            "campaign/public-demand140/PROTOCOL.md",
            "products/governance_impact140/README.md",
            "products/governance_impact140/__init__.py",
            "products/governance_impact140/engine.py",
            "tests/test_governance_impact140.py",
        })
        self.assertFalse(any("account" in f.lower() or ".env" in f
                             or "private" in f.lower() for f in FILES))


if __name__ == "__main__":
    unittest.main()
