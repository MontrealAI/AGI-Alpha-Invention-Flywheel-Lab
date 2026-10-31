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

 def test_every_atomic_publication_boundary_retries_without_partial_canonical_object(self):
  for boundary in ['stage_created','stage_synced','object_published']:
   with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    def crash(where,stage):
     if where==boundary:raise InterruptedError(boundary)
    with self.assertRaises(InterruptedError):persist_evidence(root,self.blobs,failpoint=crash)
    if (root/self.name).exists():self.assertEqual((root/self.name).read_bytes(),self.raw)
    persist_evidence(root,self.blobs)
    rows=recover_stages(root)
    self.assertEqual(len(rows),1);self.assertFalse(list(root.glob('.stage-*')))
    self.assertEqual((root/rows[0]['path']).stat().st_size,rows[0]['bytes'])
    with evidence_directory(root):self.assertEqual(te._store.get().get(self.name),self.raw)
 def test_nested_directory_scope_does_not_lock_out_writer_subprocess(self):
  import subprocess,sys,os
  with evidence_directory(self.root):
   code='import sys;from connected_enterprise.transition_evidence import persist_evidence;persist_evidence(sys.argv[1],{sys.argv[2]:bytes.fromhex(sys.argv[3])})'
   done=subprocess.run([sys.executable,'-c',code,str(self.root),self.name,self.raw.hex()],text=True,capture_output=True,timeout=10)
   self.assertEqual(done.returncode,0,done.stderr)
   self.assertEqual(te._store.get().get(self.name),self.raw)
 def test_two_writers_deduplicate_without_overwrite(self):
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=2) as pool:
   jobs=[pool.submit(persist_evidence,self.root,self.blobs) for i in range(2)]
   for job in jobs:job.result(timeout=10)
  self.assertEqual([p.name for p in self.root.iterdir()],[self.name])
