import copy,json,tempfile,unittest
from pathlib import Path
from producer import VERSION,canonical,digest,verify,verify_sources,Producer
class BindingTests(unittest.TestCase):
 def setUp(self):
  self.request={'schema':VERSION,'queries':['road']};self.row={'query':'road','filename':'a.jpg','timestamp':'t','url':'https://example.invalid/a','sha256':'abc'};self.outputs={'road':[self.row]};self.contract={'request':self.request,'request_sha256':digest(canonical(self.request)),'outputs':{'road':{'rows':1,'sha256':digest(canonical([self.row]))}},'source_bindings':{}}
 def test_valid(self):self.assertTrue(verify(self.contract,self.outputs))
 def test_tampered_observation(self):
  self.outputs['road'][0]['sha256']='changed'
  with self.assertRaises(ValueError):verify(self.contract,self.outputs)
 def test_request_change(self):
  self.contract['request']['queries']=['canopy']
  with self.assertRaises(ValueError):verify(self.contract,self.outputs)
 def test_unknown_schema(self):
  self.contract['request']['schema']='co2'
  with self.assertRaises(ValueError):verify(self.contract,self.outputs)
 def test_cross_scope(self):
  self.row['query']='canopy'
  with self.assertRaises(ValueError):verify(self.contract,self.outputs)
 def test_missing_product(self):
  with self.assertRaises(ValueError):verify(self.contract,{})
 def test_duplicate_observation(self):
  self.outputs['road'].append(self.row)
  with self.assertRaises(ValueError):verify(self.contract,self.outputs)
 def test_reject_duplicate_query(self):
  with self.assertRaises(ValueError):Producer('/tmp','/tmp').run(['road','road'])
 def test_reject_unknown_query(self):
  with self.assertRaises(ValueError):Producer('/tmp','/tmp').run(['fertility'])
 def test_bad_image_hash(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x';p.write_bytes(b'not image')
   with self.assertRaisesRegex(ValueError,'Source hash'):Producer(d,d).read_image({'sha256':'wrong'},p)
 def test_metadata_and_source_audit(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'manifest.json';p.write_bytes(canonical([self.row]));self.contract['source_bindings']={'manifest.json':digest(p.read_bytes())}
   self.assertEqual(verify_sources(self.contract,self.outputs,d)['verification_source_rows'],1)
   p.write_bytes(b'[]')
   with self.assertRaisesRegex(ValueError,'Changed metadata'):verify_sources(self.contract,self.outputs,d)
if __name__=='__main__':unittest.main()
