"""Compile a coherent encoder into uniformly controlled Ry and CNOT gates.

Uses the classical parity scaffold to prepare only its13 free bits, then
computes5 parity bits and erases the2 logical-input helpers. Native rotations
are floating approximations to exact conditional rational probabilities.
"""
from __future__ import annotations
import argparse,json,pathlib,hashlib,math,time,resource
from fractions import Fraction
import numpy as np

def parity_structure(n):
    rows=[sum(((j+1)>>i&1)<<j for j in range(n)) for i in range(n.bit_length())]
    piv=[];rank=0
    for j in range(n):
        i=next((i for i in range(rank,len(rows)) if rows[i]>>j&1),None)
        if i is None:continue
        rows[rank],rows[i]=rows[i],rows[rank]
        for k in range(len(rows)):
            if k!=rank and rows[k]>>j&1:rows[k]^=rows[rank]
        piv.append(j);rank+=1
    free=[i for i in range(n) if i not in piv]
    return [(p,[j for j in free if rows[i]>>j&1]) for i,p in enumerate(piv)],free

def free_word(word,free):
    return sum(((word>>bit)&1) << (len(free)-1-j) for j,bit in enumerate(free))

def tables(candidate):
    d=json.loads(pathlib.Path(candidate).read_text());n=d['n'];pivots,free=parity_structure(n);m=len(free);rows=[]
    distributions=[{free_word(int(w,2),free):Fraction(p) for w,p in r['probabilities'].items()} for r in d['codewords']]
    for depth in range(m):
        cos2=[Fraction(1)]*(1 << (depth+2))
        for logical,dist in enumerate(distributions):
            groups={}
            for word,p in dist.items():
                prefix=word>>(m-depth);bit=word>>(m-depth-1)&1
                groups.setdefault(prefix,[Fraction(0),Fraction(0)])[bit]+=p
            for prefix,(p0,p1) in groups.items():cos2[(logical<<depth)+prefix]=p0/(p0+p1)
        theta=np.array([2*math.acos(math.sqrt(float(p))) for p in cos2])
        transformed=theta.copy();h=1
        while h<len(theta):
            view=transformed.reshape(-1,2*h);a=view[:,:h].copy();b=view[:,h:].copy();view[:,:h]=a+b;view[:,h:]=a-b;h*=2
        native=transformed[np.arange(len(theta)) ^ (np.arange(len(theta))>>1)]/len(theta)
        rows.append({'depth':depth,'cos2':cos2,'theta':theta,'native_angles':native})
    return d,pivots,free,rows

def ry(vector,q,angle,width):
    view=vector.reshape(1<<q,2,1<<(width-q-1));a=view[:,0,:].copy();b=view[:,1,:].copy();c=math.cos(angle/2);s=math.sin(angle/2)
    view[:,0,:]=c*a-s*b;view[:,1,:]=s*a+c*b

def simulate_native(candidate,alpha):
    start=time.monotonic();cpu=time.process_time();d,pivots,free,levels=tables(candidate);m=len(free);width=m+2
    vector=np.zeros(1<<width,complex)
    for j,a in enumerate(alpha):vector[j<<m]=a
    indices=np.arange(len(vector),dtype=np.uint32);swaps={};rotations=cnot=0
    for level in levels:
        target=2+level['depth'];num=1<<target
        for i,angle in enumerate(level['native_angles']):
            ry(vector,target,float(angle),width);rotations+=1
            gray=i^(i>>1);next_i=(i+1)%num;next_gray=next_i^(next_i>>1);toggle=(gray^next_gray).bit_length()-1;control=target-1-toggle
            key=(control,target)
            if key not in swaps:
                a=indices[((indices>>(width-1-control))&1).astype(bool)&~((indices>>(width-1-target))&1).astype(bool)];swaps[key]=(a,a^(1<<(width-1-target)))
            a,b=swaps[key];tmp=vector[a].copy();vector[a]=vector[b];vector[b]=tmp;cnot+=1
    expected=np.zeros_like(vector)
    for logical,row in enumerate(d['codewords']):
        for word,p in row['probabilities'].items():expected[(logical<<m)+free_word(int(word,2),free)]=alpha[logical]*math.sqrt(float(Fraction(p)))
    error=float(np.linalg.norm(vector-expected));norm=float(np.vdot(vector,vector).real)
    # Exact classical reversible extension from free bits to the parity scaffold.
    support={}
    for idx,a in enumerate(vector):
        if abs(a)<1e-14:continue
        logical=idx>>m;f=idx&((1<<m)-1);word=sum(((f>>(m-1-j))&1)<<bit for j,bit in enumerate(free))
        for pivot,controls in pivots:
            if sum(word>>bit&1 for bit in controls)%2:word|=1<<pivot
        support[(logical,word)]=a
    return {'compact_preparation_simulation_wires':width,'peak_encoder_physical_wires':d['n']+2,'final_data_qubits':d['n'],'logical_helpers':2,'helpers_after_parity_erasure':'zero, provided dense color masks match the codeword labels','free_bits':m,'parity_pivots':len(pivots),'native_Ry_count':rotations,'native_CNOT_count_preparation':cnot,'parity_CNOT_count':sum(len(cs) for _,cs in pivots),'statevector_L2_error':error,'compact_state_norm':norm,'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'sparse_prepared_terms':len(support),'discarded_numeric_tail_probability':float(sum(abs(a)**2 for a in vector if abs(a)<1e-14)),'scope':'Executed ideal native Ry/CNOT state preparation. Arbitrary rotations are assumed native; finite gate-set synthesis and noisy fault-tolerant preparation/recovery remain unqualified.'},support

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--numeric',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(600,600))
    out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=False)
    alpha=np.array([1,2j,-3,4-1j],complex);alpha/=np.linalg.norm(alpha);r,support=simulate_native(a.candidate,alpha)
    numeric_bytes=pathlib.Path(a.numeric).read_bytes();numeric=json.loads(numeric_bytes);d=json.loads(pathlib.Path(a.candidate).read_text())
    if hashlib.sha256(numeric_bytes).hexdigest()!=d['source_numeric_sha256']:raise ValueError('NUMERIC_SOURCE_IDENTITY_MISMATCH')
    masks=numeric['color_masks'];helper_error=0.;actual={}
    for (logical,word),amp in support.items():
        recovered_label=sum((word&mask).bit_count()%2<<j for j,mask in enumerate(masks))
        if logical!=recovered_label:helper_error+=abs(amp)**2
        actual[word]=actual.get(word,0)+amp
    d=json.loads(pathlib.Path(a.candidate).read_text());expected={}
    for j,row in enumerate(d['codewords']):
        for word,p in row['probabilities'].items():expected[int(word,2)]=alpha[j]*math.sqrt(float(Fraction(p)))
    final_error=math.sqrt(sum(abs(actual.get(w,0)-expected.get(w,0))**2 for w in actual.keys()|expected.keys()))
    r.update(helper_erasure_failure_probability=helper_error,full_encoded_state_L2_error=final_error,helper_erasure_CNOT_count=sum(m.bit_count() for m in masks),candidate_sha256=hashlib.sha256(pathlib.Path(a.candidate).read_bytes()).hexdigest(),passed=final_error<1e-10 and helper_error<1e-10)
    np.savez_compressed(out/'NATIVE_ROTATIONS.npz',**{f'level{row["depth"]}':row['native_angles'] for row in tables(a.candidate)[3]})
    (out/'ENCODER_REPORT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
