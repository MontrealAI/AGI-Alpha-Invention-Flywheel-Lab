import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from flywheel import archive_v2
from flywheel.reproduction006 import FREEZE, FREEZE_SHA256, SNAPSHOTS, materialize

ROOT = Path(__file__).resolve().parents[1]
PART = 'artifacts/enterprise011-parts/part-001.bin'
COMBINED = 'artifacts/AGI_ALPHA_Enterprise_011_source_evidence.zip'


class ArchiveTransport011Tests(unittest.TestCase):
    def test_only_completed_enterprise_transport_is_omitted(self):
        keep = {
            'enterprise/model.py': b'current source',
            'evidence/cycle-006/artifacts/release.zip': b'historical evidence',
            'historical/cycle-006/original.txt': b'historical source',
            'artifacts/earlier-release.zip': b'other artifact',
            'artifacts/ENTERPRISE011_PACKAGE.json': b'package provenance retained',
            'artifacts/enterprise011-parts-v2/keep.txt': b'lookalike name retained',
            'other/enterprise011-parts/keep.txt': b'other directory retained',
            'nested/artifacts/enterprise011-parts/keep.txt': b'only root transport omitted',
        }
        with tempfile.TemporaryDirectory() as tmp:
            root, source = Path(tmp), Path(tmp) / 'source'
            for name, raw in {**keep, PART: b'opaque new transport', COMBINED: b'opaque combined transport'}.items():
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            result = archive_v2.build(source, root / 'bounded.zip')
            self.assertEqual(set(result['manifest']['files']), set(keep))
            self.assertEqual(result['files'], len(keep))
            extracted = root / 'unpacked'
            archive_v2.extract(root / 'bounded.zip', extracted)
            self.assertEqual({str(p.relative_to(extracted)) for p in extracted.rglob('*') if p.is_file()}, set(keep))
            for name, raw in keep.items():
                self.assertEqual((extracted / name).read_bytes(), raw)
            self.assertFalse((extracted / PART).exists())
            self.assertFalse((extracted / COMBINED).exists())

    def test_current_caps_apply_to_retained_payloads(self):
        self.assertEqual(archive_v2.MAX_BYTES, 512 * 1024**2)
        self.assertEqual(archive_v2.MAX_FILES, 10000)
        with tempfile.TemporaryDirectory() as tmp:
            root, source = Path(tmp), Path(tmp) / 'source'
            source.mkdir()
            (source / 'retained.txt').write_bytes(b'x' * 21)
            with patch.object(archive_v2, 'MAX_BYTES', 20):
                with self.assertRaisesRegex(ValueError, 'ARCHIVE_RESOURCE_BOUND'):
                    archive_v2.build(source, root / 'too-large.zip')
            self.assertFalse((root / 'too-large.zip').exists())
            (source / 'second.txt').write_bytes(b'y')
            with patch.object(archive_v2, 'MAX_FILES', 1):
                with self.assertRaisesRegex(ValueError, 'ARCHIVE_RESOURCE_BOUND'):
                    archive_v2.build(source, root / 'too-many.zip')
            self.assertFalse((root / 'too-many.zip').exists())

    def test_existing_archive_transport_is_still_verified_and_extractable(self):
        payloads = {'enterprise/current.py': b'current code', PART: b'previously included opaque transport'}
        manifest = {'schema': 'lab/self-contained-source-archive/v2',
                    'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, corrupt in [('good', False), ('corrupt', True)]:
                with zipfile.ZipFile(root / (name + '.zip'), 'x') as archive:
                    for path, raw in payloads.items():
                        archive.writestr(archive_v2.PREFIX + path, b'tampered' if corrupt and path == PART else raw)
                    archive.writestr(archive_v2.PREFIX + archive_v2.MANIFEST, json.dumps(manifest))
            archive_v2.extract(root / 'good.zip', root / 'good')
            self.assertEqual((root / 'good' / PART).read_bytes(), payloads[PART])
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_CONTENT_IDENTITY_MISMATCH'):
                archive_v2.extract(root / 'corrupt.zip', root / 'corrupt')
            self.assertFalse((root / 'corrupt').exists())

    def test_frozen6363_sources_restore_original_archiver_byte_for_byte(self):
        freeze_raw = (ROOT / FREEZE).read_bytes()
        self.assertEqual(hashlib.sha256(freeze_raw).hexdigest(), FREEZE_SHA256)
        frozen = json.loads(freeze_raw)
        expected = frozen['sources']['flywheel/archive_v2.py']
        historical = ROOT / SNAPSHOTS['flywheel/archive_v2.py']
        self.assertEqual(hashlib.sha256(historical.read_bytes()).hexdigest(), expected)
        namespace = {'__name__':'frozen_archive_transport011_policy'}
        exec(compile(historical.read_bytes(), str(historical), 'exec'), namespace)
        self.assertEqual(namespace['MAX_BYTES'], 250 * 1024**2)
        self.assertEqual(namespace['MAX_FILES'], 10000)
        self.assertNotEqual(hashlib.sha256((ROOT / 'flywheel/archive_v2.py').read_bytes()).hexdigest(), expected)
        with tempfile.TemporaryDirectory(prefix='transport011-frozen6363-', dir='/tmp') as tmp:
            destination = Path(tmp) / 'original'
            receipt = materialize(ROOT, destination)
            self.assertEqual(receipt['sources_checked'], 6363)
            self.assertEqual((destination / FREEZE).read_bytes(), freeze_raw)
            self.assertEqual((destination / 'flywheel/archive_v2.py').read_bytes(), historical.read_bytes())
            self.assertEqual(receipt['substituted_original_inputs']['flywheel/archive_v2.py']['sha256'], expected)
            self.assertEqual((destination / 'tests/test_archive_v2.py').read_bytes(),
                             (ROOT / SNAPSHOTS['tests/test_archive_v2.py']).read_bytes())
            for name, source_hash in frozen['sources'].items():
                self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), source_hash, name)


if __name__ == '__main__':
    unittest.main()
