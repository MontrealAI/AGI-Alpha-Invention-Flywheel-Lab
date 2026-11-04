import csv, hashlib, itertools, json, math, resource, time
from fractions import Fraction as F
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parent
def local(e): return e.tag.rsplit('}', 1)[-1]
def ast(e):
    kind = local(e)
    if kind == 'math': return ast(e[0])
    if kind == 'ci': return ('symbol', e.text.strip())
    if kind == 'cn': return ('number', F(e.text.strip()))
    if kind != 'apply' or local(e[0]) not in {'times','divide','plus','minus','power','ln'}: raise ValueError('unsupported MathML')
    return (local(e[0]), *[ast(x) for x in e[1:]])
def value(e, env):
    k = e[0]
    if k == 'number': return float(e[1])
    if k == 'symbol': return env[e[1]]
    a = [value(x, env) for x in e[1:]]
    if k == 'times': return math.prod(a)
    if k == 'divide': return a[0]/a[1]
    if k == 'plus': return sum(a)
    if k == 'minus': return a[0]-sum(a[1:]) if len(a)>1 else -a[0]
    if k == 'ln': return math.log(a[0])
    if k == 'power': return a[0]**a[1]
    raise ValueError(k)
def read_tsv(name):
    with (ROOT/'source'/name).open() as h: return list(csv.DictReader(h, delimiter='\t'))
def load():
    root = ET.parse(ROOT/'source/model.xml').getroot()
    p = {x['parameterId']: float(x['nominalValue']) for x in read_tsv('parameters.tsv')}
    species = [x.attrib['id'] for x in root.iter() if local(x)=='species']
    initial = {x.attrib['symbol']: ast(next(y for y in x if local(y)=='math')) for x in root.iter() if local(x)=='initialAssignment'}
    reactions=[]
    for r in root.iter():
        if local(r)!='reaction': continue
        rhs=ast(next(x for x in r.iter() if local(x)=='math'))
        changes={}
        for sub in r:
            sign=-1 if local(sub)=='listOfReactants' else 1 if local(sub)=='listOfProducts' else 0
            if sign:
                for s in sub: changes[s.attrib['species']]=sign*float(s.attrib.get('stoichiometry','1'))
        reactions.append((r.attrib['id'],rhs,changes))
    return p,species,initial,reactions
def rref(rows, n):
    a=[[F(x) for x in row] for row in rows if any(row)]
    piv=[];r=0
    for c in range(n):
        s=next((j for j in range(r,len(a)) if a[j][c]),None)
        if s is None: continue
        a[r],a[s]=a[s],a[r];z=a[r][c];a[r]=[x/z for x in a[r]]
        for j in range(len(a)):
            if j!=r and a[j][c]:
                z=a[j][c];a[j]=[x-z*y for x,y in zip(a[j],a[r])]
        piv.append(c);r+=1
        if r==len(a):break
    return a,piv
def nullspace(rows,n):
    a,piv=rref(rows,n);basis=[]
    for c in range(n):
        if c in piv:continue
        v=[F(0)]*n;v[c]=F(1)
        for r,j in enumerate(piv):v[j]=-a[r][c]
        basis.append(v)
    return basis
def compile_weights(p,species,initial,reactions):
    names=species+list(p);n=len(names);index={s:i for i,s in enumerate(names)}
    def unit(s):
        x=[F(0)]*n
        if s!='cell':x[index[s]]=F(1)
        return x
    rows=[]
    def add(a,b):return [x+y for x,y in zip(a,b)]
    def sub(a,b):return [x-y for x,y in zip(a,b)]
    def wt(e,exponent):
        if e[0]=='number':return [F(0)]*n
        if e[0]=='symbol':return unit(e[1])
        k=e[0];a=[wt(x,exponent) for x in e[1:]]
        if k in {'plus','minus'}:
            for x in a[1:]:rows.append(sub(x,a[0]))
            return a[0]
        if k=='times':return [sum(x) for x in zip(*a)]
        if k=='divide':return sub(a[0],a[1])
        if k=='ln':rows.append(a[0]);return [F(0)]*n
        if k=='power':
            rows.append(a[1])
            if e[2][0]=='number':v=e[2][1]
            elif e[2]==('symbol','n_Hill'):v=F(exponent)
            else:raise ValueError('unsupported symbolic power')
            return [v*x for x in a[0]]
        raise ValueError(k)
    for exponent in [2,3]:
        for s,e in initial.items():rows.append(sub(unit(s),wt(e,exponent)))
        for name,e,changes in reactions:
            w=wt(e,exponent)
            for s in changes:rows.append(sub(w,unit(s)))
        rows.append(unit('background'))
        rows.append(add(unit('scale'),unit('GFP')))
        rows.append(unit('sigma'))
    return names,rows,unit
