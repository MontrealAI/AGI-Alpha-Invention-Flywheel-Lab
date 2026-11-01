import unittest
import producer
class CacheIdentityTests(unittest.TestCase):
 def test_observable_roi_separated(self):
  self.assertNotEqual(producer.feature_key('same-image','road'),producer.feature_key('same-image','promenade'))
 def test_version_separated(self):
  a=producer.feature_key('same-image','road');old=producer.VERSION
  try:
   producer.VERSION='next-version';self.assertNotEqual(a,producer.feature_key('same-image','road'))
  finally:producer.VERSION=old
 def test_roi_separated(self):
  a=producer.feature_key('same-image','road');old=producer.ROIS['road']
  try:
   producer.ROIS['road']=[(1,2),(3,4),(5,6)];self.assertNotEqual(a,producer.feature_key('same-image','road'))
  finally:producer.ROIS['road']=old
 def test_source_separated(self):self.assertNotEqual(producer.feature_key('image-a','road'),producer.feature_key('image-b','road'))
 def test_half_open_window(self):
  self.assertTrue(producer.in_window({'timestamp':'2024-06-20'},['2024-06-20','2024-06-21']))
  self.assertFalse(producer.in_window({'timestamp':'2024-06-21'},['2024-06-20','2024-06-21']))
 def test_incompatible_window(self):
  with self.assertRaises(ValueError):producer.Producer('/tmp','/tmp').run(['road'],{'road':['z','a']})
if __name__=='__main__':unittest.main()

class NormalizationBindingTest(unittest.TestCase):
 def test_normalization_is_part_of_key(self):
  config={'version':producer.VERSION,'source_sha256':'s','observable':'road','roi':producer.ROIS['road'],'normalization':'PIL RGB resize720x405 /255;river-relative;median,std,gradient quantiles'}
  self.assertEqual(producer.feature_key('s','road'),producer.digest(producer.canonical(config)))
  config['normalization']='different resize or color space'
  self.assertNotEqual(producer.feature_key('s','road'),producer.digest(producer.canonical(config)))
