import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('transport011',ROOT/'scripts/reassemble_enterprise011.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class PackageTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('source/receipt.json','{"scope":"SIMULATED"}')
        raw=stream.getvalue();a,b=raw[:70],raw[70:]
        self.parts=[]
        offset=0
        for i,part in enumerate([a,b]):
            name=f'part-{i:03d}.bin';(self.root/name).write_bytes(part)
            self.parts.append({'path':name,'offset':offset,'bytes':len(part),'sha256':hashlib.sha256(part).hexdigest()});offset+=len(part)
        self.data={'schema':'agi-alpha/enterprise011-package-parts/v1','archive_filename':'evidence.zip','archive_bytes':len(raw),'archive_sha256':hashlib.sha256(raw).hexdigest(),'parts':self.parts}
        self.manifest=self.root/'INDEX.json';self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):self.manifest.write_text(json.dumps(self.data))
    def test_exact_zip_and_no_overwrite(self):
        output=self.root/'out.zip';receipt=module.reassemble(self.manifest,output)
        self.assertEqual(receipt['sha256'],self.data['archive_sha256'])
        with self.assertRaises(FileExistsError):module.reassemble(self.manifest,output)
    def test_tampered_or_missing_part_does_not_publish(self):
        part=self.root/'part-001.bin';part.write_bytes(b'x'*part.stat().st_size)
        with self.assertRaisesRegex(ValueError,'PART_HASH'):module.reassemble(self.manifest,self.root/'bad.zip')
        self.assertFalse((self.root/'bad.zip').exists());part.unlink()
        with self.assertRaises(ValueError):module.reassemble(self.manifest,self.root/'bad.zip')
    def test_duplicate_reordered_or_path_escape_refused(self):
        for key,value in [('path','../escape'),('offset',0),('path','part-000.bin')]:
            original=self.data['parts'][1][key];self.data['parts'][1][key]=value;self.save()
            with self.assertRaises(ValueError):module.reassemble(self.manifest,self.root/'bad.zip')
            self.data['parts'][1][key]=original
    def test_complete_hash_and_symlink_refused(self):
        self.data['archive_sha256']='0'*64;self.save()
        with self.assertRaisesRegex(ValueError,'COMPLETE_ARCHIVE'):module.reassemble(self.manifest,self.root/'bad.zip')
        link=self.root/'linked.json';link.symlink_to(self.manifest)
        with self.assertRaises(ValueError):module.reassemble(link,self.root/'bad.zip')