def integrate(p,species,initial,reactions,times):
    params=dict(p,cell=1.)
    y0=[value(initial[s],params) for s in species]
    changes=np.array([[c.get(s,0.) for _,_,c in reactions] for s in species])
    def fun(t,y):
        env=dict(params,**dict(zip(species,y)))
        return changes@np.array([value(e,env) for _,e,_ in reactions])
    solution=solve_ivp(fun,(0.,float(max(times))),y0,method='LSODA',t_eval=times,rtol=1e-9,atol=1e-12)
    if not solution.success:raise RuntimeError(solution.message)
    obs=p['background']+p['scale']*solution.y[species.index('GFP')]
    return solution.y,obs,solution.nfev
def main():
    begin=time.monotonic();p,species,initial,reactions=load();names,rows,unit=compile_weights(p,species,initial,reactions)
    n=len(names);basis=nullspace(rows,n)
    candidates=species
    ordinary=[];tested=0
    for k in range(len(candidates)+1):
        for subset in itertools.combinations(candidates,k):
            tested+=1
            if not nullspace(rows+[unit(s) for s in subset],n):ordinary.append(subset)
        if ordinary:break
    remaining=list(rows);constructed=[];trace=[]
    while nullspace(remaining,n):
        before=len(nullspace(remaining,n))
        options=[(len(nullspace(remaining+[unit(s)],n)),s) for s in candidates if s not in constructed]
        after,s=min(options)
        if after>=before:break
        remaining.append(unit(s));constructed.append(s);trace.append({'ambiguity_before':before,'add_calibrated_absolute_observable':s,'ambiguity_after':after})
    data=read_tsv('measurements.tsv');times=np.array([float(x['time']) for x in data]);observed=np.array([float(x['measurement']) for x in data])
    states,signal,nfev=integrate(p,species,initial,reactions,times)
    witnesses=[]
    bounds={x['parameterId']:(float(x['lowerBound']),float(x['upperBound'])) for x in read_tsv('parameters.tsv')}
    for v in basis:
        choices=[]
        for lam in [.5,.8,.95,1.05,1.25,2.]:
            q={s:p[s]*lam**float(v[names.index(s)]) for s in p}
            if all(lo<=q[s]<=hi for s,(lo,hi) in bounds.items()):choices.append((lam,q))
        lam,q=choices[0] if choices else (1.000000001,{s:p[s]*1.000000001**float(v[names.index(s)]) for s in p})
        moved,output,calls=integrate(q,species,initial,reactions,times)
        intended=np.array([lam**float(v[names.index(s)]) for s in species])[:,None]*states
        witnesses.append({'lambda':lam,'within_declared_parameter_bounds':bool(choices),'parameter_scaling':{s:str(v[names.index(s)]) for s in p if v[names.index(s)]},'relative_output_disagreement':float(np.max(abs(output-signal))/max(abs(signal))),'relative_state_symmetry_error':float(np.max(abs(moved-intended))/max(np.max(abs(intended)),1.)),'solver_calls':calls,'observation_contract_unchanged':True})
    residual=np.log10(signal)-np.log10(observed)
    files={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in (ROOT/'source').iterdir() if x.is_file()}
    report={'scope':'Executed exploratory probe on public measured repressilator model; scale ambiguities only, not complete identifiability or physical experiment validation','source_sha256':files,'data_rows':len(data),'states':len(species),'parameters':len(p),'known_scaling_ambiguity_dimension':len(basis),'generators':[{names[i]:str(x) for i,x in enumerate(v) if x} for v in basis],'constructed_observation_plan':constructed,'construction_trace':trace,'ordinary_exhaustive_minimum_observations':len(ordinary[0]) if ordinary else None,'ordinary_optimal_sets':ordinary,'ordinary_subsets_tested':tested,'constructed_plan_ties_ordinary':bool(ordinary and len(constructed)==len(ordinary[0])),'known_ambiguities_after_plan':len(nullspace(remaining,n)),'numerical_witnesses':witnesses,'nominal_log10_RMSE_on_real_data':float(np.sqrt(np.mean(residual**2))),'nominal_sigma':p['sigma'],'nominal_solver_calls':nfev,'remaining_caveat':'Removing all detected scaling symmetries does not establish structural or practical identifiability. Additional nonlinear symmetries and sloppy finite-data directions may remain. Direct calibrated measurements were only specified, not physically acquired.','human_supplied_mapping':'Researcher/assistant proposed gauge fixing; code derives exact constant-exponent scaling directions from parsed SBML and generates observation plan. No autonomous donor discovery claim.','decision':'NOT_ADMITTED: conventional exact observation-subset route ties constructive plan; no qualified economic failure cohort; demand unmeasured','runtime_seconds':time.monotonic()-begin,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'maximum_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (ROOT/'PROBE_RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['data_rows','known_scaling_ambiguity_dimension','constructed_observation_plan','ordinary_exhaustive_minimum_observations','constructed_plan_ties_ordinary','numerical_witnesses','runtime_seconds','decision']},indent=2))
if __name__=='__main__':main()
