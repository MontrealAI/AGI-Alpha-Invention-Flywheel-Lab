"""Reconstruct sparse development supports as exact rational moment solutions."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, resource, time
from fractions import Fraction
from sympy import Matrix
from sympy.polys.matrices import DomainMatrix
from sympy.polys.domains import ZZ

def exactify(source, output):
    source=pathlib.Path(source);output=pathlib.Path(output)
    if output.exists():raise FileExistsError(output)
    d=json.loads(source.read_text())
    if not d['all_numeric_feasible']:raise ValueError('NUMERIC_SUPPORT_NOT_FEASIBLE')
    start=time.monotonic();cpu=time.process_time();states=[];reports=[]
    for state in d['states']:
        support=state['words'];masks=d['moment_masks']
        A=Matrix([[1 if (x & mask).bit_count()%2==0 else -1 for x in support] for mask in masks])
        b=Matrix([1]+[0]*(len(masks)-1))
        numerator,den=DomainMatrix.from_Matrix(A).convert_to(ZZ).solve_den_rref(DomainMatrix.from_Matrix(b).convert_to(ZZ))
        vals=[Fraction(int(x),int(den)) for x in numerator.to_Matrix()]
        if any(x<=0 for x in vals):raise ValueError('NONPOSITIVE_EXACT_PROBABILITY')
        if sum(vals)!=1:raise ValueError('EXACT_NORMALIZATION_FAILURE')
        assert all(sum(v*(1 if (x&m).bit_count()%2==0 else -1) for x,v in zip(support,vals))==(1 if m==0 else 0) for m in masks)
        probs={format(x,f'0{d["n"]}b'):str(v) for x,v in zip(support,vals)}
        logical=format(state['logical'],f'0{d["logical_qubits"]}b')
        states.append({'logical':logical,'probabilities':probs})
        reports.append({'logical':logical,'terms':len(probs),'largest_denominator_bits':max(x.denominator.bit_length() for x in vals)})
        print(json.dumps({'exactified':logical,**reports[-1]}),flush=True)
    candidate={'schema':'sparse-phase-code/v1','n':d['n'],'physical_weights':d['physical_weights'],'global_phase_exponent':0,'logical_order':[s['logical'] for s in states],'codewords':states,'amplitude_convention':'positive real square root of each exact rational probability','physical_operation':'tensor product of diag(1,i**w_j), applied once per physical qubit','claimed_distance_lower_bound':3,'source_numeric_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'claim_scope':'Exact algebraic construction only; preparation circuit, noisy recovery and physical hardware not qualified.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(candidate,indent=2)+'\n')
    report={'candidate_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'states':reports,'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'independent_verification':'PENDING'}
    output.with_suffix('.reconstruction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(600,600));exactify(a.source,a.output)
