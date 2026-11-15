import unittest,json,subprocess,sys,tempfile,zipfile,random
from pathlib import Path
from RUN_WORKSHOP import run,load,check,ROOT
class Tests(unittest.TestCase):
 def test_reference(self): self.assertEqual(check()['passed'],10)
 def test_fault_detected(self): self.assertLess(check(load(ROOT/'missions/total-only-fault.json'))['passed'],10)
 def test_candidate_integrity(self):
  spec=load(ROOT/'instrument.json');base=load(ROOT/'inputs/funded.json')
  with self.assertRaises(ValueError):run(base,{})
  with self.assertRaises(ValueError):run(base,spec|{'outputs':{'accepted':{'formula':'true'}}})
  bad=spec|{'outputs':spec['outputs']|{'gap':{'formula':'999'}}}
  self.assertLess(check(bad)['passed'],10)
 def test_boundaries(self):
  base=load(ROOT/'inputs/funded.json')
  for value in [True,None,1.5,'90',10**9+1]:
   with self.assertRaises(ValueError):run(base|{'a':value})
  for value in [1,'true',None]:
   with self.assertRaises(ValueError):run(base|{'consent_a':value})
  with self.assertRaises(ValueError):run(base|{'extra':0})
  with self.assertRaises(ValueError):run({})
 def test_strict_json(self):
  from vendor.instruments import strict_portable_json
  for s in ['{"a":1,"a":2}','{"a":NaN}','{"a":1e999}']:
   with self.assertRaises(ValueError):strict_portable_json(s)
 def test_formula_sandbox(self):
  from vendor.instruments import evaluate
  for expr in ['__import__("os")','a.real','a[0]','open("foo")']:
   with self.assertRaises(ValueError):evaluate({'inputs':['a'],'outputs':{'x':{'formula':expr}}},{'a':1})
 def test_generated_oracle(self):
  rng=random.Random(99171)
  for _ in range(2000):
   v={k:rng.randint(-1,600) for k in ['cap_a','cap_b','cap_c','a','b','c','cost','contingency']};v.update({k:rng.choice([True,False]) for k in ['consent_a','consent_b','consent_c']})
   expected=all(v[k]>=0 for k in ['cap_a','cap_b','cap_c','a','b','c','cost','contingency']) and all(v[k]<=v['cap_'+k] for k in ['a','b','c']) and all(v[k] for k in ['consent_a','consent_b','consent_c']) and sum(v[k] for k in ['a','b','c'])>=v['cost']+v['contingency']
   o=run(v);self.assertIs(o['accepted'],expected);self.assertEqual(o['gap'],max(0,v['cost']+v['contingency']-v['a']-v['b']-v['c']))
 def test_export_reopen(self):
  with tempfile.TemporaryDirectory() as t:
   z=Path(t)/'kit.zip'
   with zipfile.ZipFile(z,'w') as f:
    for p in ROOT.rglob('*'):
     if p.is_file() and '__pycache__' not in str(p) and p.suffix!='.zip':f.write(p,p.relative_to(ROOT))
   out=Path(t)/'reopened'
   with zipfile.ZipFile(z) as f:f.extractall(out)
   r=subprocess.run([sys.executable,str(out/'RUN_WORKSHOP.py'),'run',str(out/'inputs/fresh-reopen.json')],capture_output=True,text=True,cwd=t)
   self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(json.loads(r.stdout)['accepted'])
if __name__=='__main__': unittest.main(verbosity=2)
