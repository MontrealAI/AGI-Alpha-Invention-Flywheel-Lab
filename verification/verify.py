import argparse, copy, hashlib, importlib.util, json, math, os, pathlib, random, re, sys, time
import numpy as np

SPEC_SHA = 'a34c63f23c3f136a8cabadc8981482347dac1d370e93124d195bf80225ad9a90'
ATOL, RTOL = 1e-6, 1e-8

def sha_file(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def model_sha(model):
    return hashlib.sha256(json.dumps(model, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def reference(model):
    buses, branches = model['buses'], model['branches']
    lookup = {v:i for i,v in enumerate(buses)}
    n, base = len(buses), float(model['base_mva'])
    p = np.asarray(model['p_mw'], dtype=float).copy()
    p[0] -= p.sum()
    result = []
    for target in branches:
        if not target['status']:
            continue
        active = [b for b in branches if b['status'] and b['id'] != target['id']]
        adjacency = [set() for _ in buses]
        for b in active:
            i,j=lookup[b['from_bus']],lookup[b['to_bus']]
            adjacency[i].add(j); adjacency[j].add(i)
        seen, stack = {0}, [0]
        while stack:
            i = stack.pop()
            for j in adjacency[i] - seen:
                seen.add(j); stack.append(j)
        if len(seen) != n:
            result.append({'outage':target['id'],'status':'ISLANDING_UNKNOWN','flows_mw':None,'overloads':[]})
            continue
        lap = np.zeros((n,n)); rhs = p.copy()
        for b in active:
            i,j=lookup[b['from_bus']],lookup[b['to_bus']]
            tap = b['tap'] or 1.0
            coefficient = base / (b['x'] * tap)
            shift = math.radians(b['shift_deg'])
            lap[i,i] += coefficient; lap[j,j] += coefficient
            lap[i,j] -= coefficient; lap[j,i] -= coefficient
            rhs[i] += coefficient*shift; rhs[j] -= coefficient*shift
        theta = np.zeros(n)
        theta[1:] = np.linalg.solve(lap[1:,1:],rhs[1:])
        flows, overloads = [], []
        for b in branches:
            f = 0.0
            if b['status'] and b['id'] != target['id']:
                i,j=lookup[b['from_bus']],lookup[b['to_bus']]
                f = base/(b['x']*(b['tap'] or 1.0))*(theta[i]-theta[j]-math.radians(b['shift_deg']))
                if b['rate_mw'] > 0 and abs(f) > b['rate_mw'] + ATOL:
                    overloads.append(b['id'])
            flows.append(float(f))
        result.append({'outage':target['id'],'status':'CONNECTED','flows_mw':flows,'overloads':overloads})
    return result

def parse_case_independently(path):
    text = pathlib.Path(path).read_text()
    text = '\n'.join(line.split('%')[0] for line in text.splitlines())
    def matrix(name):
        content = re.search(r'mpc\.'+name+r'\s*=\s*\[(.*?)\]\s*;',text,re.S).group(1)
        return [[float(x) for x in row.split()] for row in content.split(';') if row.strip()]
    base = float(re.search(r'mpc\.baseMVA\s*=\s*([0-9.eE+-]+)\s*;',text).group(1))
    bus, gen, branch = matrix('bus'), matrix('gen'), matrix('branch')
    ids = [int(row[0]) for row in bus]
    p = [-row[2] for row in bus]
    for g in gen:
        if int(g[7]): p[ids.index(int(g[0]))] += g[1]
    return {'base_mva':base,'buses':ids,'p_mw':p,'branches':[{'id':i,'from_bus':int(b[0]),'to_bus':int(b[1]),'x':b[3],'tap':b[8] or 1.,'shift_deg':b[9],'rate_mw':b[5],'status':int(b[10])} for i,b in enumerate(branch)]}

def equivalent_parsing(a,b):
    a=copy.deepcopy(a);b=copy.deepcopy(b)
    for model in (a,b):
        model['p_mw'][0] -= sum(model['p_mw'])
        for branch in model['branches']:
            branch['tap'] = branch['tap'] or 1.0
    return a == b

def protected_panel():
    rng = random.Random(90372111)
    cases = []
    for k in range(12):
        n = 4+k%5
        edges = [(i,(i+1)%n) for i in range(n)]
        for i in range(n):
            for j in range(i+2,n):
                if (i,j) not in edges and (j,i) not in edges and rng.random()<0.35:
                    edges.append((i,j))
        branches = [{'id':i,'from_bus':a+1,'to_bus':b+1,'x':round(rng.uniform(0.03,0.4),4),'tap':round(rng.uniform(0.85,1.15),4),'shift_deg':round(rng.uniform(-8,8),4),'rate_mw':float(rng.randrange(30,100)),'status':1} for i,(a,b) in enumerate(edges)]
        p = [float(rng.randrange(-90,90)) for _ in range(n)]
        p[0] -= sum(p)
        cases.append({'name':'held-'+str(k),'model':{'base_mva':100.0,'buses':list(range(1,n+1)),'p_mw':p,'branches':branches}})
    branches = [{'id':i,'from_bus':a,'to_bus':b,'x':x,'tap':tap,'shift_deg':shift,'rate_mw':rate,'status':1} for i,(a,b,x,tap,shift,rate) in enumerate([(1,2,.11,1,0,80),(2,3,.17,.92,7,70),(3,1,.21,1.03,-4,50),(3,4,.12,1,0,90)])]
    cases.append({'name':'held-bridge','model':{'base_mva':100.0,'buses':[1,2,3,4],'p_mw':[70.,-20.,-15.,-35.],'branches':branches}})
    return cases

def compare(model, actual):
    expected = reference(model)
    errors = []
    actual_rows = actual.get('contingencies')
    if not isinstance(actual_rows,list):
        return ['missing contingencies']
    by_id = {row['outage']:row for row in actual_rows}
    if len(by_id) != len(actual_rows) or set(by_id) != {r['outage'] for r in expected}:
        return ['outage identity mismatch']
    for e in expected:
        a = by_id[e['outage']]
        if a.get('status') != e['status']:
            errors.append(f"outage {e['outage']} status {a.get('status')} != {e['status']}")
            continue
        if e['flows_mw'] is None:
            if a.get('flows_mw') is not None:
                errors.append('island returned flows')
            continue
        try:
            af = np.asarray(a['flows_mw'],dtype=float)
            ef = np.asarray(e['flows_mw'])
            if af.shape != ef.shape or not np.isfinite(af).all() or not np.allclose(af,ef,atol=ATOL,rtol=RTOL):
                errors.append(f"outage {e['outage']} flow mismatch")
            if set(a['overloads']) != set(e['overloads']):
                errors.append(f"outage {e['outage']} overload mismatch")
        except (KeyError,TypeError,ValueError):
            errors.append('invalid flows/overloads shape')
    return errors

def evaluate(candidate_path,expected_sha,case_paths,output,spec_path=None):
    candidate_path=pathlib.Path(candidate_path).resolve()
    if sha_file(candidate_path) != expected_sha:
        raise ValueError('candidate identity mismatch')
    spec_path = pathlib.Path(spec_path) if spec_path else pathlib.Path(__file__).with_name('spec.json')
    if sha_file(spec_path) != SPEC_SHA:
        raise ValueError('verifier specification identity mismatch')
    output=pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=False)
    os.environ['OPENBLAS_NUM_THREADS']='1'
    module_spec=importlib.util.spec_from_file_location('frozen_candidate',candidate_path)
    candidate=importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(candidate)
    results=[]; start=time.monotonic()
    cases=protected_panel()
    for path in case_paths:
        parsed = candidate.load_case(path)
        independently_parsed = parse_case_independently(path)
        results.append({'name':'independent-parser-'+pathlib.Path(path).name,'passed':equivalent_parsing(parsed,independently_parsed),'errors':[] if equivalent_parsing(parsed,independently_parsed) else ['candidate parsing differs from independent data extraction']})
        cases.append({'name':pathlib.Path(path).name,'model':independently_parsed,'input_sha256':sha_file(path)})
    for case in cases:
        model=case['model']; cache={}
        try:
            actual=candidate.screen(copy.deepcopy(model),cache=cache)
            errors=compare(model,actual)
            second=candidate.screen(copy.deepcopy(model),cache=cache)
            errors+=compare(model,second)
            if not second.get('cache_reused'):
                errors.append('identical model did not reuse populated result cache')
            results.append({'name':case['name'],'passed':not errors,'errors':errors,'model_sha256':model_sha(model),'input_sha256':case.get('input_sha256'),'contingencies':len(actual.get('contingencies',[]))})
        except Exception as e:
            results.append({'name':case['name'],'passed':False,'errors':[type(e).__name__+': '+str(e)],'model_sha256':model_sha(model)})
        if time.monotonic()-start>120:
            raise RuntimeError('verifier wall budget exceeded')
    root=cases[0]['model']
    mutations={
        'tap':lambda m:m['branches'][0].__setitem__('tap',.72),
        'phase':lambda m:m['branches'][0].__setitem__('shift_deg',19.0),
        'rating':lambda m:m['branches'][0].__setitem__('rate_mw',.01),
        'reactance':lambda m:m['branches'][0].__setitem__('x',.041),
        'injection':lambda m:m['p_mw'].__setitem__(1,m['p_mw'][1]+17.0),
        'base':lambda m:m.__setitem__('base_mva',50.0),
        'topology':lambda m:m['branches'][0].__setitem__('to_bus',3),
        'status':lambda m:m['branches'][0].__setitem__('status',0),
        'branch_order':lambda m:m['branches'].reverse(),
        'bus_order':lambda m:(m['buses'].reverse(),m['p_mw'].reverse()),
    }
    for name,change in mutations.items():
        cache={}; candidate.screen(copy.deepcopy(root),cache=cache)
        model=copy.deepcopy(root); change(model)
        try:
            actual=candidate.screen(model,cache=cache); errors=compare(model,actual)
            if actual.get('cache_reused'):
                errors.append('stale complete-result cache reused')
            results.append({'name':'cache-'+name,'passed':not errors,'errors':errors})
        except Exception as e:
            results.append({'name':'cache-'+name,'passed':False,'errors':[str(e)]})
    bad_cases={
        'nonfinite':lambda m:m['p_mw'].__setitem__(0,float('nan')),
        'duplicate_bus':lambda m:m['buses'].__setitem__(1,m['buses'][0]),
        'invalid_reference':lambda m:m['branches'][0].__setitem__('to_bus',999),
        'zero_reactance':lambda m:m['branches'][0].__setitem__('x',0),
        'duplicate_branch':lambda m:m['branches'][1].__setitem__('id',m['branches'][0]['id']),
        'oversized':lambda m:m.__setitem__('buses',list(range(257))),
    }
    for name,change in bad_cases.items():
        model=copy.deepcopy(root); change(model)
        try:
            candidate.screen(model); passed=False; error='malformed model accepted'
        except (ValueError,TypeError,KeyError):
            passed=True; error=None
        except Exception as e:
            passed=False; error='unexpected exception '+type(e).__name__
        results.append({'name':'reject-'+name,'passed':passed,'errors':[] if passed else [error]})
    report={'schema':'agi-alpha-independent-dc-verification-v1','candidate_sha256':expected_sha,'spec_sha256':SPEC_SHA,'verifier_sha256':sha_file(__file__),'all_passed':all(r['passed'] for r in results),'checks':results,'duration_seconds':time.monotonic()-start,'scope':'Deterministic DC engineering validation; procedural separation, shared host and model family; zero statistical confirmation alpha consumed.'}
    (output/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (output/'exposed_panel.json').write_text(json.dumps(cases,indent=2,allow_nan=False)+'\n')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--sha256',required=True);p.add_argument('--case',action='append',default=[]);p.add_argument('--output',required=True);p.add_argument('--spec');a=p.parse_args()
    report=evaluate(a.candidate,a.sha256,a.case,a.output,a.spec)
    print(json.dumps({'all_passed':report['all_passed'],'checks':len(report['checks']),'output':a.output}))
    return 0 if report['all_passed'] else 1

if __name__=='__main__':
    sys.exit(main())
