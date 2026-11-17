"""Operate newly exported packages through their real offline CLI in fresh directories."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from ignition.construction import build, freeze_contract
from ignition.delivery import export_bundle
from ignition.evaluation import evaluate


def unpack(root, kind, definition, cases):
    frozen = freeze_contract({"kind": kind, "purpose": "Check recipient delivery against the supplied contract",
                              "definition": definition, "cases": cases})
    artifact = build(frozen, {"kind": kind, "program": definition})
    archive = export_bundle(frozen, artifact, evaluate(frozen, artifact))
    directory = root / kind
    directory.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        bundle.extractall(directory)
    return directory


def run(directory, *args, data=None):
    return subprocess.run([sys.executable, "-I", str(directory / "run.py"), *map(str, args)],
                          cwd=directory, input=data, capture_output=True, timeout=15)


@unittest.skipUnless(os.name == "posix", "descriptor-relative audit uses POSIX")
class RecipientDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.received = root / "received"
        (self.received / "nested").mkdir(parents=True)
        self.payload = (b"0123456789" * 300_000)  # Exceeds the entire original JSON transport limit.
        (self.received / "nested" / "large.bin").write_bytes(self.payload)
        (self.received / "entry.txt").write_bytes(b"entry")
        manifest = {"nested/large.bin": hashlib.sha256(self.payload).hexdigest(), "entry.txt": hashlib.sha256(b"entry").hexdigest()}
        self.package = unpack(root, "manifest_audit", {"manifest": manifest}, [{
            "name": "empty inventory", "input": {"files": {}},
            "expected": {"ok": False, "matched": [], "changed": [], "missing": sorted(manifest), "unexpected": []}}])

    def test_large_file_and_complete_mixed_fault_inventory(self):
        clean = run(self.package, "audit-directory", self.received)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertEqual(json.loads(clean.stdout), {"ok": True, "matched": ["entry.txt", "nested/large.bin"],
                                                    "missing": [], "changed": [], "unexpected": []})
        (self.received / "nested" / "large.bin").unlink()
        (self.received / "entry.txt").write_bytes(b"changed")
        (self.received / "extra.txt").write_bytes(b"added")
        changed = run(self.package, "audit-directory", self.received)
        self.assertEqual(changed.returncode, 1, changed.stderr)
        self.assertEqual(json.loads(changed.stdout), {"ok": False, "matched": [], "missing": ["nested/large.bin"],
                                                      "changed": ["entry.txt"], "unexpected": ["extra.txt"]})

    def test_links_special_files_and_traversal_are_refused(self):
        root = self.received.parent
        (root / "outside").write_bytes(b"private")
        link = self.received / "different"
        for create in (lambda: link.symlink_to(root / "outside"), lambda: link.symlink_to(root),
                       lambda: os.mkfifo(link), lambda: os.link(root / "outside", link)):
            create()
            result = run(self.package, "audit-directory", self.received)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            link.unlink()
        (root / "redirect").symlink_to(self.received, target_is_directory=True)
        for target in (root / "redirect", root / "redirect" / "nested", self.received / ".." / "received"):
            with self.subTest(target=target):
                self.assertEqual(run(self.package, "audit-directory", target).returncode, 2)
        self.assertEqual((root / "outside").read_bytes(), b"private")

    def test_refuses_unsafe_name_and_does_not_offer_wrong_family(self):
        (self.received / "a:b").touch()
        self.assertEqual(run(self.package, "audit-directory", self.received).returncode, 2)
        self.assertEqual(run(self.package, "migrate-jsonl", data=b"").returncode, 2)


class RecipientJsonLines(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.package = unpack(Path(self.tmp.name), "record_migration",
                              {"columns": [{"source": "key", "target": "id", "type": "integer"}], "extra_fields": "reject"},
                              [{"name": "one", "input": {"rows": [{"key": "28"}]}, "expected": {"rows": [{"id": 28}]}}])

    def test_stream_preserves_rows_and_accepts_unterminated_last_line(self):
        result = run(self.package, "migrate-jsonl", data=b'{"key":"8"}\n{"key":9}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [b'{"id":8}', b'{"id":9}'])
        self.assertEqual(run(self.package, "migrate-jsonl", data=b"").returncode, 0)
        self.assertEqual(run(self.package, "audit-directory", self.package).returncode, 2)

    def test_errors_preserve_only_preceding_rows(self):
        for bad in (b"\n", b"null\n", b'{"key":"02"}\n', b'{"key":3,"key":4}\n', b'{"key":"\xff"}\n',
                    b" " * (2 * 1024 * 1024 + 1)):
            with self.subTest(bad=bad[:30]):
                result = run(self.package, "migrate-jsonl", data=b'{"key":"7"}\n' + bad + b'{"key":"9"}\n')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b'{"id":7}\n')
                report = json.loads(result.stderr)
                self.assertEqual((report["line"], report["emitted"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
