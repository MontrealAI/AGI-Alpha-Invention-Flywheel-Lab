import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

from scripts.archive_commercial010_evidence import archive, canonical, digest_file, extract, reassemble, validate_index


class Commercial010ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='commercial010-publication-unit-')
        self.root = Path(self.tmp.name)
        self.old, self.new = self.root / 'old', self.root / 'new'
        self.old.mkdir()
        (self.new / 'artifacts').mkdir(parents=True)
        (self.old / 'PENDING.json').write_text('{"state":"pending","scope":"UNIT_TEST_ONLY"}\n')
        (self.old / 'empty').mkdir()
        (self.old / 'partial.sqlite').write_bytes(b'\x00\xff\x17SQLite fixture, not commercial evidence')
        (self.new / 'artifacts/RESULT.json').write_text('{"scope":"UNIT_TEST_ONLY"}\n')
        (self.new / 'stdout.log').write_bytes(b'original raw log\n')
        (self.new / 'RECEIPT.json').write_bytes(canonical({'state': 'complete', 'descendant_survivors': False}))
        (self.new / 'RECOVERY_PROGRESS.jsonl').write_text('{"scope":"UNIT_TEST_ONLY"}\n')
        self.freeze = 'e' * 64
        (self.new / 'RECOVERY.json').write_bytes(canonical({
            'schema': 'agi-alpha/commercial010-recovery/v1', 'scope': 'SIMULATED_ENGINEERING_RECOVERY',
            'candidate_changes': False, 'seed_substitutions': False, 'parameter_adaptations': False,
            'source_freeze_sha256': self.freeze, 'interruption_inventory_sha256': 'f' * 64,
            'result_sha256': digest_file(self.new / 'artifacts/RESULT.json'),
            'progress_sha256': digest_file(self.new / 'RECOVERY_PROGRESS.jsonl')}))

    def tearDown(self):
        self.tmp.cleanup()

    def pack(self, suffix='parts'):
        path = self.root / suffix
        result = archive(self.old, self.new, path, self.freeze)
        return path, result

    def test_lossless_binary_logs_empty_dirs_and_deterministic_zip(self):
        parts, first = self.pack()
        other, second = self.pack('other-parts')
        a, b = json.loads((parts / 'INDEX.json').read_text()), json.loads((other / 'INDEX.json').read_text())
        self.assertEqual(a['archive_sha256'], b['archive_sha256'])
        self.assertEqual(first['index_sha256'], second['index_sha256'])
        restored = self.root / 'restored'
        extract(parts / 'INDEX.json', restored, first['index_sha256'])
        self.assertTrue((restored / 'original/empty').is_dir())
        for prefix, original in [('original', self.old), ('resumed', self.new)]:
            for path in original.rglob('*'):
                if path.is_file():
                    copy = restored / prefix / path.relative_to(original)
                    self.assertEqual(path.read_bytes(), copy.read_bytes())
                    self.assertEqual(int(copy.stat().st_mtime), 315532800)

    def test_part_limit_order_and_corruption_rejection(self):
        (self.old / 'incompressible.bin').write_bytes(random.Random(10).randbytes(650000))
        parts, _ = self.pack()
        index = json.loads((parts / 'INDEX.json').read_text())
        self.assertGreaterEqual(len(index['parts']), 2)
        self.assertTrue(all(p['bytes'] <= 600000 for p in index['parts']))
        output = self.root / 'complete.zip'
        reassemble(parts / 'INDEX.json', output)
        self.assertEqual(digest_file(output), index['archive_sha256'])
        part = parts / index['parts'][0]['filename']
        raw = part.read_bytes()
        part.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        refused = self.root / 'bad.zip'
        with self.assertRaises(ValueError):
            reassemble(parts / 'INDEX.json', refused)
        self.assertFalse(refused.exists())

    def test_existing_outputs_are_never_overwritten(self):
        parts, _ = self.pack()
        existing = self.root / 'existing.zip'
        existing.write_bytes(b'KEEP')
        with self.assertRaises(FileExistsError):
            reassemble(parts / 'INDEX.json', existing)
        self.assertEqual(existing.read_bytes(), b'KEEP')
        with self.assertRaises(FileExistsError):
            archive(self.old, self.new, parts, self.freeze)

    def test_unsafe_or_duplicate_entry_paths_refused(self):
        parts, _ = self.pack()
        base = json.loads((parts / 'INDEX.json').read_text())
        for name in ['../outside', '/absolute', 'original/../outside', 'original\\outside', 'C:outside']:
            mutated = copy.deepcopy(base)
            mutated['entries'][0]['path'] = name
            path = self.root / 'mutated.json'
            path.write_bytes(canonical(mutated))
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_index(path)
        mutated = copy.deepcopy(base)
        mutated['entries'].append(mutated['entries'][0])
        path.write_bytes(canonical(mutated))
        with self.assertRaises(ValueError):
            validate_index(path)

    def test_incomplete_run_or_changed_aggregate_cannot_be_packaged(self):
        receipt = self.new / 'RECEIPT.json'
        receipt.write_bytes(canonical({'state': 'pending', 'descendant_survivors': False}))
        with self.assertRaises(ValueError):
            self.pack()
        self.assertFalse((self.root / 'parts').exists())
        receipt.write_bytes(canonical({'state': 'complete', 'descendant_survivors': False}))
        (self.new / 'artifacts/RESULT.json').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.pack()
        self.assertFalse((self.root / 'parts').exists())

    def test_index_part_reordering_or_external_identity_change_refused(self):
        parts, first = self.pack()
        with self.assertRaises(ValueError):
            reassemble(parts / 'INDEX.json', self.root / 'refused.zip', '0' * 64)
        index = json.loads((parts / 'INDEX.json').read_text())
        index['parts'][0]['order'] = 1
        (parts / 'INDEX.json').write_bytes(canonical(index))
        with self.assertRaises(ValueError):
            validate_index(parts / 'INDEX.json')


if __name__ == '__main__':
    unittest.main()
