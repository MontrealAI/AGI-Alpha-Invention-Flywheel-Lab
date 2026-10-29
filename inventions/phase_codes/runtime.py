"""Sparse ideal encode / local-phase / single-qubit-noise / recovery instrument.

This simulates a mathematical code and ideal recovery, not hardware or an
implemented fault-tolerant state-preparation or syndrome-extraction circuit.
"""
from __future__ import annotations
import argparse, hashlib, json, math, pathlib, time, resource
from fractions import Fraction
import numpy as np

def pauli(state, n, qubit, op):
    if op not in ('I','X','Y','Z') or not 0 <= qubit < n: raise ValueError('BAD_PAULI')
    if op == 'I': return dict(state)
    mask=1 << (n-1-qubit); out={}
    for word,amp in state.items():
        b=bool(word & mask); dest=word ^ mask if op in ('X','Y') else word
        phase=(-1 if b else 1) if op=='Z' else ((-1j if b else 1j) if op=='Y' else 1)
        out[dest]=out.get(dest,0)+phase*amp
    return out

def damping(state,n,qubit,gamma):
    if not 0 <= gamma <= 1 or not 0 <= qubit < n:raise ValueError('BAD_NOISE')
    mask=1 << (n-1-qubit);a={};b={}
    for word,amp in state.items():
        if word & mask:
            a[word]=amp*math.sqrt(1-gamma)
            b[word ^ mask]=b.get(word ^ mask,0)+amp*math.sqrt(gamma)
        else:a[word]=amp
    return [a,b]

class Instrument:
    def __init__(self,path,expected_sha256):
        raw=pathlib.Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('CANDIDATE_IDENTITY_MISMATCH')
        d=json.loads(raw);self.n=d['n'];self.weights=d['physical_weights'];self.labels=d['logical_order']
        if self.n>20 or len(d['codewords'])!=4 or self.labels!=['00','01','10','11']:raise ValueError('RESOURCE_OR_CODE_SHAPE')
        self.basis=[]
        for row in d['codewords']:
            state={int(word,2):math.sqrt(float(Fraction(prob))) for word,prob in row['probabilities'].items()}
            self.basis.append(state)
        self.errors=[(-1,'I')]+[(q,p) for q in range(self.n) for p in ('X','Y','Z')]
        self.error_basis=[[dict(v) if q<0 else pauli(v,self.n,q,p) for v in self.basis] for q,p in self.errors]
        self.code_sha256=expected_sha256

    def encode(self,logical):
        alpha=np.asarray(logical,dtype=complex)
        if alpha.shape!=(4,) or not np.isfinite(alpha).all() or abs(np.vdot(alpha,alpha)-1)>1e-10:raise ValueError('BAD_LOGICAL_STATE')
        out={}
        for coeff,state in zip(alpha,self.basis):
            for word,amp in state.items():out[word]=out.get(word,0)+coeff*amp
        return out

    def phase(self,state):
        return {word:amp*(1j**sum(w*((word>>(self.n-1-j))&1) for j,w in enumerate(self.weights))) for word,amp in state.items()}

    def recover(self,branches):
        rho=np.zeros((4,4),complex)
        for state in branches:
            for basis in self.error_basis:
                coeff=np.array([sum(np.conjugate(amp)*state.get(word,0) for word,amp in vec.items()) for vec in basis])
                rho+=np.outer(coeff,coeff.conjugate())
        input_probability=sum(float(sum(abs(a)**2 for a in state.values())) for state in branches)
        return {'logical_density':rho,'input_probability':input_probability,'correctable_probability':float(np.trace(rho).real),'unrecovered_probability':float(max(0,input_probability-np.trace(rho).real))}

    def logical_kraus(self, noise, before=False):
        columns=[]
        for vector in self.basis:
            branches=noise(vector) if before else [self.phase(vector)]
            branches=[self.phase(x) for x in branches] if before else [y for x in branches for y in noise(x)]
            columns.append(branches)
        matrices=[]
        for branch in range(len(columns[0])):
            for basis in self.error_basis:
                mat=np.array([[sum(np.conjugate(a)*columns[col][branch].get(w,0) for w,a in vec.items()) for col in range(4)] for vec in basis])
                matrices.append(mat)
        return matrices

    def process(self,noise,before=False):
        mats=self.logical_kraus(noise,before)
        target=np.diag([1,1,1,1j]);completeness=sum((m.conj().T@m for m in mats),start=np.zeros((4,4),complex))
        fidelity=sum(abs(np.trace(target.conj().T@m))**2 for m in mats)/16
        return {'entanglement_fidelity':float(fidelity.real),'max_completeness_residual':float(np.max(np.abs(completeness-np.eye(4))))}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(600,600))
    out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=False);t=time.monotonic();cpu=time.process_time();m=Instrument(a.candidate,a.sha256)
    alpha=np.array([1,1,1,1],complex)/2;ideal=np.array([1,1,1,1j],complex)/2
    tests=[]
    for q,op in m.errors:
        branches=[m.phase(m.encode(alpha))];branches=branches if q<0 else [pauli(branches[0],m.n,q,op)]
        r=m.recover(branches);f=float((ideal.conj()@r['logical_density']@ideal).real)
        tests.append({'qubit':q,'pauli':op,'logical_fidelity':f,'unrecovered_probability':r['unrecovered_probability']})
    process=[]
    for q in (0,m.n//2,m.n-1):
        for gamma in (.25,1.0):
            for before in (False,True):
                result=m.process(lambda state,q=q,gamma=gamma:damping(state,m.n,q,gamma),before=before)
                process.append({'qubit':q,'amplitude_damping':gamma,'before_gate':before,**result})
    report={'schema':'ideal-protected-phase-operation/v1','candidate_sha256':a.sha256,'pauli_state_tests':tests,'reference_entangled_process_tests':process,'all_development_checks_passed':all(t['logical_fidelity']>1-1e-10 and t['unrecovered_probability']<1e-10 for t in tests) and all(t['entanglement_fidelity']>1-1e-10 and t['max_completeness_residual']<1e-10 for t in process),'logical_output_density':[[[float(x.real),float(x.imag)] for x in row] for row in m.recover([m.phase(m.encode(alpha))])['logical_density']],'wall_seconds':time.monotonic()-t,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'Builder development; exact quantum-code claim requires separate certifier. Ideal mathematical recovery; no physical implementation, gate-noise threshold, business or full-cost advantage claim.'}
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['all_development_checks_passed','wall_seconds','cpu_seconds','peak_rss_kib']}))
