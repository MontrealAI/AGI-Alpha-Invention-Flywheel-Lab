from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp

PAIR = {'capacity_ah': [2.0, 3.0], 'shared_discharge_ah': 0.4, 'r0_ohm': 0.02, 'r1_ohm': 0.01, 'tau_s': 30.0, 'initial_soc': 1.0, 'initial_polarization_v': 0.0, 'ocv_full_v': 4.2, 'ocv_empty_v': 2.5, 'shared_slope_v_per_ah': 0.4, 'pack_total_a': 8.0, 'pack_duration_s': 2100.0, 'segment_loop_ohm': [0.002, 0.002, 0.002], 'unknown_cell_index': 0, 'other_cell_capacity_ah': 2.0, 'short_probe_a': 0.75, 'short_probe_s': 600.0, 'additional_verifier_probe_a': 1.0, 'additional_verifier_probe_s': 1440.0}
SOURCES = {'protocol': 'https://doi.org/10.1016/j.dib.2024.110227', 'data': 'https://doi.org/10.17632/zh58byr53c.2', 'circuit': 'https://arxiv.org/abs/2508.14454', 'status': 'synthetic numerical challenge; no experimental measurements are used'}

def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def cost_bound(shared_hours='20', anchor_hours='1.04', full_anchors=10, sparse_anchors=4):
    f, a = Fraction(shared_hours), Fraction(anchor_hours)
    if f < 20 or a < 0 or type(full_anchors) is not int or type(sparse_anchors) is not int or not 0 <= sparse_anchors < full_anchors:
        raise ValueError('INVALID_PROTOCOL_BOUND')
    full, sparse = f + full_anchors*a, f + sparse_anchors*a
    fraction = (full-sparse)/full
    required = f/(full_anchors-2*sparse_anchors) if full_anchors > 2*sparse_anchors else None
    return {'shared_hours_lower_bound': float(f), 'per_anchor_hours_approximation': float(a), 'full_anchors': full_anchors, 'sparse_anchors': sparse_anchors, 'full_hours_lower_bound_model': float(full), 'sparse_hours_lower_bound_model': float(sparse), 'saved_channel_hours': float(full-sparse), 'maximum_fraction_saved_at_shared_lower_bound': float(fraction), 'exact_fraction': str(fraction), 'half_burden_gate': fraction >= Fraction(1, 2), 'per_anchor_hours_required_for_half_saving': float(required) if required is not None else None, 'scope': 'occupied-channel hours under unchanged shared acquisition and equal per-anchor rates; not a universal dollar-cost bound', 'unmodeled_common_costs': ['charging', 'other rests', 'calibration', 'checking', 'shared-prior acquisition'], 'source': SOURCES['protocol']}

def analytic_ocv(soc, capacity_ah):
    z = np.asarray(soc, float)
    if not np.isfinite(z).all() or np.any(z < -1e-8) or np.any(z > 1+1e-8):
        raise ValueError('SOC_OUTSIDE_SYNTHETIC_DOMAIN')
    q = capacity_ah*(1-z)
    c = (4.2-0.4*capacity_ah-2.5)/(capacity_ah-0.4)**2
    return 4.2-0.4*q-c*np.maximum(q-0.4, 0)**2

