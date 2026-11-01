import unittest,itertools,math
import numpy as np,stim,tesseract_decoder as td
from kernel import MassKernel,mask
class Tests(unittest.TestCase):
 def setUp(self):
  self.dem=stim.DetectorErrorModel('error(0.20) D0\nerror(0.15) D0 L0\nerror(0.12) D1\nerror(0.10) D0 D1 L0\nerror(0.08) L0')
  self.decoder=td.tesseract.TesseractConfig(self.dem,merge_errors=False).compile_decoder();self.k=MassKernel(self.decoder)
 def test_exact_class_mass(self):
  k=self.k;n=len(k.h)
  for s in range(4):
   pool={m for m in range(1<<n) if k.syndrome(m)==s};_,selected,masses=k.decide(pool);brute={}
   for m in pool:
    probability=1
    for i,e in enumerate(self.decoder.errors):probability*=e.get_probability() if m>>i&1 else 1-e.get_probability()
    l=k.logical(m);brute[l]=brute.get(l,0)+probability
   self.assertEqual(selected,max(brute,key=brute.get))
   for l in brute:self.assertAlmostEqual(masses[l]/sum(masses.values()),brute[l]/sum(brute.values()))
 def test_moves_and_fallback(self):
  for m in self.k.moves:self.assertEqual(self.k.syndrome(m),0)
  for s in range(4):self.assertEqual(self.k.syndrome(self.k.fallback(s)),s)
 def test_pool_syndrome_dedup_and_api_mapping(self):
  for s in range(4):
   pool,stats=self.k.pool(np.array([s&1,s&2],dtype=bool),orders=4)
   self.assertEqual(len(pool),len(set(pool)))
   for m in pool:
    self.assertEqual(self.k.syndrome(m),s)
    ids=[i for i in range(len(self.k.h)) if m>>i&1]
    self.assertAlmostEqual(self.k.cost(m),self.decoder.cost_from_errors(ids))
    self.assertEqual(self.k.logical(m),mask(i for i,x in enumerate(self.decoder.get_observables_from_errors(ids)) if x))
 def test_normalized_index_contract(self):
  raw=stim.DetectorErrorModel('error(0.1) D0 L0\nerror(0.2) D0 L0\nerror(0.03) D0\nerror(0.0) D1')
  first=td.tesseract.TesseractConfig(raw).compile_decoder()
  norm=td.tesseract.TesseractConfig(first.config.dem,merge_errors=False).compile_decoder()
  k=MassKernel(norm)
  self.assertEqual(len(norm.errors),2)
  self.assertEqual(sorted(round(e.get_probability(),8) for e in norm.errors),[0.03,0.26])
  for s in [np.array([False,False]),np.array([True,False])]:
   ids=norm.decode_to_errors(s)
   self.assertTrue(all(i<len(norm.errors) for i in ids))
   self.assertEqual(k.syndrome(mask(ids)),mask(s.nonzero()[0]))
 def test_parity_constrained_candidate_integrity(self):
  from diversify import ParityDiversifier
  d=ParityDiversifier(self.decoder.config.dem,1,2)
  for s in range(4):
   syndrome=np.array([s&1,s&2],dtype=bool)
   pool,_=self.k.pool(syndrome)
   extra,invalid=d.candidates(syndrome,self.k,pool)
   _,base,_=self.k.decide(pool)
   self.assertTrue(extra)
   for m in extra:
    self.assertEqual(self.k.syndrome(m),s)
    self.assertNotEqual(self.k.logical(m)&1,base&1)
if __name__=='__main__':unittest.main()

