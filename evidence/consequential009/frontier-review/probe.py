"""Bounded independent adversarial probe; no candidate edits, network or paid calls."""
import hashlib,json,os,resource,time
from fractions import Fraction as F
from pathlib import Path
from itertools import combinations,product
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
start=time.perf_counter();cpu=time.process_time()
os.chdir(ROOT)

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clip(poly,a,b,c):
    out=[]
    if not poly:return out
    for p,q in zip(poly,poly[1:]+poly[:1]):
        fp=a*p[0]+b*p[1]-c;fq=a*q[0]+b*q[1]-c
        if fp<=0:out.append(p)
        if (fp<0 and fq>0) or (fp>0 and fq<0):
            t=fp/(fp-fq);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return out

def tubes_overlap(x,y,lo,hi,eps):
    # Feasibility of two scalar gains and bounded independent coordinate errors:
    # |gain_x*x_coordinate - gain_y*y_coordinate| <= 2*eps.
    poly=[(lo,lo),(hi,lo),(hi,hi),(lo,hi)]
    for a,b in zip(x,y):
        poly=clip(poly,a,-b,2*eps);poly=clip(poly,-a,b,2*eps)
    return bool(poly)

def rectangles_overlap(x,y,lo,hi,eps):
    for a,b in zip(x,y):
        ax,bx=sorted([lo*a,hi*a]);ay,by=sorted([lo*b,hi*b])
        if bx+eps<ay-eps or by+eps<ax-eps:return False
    return True

result={'scope':'AI-native independent procedural review of exposed DEVELOPMENT artifacts; not external certification',
 'requested_model_alias':'gpt-6-astra','served_revision':None,'served_identity_limit':'Parent requested alias; runtime exposes no exact model revision, routing proof, token or bill receipt.',
 'external_paid_calls':0,'downloads':0,'new_commerce':False,'candidate_modified':False}
files=['inventions/consequential009/circuit.py','inventions/consequential009/reference_extension.py','research/consequential009/analog/REFERENCE_PROTOCOL.json','research/consequential009/analog/PROTOCOL.json','campaign/consequential-009/ALLOCATION.json','evidence/consequential009/resources/commerce-r1/artifacts/RESULT.json']
result['input_sha256']={p:sha(p) for p in files}
source_checks=[]
for f in read('research/consequential009/analog/SOURCES.json')['files']:
    b=Path(f['local_path']).read_bytes();blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
    source_checks.append({'path':f['local_path'],'sha256_matches':hashlib.sha256(b).hexdigest()==f['sha256'],'git_blob_matches':blob==f['upstream_git_blob'],'bytes_match':len(b)==f['size_bytes']})
result['local_source_integrity']=source_checks
result['correlated_gain_geometry']=[]
for name in ['primary','fresh_successor']:
    p=f'evidence/consequential009/resources/analog-r3/artifacts/{name}-unknown-gain-stress.json';d=read(p);result['input_sha256'][p]=sha(p)
    hypotheses=read(f'evidence/consequential009/resources/analog-r3/artifacts/{name}-COHORT.json')['hypotheses']
    n=len(hypotheses);pairs=set(combinations(range(n),2));exact_all=set();box_all=set();per=[];example=None
    for action,raw in d['exact_responses'].items():
        values=[list(map(F,z)) for z in raw];kind='input_admittance' if action.startswith('y:') else 'voltage_ratio'
        policy=d['policies'][kind];lo,hi=map(F,policy['gain']);eps=F(policy['absolute_coordinate_error'])
        exact=set();box=set()
        for i,j in pairs:
            b=rectangles_overlap(values[i],values[j],lo,hi,eps)
            e=tubes_overlap(values[i],values[j],lo,hi,eps) if lo!=hi else b
            if not b:box.add((i,j))
            if not e:exact.add((i,j))
            if b and not e and example is None:example={'action':action,'hypothesis_ids':[hypotheses[i]['id'],hypotheses[j]['id']],'responses':raw[i:j+1] if j==i+1 else [raw[i],raw[j]],'gain':[str(lo),str(hi)],'eps':str(eps)}
        assert box<=exact
        exact_all|=exact;box_all|=box
        if kind=='input_admittance':per.append({'action':action,'rectangle_separated':len(box),'correlated_scalar_gain_separated':len(exact)})
    result['correlated_gain_geometry'].append({'cohort':name,'pairs':len(pairs),'rectangle_all_actions_separated':len(box_all),'correlated_gain_all_actions_separated':len(exact_all),'rectangle_false_nonseparations':len(exact_all-box_all),'per_current_action':per,'witness':example,'remaining_exact_unresolved':len(pairs-exact_all),'consequence':'Rectangular overlap is sufficient for abstention under the chosen endpoint, not proof of information-theoretic nonidentifiability under a scalar gain model. Fundamental impedance-scale ambiguity remains.'})

