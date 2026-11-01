import sys, itertools, math, collections, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'deps'),str(HERE)]
import stim, tesseract_decoder as td, numpy as np
from kernel import MassKernel
source=stim.DetectorErrorModel('''error(0.2) D0 D1 ^ D1 D2 L0
error(0.3) D0 D2 L0
error(0.15) D0 D2 L1
error(0.07) L0
error(0.11) D1
error(0) D4 L2
''')
def independent_parse(dem):
    out=[]
    for inst in dem.flattened():
        if inst.type!='error': continue
        d=l=0
        for t in inst.targets_copy():
            if t.is_relative_detector_id(): d ^= 1<<t.val
            elif t.is_logical_observable_id(): l ^= 1<<t.val
        out.append((inst.args_copy()[0],d,l))
    return out
def enumerate_joint(events):
    joint=collections.defaultdict(float)
    for assignment in itertools.product((0,1),repeat=len(events)):
        p=1;d=l=0
        for selected,(prob,h,logical) in zip(assignment,events):
            p *= prob if selected else 1-prob
            if selected: d ^= h; l ^= logical
        joint[d,l]+=p
    return joint
merged=td.tesseract.TesseractConfig(source).compile_decoder()
normalized=merged.config.dem
compiled=td.tesseract.TesseractConfig(normalized,merge_errors=False).compile_decoder()
a=enumerate_joint(independent_parse(source));b=enumerate_joint(independent_parse(normalized))
assert max(abs(a[x]-b[x]) for x in a.keys()|b.keys())<1e-14
assert normalized.num_detectors==5 and normalized.num_observables==3
parsed=independent_parse(normalized)
assert len(parsed)==4
assert any(abs(p-.38)<1e-14 and d==5 and l==1 for p,d,l in parsed)
assert any(abs(p-.15)<1e-14 and d==5 and l==2 for p,d,l in parsed)
k=MassKernel(compiled)
for s in {d for (d,l),prob in a.items() if prob>0}:
    pool={m for m in range(1<<len(parsed)) if k.syndrome(m)==s}
    _,decision,masses=k.decide(pool)
    norm=sum(masses.values());actual=sum(prob for (d,l),prob in a.items() if d==s)
    for l,v in masses.items(): assert abs(v/norm-a[s,l]/actual)<1e-14
    syn=np.array([bool(s>>i&1) for i in range(5)])
    obtained,stats=k.pool(syn)
    assert stats['invalid_searches']==0
    assert all(k.syndrome(m)==s for m in obtained)
print(json.dumps({'status':'PASS','original_errors':source.num_errors,'normalized_errors':normalized.num_errors,'max_joint_error':max(abs(a[x]-b[x]) for x in a.keys()|b.keys()),'checks':['XOR duplicate composition','distinct logical effects not merged','correlated separator cancellation','zero-probability removal/index dimensions','full-enumeration class mass','normalized public decoder index consistency']}))
# Independently force every search to fail and require a real valid witness.
class FailedSearch:
    errors=compiled.errors
    def decode_to_errors(self,*args): return []
fk=MassKernel(FailedSearch())
for s in [2,5,7]:
    syn=np.array([bool(s>>i&1) for i in range(5)])
    pool,stats=fk.pool(syn)
    assert stats['fallback'] and stats['invalid_searches']==4
    assert pool and all(fk.syndrome(m)==s for m in pool)
from diversify import ParityDiversifier
div=ParityDiversifier(normalized,3,5)
for s in [0,2,5,7]:
    syn=np.array([bool(s>>i&1) for i in range(5)])
    pool,_=k.pool(syn)
    additions,invalid=div.candidates(syn,k,pool)
    assert all(k.syndrome(m)==s for m in additions)
    first=(s^(s>>64)^(s>>128))%3
    _,base,_=k.decide(pool)
    assert all(any(((k.logical(m)^base)>>j)&1 for j in [first,(first+1)%3]) for m in additions)
print('PASS: forced-all-invalid searches create verified fallback witnesses; parity-diversified candidates preserve syndrome and flip requested competing parity.')
