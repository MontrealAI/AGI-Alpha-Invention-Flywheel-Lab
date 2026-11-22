import unittest,io,zipfile,json,struct
import numpy as np
from model import spatial_inputs,mask_from_native,predict
from produce import targets,select_archived
from data_io import extract_members
from baseline_io import normalization_roundtrip
class N3BTests(unittest.TestCase):
 def test_mask_domain(self):
  for a in [np.zeros((8,8)),np.full((64,64),np.nan),np.full((64,64),1.1)]:
   with self.assertRaises(ValueError):spatial_inputs(a)
 def test_native_domain(self):
  for a in [np.zeros(63),np.full(64,-.1),np.full(64,np.inf)]:
   with self.assertRaises(ValueError):mask_from_native(a)
 def test_target_geometry(self):
  a=targets();self.assertEqual(set(a),{'continuous_ridge50','annular_wall100','two_level_terrace'})
  for z in a.values():self.assertEqual(z.shape,(128,128));self.assertTrue(np.all(z[:32]==0));self.assertTrue(np.all(z[96:]==0))
  self.assertEqual(np.sum(a['continuous_ridge50']>0),16*64)
 def test_decision_denominator(self):
  with self.assertRaises(ValueError):select_archived(np.zeros((1,128,128)),['a'])
 def test_source_crc(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('test.txt',b'physical-source-binding')
  raw=b.getvalue();z=zipfile.ZipFile(io.BytesIO(raw));i=z.infolist()[0];e={'name':i.filename,'offset':0,'compressed':i.compress_size,'size':i.file_size,'crc32':i.CRC,'method':i.compress_type}
  self.assertEqual(extract_members(raw,0,[e])[0][1],b'physical-source-binding')
  e['crc32']+=1
  with self.assertRaises(ValueError):extract_members(raw,0,[e])
 def test_roundtrip_bound(self):
  a=np.arange(256,dtype=np.uint8);b=normalization_roundtrip(a)
  self.assertLessEqual(int(np.max(np.abs(a.astype(int)-b.astype(int)))),1)
if __name__=='__main__':unittest.main()