# Candidate normalization is probed on all 16 noise corner pairs, not only the five authored patterns.
import sys
sys.path.insert(0,str(ROOT))
from inventions.consequential009.circuit import Q
from inventions.consequential009.reference_extension import cohorts,conditional_box,normalize
from inventions.consequential009.circuit import solve
p=read('research/consequential009/analog/REFERENCE_PROTOCOL.json');eps=F(p['absolute_coordinate_error_siemens']);Gnom=F(p['reference_nominal_siemens'])
gains=[Q(F(1,2)),Q(F(-1,2)),Q(F(0),F(1,2)),Q(F(0),F(-1,2)),Q(F(3,10),F(4,10)),Q(F(-3,10),F(4,10)),Q(F(10),F(-10))]
noise=[Q(a,b) for a,b in product([-eps,eps],repeat=2)];tested=0;escapes=[]
for name,c,hs,freqs in cohorts(p):
 for h in hs:
  for w in freqs:
   Y=solve(c,h['values'],w)[1];bb=conditional_box(Y,p);box=[tuple(map(F,x)) for x in bb['box']]
   for g,m,e0,e1 in product(gains,map(F,p['raw_reference_multiplier_grid']),noise,noise):
    G=Gnom*m;est=normalize(g*Y+e0,g*(Y+G)+e1,Gnom);tested+=1
    if not all(a<=z<=b for (a,b),z in zip(box,[est.re,est.im])):escapes.append({'cohort':name,'id':h['id'],'frequency':w})
result['reference_additional_corner_probe']={'cases':tested,'escapes':len(escapes),'gain_scope':'Seven complex gains including negative real and quadrature phase, minimum modulus 1/2 and large gain; all 16 independent raw-coordinate noise-corner pairs; reference endpoints plus midpoint','analytic_bound_review':'Identity correct. With coordinate noise <=eps, |e0|<=2eps and |e1-e0|<=4eps; denominator >=gmin*Gl-4eps. The coded E is a conservative absolute complex error bound and hence coordinate bound. No false containment established.','failures':escapes[:3]}
commerce=read('evidence/consequential009/resources/commerce-r1/artifacts/RESULT.json')
result['commerce_bounds']={'nominal_authored_profit_USD':str(F(50)-36-F(7,4)),'joint_reversal_authored_loss_USD':str(F(36)+20+F(7,4)+30),'qualified_unrestricted_simulated_earned_funds_microUSD':commerce['evidence_grounded_decision']['qualified_unrestricted_simulated_earned_funds_microUSD'],'complete_actual_cost':commerce['evidence_grounded_decision']['complete_actual_cost'],'consequence':'Authored conditional parity can be commercially viable; observed profitable boundary crossing or earned-funded successor is not established. No stronger finance defect established against current explicit labels.'}
result['resources']={'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'cpu_cap_seconds':300,'rss_cap_kib':1048576}
result['probe_sha256']=sha(__file__)
(OUT/'AUDIT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in result.items() if k in ['correlated_gain_geometry','reference_additional_corner_probe','resources','local_source_integrity','commerce_bounds']},indent=2))
