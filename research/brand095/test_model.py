import copy,hashlib,unittest
from pathlib import Path
from research.brand095.model import *
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.case=dict(n=1000,mix='mixed',capital=100000,scenario='central',envelope='lean',policy='full',seed=95001)
  cls.result=simulate(**cls.case,trace=True)
 def test_dependency(self):
  self.assertEqual(hashlib.sha256(Path('research/strategic094/model.py').read_bytes()).hexdigest(),'a458dffebef7467313db54ad984d5b35e1cbe2015f0a0d23731d8ca4eb9e52db')
 def test_denominator(self):
  cells=list(matrix());self.assertEqual(len(cells),504);self.assertEqual(len({tuple(x.values()) for x in cells}),504)
 def test_no_activation(self):
  r=simulate(**{**self.case,'policy':'none'},trace=True)
  self.assertEqual((r['settled_episode_profit'],r['contacts'],r['founder_hours']),(0,0,0))
 def test_zero_audience(self):
  r=simulate(**{**self.case,'n':0});self.assertEqual(r['orders'],0);self.assertLess(r['settled_economic_profit'],0)
 def test_settlement(self):
  self.assertLess(abs(self.result['obligations']),1e-5);self.assertLess(abs(self.result['receivables']),1e-5)
 def test_founder_reconciliation(self):
  r=self.result;self.assertEqual(r['founder_hours'],8);self.assertAlmostEqual(r['settled_episode_profit']-r['settled_economic_profit'],1200)
 def test_identity(self):audit(self.result['trace'],100000)
 def test_mutation_cash(self):
  r=copy.deepcopy(self.result['trace']);r[3]['cash']+=1
  with self.assertRaises(AssertionError):audit(r,100000)
 def test_mutation_opportunity_cost(self):
  r=copy.deepcopy(self.result['trace']);r[0]['founder_opportunity_cost']=0
  with self.assertRaises(AssertionError):audit(r,100000)
 def test_mutation_duplicate(self):
  r=copy.deepcopy(self.result['trace']);r[3]['duplicate_contacts']=1
  with self.assertRaises(AssertionError):audit(r,100000)
 def test_mutation_budget(self):
  r=copy.deepcopy(self.result['trace']);r[3]['buyer_budget_violations']=1
  with self.assertRaises(AssertionError):audit(r,100000)
 def test_mutation_revenue(self):
  r=copy.deepcopy(self.result['trace']);r[3]['revenue']+=1000
  with self.assertRaises(AssertionError):audit(r,100000)
 def test_mutation_acceptance(self):
  r=copy.deepcopy(self.result['trace']);r[3]['accepted_cumulative']=10000000
  with self.assertRaises(AssertionError):audit(r,100000)
 def test_repeat(self):self.assertEqual(simulate(**self.case),simulate(**self.case))
if __name__=='__main__':unittest.main()