def nodal_currents(effective_v, r0_ohm, segment_loop_ohm, total_a):
    e, r, seg = np.asarray(effective_v, float), np.asarray(r0_ohm, float), np.asarray(segment_loop_ohm, float)
    n = len(e)
    if e.ndim != 1 or r.shape != (n,) or n < 1 or seg.shape != (n-1,) or not np.isfinite(np.r_[e,r,seg,total_a]).all() or np.any(r <= 0) or np.any(seg < 0):
        raise ValueError('INVALID_NETWORK_INPUT')
    parent = list(range(2*n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        parent[find(x)] = find(y)
    for k, v in enumerate(seg):
        if v == 0:
            union(k, k+1)
            union(n+k, n+k+1)
    roots = sorted(set(find(x) for x in range(2*n)))
    idx = {x:i for i,x in enumerate(roots)}
    node = np.array([idx[find(x)] for x in range(2*n)])
    g, b = np.zeros((len(roots), len(roots))), np.zeros(len(roots))
    def conduct(x, y, resistance):
        p, m = node[x], node[y]
        if p == m:
            return
        v = 1/resistance
        g[p,p] += v
        g[m,m] += v
        g[p,m] -= v
        g[m,p] -= v
    for k in range(n):
        conduct(k, n+k, r[k])
        b[node[k]] += e[k]/r[k]
        b[node[n+k]] -= e[k]/r[k]
    for k, v in enumerate(seg):
        if v:
            conduct(k, k+1, v/2)
            conduct(n+k, n+k+1, v/2)
    b[node[0]] -= total_a
    b[node[n]] += total_a
    ref = node[n]
    keep = np.array([k for k in range(len(roots)) if k != ref])
    potential = np.zeros(len(roots))
    potential[keep] = np.linalg.solve(g[np.ix_(keep,keep)], b[keep])
    voltage = potential[node[:n]]-potential[node[n:]]
    currents = (e-voltage)/r
    return currents, float(potential[node[0]]-potential[node[n]])

def conservation(effective_v, r0_ohm, segment_loop_ohm, current_a, total_a):
    e, r, seg, i = map(lambda x: np.asarray(x, float), (effective_v,r0_ohm,segment_loop_ohm,current_a))
    if e.shape != r.shape or e.shape != i.shape or seg.shape != (len(e)-1,) or not np.isfinite(np.r_[e,r,seg,i,total_a]).all():
        raise ValueError('INVALID_RESIDUAL_INPUT')
    terminal = e-r*i
    downstream = np.cumsum(i[::-1])[::-1][1:]
    kvl = np.diff(terminal)-seg*downstream
    return {'kcl_abs_a': float(abs(i.sum()-total_a)), 'kvl_max_abs_v': float(np.max(np.abs(kvl))) if len(kvl) else 0.0}

def reference_trace(capacities, total_a=8.0, duration_s=2100.0, step_s=0.5):
    q = np.asarray(capacities, float)
    if q.shape != (4,) or not np.isin(q, [2.,3.]).all():
        raise ValueError('UNREGISTERED_PAIR_CONFIGURATION')
    r, rp, tau, seg = np.full(4,0.02), np.full(4,0.01), np.full(4,30.0), np.full(3,0.002)
    def derivative(t, state):
        e = np.array([analytic_ocv(state[k],q[k]) for k in range(4)])-state[4:]
        i,_ = nodal_currents(e,r,seg,total_a)
        return np.r_[-i/(3600*q), (rp*i-state[4:])/tau]
    times = np.arange(0,duration_s+step_s/2,step_s)
    if times[-1] != duration_s:
        raise ValueError('NONINTEGRAL_OUTPUT_GRID')
    sol = solve_ivp(derivative,[0,duration_s],np.r_[np.ones(4),np.zeros(4)],method='DOP853',t_eval=times,rtol=1e-10,atol=1e-12,max_step=2.0)
    if not sol.success or sol.y.shape != (8,len(times)):
        raise RuntimeError('INDEPENDENT_INTEGRATION_INCOMPLETE')
    currents, voltage, kcl, kvl = [],[],[],[]
    for state in sol.y.T:
        e = np.array([analytic_ocv(state[k],q[k]) for k in range(4)])-state[4:]
        i,v = nodal_currents(e,r,seg,total_a)
        residual = conservation(e,r,seg,i,total_a)
        currents.append(i)
        voltage.append(v)
        kcl.append(residual['kcl_abs_a'])
        kvl.append(residual['kvl_max_abs_v'])
    return {'time_s':times,'current_a':np.asarray(currents),'terminal_v':np.asarray(voltage),'soc':sol.y[:4].T,'kcl_max_abs_a':max(kcl),'kvl_max_abs_v':max(kvl),'solver':'independent two-rail nodal KCL plus DOP853, analytic OCV'}

def trace_metrics(candidate, reference, total_a=8.0):
    a,b = np.asarray(candidate,float), np.asarray(reference,float)
    if a.shape != b.shape or a.ndim != 2 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('TRACE_SHAPE_OR_FINITE_ERROR')
    scale = abs(total_a)/a.shape[1]
    if scale == 0:
        raise ValueError('ZERO_CURRENT_METRIC_SCALE')
    rmse = np.sqrt(np.mean((a-b)**2,axis=0))
    peak_a, peak_b = np.max(np.abs(a),axis=0),np.max(np.abs(b),axis=0)
    return {'rmse_a_per_branch':rmse.tolist(),'nrmse_per_branch':(rmse/scale).tolist(),'max_abs_difference_a':float(np.max(np.abs(a-b))),'peak_abs_error_a_per_branch':np.abs(peak_a-peak_b).tolist(),'peak_relative_error_per_branch':(np.abs(peak_a-peak_b)/np.maximum(peak_b,1e-15)).tolist(),'complete_trace_used':True}

def short_trace_pair():
    rows=[]
    for current, duration in [(.75,600.),(1.,1440.)]:
        t = np.arange(0,duration+1.,1.)
        q = current*t/3600
        polarization = .01*current*(-np.expm1(-t/30))
        traces = [analytic_ocv(1-q/c,c)-.02*current-polarization for c in [2.,3.]]
        difference = float(np.max(np.abs(traces[0]-traces[1])))
        rows.append({'current_a':current,'duration_s':duration,'maximum_discharged_ah':float(q.max()),'max_voltage_difference_v':difference,'identical_within_1e_minus_12_v':difference<1e-12})
    return {'probes':rows,'max_voltage_difference_v':max(r['max_voltage_difference_v'] for r in rows),'identical_within_1e_minus_12_v':all(r['identical_within_1e_minus_12_v'] for r in rows),'argument':'Both models have the same OCV as a function of cumulative discharge through 0.4 Ah and identical R0, Rp and tau; identical current histories in that range yield identical observed voltage histories.'}

def identify_observation(observed_v, predicted_v, error_v=.002):
    if not np.isfinite(np.r_[observed_v,predicted_v,error_v]).all() or error_v < 0:
        raise ValueError('INVALID_OBSERVATION')
    return [k for k,v in enumerate(predicted_v) if abs(float(observed_v)-float(v)) <= error_v+1e-12]

def independent_probe_check(module):
    cells = make_constructor_cells(module,[2.,3.])
    found = module.minimum_separating_probe(cells,observation_error_v=.002,nominal_capacity_ah=2.)
    swapped = module.minimum_separating_probe(cells[::-1],observation_error_v=.002,nominal_capacity_ah=2.)
    expected=[]
    for fraction in [.05,.10,.20,.30,.40,.50,.60]:
        for rate in [.15,.5,.75]:
            current, duration = rate*2., fraction/rate*3600
            extracted = current*duration/3600
            polarization = .01*current*(-np.expm1(-duration/30))*np.exp(-300/30)
            predicted = [float(analytic_ocv(1-extracted/q,q)-polarization) for q in [2.,3.]]
            distance = abs(predicted[0]-predicted[1])
            expected.append({'fraction':fraction,'c_rate':rate,'discharge_seconds':duration,'rest_seconds':300,'total_seconds':duration+300,'terminal_separation_v':distance,'separates':distance>.004,'predicted_endpoints_v':predicted,'common_imposed_current_a':current,'common_extracted_ah':extracted})
    feasible = [r for r in expected if r['separates']]
    best = min(feasible,key=lambda r:(r['total_seconds'],r['fraction'],r['c_rate'])) if feasible else None
    got_rows = found.get('probes',[])
    match = len(got_rows)==21 and len(got_rows)==len(expected)
    largest_difference=0.
    for got,want in zip(got_rows,expected):
        for k in ['fraction','c_rate','discharge_seconds','rest_seconds','total_seconds']:
            match = match and abs(float(got.get(k,np.nan))-want[k])<1e-8
        match = match and bool(got.get('separates'))==want['separates']
        largest_difference=max(largest_difference,abs(float(got.get('terminal_separation_v',np.inf))-want['terminal_separation_v']))
    chosen=found.get('selected')
    selector_correct=(chosen is None and best is None) or (chosen is not None and best is not None and all(abs(float(chosen[k])-best[k])<1e-8 for k in ['fraction','c_rate','total_seconds']))
    swapped_chosen=swapped.get('selected')
    invariant=(chosen is None and swapped_chosen is None) or (chosen is not None and swapped_chosen is not None and all(chosen[k]==swapped_chosen[k] for k in ['fraction','c_rate','total_seconds']))
    prior_endpoint=[float(analytic_ocv(1-.75*600/(3600*q),q)-.02*.75-.01*.75*(-np.expm1(-600/30))) for q in [2.,3.]]
    prior_consistent=identify_observation(sum(prior_endpoint)/2,prior_endpoint)
    decisions=[]
    if best is not None:
        predictions=best['predicted_endpoints_v']
        for world, truth in enumerate(predictions):
            for error in [-.002,0.,.002]:
                observation=truth+error
                compatible=identify_observation(observation,predictions)
                decisions.append({'world_for_evaluation_only':world,'measurement_error_v':error,'observation_v':observation,'compatible_hypotheses_from_observation_only':compatible,'correct':compatible==[world]})
    accepted=bool(match and selector_correct and invariant and largest_difference<1e-6 and prior_consistent==[0,1] and all(r['correct'] for r in decisions))
    return {'evaluated_probes':len(expected),'selected_by_independent_enumeration':best,'constructor_menu_matches':bool(match),'max_terminal_separation_difference_v':largest_difference,'constructor_selects_menu_minimum':bool(selector_correct),'selection_invariant_to_hypothesis_order':bool(invariant),'prior_observation_compatible_hypotheses':prior_consistent,'observation_only_decisions':decisions,'accepted':accepted,'independence':'Probe choice receives both registered hypotheses and no actual-world identity. Only after selection does the observation-only inference routine receive the voltage; truth labels are used solely by this evaluator.','scope':'Optimality only within 21 specified probes and a two-model synthetic hypothesis set. Reset/SOC preparation and physical qualification remain unresolved.'}

def make_constructor_cells(module, capacities):
    z = np.linspace(0,1,2001)
    return [module.Cell(float(q),.02,.01,30.,tuple(z),tuple(analytic_ocv(z,q))) for q in capacities]

def check_constructor(module):
    rng = np.random.default_rng(20261102)
    worst_i = worst_v = worst_kcl = worst_kvl = 0.0
    cases = 0
    for n in [2,4,8,16]:
        for case in range(32):
            r = rng.uniform(.005,.1,n)
            seg = np.zeros(n-1) if case%4==0 else rng.uniform(.0001,.01,n-1)
            if case%4==1:
                seg[::2] = 0
            e = rng.uniform(2.6,4.1,n)
            load = float(rng.uniform(-20,20))
            cells = [module.Cell(2.,float(x),.01,30.,(0.,1.),(2.5,4.2)) for x in r]
            model = module.Ladder(cells,seg)
            z = (e-2.5)/1.7
            got,vg = model.currents(z,np.zeros(n),load)
            ref,vr = nodal_currents(e,r,seg,load)
            residual = conservation(e,r,seg,got,load)
            worst_i = max(worst_i,float(np.max(np.abs(got-ref))))
            worst_v = max(worst_v,abs(vg-vr))
            worst_kcl = max(worst_kcl,residual['kcl_abs_a'])
            worst_kvl = max(worst_kvl,residual['kvl_max_abs_v'])
            cases += 1
    trace_checks, references = [],[]
    for capacities in [[2.,2.,2.,2.],[3.,2.,2.,2.]]:
        ref = reference_trace(capacities)
        references.append(ref)
        model = module.Ladder(make_constructor_cells(module,capacities),PAIR['segment_loop_ohm'])
        runs = {}
        for dt in [2.,1.,.5]:
            run = model.simulate(8.,2100.,step_s=dt)
            if not run.get('completed'):
                raise RuntimeError('CONSTRUCTOR_TRUNCATED_COMPLETE_TRACE')
            stride = int(dt/.5)
            if not np.allclose(run['time_s'],ref['time_s'][::stride],atol=1e-9,rtol=0):
                raise RuntimeError('CONSTRUCTOR_TIME_GRID_MISMATCH')
            metrics = trace_metrics(run['current_a'],ref['current_a'][::stride])
            runs[str(dt)] = {'metrics_against_independent_analytic_reference':metrics,'requested_horizon_completed':True}
        trace_checks.append({'capacities_ah':capacities,'step_s_runs':runs})
    a,b = [r['current_a'] for r in references]
    pa,pb = np.max(np.abs(a),axis=0),np.max(np.abs(b),axis=0)
    separate = np.abs(pa-pb)>.10*(pa+pb)
    ambiguity = {'world_a_peak_a':pa.tolist(),'world_b_peak_a':pb.tolist(),'last_time_branch_difference_a':np.abs(a[-1]-b[-1]).tolist(),'complete_trace_rmse_separation_a':np.sqrt(np.mean((a-b)**2,axis=0)).tolist(),'half_separation_minimax_rmse_lower_bound_a':(np.sqrt(np.mean((a-b)**2,axis=0))/2).tolist(),'peak_10_percent_acceptance_intervals_disjoint':separate.tolist(),'peak_10_percent_both_world_guarantee_impossible':bool(np.any(separate)),'scope':'For any predictor receiving only the identical registered short-test observations, at least one of these two synthetic worlds must fail any disjoint peak-acceptance intervals. No probability or physical prevalence is inferred.'}
    max_trace = max(v['metrics_against_independent_analytic_reference']['max_abs_difference_a'] for t in trace_checks for v in t['step_s_runs'].values())
    probe_check=independent_probe_check(module)
    accepted = probe_check['accepted'] and worst_i<1e-8 and worst_v<1e-8 and worst_kcl<1e-8 and worst_kvl<1e-8 and max_trace<1e-4
    return {'fixture_seed':20261102,'nodal_cases':cases,'max_current_difference_a':worst_i,'max_terminal_voltage_difference_v':worst_v,'max_kcl_residual_a':worst_kcl,'max_kvl_residual_v':worst_kvl,'trace_checks':trace_checks,'probe_check':probe_check,'max_trace_error_a':max_trace,'numerical_constructor_accepted':bool(accepted),'identifiability_counterexample':ambiguity,'reference_trace_hashes':[sha({'time_s':r['time_s'].tolist(),'current_a':r['current_a'].tolist(),'terminal_v':r['terminal_v'].tolist()}) for r in references]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--constructor',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--spec-only',action='store_true')
    a=p.parse_args()
    if a.output.exists():
        raise FileExistsError('REQUIRE_NEW_RECEIPT_PATH')
    result={'sources':SOURCES,'pair_spec':PAIR,'pair_spec_sha256':sha(PAIR),'cost_bound':cost_bound()}
    if not a.spec_only:
        if not a.constructor:
            p.error('--constructor is required for numerical evaluation')
        spec=importlib.util.spec_from_file_location('registered_constructor',a.constructor)
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        result['short_test']=short_trace_pair()
        result['constructor_checks']=check_constructor(module)
        result['constructor_sha256']=hashlib.sha256(a.constructor.read_bytes()).hexdigest()
        result['verifier_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as output:
        output.write(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(a.output),'pair_spec_sha256':result['pair_spec_sha256'],'spec_only':a.spec_only,'numerical_constructor_accepted':result.get('constructor_checks',{}).get('numerical_constructor_accepted')},sort_keys=True))
    if not a.spec_only and not result['constructor_checks']['numerical_constructor_accepted']:
        raise SystemExit(2)

if __name__=='__main__':
    main()
