"""Independent black-box finite qualification; never imports builder internals.

The mathematical certificate is checked directly against independently generated
Pauli action and a QR-derived correctable subspace. No candidate source is read
as prose; file bytes are hashed only. This is procedural, non-adversarial blinding.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
from numbers import Integral
from pathlib import Path
import resource
import sys
import time
import traceback

import numpy as np
from scipy.linalg import qr

HERE=Path(__file__).resolve().parent
TOL=2e-8
PAULIS=(np.array([[0,1],[1,0]],complex),
         np.array([[0,-1j],[1j,0]],complex),
         np.array([[1,0],[0,-1]],complex))


def load_complex(data):
    a=np.asarray(data,float)
    return a[...,0]+1j*a[...,1]


def load_state(data):
    return {int(w):complex(r,i) for w,r,i in data}


def local(state,n,q,matrix):
    out={}
    bit=1<<(n-q-1)
    for word,value in state.items():
        column=(word&bit)!=0
        for row in range(2):
            destination=(word&~bit)|(row*bit)
            out[destination]=out.get(destination,0j)+matrix[row,int(column)]*value
    return {w:z for w,z in out.items() if z!=0}


def encode(code,vector):
    out={}
    for state,coefficient in zip(code,vector):
        for word,amplitude in state.items():
            out[word]=out.get(word,0j)+coefficient*amplitude
    return {w:z for w,z in out.items() if z!=0}


def norm2(state):
    return math.fsum(abs(z)**2 for z in state.values())


def scale(state,coefficient):
    return {w:coefficient*z for w,z in state.items() if coefficient*z!=0}


def add_states(*states):
    out={}
    for state in states:
        for w,z in state.items():
            out[w]=out.get(w,0j)+z
    return {w:z for w,z in out.items() if z!=0}


def assert_small(value,label,tolerance=TOL):
    value=float(value)
    if not math.isfinite(value) or value>tolerance:
        raise AssertionError(f'{label}: {value:.12g} > {tolerance:.12g}')


def valid_state(state,n):
    if not isinstance(state,dict):
        raise TypeError('Sparse states/rows must be dictionaries')
    converted={}
    for w,z in state.items():
        if not isinstance(w,Integral) or not 0<=w<2**n:
            raise ValueError('Invalid physical coordinate')
        z=complex(z)
        if not math.isfinite(z.real) or not math.isfinite(z.imag):
            raise ValueError('Nonfinite amplitude')
        converted[int(w)]=z
    return converted


def system(case):
    n=case['n']; code=[load_state(s) for s in case['codewords']]; k=len(code)
    error_states=[code]
    for q in range(n):
        for p in PAULIS:
            error_states.append([local(s,n,q,p) for s in code])
    coordinates=sorted(set().union(*(s for block in error_states for s in block)))
    index={w:i for i,w in enumerate(coordinates)}
    b=np.zeros((len(coordinates),len(error_states)*k),complex)
    for a,block in enumerate(error_states):
        for j,state in enumerate(block):
            for w,z in state.items():
                b[index[w],a*k+j]=z
    gram=b.conj().T@b
    blockgram=gram.reshape(len(error_states),k,len(error_states),k)
    lam=np.trace(blockgram,axis1=1,axis2=3)/k
    residual=np.max(np.abs(blockgram-np.einsum('ab,ij->aibj',lam,np.eye(k))))
    assert_small(residual,'Independent fixture KL residual',1e-10)
    assert_small(np.max(np.abs(gram[:k,:k]-np.eye(k))),'Code orthonormality',1e-10)
    qmat,rmat,_=qr(b,mode='economic',pivoting=True)
    rank=int(np.count_nonzero(np.abs(np.diag(rmat))>1e-9))
    subspace=qmat[:,:rank]
    assert_small(np.linalg.norm(b-subspace@(subspace.conj().T@b)),
                 'Correctable-span QR residual',1e-9)
    for channel in case['channels']:
        matrices=[load_complex(a) for a in channel['kraus']]
        assert_small(np.max(np.abs(sum(a.conj().T@a for a in matrices)-np.eye(2))),
                     'Frozen noise CPTP residual',1e-12)
    return {'n':n,'code':code,'k':k,'errors':error_states,'coordinates':coordinates,
            'index':index,'b':b,'subspace':subspace,'rank':rank,
            'gram_rank':int(np.count_nonzero(np.linalg.eigvalsh(lam)>1e-9)),
            'kl_residual':float(residual),'lam':lam}


def certificate(recovery,s):
    exported=recovery.kraus()
    if not isinstance(exported,(list,tuple)) or not exported:
        raise TypeError('kraus() must return a nonempty list of operators')
    operators=[]
    for operator in exported:
        if len(operator)!=s['k']:
            raise ValueError('Recovery operator row count differs from logical dimension')
        operators.append([valid_state(row,s['n']) for row in operator])
    coordinates=sorted(set(s['coordinates']).union(*(row for op in operators for row in op)))
    index={w:i for i,w in enumerate(coordinates)}
    a=np.zeros((len(operators)*s['k'],len(coordinates)),complex)
    for j,operator in enumerate(operators):
        for l,row in enumerate(operator):
            for w,z in row.items():
                a[j*s['k']+l,index[w]]=z
    u=np.zeros((len(coordinates),s['rank']),complex)
    b=np.zeros((len(coordinates),s['b'].shape[1]),complex)
    destination=[index[w] for w in s['coordinates']]
    u[destination,:]=s['subspace']; b[destination,:]=s['b']
    compressed=a@u
    support_residual=float(np.linalg.norm(a-compressed@u.conj().T))
    projector_residual=float(np.linalg.norm(compressed.conj().T@compressed-np.eye(s['rank']),ord=2))
    contraction_max=float(np.linalg.eigvalsh(a@a.conj().T)[-1])
    assert_small(support_residual,'Kraus action outside correctable subspace')
    assert_small(projector_residual,'Kraus completeness on correctable subspace')
    assert_small(max(0,contraction_max-1),'Global logical-map contraction')
    images=(a@b).reshape(len(operators),s['k'],len(s['errors']),s['k'])
    scalars=np.trace(images,axis1=1,axis2=3)/s['k']
    scalar_images=np.einsum('ja,lm->jlam',scalars,np.eye(s['k']))
    correction_residual=float(np.max(np.abs(images-scalar_images)))
    assert_small(correction_residual,'Recovery Kraus correction of logical matrix units')
    assert_small(np.max(np.abs(np.sum(abs(scalars)**2,axis=0)-1)),
                 'Correction probability of each Pauli')
    return {'operators':operators,'a':a,'coordinates':coordinates,'index':index,
            'operator_count':len(operators),'logical_dimension':s['k'],
            'metrics':{'support_residual':support_residual,'projector_residual':projector_residual,
                       'maximum_contraction_eigenvalue':contraction_max,
                       'correction_residual':correction_residual}}


def certified_density(cert,branches):
    out=np.zeros((cert['logical_dimension'],cert['logical_dimension']),complex)
    for branch in branches:
        vector=np.zeros(len(cert['coordinates']),complex)
        for w,z in branch.items():
            if w in cert['index']:
                vector[cert['index'][w]]=z
        values=(cert['a']@vector).reshape(cert['operator_count'],cert['logical_dimension'])
        out+=values.T@values.conj()
    return out


def check_recover(recovery,cert,s,branches,expected=None,expected_erasure=None):
    branches=[dict(b) for b in branches]
    input_mass=math.fsum(norm2(b) for b in branches)
    tolerance=TOL*max(1,input_mass)
    predicted=certified_density(cert,branches)
    result=recovery.recover(branches)
    density=np.asarray(result['logical_density'],complex)
    if density.shape!=(s['k'],s['k']) or not np.all(np.isfinite(density)):
        raise ValueError('Invalid logical density output')
    probabilities=[float(result[key]) for key in
                   ('input_probability','correctable_probability','erasure_probability')]
    if not all(math.isfinite(p) for p in probabilities):
        raise ValueError('Nonfinite probability output')
    reported_input,correctable,erasure=probabilities
    trace=float(np.trace(density).real)
    assert_small(abs(reported_input-input_mass),'Raw input mass',tolerance)
    assert_small(abs(correctable-trace),'Correctable mass',tolerance)
    assert_small(abs(erasure-(input_mass-trace)),'Erasure completion mass',tolerance)
    assert_small(max(0,-correctable,-erasure),'Probability nonnegativity',tolerance)
    assert_small(np.max(np.abs(density-density.conj().T)),'Hermiticity',tolerance)
    assert_small(max(0,-float(np.linalg.eigvalsh((density+density.conj().T)/2)[0])),
                 'Positive logical density',tolerance)
    assert_small(np.max(np.abs(density-predicted)),'Agreement with exported Kraus map',tolerance)
    if expected is not None:
        assert_small(np.max(np.abs(density-expected)),'Independent logical target',tolerance)
    if expected_erasure is not None:
        assert_small(abs(erasure-expected_erasure),'Independent erasure target',tolerance)


class Recorder:
    def __init__(self): self.records=[]
    def run(self,label,fn):
        start=time.perf_counter()
        try:
            result=fn(); record={'id':label,'pass':True}
        except Exception as exc:
            result=None; record={'id':label,'pass':False,'error':type(exc).__name__+': '+str(exc)}
        record['wall_seconds']=time.perf_counter()-start
        self.records.append(record)
        return result


def run_case(case,Recovery,rec):
    prefix=case['id']
    s=system(case)
    start=time.perf_counter()
    recovery=rec.run(prefix+'/construct',lambda:Recovery(s['n'],[dict(c) for c in s['code']]))
    construction_wall=time.perf_counter()-start
    if recovery is None: return {'id':prefix,'construction_failed':True}
    cert=rec.run(prefix+'/global_certificate',lambda:certificate(recovery,s))
    if cert is None: return {'id':prefix,'certificate_failed':True}
    vectors=[load_complex(p) for p in case['logical_probes']]
    for i,vector in enumerate(vectors):
        for mass in case['input_scales']:
            v=np.sqrt(mass)*vector
            def check_encoding(v=v):
                obtained=valid_state(recovery.encode(v.copy()),s['n'])
                expected=encode(s['code'],v)
                assert_small(max((abs(obtained.get(w,0)-expected.get(w,0))
                                  for w in set(obtained)|set(expected)),default=0),
                             'Encoding linear combination')
            rec.run(f'{prefix}/encode/{i}/{mass}',check_encoding)
    vector=vectors[0]; state=encode(s['code'],vector); target=np.outer(vector,vector.conj())
    rec.run(prefix+'/identity',lambda:check_recover(recovery,cert,s,[state],target,0))
    for q in range(s['n']):
        for pindex,p in enumerate(PAULIS):
            branch=local(state,s['n'],q,p)
            rec.run(f'{prefix}/pauli/{q}/{pindex}',
                    lambda branch=branch:check_recover(recovery,cert,s,[branch],target,0))
    for cindex,channel in enumerate(case['channels']):
        matrices=[load_complex(a) for a in channel['kraus']]
        for vindex,vector in enumerate(vectors):
            branches=[local(encode(s['code'],vector),s['n'],channel['qubit'],a) for a in matrices]
            target=np.outer(vector,vector.conj())
            rec.run(f'{prefix}/cptp/{cindex}/{vindex}',
                    lambda branches=branches,target=target:check_recover(recovery,cert,s,branches,target,0))
    channel=case['channels'][-1]; matrices=[load_complex(a) for a in channel['kraus']]
    tomography=[np.eye(s['k'],dtype=complex)[i] for i in range(s['k'])]
    for i in range(s['k']):
        for j in range(i+1,s['k']):
            for phase in (1,1j):
                v=np.zeros(s['k'],complex); v[i]=1/np.sqrt(2); v[j]=phase/np.sqrt(2)
                tomography.append(v)
    for i,vector in enumerate(tomography):
        branches=[local(encode(s['code'],vector),s['n'],channel['qubit'],a) for a in matrices]
        target=np.outer(vector,vector.conj())
        rec.run(f'{prefix}/tomography/{i}',
                lambda branches=branches,target=target:check_recover(recovery,cert,s,branches,target,0))
    vector=vectors[1]; state=encode(s['code'],vector); target=np.outer(vector,vector.conj())
    branches=[local(state,s['n'],channel['qubit'],a) for a in matrices]
    for mass in case['input_scales']:
        scaled=[scale(b,np.sqrt(mass)) for b in branches]
        rec.run(f'{prefix}/mass/{mass}',
                lambda scaled=scaled,mass=mass:check_recover(recovery,cert,s,scaled,mass*target,0))
    split=[scale(b,1/np.sqrt(3)) for b in reversed(branches) for _ in range(3)]
    rec.run(prefix+'/branch_split_and_order',lambda:check_recover(recovery,cert,s,split,target,0))
    rec.run(prefix+'/empty',lambda:check_recover(recovery,cert,s,[],np.zeros_like(target),0))
    rng=np.random.default_rng(case['outside_seed'])
    raw=rng.normal(size=len(s['coordinates']))+1j*rng.normal(size=len(s['coordinates']))
    orthogonal=raw-s['subspace']@(s['subspace'].conj().T@raw)
    orthogonal/=np.linalg.norm(orthogonal)
    outside={w:z for w,z in zip(s['coordinates'],orthogonal) if z!=0}
    rec.run(prefix+'/outside_subspace',
            lambda:check_recover(recovery,cert,s,[outside],np.zeros_like(target),1))
    mixed=add_states(scale(state,np.sqrt(.61)),scale(outside,np.sqrt(.39)))
    rec.run(prefix+'/coherent_correctable_and_erased',
            lambda:check_recover(recovery,cert,s,[mixed],.61*target,.39))
    combined=[scale(state,np.sqrt(.13)),scale(outside,np.sqrt(.22)),scale(mixed,np.sqrt(.37))]
    rec.run(prefix+'/incoherent_correctable_and_erased',
            lambda:check_recover(recovery,cert,s,combined,(.13+.37*.61)*target,.22+.37*.39))
    raw/=np.linalg.norm(raw)
    arbitrary={w:z for w,z in zip(s['coordinates'],raw)}
    erasure=1-float(np.linalg.norm(s['subspace'].conj().T@raw)**2)
    rec.run(prefix+'/arbitrary_physical_state',
            lambda:check_recover(recovery,cert,s,[arbitrary],expected_erasure=erasure))
    occupied=set(s['coordinates'])
    outsider=next((w for w in range(2**s['n']) if w not in occupied),None)
    if outsider is not None:
        rec.run(prefix+'/outside_coordinate_support',
                lambda:check_recover(recovery,cert,s,[{outsider:1j}],np.zeros_like(target),1))
    if case['id']=='archived_s15':
        phase=lambda branch:{w:(1j**w.bit_count())*z for w,z in branch.items()}
        logical_phase=np.array([1,1,1,1j])
        transformed=logical_phase*vector
        expected=np.outer(transformed,transformed.conj())
        for order in ('before','after'):
            if order=='before':
                noise=[phase(local(state,s['n'],channel['qubit'],a)) for a in matrices]
            else:
                noise=[local(phase(state),s['n'],channel['qubit'],a) for a in matrices]
            rec.run(prefix+'/controlled_s_noise_'+order,
                    lambda noise=noise:check_recover(recovery,cert,s,noise,expected,0))
    return {'id':prefix,'n':s['n'],'logical_dimension':s['k'],
            'active_physical_coordinates':len(s['coordinates']),
            'correctable_subspace_rank':s['rank'],'error_gram_rank':s['gram_rank'],
            'independent_kl_residual':s['kl_residual'],
            'exported_kraus_count':cert['operator_count'],
            'certificate':cert['metrics'],'constructor_wall_seconds':construction_wall}


def invalid_code_tests(cases,Recovery,rec):
    shor=next(c for c in cases if c['id']=='shor9_original')
    code=[load_state(s) for s in shor['codewords']]
    invalid=[('nonorthonormal',9,[scale(code[0],2),code[1]]),
             ('not_phase_correcting',3,[{0:1+0j},{7:1+0j}])]
    for label,n,words in invalid:
        def check(n=n,words=words):
            try: Recovery(n,words)
            except Exception: return True
            raise AssertionError('Clearly invalid code was accepted')
        rec.run('invalid_code/'+label,check)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('candidate',nargs='?')
    parser.add_argument('--output',required=True)
    parser.add_argument('--audit-inputs',action='store_true')
    args=parser.parse_args()
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    wall=time.perf_counter(); cpu=time.process_time()
    inputs=json.loads((HERE/'cases.json').read_text())
    result={'schema':'frontier.general_recovery.qualification.v1','started_utc':started,
            'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'frozen_inputs_sha256':hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest(),
            'blinding':'Separate verifier agent; no candidate source inspected; ordinary shared host, not security isolation.'}
    if args.audit_inputs:
        audits=[]
        for case in inputs['cases']:
            s=system(case)
            audits.append({'id':case['id'],'n':s['n'],'K':s['k'],'error_gram_rank':s['gram_rank'],
                           'correctable_rank':s['rank'],'kl_residual':s['kl_residual']})
        result.update({'input_audit':audits,'pass':True})
    else:
        path=Path(args.candidate).resolve()
        result['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        spec=importlib.util.spec_from_file_location('qualified_recovery_candidate',path)
        module=importlib.util.module_from_spec(spec)
        sys.path.insert(0,str(path.parent))
        sys.modules[spec.name]=module
        rec=Recorder()
        loaded=rec.run('module_import',lambda:spec.loader.exec_module(module) or True)
        cases=[]
        if loaded:
            for case in inputs['cases']:
                try: cases.append(run_case(case,module.Recovery,rec))
                except Exception as exc:
                    rec.records.append({'id':case['id']+'/checker_or_unexpected_error','pass':False,
                                        'error':type(exc).__name__+': '+str(exc),
                                        'traceback':traceback.format_exc()})
            invalid_code_tests(inputs['cases'],module.Recovery,rec)
        result.update({'cases':cases,'checks':rec.records,
                       'passed_checks':sum(r['pass'] for r in rec.records),
                       'total_checks':len(rec.records),
                       'pass':bool(loaded) and bool(cases) and all(r['pass'] for r in rec.records)})
    result['wall_seconds']=time.perf_counter()-wall
    result['cpu_seconds']=time.process_time()-cpu
    result['maximum_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('pass','wall_seconds','cpu_seconds','maximum_rss_kib')}
                     | {key:result[key] for key in ('passed_checks','total_checks') if key in result}))


if __name__=='__main__': main()
