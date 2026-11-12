import copy,hashlib,itertools,json,pathlib,shutil,sys,tempfile,unittest
from fractions import Fraction
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
if not (ROOT/'flywheel/sandbox.py').is_file(): ROOT=ROOT/'lab'
sys.path.insert(0,str(ROOT))
from flywheel.sandbox import run
from experiments import observability008 as driver
INTERPRETER_SHA256='b5ff72fb964ab5c86914b2c23156e7ca4ec9c4d1f7999971906f3fd87d83bb22'
def rank(rows,n):
 a=[[Fraction(x) for x in row] for row in rows];r=0
 for c in range(n):
  k=next((j for j in range(r,len(a)) if a[j][c]),None)
  if k is None:continue
  a[r],a[k]=a[k],a[r];z=a[r][c];a[r]=[x/z for x in a[r]]
  for j in range(r+1,len(a)):
   z=a[j][c];a[j]=[x-z*y for x,y in zip(a[j],a[r])]
  r+=1
  if r==len(a):break
 return r
class Observability008Verification(unittest.TestCase):
 def payload(self):
  return {'language':'linear-ambiguity-plan/v1','dimension':3,'constraints':[['1/2','1/2',0]],'measurements':[{'id':name,'row':row,'calibrated':True,'cost_units':cost} for name,row,cost in [('a',[1,0,0],5),('b',[0,1,0],1),('c',[0,0,1],4),('d',[1,1,1],2)]],'requires_absolute_calibration':True,'max_plans':256}
 def execute(self,p):
  return run(ROOT/'inventions/observability008/interpreter.py','interpret',p,INTERPRETER_SHA256)
 def test_unknown_obligation_refused_inside_worker(self):
  p=self.payload();p['requires_global_identifiability']=True;r=self.execute(p)
  self.assertEqual(r['state'],'FAILED');self.assertIn('UNSUPPORTED_FIELD_OR_OBLIGATION',r['stderr'])
 def test_unknown_gain_cannot_satisfy_absolute_obligation(self):
  p=self.payload()
  for x in p['measurements']:
   if x['row'][2]:x['calibrated']=False
  r=self.execute(p);self.assertEqual(r['state'],'COMPLETE');v=r['worker']['result'];self.assertEqual(v['remaining_ambiguity'],1);self.assertEqual(v['status'],'INSUFFICIENT_MEASUREMENTS');self.assertEqual({x['id'] for x in v['refused']},{'c','d'})
  p.update(mode='execute',plan=['b','d']);r=self.execute(p);self.assertEqual(r['state'],'FAILED');self.assertIn('INAPPLICABLE_MEASUREMENT_IN_PLAN',r['stderr'])
 def test_actual_plan_matches_independent_fraction_exhaustion(self):
  p=self.payload();r=self.execute(p);self.assertEqual(r['state'],'COMPLETE');self.assertEqual(r['worker']['confinement'],'linux-seccomp-default-deny');v=r['worker']['result'];costs=[]
  for n in range(len(p['measurements'])+1):
   for subset in itertools.combinations(p['measurements'],n):
    if rank(p['constraints']+[x['row'] for x in subset],p['dimension'])==p['dimension']:costs.append(sum(x['cost_units'] for x in subset))
  selected=[x for x in p['measurements'] if x['id'] in v['plan']];self.assertEqual(rank(p['constraints']+[x['row'] for x in selected],3),3);self.assertEqual(v['cost_units'],min(costs));self.assertEqual(v['cost_units'],3);self.assertFalse(v['physical_calibration_acquired'])
 def test_caller_cannot_forge_or_change_frozen_acceptance(self):
  previous=ROOT/'evidence/overnight-008/observability-development-r2/artifacts';issued=ROOT/'evidence/overnight-008/observability-accepted-r2/ACCEPTANCE.json';fresh=ROOT/'research/observability008/crauste/model_constraints.json';valid=json.loads(issued.read_text())
  with tempfile.TemporaryDirectory() as temp:
   home=pathlib.Path(temp);replica=home/'root'
   for rel in ['inventions/observability008/interpreter.py','verification/observability008_AUTHORITY.json','verification/accept_linear_plan008.py']:
    path=replica/rel;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,path)
   for name,body in [('forged',{k:valid[k] for k in ['accepted','artifact_sha256','interpreter_sha256','scope']}),('changed',dict(valid,unreviewed_annotation='caller'))]:
    with self.subTest(name=name):
     receipt=home/(name+'.json');receipt.write_text(json.dumps(body)+'\n');output=home/(name+'-output')
     with patch.object(driver,'ROOT',replica):
      with self.assertRaisesRegex(ValueError,'RECEIPT_NOT_AUTHORIZED_FOR_ARTIFACT'):driver.retain_and_use(previous,receipt,fresh,output)
     self.assertFalse(output.exists())
if __name__=='__main__':unittest.main()
