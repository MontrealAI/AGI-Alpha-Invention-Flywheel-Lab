import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from connected_enterprise.transition_evidence import persist_evidence,evidence_directory,read_evidence_blob
class Recovery(unittest.TestCase):
 def test_interrupted_staging_retries_without_overwriting_final(self):
  with tempfile.TemporaryDirectory() as tmp:
   raw=b'{"proof":"synthetic"}';sha=hashlib.sha256(raw).hexdigest();p=Path(tmp)
   with patch('connected_enterprise.transition_evidence.os.link',side_effect=InterruptedError('after fsync')),self.assertRaises(InterruptedError):persist_evidence(p,{sha:raw})
   self.assertFalse((p/sha).exists());self.assertEqual((p/('.pending-'+sha)).read_bytes(),raw)
   persist_evidence(p,{sha:raw});inode=(p/sha).stat().st_ino
   persist_evidence(p,{sha:raw});self.assertEqual((p/sha).stat().st_ino,inode)
   self.assertEqual([x.name for x in p.iterdir()],[sha])
   with evidence_directory(p):self.assertEqual(read_evidence_blob(sha),raw)
 def test_incomplete_pending_retry_and_corrupt_final_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   raw=b'{"proof":"synthetic"}';sha=hashlib.sha256(raw).hexdigest();p=Path(tmp)
   (p/('.pending-'+sha)).write_bytes(b'{')
   persist_evidence(p,{sha:raw});self.assertEqual((p/sha).read_bytes(),raw)
   (p/sha).write_bytes(b'bad')
   with self.assertRaises(ValueError):persist_evidence(p,{sha:raw})
   self.assertEqual((p/sha).read_bytes(),b'bad')
 def test_link_before_unlink_crash_at_exact_store_bound(self):
  import os
  from connected_enterprise import transition_evidence as te
  with tempfile.TemporaryDirectory() as tmp:
   raw=b'{"proof":"synthetic"}';sha=hashlib.sha256(raw).hexdigest();p=Path(tmp)
   (p/sha).write_bytes(raw);os.link(p/sha,p/('.pending-'+sha))
   with patch.object(te,'MAX_BUNDLE_FILES',1),patch.object(te,'MAX_BUNDLE_BYTES',len(raw)):
    persist_evidence(p,{sha:raw})
    with evidence_directory(p):self.assertEqual(read_evidence_blob(sha),raw)
   self.assertEqual([x.name for x in p.iterdir()],[sha])
 def test_actual_business_scope_recovers_exact_bound_alias(self):
  import os
  from connected_enterprise import transition_evidence as te
  with tempfile.TemporaryDirectory() as tmp:
   raw=b'{"proof":"synthetic"}';sha=hashlib.sha256(raw).hexdigest();p=Path(tmp)/'transition-evidence';p.mkdir()
   (p/sha).write_bytes(raw);os.link(p/sha,p/('.pending-'+sha))
   with patch.object(te,'MAX_BUNDLE_FILES',1),patch.object(te,'MAX_BUNDLE_BYTES',len(raw)):
    with te.business_evidence(tmp):
     persist_evidence(p,{sha:raw})
     self.assertEqual(read_evidence_blob(sha),raw)
   self.assertEqual([x.name for x in p.iterdir()],[sha])
if __name__=='__main__':unittest.main()
