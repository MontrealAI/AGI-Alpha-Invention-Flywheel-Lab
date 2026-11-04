import copy,unittest
import numpy as np
from research.business096.model import *
class Tests(unittest.TestCase):
 def test_scalar_vector_game(self):
  for world in ('central','strong_rival','cost_overrun'):
   for o in OFFERS:
    w=params(world);g=competitive_game(o,o.ai_cost,.85,w,1.)
    share,_=price_response(o,g['price'],.85,w,1.)
    self.assertAlmostEqual(share,g['share'])
    self.assertAlmostEqual(g['margin'],share*(g['price']*.85*.97-o.ai_cost*1.025),places=5)
 def test_nonentry(self):
  r=run(100000,'none','central',96001,True)
  self.assertEqual(r['settled_profit'],0);self.assertEqual(r['orders'],0)
 def test_zero_demand(self):
  r=run(1000000,'combined','zero_demand',96001)
  self.assertEqual(r['accepted'],0);self.assertLessEqual(r['settled_profit'],0)
 def test_finance_and_counts(self):
  r=run(100000000,'combined','central',96001,True);cum=rev=coll=0;old=0
  for x in r['trace']:
   cum+=x['profit'];rev+=x['revenue'];coll+=x['collected']
   self.assertAlmostEqual(x['revenue']-x['expense'],x['profit'],places=5)
   self.assertAlmostEqual(rev-coll,x['receivables'],places=4)
   self.assertAlmostEqual(x['cash']+x['receivables']-x['tax_payable']-1e8,cum,places=4)
   self.assertLessEqual(old,x['accepted']);self.assertLessEqual(x['accepted'],x['orders']);old=x['accepted']
   self.assertGreaterEqual(x['cash']+1e-5,x['reserved'])
  self.assertLess(abs(r['receivables']),1e-5);self.assertLess(abs(r['obligations']),1e-5)
 def test_staging_uses_current_cash(self):
  r=run(100000,'combined','central',96001,True)
  self.assertEqual(r['orders'],0);self.assertTrue(all(x['cash']>=0 for x in r['trace']))
 def test_shared_permissions(self):
  for m in ('founder','autonomous','combined','conventional'):
   r=run(1000000,m,'central',96001)
   self.assertLessEqual(r['accepted'],r['orders'])
 def test_final_field_mutations(self):
  from research.business096.audit import audit_row
  r=run(1000000,'combined','central',96001,True)
  for key in ('cash','accepted','orders','contacts','human_hours','founder_hours'):
   bad=copy.deepcopy(r);bad[key]+=1000
   with self.assertRaises(AssertionError):audit_row(bad)
 def test_finite_price_grid(self):self.assertEqual(len(PRICES),1001)
if __name__=='__main__':unittest.main()
