import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('completion015_transport',ROOT/'scripts/package_completion015_evidence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
INDEX=ROOT/'evidence/completion015/HISTORICAL_EVIDENCE.json'

class Completion015TransportTests(unittest.TestCase):
 def setUp(self):
  self.raw=INDEX.read_bytes();self.index=json.loads(self.raw);self.zip=(INDEX.parent/'HISTORICAL_EVIDENCE.zip').read_bytes()
 def test_exact_original_inventory(self):
  files=m.payloads(self.raw,self.zip)
  self.assertEqual(len(files),100);self.assertEqual(sum(map(len,files.values())),978038)
  self.assertEqual(self.index['source_commit'],'7d75766401adede49afd2427be82eb0302934b80')
  self.assertEqual(m.MAX_FILES,10000);self.assertEqual(m.MAX_BYTES,512*1024**2)
  for name,raw in files.items():
   self.assertFalse(name.endswith(('.py','.md')))
   self.assertNotIn('/qualification/',name);self.assertNotIn('/confirmation/',name)
   self.assertEqual(m.blob(raw),self.index['files'][name]['git_blob_sha1'])
 def test_extract_preserves_bytes_without_existing_tree_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'restored';self.assertEqual(m.extract(INDEX,out),100)
   for name,raw in m.verify(INDEX).items():self.assertEqual((out/name).read_bytes(),raw)
   with self.assertRaises(FileExistsError):m.extract(INDEX,out)
 def test_corrupt_transport_rejected(self):
  with self.assertRaisesRegex(ValueError,'TRANSPORT_IDENTITY'):m.payloads(self.raw,self.zip[:-1]+bytes([self.zip[-1]^1]))
 def test_rebound_corrupt_member_still_rejected(self):
  files=m.payloads(self.raw,self.zip);name=sorted(files)[0];files[name]+=b'changed'
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as z:
   for n,b in sorted(files.items()):
    i=zipfile.ZipInfo(n);i.external_attr=(stat.S_IFREG|0o644)<<16;z.writestr(i,b)
  raw=stream.getvalue();index=copy.deepcopy(self.index);index['bundle'].update(bytes=len(raw),sha256=m.sha(raw));index['uncompressed_bytes']+=7
  with self.assertRaisesRegex(ValueError,'ORIGINAL_BYTE_IDENTITY'):m.payloads(json.dumps(index).encode(),raw)
 def test_duplicate_index_key_rejected(self):
  with self.assertRaisesRegex(ValueError,'DUPLICATE_FIELD'):m.strict(b'{"files":{},"files":{}}')
 def test_path_scope_rejected(self):
  for name in ['../x','evidence/completion015/../escape','evidence/completion015/root.json','/evidence/completion015/x/y','evidence/completion015/x//y']:
   with self.subTest(name=name),self.assertRaises(ValueError):m.safe(name)
 def test_bounds_fail_closed(self):
  with patch.object(m,'MAX_FILES',99),self.assertRaisesRegex(ValueError,'FILE_BOUND'):m.payloads(self.raw,self.zip)
  with patch.object(m,'MAX_BYTES',len(self.zip)-1),self.assertRaisesRegex(ValueError,'TRANSPORT_IDENTITY'):m.payloads(self.raw,self.zip)
  with patch.object(m,'MAX_BYTES',978037),self.assertRaisesRegex(ValueError,'BYTE_BOUND'):m.payloads(self.raw,self.zip)
 def test_original_blob_binding_rejected(self):
  index=copy.deepcopy(self.index);index['files'][sorted(index['files'])[0]]['git_blob_sha1']='0'*40
  with self.assertRaisesRegex(ValueError,'ORIGINAL_BYTE_IDENTITY'):m.payloads(json.dumps(index).encode(),self.zip)
 def test_symlink_destination_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'actual').mkdir();(root/'link').symlink_to(root/'actual',target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'SYMLINK_REFUSED'):m.extract(INDEX,root/'link/new')

if __name__=='__main__':unittest.main()
