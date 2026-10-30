import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from scripts.reassemble_evidence006 import reassemble


class EvidenceTransportTests(unittest.TestCase):
    def fixture(self, root):
        raw = b'PK-exact-evidence-bytes' * 100
        parts = [raw[:1000], raw[1000:]]
        rows = []
        for index, part in enumerate(parts):
            name = 'part-%03d.bin' % index
            (root / name).write_bytes(part)
            rows.append({'file': name, 'sha256': hashlib.sha256(part).hexdigest(), 'bytes': len(part)})
        expected = hashlib.sha256(raw).hexdigest()
        path = root / 'INDEX.json'
        path.write_text(json.dumps({'schema': 'agi-alpha/raw-evidence-multipart006/v1', 'archive_file': 'raw.zip',
            'archive_sha256': expected, 'archive_bytes': len(raw), 'parts': rows}))
        return raw, path, expected

    def test_roundtrip_and_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); raw, index, expected = self.fixture(root)
            output = root / 'whole.zip'
            self.assertFalse(reassemble(index, output, expected)['executed'])
            self.assertEqual(output.read_bytes(), raw)
            with self.assertRaises(FileExistsError): reassemble(index, output, expected)
            self.assertEqual(output.read_bytes(), raw)

    def test_corruption_and_symlink_refused_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); unused, index, expected = self.fixture(root)
            part = root / 'part-000.bin'; original = part.read_bytes(); part.write_bytes(b'x' * len(original))
            with self.assertRaisesRegex(ValueError, 'IDENTITY_MISMATCH'): reassemble(index, root / 'whole.zip', expected)
            self.assertFalse((root / 'whole.zip').exists())
            real = root / 'actual.bin'; real.write_bytes(original); part.unlink(); part.symlink_to(real)
            with self.assertRaisesRegex(ValueError, 'SYMLINK'): reassemble(index, root / 'whole.zip', expected)

    def test_nonregular_index_refused_without_blocking(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); fifo = root / 'fifo'; os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, 'REGULAR_FILE'):
                reassemble(fifo, root / 'whole.zip', '0' * 64)

    def test_wrong_whole_pin_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); unused, index, expected = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'WHOLE_IDENTITY'): reassemble(index, root / 'whole.zip', '0' * 64)


if __name__ == '__main__': unittest.main()
