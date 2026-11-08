#!/usr/bin/env python3
"""Negative tests for evidence inventory integrity and safe extraction."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import evidence


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = self.root / "source"
        for name in evidence.REQUIRED:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic inventory fixture: " + name)
        self.package = self.root / "package"
        evidence.create(source, self.package)

    def replace_archive(self, change):
        archive = self.package / "REPRODUCTION.tar.gz"
        rows = []
        with tarfile.open(archive) as previous:
            for member in previous:
                rows.append((member, previous.extractfile(member).read()))
        rows = change(rows)
        with tarfile.open(archive, "w:gz") as updated:
            for member, content in rows:
                updated.addfile(member, io.BytesIO(content) if member.isfile() else None)
        manifest_path = self.package / "EVIDENCE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["archive"].update(bytes=archive.stat().st_size, sha256=evidence.digest(archive))
        manifest_path.write_text(json.dumps(manifest))

    def test_exact_inventory_extracts(self):
        target = self.root / "extracted"
        receipt = evidence.verify(self.package, target)
        self.assertEqual(receipt["files"], len(evidence.REQUIRED))
        self.assertFalse(receipt["scientific_acceptance_checked"])
        self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}, evidence.REQUIRED)

    def test_changed_archive_rejected(self):
        path = self.package / "REPRODUCTION.tar.gz"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "identity"):
            evidence.verify(self.package)

    def test_missing_member_rejected_even_with_resealed_archive(self):
        self.replace_archive(lambda rows: rows[1:])
        with self.assertRaisesRegex(ValueError, "coverage"):
            evidence.verify(self.package)

    def test_content_change_rejected_even_with_resealed_archive(self):
        def modify(rows):
            member, contents = rows[0]
            rows[0] = (member, b"X" + contents[1:])
            return rows
        self.replace_archive(modify)
        with self.assertRaisesRegex(ValueError, "content"):
            evidence.verify(self.package)

    def test_duplicate_member_rejected(self):
        self.replace_archive(lambda rows: rows + [rows[0]])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evidence.verify(self.package)

    def test_symlink_rejected(self):
        def inject(rows):
            link = tarfile.TarInfo("surprise")
            link.type, link.linkname = tarfile.SYMTYPE, "../outside"
            return rows + [(link, b"")]
        self.replace_archive(inject)
        with self.assertRaisesRegex(ValueError, "nonregular"):
            evidence.verify(self.package, self.root / "extract")
        self.assertFalse((self.root / "outside").exists())

    def test_traversal_rejected(self):
        def inject(rows):
            member = tarfile.TarInfo("../outside")
            member.size = 1
            return rows + [(member, b"X")]
        self.replace_archive(inject)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            evidence.verify(self.package, self.root / "extract")
        self.assertFalse((self.root / "outside").exists())

    def test_required_coverage_cannot_be_removed_from_manifest(self):
        path = self.package / "EVIDENCE_MANIFEST.json"
        value = json.loads(path.read_text())
        value["files"] = value["files"][1:]
        value["file_count"] -= 1
        value["uncompressed_bytes"] = sum(row["bytes"] for row in value["files"])
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "Required"):
            evidence.verify(self.package)

    def test_existing_destination_preserved(self):
        target = self.root / "existing"
        target.mkdir()
        marker = target / "marker"
        marker.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "new absolute"):
            evidence.verify(self.package, target)
        self.assertEqual(marker.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
