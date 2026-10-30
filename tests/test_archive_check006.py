import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from verification.cycle006_archive_check import check, payloads, PREFIX


class DownloadedArchiveBoundaryTests(unittest.TestCase):
    def test_external_identity_and_payload_corruption_refuse_before_output(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            root = Path(temporary)
            archive, output = root / 'source.zip', root / 'report'
            raw = b'print("must never execute")'
            manifest = {'schema': 'lab/self-contained-source-archive/v2', 'files': {'run_cycle006.py': hashlib.sha256(raw).hexdigest()}}
            with zipfile.ZipFile(archive, 'x') as z:
                z.writestr(PREFIX + 'run_cycle006.py', raw)
                z.writestr(PREFIX + 'ARCHIVE_MANIFEST.json', json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'EXTERNAL_ARCHIVE_IDENTITY_MISMATCH'):
                check(archive, '0' * 64, output)
            self.assertFalse(output.exists())
            valid_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            receipt = check(archive, valid_digest, output, identity_only=True)
            self.assertTrue(receipt['identity_verified'])
            self.assertFalse(receipt['runtime_qualified'])
            self.assertEqual(receipt['checks'], {})
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_REPORT_DESTINATION_SCOPE'):
                check(archive, valid_digest, output, identity_only=True)
            corrupt = root / 'corrupt.zip'
            with zipfile.ZipFile(corrupt, 'x') as z:
                z.writestr(PREFIX + 'run_cycle006.py', b'changed')
                z.writestr(PREFIX + 'ARCHIVE_MANIFEST.json', json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_PAYLOAD_IDENTITY'):
                check(corrupt, hashlib.sha256(corrupt.read_bytes()).hexdigest(), root / 'refused')
            self.assertFalse((root / 'refused').exists())

    def test_digest_checked_bytes_survive_external_path_replacement(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            root = Path(temporary)
            archive, replacement = root / 'input.zip', root / 'replacement.zip'
            for target, name, content in [(archive, 'original.txt', b'original'), (replacement, 'changed.txt', b'changed')]:
                manifest = {'schema': 'lab/self-contained-source-archive/v2', 'files': {name: hashlib.sha256(content).hexdigest()}}
                with zipfile.ZipFile(target, 'x') as z:
                    z.writestr(PREFIX + name, content)
                    z.writestr(PREFIX + 'ARCHIVE_MANIFEST.json', json.dumps(manifest))
            verified_raw, replacement_raw = archive.read_bytes(), replacement.read_bytes()
            original_read = Path.read_bytes
            def replace_after_read(path):
                raw = original_read(path)
                if path == archive:
                    path.write_bytes(replacement_raw)
                return raw
            with mock.patch.object(Path, 'read_bytes', replace_after_read):
                data, _, snapshot = payloads(archive, hashlib.sha256(verified_raw).hexdigest())
            self.assertEqual(data, {'original.txt': b'original'})
            self.assertEqual(snapshot, verified_raw)
            self.assertEqual(archive.read_bytes(), replacement_raw)

    def test_path_escape_and_ambiguous_manifest_refuse(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            root = Path(temporary)
            for label, name, manifest, expected in [
                ('escape', '../outside', '{}', 'ARCHIVE_PATH_OR_DUPLICATE'),
                ('ambiguous', 'one', '{"schema":"x","schema":"y","files":{}}', 'ARCHIVE_DUPLICATE_JSON_KEY')]:
                with self.subTest(label=label):
                    archive = root / (label + '.zip')
                    with zipfile.ZipFile(archive, 'x') as z:
                        z.writestr(PREFIX + name, 'one')
                        z.writestr(PREFIX + 'ARCHIVE_MANIFEST.json', manifest)
                    with self.assertRaisesRegex(ValueError, expected):
                        payloads(archive, hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertFalse((root / 'outside').exists())
