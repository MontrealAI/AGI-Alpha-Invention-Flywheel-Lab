import unittest
from water import construct,simulate,separate
class WaterTests(unittest.TestCase):
 def test_known_storage(self):
  r=construct([0,20,0,0],[5]*4);self.assertTrue(r['feasible']);self.assertAlmostEqual(r['capacity_l'],15);self.assertAlmostEqual(r['initial_l'],5)
 def test_no_supply(self):self.assertFalse(construct([0]*24,[1]*24)['feasible'])
 def test_zero_demand(self):self.assertEqual(construct([1]*24,[0]*24)['capacity_l'],0)
 def test_no_storage_fails(self):self.assertGreater(simulate([0,20,0,0],[5]*4,0,0)['unserved_l'],0)
 def test_salt_balance(self):
  for r in [.5,.8,.95]:
   a=separate(1000,2,.5,r,10);self.assertAlmostEqual(a['salt_in_kg'],a['salt_product_kg']+a['salt_brine_kg']);self.assertAlmostEqual(a['product_l']+a['brine_l'],1000)
 def test_eta_cost(self):
  a=separate(1000,2,.5,.8,10,.4);b=separate(1000,2,.5,.8,10,.9);self.assertAlmostEqual(a['charge_c']/b['charge_c'],.9/.4)
 def test_invalid(self):
  for r in [0,1,-1]:
   with self.assertRaises(ValueError):separate(1000,2,.5,r,10)
  with self.assertRaises(ValueError):separate(1000,2,.5,.8,0)
 def test_disposal_not_salt_disappearance(self):
  low=separate(1000,2,0,.5,10);high=separate(1000,2,0,.95,10);self.assertAlmostEqual(low['salt_brine_kg'],high['salt_brine_kg']);self.assertGreater(high['brine_g_l'],low['brine_g_l'])
if __name__=='__main__':unittest.main()
