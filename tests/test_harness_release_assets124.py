"""Frozen HARNESS124 publish-asset preflight regressions; synthetic bytes only."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.harness_release_assets124 import MANIFEST, prepare

SHA = "68c2c1a00c78579b76788955a87f74dace8cc404"


class PublishAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / "received"
        self.assets.mkdir()
        self.paths0 = self.root / "paths0"

    def put(self, name, payload):
        path = self.assets / name
        path.write_bytes(payload)
        return path

    def test_01_full_nonempty_inventory_unmodified_and_shell_safe(self):
        p = self.put("ALPHA_source.zip", b"source-archive-unique")
        stderr = self.put("Darwin-probe.stderr.txt", b"material_failure")
        result = prepare(self.assets, SHA, self.paths0)
        assert [x["name"] for x in result["included"]] == ["ALPHA_source.zip", "Darwin-probe.stderr.txt"]
        assert result["omitted_only_empty_stderr"] == []
        assert result["included"][0]["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
        names = [Path(x.decode()).name for x in self.paths0.read_bytes().split(b"\0") if x]
        assert names == ["ALPHA_source.zip", "Darwin-probe.stderr.txt", MANIFEST]
        assert stderr.read_bytes() == b"material_failure"
        assert json.loads((self.assets / MANIFEST).read_text()) == result

    def test_02_skip_only_empty_stderr_while_retaining_hosted_evidence(self):
        self.put("ALPHA_source.zip", b"valid")
        empty = self.put("Darwin-probe.stderr.txt", b"")
        keep = self.put("Windows-probe.stderr.txt", b"real-error")
        result = prepare(self.assets, SHA, self.paths0)
        assert result["omitted_only_empty_stderr"] == [
            {"name": empty.name, "size": 0, "reason": "EMPTY_OPTIONAL_STDERR"}
        ]
        assert keep.name in [item["name"] for item in result["included"]]
        assert empty.exists() and empty.stat().st_size == 0
        assert empty.name.encode() not in self.paths0.read_bytes()

    def test_03_empty_required_fails_before_any_manifest_or_release_list(self):
        self.put("ALPHA_source.zip", b"")
        self.put("Darwin-probe.stderr.txt", b"")
        with self.assertRaisesRegex(ValueError, "EMPTY_REQUIRED_RELEASE_ASSET"):
            prepare(self.assets, SHA, self.paths0)
        assert not (self.assets / MANIFEST).exists()
        assert not self.paths0.exists()

    def test_04_symlink_nested_and_unsafe_names_rejected(self):
        for kind in ("symlink", "nested", "unsafe"):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as tmp:
                    d = Path(tmp) / "assets"
                    d.mkdir()
                    (d / "source.zip").write_bytes(b"okay")
                    if kind == "symlink":
                        (d / "other.txt").symlink_to(d / "source.zip")
                    elif kind == "nested":
                        (d / "subdir").mkdir()
                    else:
                        (d / "bad\nname.txt").write_bytes(b"content")
                    with self.assertRaises(ValueError):
                        prepare(d, SHA, Path(tmp) / "paths0")
                    assert not (d / MANIFEST).exists()

    def test_05_existing_output_invalid_source_and_zero_selected_fail(self):
        self.put("ALPHA_source.zip", b"valid")
        with self.assertRaisesRegex(ValueError, "EXACT_COMMIT_SHA_REQUIRED"):
            prepare(self.assets, "stale", self.paths0)
        self.paths0.write_bytes(b"existing")
        with self.assertRaisesRegex(ValueError, "PREEXISTING_ASSET_PATH_LIST"):
            prepare(self.assets, SHA, self.paths0)
        self.paths0.unlink()
        (self.assets / "ALPHA_source.zip").unlink()
        self.put("Darwin-probe.stderr.txt", b"")
        with self.assertRaisesRegex(ValueError, "NONEMPTY_SOURCE_ARCHIVE_REQUIRED"):
            prepare(self.assets, SHA, self.paths0)


if __name__ == "__main__":
    unittest.main()
