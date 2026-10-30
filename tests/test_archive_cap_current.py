import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from flywheel import archive_v2

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_SHA256 = 'e80512aa0e06503c8e49c78c43f09e786df1ba51ee26c3bb36b52ab703328007'


class CurrentArchiveCapTests(unittest.TestCase):
    def test_current_transport_bounds_are_explicit(self):
        self.assertEqual(archive_v2.MAX_BYTES, 512 * 1024**2)
        self.assertEqual(archive_v2.MAX_FILES, 10000)

    def test_actual_over_cap_source_bytes_refused_before_archive_creation(self):
        with tempfile.TemporaryDirectory(prefix='alpha-archive-byte-cap-') as folder:
            root=Path(folder)/'source';root.mkdir()
            with (root/'oversized-sparse-input.bin').open('wb') as stream:
                stream.truncate(512 * 1024**2 + 1)
            target=Path(folder)/'refused.zip'
            with self.assertRaisesRegex(ValueError,'ARCHIVE_RESOURCE_BOUND'):
                archive_v2.build(root,target)
            self.assertFalse(target.exists())

    def test_original_250mib_counterexample_and_source_identity_preserved(self):
        path=ROOT/'historical/cycle-006/archive_v2.py.txt'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),ORIGINAL_SHA256)
        namespace={'__name__':'original_archive_v2_transport_test'}
        exec(compile(path.read_bytes(),str(path),'exec'),namespace)
        self.assertEqual(namespace['MAX_BYTES'],250 * 1024**2)
        with tempfile.TemporaryDirectory(prefix='alpha-original-archive-bound-') as folder:
            root=Path(folder)/'source';root.mkdir()
            with (root/'old-bound-counterexample.bin').open('wb') as stream:
                stream.truncate(250 * 1024**2 + 1)
            target=Path(folder)/'original-refused.zip'
            with self.assertRaisesRegex(ValueError,'ARCHIVE_RESOURCE_BOUND'):
                namespace['build'](root,target)
            self.assertFalse(target.exists())

    def test_reserved_transaction_staging_is_not_published_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source';source.mkdir()
            (source/'published').mkdir();(source/'published/result.json').write_text('preserve')
            stage=source/'.commercial010-package-fixture';stage.mkdir()
            (stage/'uncommitted-copy.bin').write_text('transaction staging only')
            result=archive_v2.build(source,Path(folder)/'source.zip')
            self.assertEqual(set(result['manifest']['files']),{'published/result.json'})
