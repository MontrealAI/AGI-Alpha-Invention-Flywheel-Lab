"""Independent preregistered comparison against unchanged official scorer."""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
from scipy.signal import convolve2d
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source'/'Codes_Python'))
import KTCScoring as official
import score_fast as fast
TOLERANCE=1e-10

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def execute():
 z=np.zeros((7,9),dtype=np.float64);o=np.ones_like(z)
 a=z.copy();a[0,0]=1;b=z.copy();b[-1,-1]=1
 rng=np.random.default_rng(99117);r1=rng.integers(0,2,z.shape).astype(float);r2=rng.integers(0,2,z.shape).astype(float)
 rng2=np.random.default_rng(99118);m1=rng2.integers(0,2,z.shape).astype(float);m2=m1.copy();m2[0,:]=1-m2[0,:];m2[3,4]=1-m2[3,4]
 cases=[('zeros',z,z),('ones',o,o),('zero_vs_one',z,o),('opposite_edge_impulses',a,b),('seeded_binary_99117',r1,r2),('mixed_edges_interior_99118',m1,m2)]
 w=np.arange(-160,161);X,Y=np.meshgrid(w,w);ker=(1/np.sqrt(2*np.pi))*np.exp(-.5*(X*X+Y*Y)/(80**2))
 g=np.exp(-.5*w*w/(80**2));kernel_error=float(np.max(np.abs(ker-(1/np.sqrt(2*np.pi))*np.outer(g,g))))
 records=[]
 for name,t,r in cases:
  a=float(official.ssim(t,r));b=fast.binary_ssim(t,r)
  corr=convolve2d(np.ones(t.shape),ker,mode='same')
  errors={}
  for label,arr in [('truth',t),('reconstruction',r),('truth_squared',t*t),('reconstruction_squared',r*r),('cross',t*r)]:
   original=convolve2d(arr,ker,mode='same')/corr
   candidate=fast.normalized_filter(arr)/fast.normalized_filter(np.ones(arr.shape))
   errors[label]=float(np.max(np.abs(original-candidate)))
  records.append({'case':name,'original_score':a,'fast_score':b,'absolute_error':abs(a-b),'moment_max_absolute_errors':errors,'accepted':abs(a-b)<=TOLERANCE and all(x<=TOLERANCE for x in errors.values())})
 originals=[]
 for level in (1,4):
  source=ROOT/'scores'/f'limited-{level}.json';candidate=ROOT/'scores_fast'/f'limited-{level}.json'
  if source.exists() and candidate.exists():
   a=json.loads(source.read_text());b=json.loads(candidate.read_text());identity=all(a[k]==b[k] for k in ('truth_sha256','output_sha256','level','phantom')) and a['scorer_sha256']==sha(ROOT/'source'/'Codes_Python'/'KTCScoring.py') and b['scorer_sha256']==sha(ROOT/'score_fast.py') and a['truth_sha256']==sha(ROOT/'data'/'EvaluationData'/'GroundTruths'/f'level_{level}'/'1_true.mat') and a['output_sha256']==sha(ROOT/'outputs'/f'limited-{level}'/'1.mat')
   originals.append({'level':level,'identical_inputs':identity,'original_score':a['official_score'],'fast_score':b['official_score'],'absolute_error':abs(a['official_score']-b['official_score']),'accepted':identity and abs(a['official_score']-b['official_score'])<=TOLERANCE,'original_receipt_sha256':sha(source),'fast_receipt_sha256':sha(candidate)})
  else:originals.append({'level':level,'accepted':False,'status':'PENDING_ORIGINAL_RECEIPT'})
 return {'schema':'ktc/scorer-equivalence-review/v1','absolute_tolerance':TOLERANCE,'protocol_sha256':sha(ROOT/'SCORER_EQUIVALENCE_PROTOCOL.md'),'official_source_sha256':sha(ROOT/'source'/'Codes_Python'/'KTCScoring.py'),'fast_source_sha256':sha(ROOT/'score_fast.py'),'review_source_sha256':sha(Path(__file__)),'mathematical_basis':'Finite Gaussian kernel c*g(x)*g(y); common scalar cancels each moment normalization. Odd321 support [-160,160], sigma80, constant-zero extension and centered same output match. Constants, masks and population formula unchanged.','kernel_factorization_max_absolute_error':kernel_error,'synthetic_controls':records,'physical_output_controls':originals,'synthetic_equivalence_accepted':all(r['accepted'] for r in records),'full_validation_accepted':all(r['accepted'] for r in records+originals),'scope':'Numerical equivalence of this metric implementation, not qualification of reconstruction, demand, finance or physical capability.'}

if __name__=='__main__':
 p=ROOT/'INDEPENDENT_SCORER_REVIEW.json';r=execute();p.write_text(json.dumps(r,indent=2)+'\n')
 complete=all('absolute_error' in row for row in r['physical_output_controls'])
 gate={'passed':r['full_validation_accepted'],'absolute_tolerance':TOLERANCE,'cases':r['physical_output_controls'],
       'max_absolute_error':max(row['absolute_error'] for row in r['physical_output_controls']) if complete else None,
       'synthetic_controls_passed':r['synthetic_equivalence_accepted'],'independent_review_file':p.name,
       'independent_review_sha256':sha(p),'reason':'Both original full-resolution controls and six synthetic controls accepted' if r['full_validation_accepted'] else 'Awaiting unchanged official full-resolution receipts or equivalence rejected'}
 (ROOT/'original_score_validation.json').write_text(json.dumps(gate,indent=2)+'\n');print(json.dumps(r,indent=2))
