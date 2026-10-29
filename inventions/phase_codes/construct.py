"""Trusted bounded inverse construction of sparse nonadditive phase-gate codes.

Classical minimum-distance scaffolds remove bit-flip confusability; SSLP moment
constraints enforce distance >=3. Numeric solutions are NOT certificates.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, pathlib, time, resource
import numpy as np
from scipy.optimize import linprog

def words(n: int):
    xs = np.arange(1 << n, dtype=np.uint32)
    syndrome = np.zeros(len(xs), dtype=np.uint32)
    for bit in range(n):
        syndrome ^= ((xs >> bit) & 1) * (bit + 1)
    return xs[syndrome == 0]

def parity(xs, mask):
    v = xs & np.uint32(mask)
    v ^= v >> 16; v ^= v >> 8; v ^= v >> 4; v ^= v >> 2; v ^= v >> 1
    return v & 1

def construct(n, logical, modulus, seed, out):
    if not (8 <= n <= 20 and logical == 2 and modulus == 4):
        raise ValueError('RESOURCE_OR_TASK_BOUND')
    start = time.monotonic(); cpu = time.process_time()
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=False)
    xs = words(n); rng = np.random.default_rng(seed)
    colors = [int(rng.integers(1, 1 << n)) for _ in range(logical)]
    label = sum(parity(xs, mask) << j for j, mask in enumerate(colors))
    charge = np.zeros(len(xs), np.uint32)
    for bit in range(n): charge += (xs >> bit) & 1
    charge %= modulus
    masks = [0] + [1 << j for j in range(n)] + [(1 << a) | (1 << b) for a, b in itertools.combinations(range(n), 2)]
    states = []; reports = []
    for j in range(1 << logical):
        residue = 1 if j == (1 << logical)-1 else 0
        support = xs[(label == j) & (charge == residue)]
        if len(support) == 0:
            reports.append({'logical':j,'success':False,'reason':'EMPTY_SUPPORT'}); break
        A = np.stack([1 - 2 * parity(support, m).astype(np.int8) for m in masks]).astype(float)
        b = np.zeros(len(masks)); b[0] = 1
        # Deterministic bounded LP; all nontrivial one-/two-body moments zero.
        result = linprog(np.zeros(len(support)), A_eq=A, b_eq=b, bounds=(0, None), method='highs', options={'time_limit':45})
        report = {'logical':j,'phase_residue':residue,'support_pool':len(support),'success':bool(result.success),'status':int(result.status),'message':str(result.message)}
        if result.success:
            chosen = result.x > 1e-9
            report.update(nonzero=int(chosen.sum()), max_residual=float(np.max(np.abs(A @ result.x - b))))
            states.append({'logical':j,'phase_residue':residue,'words':[int(x) for x in support[chosen]],'probabilities_float':[float(x) for x in result.x[chosen]]})
        reports.append(report)
        if not result.success: break
    record = {'schema':'phase-code-numeric-development/v1','n':n,'logical_qubits':logical,'K':1 << logical,'phase_modulus':modulus,'physical_weights':[1]*n,'classical_parity_columns':list(range(1,n+1)),'color_masks':colors,'seed':seed,'target_residues':[0]*((1<<logical)-1)+[1],'moment_masks':masks,'states':states,'reports':reports,'all_numeric_feasible':len(states)==1<<logical,'exact_certificate':False,'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'Development synthesis; floating LP is not a quantum-code certificate, new-capability result, device validation or business result.'}
    (out/'NUMERIC.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ['n','K','seed','all_numeric_feasible','wall_seconds','cpu_seconds','peak_rss_kib']}))
    return record

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--n',type=int,default=18);p.add_argument('--logical',type=int,default=2);p.add_argument('--modulus',type=int,default=4);p.add_argument('--seed',type=int,default=42017);p.add_argument('--output',required=True);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(240,240))
    construct(a.n,a.logical,a.modulus,a.seed,a.output)
