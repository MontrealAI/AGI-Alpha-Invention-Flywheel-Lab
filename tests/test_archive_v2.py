import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from flywheel.archive_v2 import build, extract, materialize_cycle004, PREFIX
from flywheel.legacy import materialize

ROOT = Path(__file__).resolve().parents[1]


class ArchiveTests(unittest.TestCase):
    def test_no_git_legacy_snapshot_and_historical_replay_sources(self):
        with tempfile.TemporaryDirectory(prefix="alpha-no-git-", dir="/tmp") as temporary:
            root = Path(temporary)
            build(ROOT, root / "source.zip")
            extract(root / "source.zip", root / "unpacked")
            unpacked = root / "unpacked"
            self.assertFalse((unpacked / ".git").exists())
            self.assertFalse((root / ".git").exists())
            receipt = materialize(unpacked, root / "legacy")
            self.assertEqual(receipt["files"][".github/workflows/campaign.yml"]["sha256"],
                             "df1da7dfcd734f027015b0a6e83e393173261cf32bb27f0a1e2852e9efc090d7")
            old = materialize_cycle004(unpacked, root / "cycle004")
            self.assertEqual(len(old["paths"]), 23)
            freeze = json.loads((root / "cycle004/campaign/cycle-004/FREEZE.json").read_text())
            for name, expected in freeze["sources"].items():
                self.assertEqual(hashlib.sha256((root / "cycle004" / name).read_bytes()).hexdigest(), expected)
            with self.assertRaises(FileExistsError):
                extract(root / "source.zip", unpacked)
            with self.assertRaises(FileExistsError):
                materialize_cycle004(unpacked, root / "cycle004")
            historical = unpacked / "historical/cycle-001/campaign-workflow.yml.txt"
            saved = historical.read_bytes()
            historical.unlink()
            with self.assertRaisesRegex(ValueError, "LEGACY_HISTORICAL_INPUT_MISSING"):
                materialize(unpacked, root / "missing-workflow")
            historical.write_bytes(saved + b"corrupt")
            with self.assertRaisesRegex(ValueError, "LEGACY_IDENTITY_MISMATCH"):
                materialize(unpacked, root / "corrupt-workflow")
            self.assertFalse((root / "missing-workflow").exists())
            self.assertFalse((root / "corrupt-workflow").exists())

    def test_missing_and_corrupt_historical_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / "historical", root / "historical")
            leaf = root / "historical/cycle-004/files/flywheel/legacy.py.txt"
            saved = leaf.read_bytes()
            leaf.unlink()
            with self.assertRaisesRegex(ValueError, "HISTORICAL_INPUT_MISSING"):
                materialize_cycle004(root, root / "out")
            self.assertFalse((root / "out").exists())
            leaf.write_bytes(saved + b"corrupt")
            with self.assertRaisesRegex(ValueError, "HISTORICAL_SOURCE_IDENTITY_MISMATCH"):
                materialize_cycle004(root, root / "out")

    def test_corruption_and_path_escape_refuse_before_extract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "one.txt").write_text("original")
            build(source, root / "good.zip")
            with self.assertRaises(FileExistsError):
                build(source, root / "good.zip")
            with zipfile.ZipFile(root / "good.zip") as archive, zipfile.ZipFile(root / "bad.zip", "x") as bad:
                for item in archive.infolist():
                    bad.writestr(item, b"corrupt" if item.filename.endswith("one.txt") else archive.read(item))
            with self.assertRaisesRegex(ValueError, "ARCHIVE_CONTENT_IDENTITY_MISMATCH"):
                extract(root / "bad.zip", root / "bad-out")
            with zipfile.ZipFile(root / "escape.zip", "x") as archive:
                archive.writestr(PREFIX + "../escaped.txt", "no")
            with self.assertRaisesRegex(ValueError, "ARCHIVE_PATH_SCOPE"):
                extract(root / "escape.zip", root / "escape-out")
            self.assertFalse((root / "bad-out").exists())
            self.assertFalse((root / "escape-out").exists())


if __name__ == "__main__":
    unittest.main()
