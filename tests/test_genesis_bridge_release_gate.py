import copy,importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('bridge_gate',ROOT/'scripts/gate_genesis_bridge_release.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class GateTests(unittest.TestCase):
 def setUp(self):self.sha='1'*40;self.rows=[{'id':i+1,'path':'.github/workflows/'+p,'head_sha':self.sha,'head_branch':'main','event':'push','status':'completed','conclusion':'success'} for i,p in enumerate(sorted(g.REQUIRED))]
 def test_pass(self):self.assertTrue(g.decide(self.sha,self.sha,self.rows)['accepted'])
 def test_missing(self):
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows[:-1])
 def test_main_moves(self):
  with self.assertRaises(ValueError):g.decide(self.sha,'2'*40,self.rows)
 def test_failed(self):
  self.rows[0]['conclusion']='failure'
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows)
 def test_pending(self):
  self.rows[0]['status']='in_progress';self.rows[0]['conclusion']=None
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows)
 def test_pr_does_not_qualify(self):
  self.rows[0]['event']='pull_request'
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows)
 def test_old_sha_does_not_qualify(self):
  self.rows[0]['head_sha']='2'*40
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows)
 def test_extra_observed_failure_blocks(self):
  self.rows.append({**self.rows[0],'id':99,'path':'.github/workflows/extra.yml','conclusion':'failure'})
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows)
 def test_later_attempt_failure_blocks(self):
  self.rows.append({**self.rows[0],'run_attempt':2,'conclusion':'failure'})
  with self.assertRaises(ValueError):g.decide(self.sha,self.sha,self.rows)
if __name__=='__main__':unittest.main()
