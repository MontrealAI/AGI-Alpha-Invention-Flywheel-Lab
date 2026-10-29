import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from flywheel.baseline005 import materialize, ARCHIVE_PATH, ARCHIVE_SHA256, FREEZE_SHA256

ROOT = Path(__file__).resolve().parents[1]


class Baseline005Tests(unittest.TestCase):
    def test_exact_snapshot_without_metadata_or_history(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            destination = Path(temporary)/'snapshot'
            receipt = materialize(ROOT, destination)
            self.assertEqual(receipt['archive_sha256'], ARCHIVE_SHA256)
            self.assertEqual(hashlib.sha256((destination/'campaign/cycle-005/FREEZE.json').read_bytes()).hexdigest(), FREEZE_SHA256)
            self.assertEqual(len(receipt['sources']), 50)
            for name, expected in receipt['sources'].items():
                self.assertEqual(hashlib.sha256((destination/name).read_bytes()).hexdigest(), expected)
            self.assertFalse((destination/'ARCHIVE_MANIFEST.json').exists())
            self.assertFalse((destination/'.git').exists())
            with self.assertRaises(FileExistsError):
                materialize(ROOT, destination)

    def test_missing_and_corrupt_input_refuse_before_output(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            root = Path(temporary)
            destination = root/'snapshot'
            with self.assertRaisesRegex(ValueError, 'BASELINE005_ARCHIVE_MISSING_OR_SYMLINK'):
                materialize(root, destination)
            self.assertFalse(destination.exists())
            archive = root/ARCHIVE_PATH
            archive.parent.mkdir(parents=True)
            shutil.copyfile(ROOT/ARCHIVE_PATH, archive)
            with archive.open('r+b') as stream:
                stream.seek(100); byte = stream.read(1); stream.seek(100); stream.write(bytes([byte[0]^1]))
            with self.assertRaisesRegex(ValueError, 'BASELINE005_ARCHIVE_IDENTITY_MISMATCH'):
                materialize(root, destination)
            self.assertFalse(destination.exists())
