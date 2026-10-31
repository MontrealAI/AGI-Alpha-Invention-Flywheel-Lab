"""Bounded CAS transport/authentication unit checks with ephemeral fixture keys."""
import copy,hashlib,hmac,json,tempfile,unittest
from pathlib import Path
from connected_enterprise import transition_evidence as te
class EvidenceProtocolTests(unittest.TestCase):
 def fixture(self):
  body={k:'fixture' for k in te.FIELDS};body.update(schema=te.V1,counter=1,prior_record={'nested':[1,2]},prior_envelope={'body':{'entries':[]}})
  blobs={};wire=te.externalize(body,blobs);key=b'ephemeral-unit-key';ticket={'body':wire,'signature':hmac.new(key,te.DOMAIN+te.canonical(wire),hashlib.sha256).hexdigest()};return body,ticket,blobs,key
 def test_legacy_and_cas_exact_resolved_body(self):
  body,t,b,k=self.fixture()
  self.assertEqual(te.canonical(te.ticket_body({'body':body,'signature':'fixture'})),te.canonical(body))
  with te.evidence_scope(b):self.assertEqual(te.ticket_body(t,key=k),body)
 def test_defensive_copy_and_scope_exit(self):
  body,t,b,k=self.fixture()
  with te.evidence_scope(b):
   te.ticket_body(t,key=k)['prior_record']['nested'].append('changed');self.assertEqual(te.ticket_body(t,key=k),body)
  with self.assertRaises(ValueError):te.ticket_body(t,key=k)
 def test_header_signature_and_descriptor_tamper(self):
  body,t,b,k=self.fixture()
  with te.evidence_scope(b):
   changed=copy.deepcopy(t);changed['body']['id']='tampered'
   with self.assertRaises(ValueError):te.ticket_body(changed,key=k)
   changed=copy.deepcopy(t);changed['signature']='0'*64
   with self.assertRaises(ValueError):te.ticket_body(changed,key=k)
 def test_missing_and_changed_object(self):
  body,t,b,k=self.fixture();missing=dict(b);missing.pop(next(iter(missing)))
  with te.evidence_scope(missing),self.assertRaises(ValueError):te.ticket_body(t,key=k)
  with tempfile.TemporaryDirectory() as tmp:
   te.persist_evidence(tmp,b)
   with te.evidence_directory(tmp):
    te.ticket_body(t,key=k);next(Path(tmp).iterdir()).write_bytes(b'{}')
    with self.assertRaises(ValueError):te.ticket_body(t,key=k)
 def test_explicit_store_rejects_symlink(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'actual').mkdir();(root/'alias').symlink_to(root/'actual',target_is_directory=True)
   with self.assertRaises((ValueError,OSError)):
    with te.evidence_directory(root/'alias'):pass
if __name__=='__main__':unittest.main()
