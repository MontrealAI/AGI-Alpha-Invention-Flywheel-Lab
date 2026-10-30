import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('adaptive_transport',ROOT/'scripts/reassemble_enterprise011.py')
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)


class AdaptiveTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.manifest=self.root/'INDEX.json';self.prepare()

    def tearDown(self):self.temp.cleanup()

    def prepare(self,*,key=False,corrupt_crc=False):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr('source/REPORT.json',b'{"scope":"SIMULATED"}')
            if key:archive.writestr('source/live-account.adaptive-simulation-key',b'simulation-only-secret')
        raw=stream.getvalue()
        if corrupt_crc:raw=raw.replace(b'SIMULATED',b'SIMULATEE',1)
        self.raw=raw;parts=[];offset=0
        for index,piece in enumerate([raw[:70],raw[70:]]):
            name=f'part-{index:03d}.bin';(self.root/name).write_bytes(piece)
            parts.append({'path':name,'offset':offset,'bytes':len(piece),'sha256':hashlib.sha256(piece).hexdigest()});offset+=len(piece)
        self.data={'schema':'agi-alpha/adaptive012-package-parts/v1','archive_filename':'adaptive012.zip','archive_bytes':len(raw),'archive_sha256':hashlib.sha256(raw).hexdigest(),'parts':parts}
        self.save()

    def save(self):self.manifest.write_text(json.dumps(self.data))

    def test_new_namespace_exact_keyfree_zip_and_no_overwrite(self):
        output=self.root/'delivered.zip';receipt=transport.reassemble(self.manifest,output)
        self.assertEqual(output.read_bytes(),self.raw)
        self.assertEqual(receipt['sha256'],self.data['archive_sha256'])
        self.assertEqual(receipt['parts_verified'],2)
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertFalse(any(name.endswith('.adaptive-simulation-key') for name in archive.namelist()))
        with self.assertRaises(FileExistsError):transport.reassemble(self.manifest,output)

    def test_reordered_duplicate_offsets_and_escape_paths_refused(self):
        for key,value in [('path','../part-001.bin'),('path','part-000.bin'),('offset',0),('offset',71)]:
            self.prepare();self.data['parts'][1][key]=value;self.save()
            with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'ORDERED_UNIQUE_CONTIGUOUS'):
                transport.reassemble(self.manifest,self.root/'bad.zip')
            self.assertFalse((self.root/'bad.zip').exists())

    def test_part_and_complete_hash_tampering_never_publishes(self):
        part=self.root/'part-001.bin';part.write_bytes(b'x'*part.stat().st_size)
        with self.assertRaisesRegex(ValueError,'PART_HASH'):transport.reassemble(self.manifest,self.root/'bad.zip')
        self.prepare();self.data['archive_sha256']='0'*64;self.save()
        with self.assertRaisesRegex(ValueError,'COMPLETE_ARCHIVE_HASH'):transport.reassemble(self.manifest,self.root/'bad.zip')
        self.assertFalse((self.root/'bad.zip').exists())

    def test_rehashed_zip_with_bad_crc_is_rejected(self):
        self.prepare(corrupt_crc=True)
        with self.assertRaises((ValueError,zipfile.BadZipFile)):transport.reassemble(self.manifest,self.root/'bad.zip')
        self.assertFalse((self.root/'bad.zip').exists())

    def test_valid_hashes_cannot_publish_live_simulation_key(self):
        self.prepare(key=True)
        with self.assertRaisesRegex(ValueError,'PRIVATE_SIMULATION_KEY_PUBLICATION_REFUSED'):
            transport.reassemble(self.manifest,self.root/'bad.zip')
        self.assertFalse((self.root/'bad.zip').exists())
        self.assertEqual(list(self.root.glob('enterprise011-pending-*')),[])

    def test_unsupported_namespace_and_symlink_refused(self):
        self.data['schema']='agi-alpha/arbitrary/v1';self.save()
        with self.assertRaisesRegex(ValueError,'EXACT_PART_MANIFEST_SCHEMA'):
            transport.reassemble(self.manifest,self.root/'bad.zip')
        link=self.root/'alias.json';link.symlink_to(self.manifest)
        with self.assertRaisesRegex(ValueError,'REGULAR_PART_MANIFEST'):
            transport.reassemble(link,self.root/'bad.zip')


if __name__=='__main__':unittest.main()
