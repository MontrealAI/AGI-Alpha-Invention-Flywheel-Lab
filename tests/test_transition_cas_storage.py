import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from connected_enterprise.transition_evidence import *
from connected_enterprise import transition_evidence as te

class StorageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.raw=canonical({'accepted':True});self.name=hashlib.sha256(self.raw).hexdigest();self.blobs={self.name:self.raw}
 def tearDown(self):self.tmp.cleanup()
 def test_persist_is_idempotent_and_scope_pins_bytes(self):
  persist_evidence(self.root,self.blobs);before=(self.root/self.name).stat().st_ino
  persist_evidence(self.root,self.blobs);self.assertEqual(before,(self.root/self.name).stat().st_ino)
  with evidence_directory(self.root):self.assertEqual(te._store.get().get(self.name),self.raw)
 def test_symlink_blob_and_directory_rejected(self):
  outside=self.root/'other';outside.write_bytes(self.raw)
  (self.root/self.name).symlink_to(outside)
  with self.assertRaises(ValueError):
   with evidence_directory(self.root):pass
  link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(OSError):
   with evidence_directory(link):pass
 def test_corruption_after_scope_entry_rejected(self):
  persist_evidence(self.root,self.blobs)
  with evidence_directory(self.root):
   (self.root/self.name).write_bytes(b'0'*len(self.raw))
   with self.assertRaisesRegex(ValueError,'MISSING_OR_CHANGED'):te._store.get().get(self.name)
 def test_per_blob_and_aggregate_and_file_count_reject(self):
  with patch.object(te,'MAX_BLOB_BYTES',1),self.assertRaises(ValueError):persist_evidence(self.root,self.blobs)
  with patch.object(te,'MAX_BUNDLE_BYTES',1),self.assertRaises(ValueError):persist_evidence(self.root,self.blobs)
  with patch.object(te,'MAX_BUNDLE_FILES',0),self.assertRaises(ValueError):persist_evidence(self.root,self.blobs)
  self.assertEqual(list(self.root.iterdir()),[])
 def test_preparse_depth_nodes_and_string_escapes(self):
  with self.assertRaises(ValueError):te._parse_budget(b'['*129+b'0'+b']'*129)
  te._parse_budget(canonical({'text':'\\\\"[{'*1000}))
  with self.assertRaises(ValueError):te._parse_budget(b'['+b'0,'*2_000_000+b'0]')
 def test_partial_existing_blob_is_not_overwritten(self):
  (self.root/self.name).write_bytes(self.raw[:2])
  with self.assertRaises(ValueError):persist_evidence(self.root,self.blobs)
  self.assertEqual((self.root/self.name).read_bytes(),self.raw[:2])
