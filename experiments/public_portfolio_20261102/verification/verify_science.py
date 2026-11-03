from __future__ import annotations
import argparse, copy, hashlib, importlib, json, math, sys, time
from functools import lru_cache
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE.parent
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_inventory(route):
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted((BASE / route).rglob('*'))
            if p.is_file() and (p.suffix in ('.py', '.yml') or p.name == 'PREREGISTRATION.json')}


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, name, passed, **details):
        self.rows.append({'check': name, 'passed': bool(passed), **details})

    def reject(self, name, function):
        try:
            result = function()
            refused = isinstance(result, dict) and 'accepted' in result and not np.asarray(result['accepted']).any()
            self.add(name, refused, outcome='refused' if refused else 'not_refused')
        except (ValueError, TypeError, KeyError, OverflowError):
            self.add(name, True, outcome='exception_rejection')


def module(route, filename):
    return importlib.import_module('experiments.public_portfolio_20261102.' + route + '.' + filename)


def independent_wins(game, safe, targets, horizon, invariant=None):
    allowed = set(safe) & (set(game) if invariant is None else set(invariant))
    @lru_cache(None)
    def win(state, steps):
        if state not in allowed:
            return False
        if state in targets:
            return True
        if not steps:
            return False
        return any(bool(outcomes) and all(win(nxt, steps-1) for nxt in outcomes) for outcomes in game[state].values())
    return [{s for s in game if win(s, t)} for t in range(horizon+1)]


def purpose(checks, rng):
    k = module('purpose', 'kernel')
    d = module('purpose', 'diagnosis')
    mismatches = []
    policy_failures = []
    for case in range(64):
        states = [str(i) for i in range(7)]
        game = {s: {str(a): tuple(rng.choice(states, size=int(rng.integers(1, 4)), replace=False))
                    for a in range(int(rng.integers(0, 4)))} for s in states}
        safe = {s for s in states if rng.random() < .8}
        targets = {s for s in states if rng.random() < .25}
        invariant = {s for s in states if rng.random() < .9}
        result = k.reach_avoid(game, safe, targets, 5, invariant)
        expected = independent_wins(game, safe, targets, 5, invariant)
        if result.layers != expected:
            mismatches.append(case)
        for t, winners in enumerate(result.layers[1:], 1):
            for s in winners - targets:
                action = result.policy.get((t, s))
                if action not in game[s] or not all(v in expected[t-1] for v in game[s][action]):
                    policy_failures.append([case, t, s])
    checks.add('finite_games_independent_exhaustive_truth', not mismatches, cases=64, mismatches=mismatches)
    checks.add('every_emitted_policy_preserves_robust_outcomes', not policy_failures, failures=policy_failures)
    game = {'start': {'deliver': ('goal',), 'abort': ('home',)}, 'goal': {'fall': ('unsafe',)},
            'home': {'stay': ('home',)}, 'unsafe': {'stay': ('unsafe',)}}
    safe = {'start', 'goal', 'home'}
    goal_only = k.reach_avoid(game, safe, {'goal'}, 2)
    recovery = k.recovery_set(game, safe, {'home'}, 2)
    preserved = k.reach_avoid(game, safe, {'goal'}, 2, recovery.winning)
    checks.add('goal_only_success_rejected_when_future_recovery_impossible',
               'start' in goal_only.winning and 'start' not in preserved.winning)
    checks.reject('undeclared_successor_rejected', lambda: k.reach_avoid({'s': {'a': ('missing',)}}, {'s'}, {'s'}, 2))
    checks.reject('empty_adversarial_branch_rejected', lambda: k.reach_avoid({'s': {'a': ()}}, {'s'}, {'s'}, 2))
    checks.reject('invalid_horizon_rejected', lambda: k.reach_avoid({'s': {'a': ('s',)}}, {'s'}, {'s'}, -1))
    worlds = {}
    for world, destination, observation in [('normal', 'left', 'L'), ('fault', 'right', 'R')]:
        worlds[world] = {'start': {'probe': ((destination, observation),), 'abort': (('home', 'H'),)},
                         'left': {'recover': (('home', 'H'),)}, 'right': {'recover': (('home', 'H'),)},
                         'home': {'stay': (('home', 'H'),)}, 'unsafe': {'stay': (('unsafe', 'X'),)}}
    result = d.construct_diagnosis(worlds, {'start','left','right','home'}, {'home'}, 1, 1)
    initial = d.belief_id('start', worlds)
    expected = independent_wins(result['game'], result['safe'], result['diagnosed'], 1, result['recovery'].winning)
    checks.add('new_function_active_diagnosis', initial in result['certificate'].winning and result['certificate'].layers == expected)
    opaque = copy.deepcopy(worlds)
    opaque['fault']['start']['probe'] = (('left', 'L'),)
    no_information = d.construct_diagnosis(opaque, {'start','left','right','home'}, {'home'}, 3, 1)
    checks.add('unidentifiable_faults_refused', initial not in no_information['certificate'].winning)
    unsafe = copy.deepcopy(worlds)
    unsafe['fault']['start']['probe'] = (('unsafe', 'X'),)
    rejected = d.construct_diagnosis(unsafe, {'start','left','right','home'}, {'home'}, 3, 1)
    checks.add('unsafe_identification_probe_refused', initial not in rejected['certificate'].winning)


def interface(checks, rng):
    i = module('interface', 'instrument')
    mu = np.array([[.3681,2.613],[.1704,.4584],[.1378,.2217]])
    truth = rng.uniform([0,0], [2,.5], size=(64,2))
    reference_signal = rng.uniform(1e4,1e6,size=(64,3))
    dark = rng.uniform(0,100,size=(64,3))
    sample_signal = reference_signal*np.exp(-truth@mu.T)
    exact = i.estimate(sample_signal+dark, reference_signal+dark, dark)
    error = float(np.max(abs(exact['mass_areal_density_g_cm2']-truth)))
    checks.add('independent_beer_lambert_exact_recovery', np.asarray(exact['accepted']).all() and error < 1e-10,
               cases=64, max_absolute_error=error)
    eps = 1e-4
    perturbed = i.estimate(sample_signal*(1+rng.uniform(-eps,eps,size=(64,3)))+dark,
                           reference_signal*(1+rng.uniform(-eps,eps,size=(64,3)))+dark,dark,eps)
    errors = abs(perturbed['mass_areal_density_g_cm2']-truth)
    checks.add('propagated_density_intervals_cover_bounded_measurement_noise',
               np.asarray(perturbed['accepted']).all() and np.all(errors <= perturbed['component_error_bound_g_cm2']+1e-12), cases=64)
    independent = np.linalg.solve(mu.T@mu,mu.T@(np.log(reference_signal)-np.log(sample_signal)).T).T
    checks.add('strong_standard_linear_inversion_ties',np.max(abs(independent-exact['mass_areal_density_g_cm2']))<1e-10)
    geometry = np.vstack([np.eye(4), rng.uniform(.05,.4,size=(8,4))])
    density = rng.uniform([.1,.01],[2,.4],size=(4,2))
    lines = geometry@density
    ref = rng.uniform(1e4,1e5,size=(len(geometry),3))
    dk = rng.uniform(0,100,size=ref.shape)
    samp = ref*np.exp(-lines@mu.T)
    reconstructed = i.reconstruct(samp+dk,ref+dk,dk,geometry,(2,2))
    reconstructed_error = float(np.max(abs(reconstructed['density_g_cm3'].reshape(4,2)-density)))
    checks.add('independent_known_geometry_spatial_reconstruction', reconstructed['accepted'] and reconstructed_error<1e-9,
               rays=len(geometry),pixels=4,max_absolute_error=reconstructed_error)
    checks.reject('rank_deficient_geometry_refused',lambda:i.reconstruct(samp+dk,ref+dk,dk,np.ones_like(geometry),(2,2)))
    checks.reject('nonpositive_corrected_signal_refused',lambda:i.estimate([0,1,1],[10,10,10],[0,0,0]))
    checks.reject('nonfinite_observation_refused',lambda:i.estimate([float('nan'),1,1],[10,10,10],[0,0,0]))
    checks.reject('mismatched_energy_shape_refused',lambda:i.estimate([1,1],[10,10],[0,0]))
    delta = np.array([.35,.08])
    coherent_sample = sample_signal[0]*np.exp(-mu@delta)
    mismatch = i.estimate(coherent_sample+dark[0],reference_signal[0]+dark[0],dark[0],1e-8)
    mismatch_error = float(np.max(abs(mismatch['mass_areal_density_g_cm2']-truth[0])))
    checks.add('coherent_gain_mismatch_exposes_declared_identifiability_limit',
               bool(mismatch['accepted']) and mismatch_error > float(np.max(mismatch['component_error_bound_g_cm2'])),
               accepted_under_wrong_model=bool(mismatch['accepted']), actual_density_error=mismatch_error,
               interpretation='Expected negative control: data-only guard is not physical model validation')


def thermal_case(name,demand,source,grid=50,storage=100):
    n=len(demand)
    return {'schema':'thermal-dispatch/v1','name':name,'dt_h':1.,'demand_kw':demand,'source_kw':source,
            'source_c':[55.]*n,'sink_c':110.,'carnot_fraction':.45,'approach_c':5.,'grid_limit_kw':grid,
            'hp_heat_limit_kw':200.,'store_kwh':storage,'store_power_kw':200.,'charge_efficiency':.97,
            'discharge_efficiency':.97,'hourly_retention':.999,'electricity_usd_kwh':[.1]*n}


def complementarity(checks,rng):
    m=module('complementarity','thermal')
    case=thermal_case('independent-complements',[80.,80.],[200.,0.])
    runs=[m.solve_dispatch(case,hp,store) for hp,store in [(False,False),(True,False),(False,True),(True,True)]]
    checks.add('independent_complementarity_feasibility', [r['feasible'] for r in runs]==[False,False,False,True],
               feasible=[r['feasible'] for r in runs])
    result=runs[-1]
    if result['feasible']:
        p,b,ch,dis,soc=[np.asarray(result[k]) for k in ['hp_electric_kw','boiler_electric_kw','charge_kw','discharge_kw','soc_kwh']]
        cop=.45*(110+273.15+5)/((110+273.15+5)-(55+273.15-5))
        residuals={'heat_kw':float(np.max(abs(cop*p+b+dis-ch-np.asarray(case['demand_kw'])))),
                   'storage_kwh':float(np.max(abs(soc[1:]-.999*soc[:-1]-.97*ch+dis/.97))),
                   'electrical_excess_kw':float(max(0,np.max(p+b-50))),
                   'source_excess_kw':float(max(0,np.max((cop-1)*p-np.asarray(case['source_kw'])))),
                   'initial_final_kwh':float(max(abs(soc[0]),abs(soc[-1])))}
        checks.add('independent_energy_and_inventory_conservation',max(residuals.values())<1e-6,residuals=residuals)
        tampered=copy.deepcopy(result);tampered['soc_kwh'][1]+=1.
        checks.add('storage_tampering_rejected',not m.analyze_dispatch(case,tampered)['accepted'])
    zero_source=thermal_case('independent-no-source',[80.,80.],[0.,0.])
    checks.add('insufficient_power_without_source_refused',not m.solve_dispatch(zero_source)['feasible'])
    malformed=copy.deepcopy(case);malformed['carnot_fraction']=1.1
    checks.reject('super_carnot_fraction_refused',lambda:m.solve_dispatch(malformed))
    malformed2=copy.deepcopy(case);malformed2['demand_kw'][0]=float('nan')
    checks.reject('nonfinite_thermal_demand_refused',lambda:m.solve_dispatch(malformed2))
    max_mass_error=0.
    for _ in range(32):
        feed=float(rng.uniform(500,10000));salt=float(rng.uniform(.02,.1));target=float(rng.uniform(.12,.24))
        result=m.recover_brine(feed,salt,target,float(rng.uniform(60,90)),float(rng.uniform(2,10)),float(rng.uniform(0,.9)))
        max_mass_error=max(max_mass_error,abs(result['brine_kg_h']+result['product_water_kg_h']-feed),
                           abs(result['brine_kg_h']*target-feed*salt))
    checks.add('independent_water_and_salt_balances',max_mass_error<1e-8,cases=32,max_error_kg_h=max_mass_error)
    checks.reject('inverted_salt_concentration_refused',lambda:m.recover_brine(1000,.15,.05,70,6,.5))


def silica_index(w):
    w=np.asarray(w)
    return np.sqrt(1+.6961663*w*w/(w*w-.0684043**2)+.4079426*w*w/(w*w-.1162414**2)+.8974794*w*w/(w*w-9.896161**2))


def foundry(checks,rng):
    m=module('foundry','optics')
    w=np.linspace(.71,1.49,19)
    ns=silica_index(w)
    expected=((1-ns)/(1+ns))**2
    bare=m.response([],[],w)
    checks.add('independent_bare_fresnel_reflectance',np.max(abs(bare['R']-expected))<1e-12)
    zero=m.response([0.],['MgF2'],w)
    checks.add('zero_thickness_is_bare_interface',np.max(abs(zero['R']-expected))<1e-12 and np.max(abs(zero['T']-(1-expected)))<1e-12)
    d=.137
    nl=np.sqrt(1+.48755108*w*w/(w*w-.04338408**2)+.39875031*w*w/(w*w-.09461442**2)+2.3120353*w*w/(w*w-23.793604**2))
    r01=(1-nl)/(1+nl);r12=(nl-ns)/(nl+ns)
    phase=np.exp(2j*np.pi*nl*d/w)
    airy_r=(r01+r12*phase**2)/(1+r01*r12*phase**2)
    airy_t=(2/(1+nl))*(2*nl/(nl+ns))*phase/(1+r01*r12*phase**2)
    one=m.response([d],['MgF2'],w)
    checks.add('independent_single_layer_airy_response',np.max(abs(one['R']-abs(airy_r)**2))<1e-11 and np.max(abs(one['T']-ns*abs(airy_t)**2))<1e-11)
    p=m.response([.13,.27],['MgF2','SiO2'],w,0,'p');s=m.response([.13,.27],['MgF2','SiO2'],w,0,'s')
    checks.add('normal_incidence_polarization_equality',np.max(abs(p['R']-s['R']))<1e-12)
    conservation=0.;minimum=0.
    for _ in range(16):
        thickness=rng.uniform(.01,.3,size=5)
        result=m.response(thickness,['MgF2','SiO2','MgF2','SiO2','MgF2'],w,float(rng.uniform(0,45)),'s')
        conservation=max(conservation,float(np.max(abs(result['R']+result['T']-1))))
        minimum=min(minimum,float(np.min(result['R'])),float(np.min(result['T'])))
    checks.add('lossless_multilayer_energy_conservation',conservation<1e-10 and minimum>-1e-12,cases=16,max_error=conservation)
    absorbing=m.response([.2],['Ta2O5'],w)
    checks.add('absorbing_layer_nonnegative_dissipation',np.min(absorbing['A'])>=-1e-10 and np.min(absorbing['R'])>=0 and np.min(absorbing['T'])>=0,
               minimum_absorption=float(np.min(absorbing['A'])))
    checks.reject('negative_thickness_refused',lambda:m.response([-.1],['MgF2'],w))
    checks.reject('nonfinite_thickness_refused',lambda:m.response([float('nan')],['MgF2'],w))
    checks.reject('unsupported_angle_refused',lambda:m.response([.1],['MgF2'],w,60))
    checks.reject('unsupported_wavelength_refused',lambda:m.response([.1],['MgF2'],[.5]))
    checks.reject('empty_wavelengths_refused',lambda:m.response([.1],['MgF2'],[]))
    checks.reject('multidimensional_wavelengths_refused',lambda:m.response([.1],['MgF2'],[[.8,.9]]))


def arrangement(checks,rng):
    m=module('arrangement','orbital')
    from scipy.integrate import solve_ivp,quad
    from scipy.special import ndtr
    n=.00108
    maximum=0.
    for _ in range(12):
        duration=float(rng.uniform(0,3500));initial=rng.normal(size=6)*np.array([100,100,100,.03,.03,.03])
        def ode(t,state):
            x,y,z,vx,vy,vz=state
            return [vx,vy,vz,3*n*n*x+2*n*vy,-2*n*vx,-n*n*z]
        solution=solve_ivp(ode,[0,duration],initial,rtol=1e-11,atol=1e-11)
        predicted=np.asarray(m.cw_transition(n,duration))@initial
        maximum=max(maximum,float(np.max(abs(predicted-solution.y[:,-1]))))
    checks.add('independent_cw_ode_integration',maximum<1e-5,cases=12,max_absolute_state_error=maximum)
    checks.add('cw_zero_time_identity',np.max(abs(np.asarray(m.cw_transition(n,0))-np.eye(6)))<1e-12)
    composition=np.asarray(m.cw_transition(n,1234))@np.asarray(m.cw_transition(n,2345))
    checks.add('cw_time_composition',np.max(abs(composition-np.asarray(m.cw_transition(n,3579))))<1e-8)
    checks.add('impulse_columns_match_state_transition',np.max(abs(np.asarray(m.impulse_effect(n,1200))-np.asarray(m.cw_transition(n,1200))[:,3:]))<1e-10)
    probability_failures=[]
    for case in range(8):
        mean=rng.normal(size=2)*30
        scales=rng.uniform(5,20,size=2)
        covariance=np.diag(scales**2)
        radius=float(rng.uniform(1,15));execution=float(rng.uniform(0,3))
        def disk_integrand(x):
            half=math.sqrt(max(0,radius*radius-x*x))
            density=math.exp(-.5*((x-mean[0])/scales[0])**2)/(math.sqrt(2*math.pi)*scales[0])
            return density*(ndtr((half-mean[1])/scales[1])-ndtr((-half-mean[1])/scales[1]))
        actual=float(quad(disk_integrand,-radius,radius,epsabs=1e-11)[0])
        bound=float(m.collision_bound(mean,covariance,radius,execution))
        if not 0<=bound<=1 or bound+1e-10<actual:
            probability_failures.append({'case':case,'integrated_probability':actual,'claimed_upper_bound':bound})
    checks.add('gaussian_disk_probability_below_conservative_bound',not probability_failures,cases=8,failures=probability_failures)
    checks.reject('singular_covariance_refused',lambda:m.collision_bound([1,1],[[0,0],[0,0]],1,0))
    checks.reject('nonfinite_orbital_input_refused',lambda:m.cw_transition(n,float('nan')))


ROUTES={'purpose':purpose,'interface':interface,'complementarity':complementarity,'arrangement':arrangement,'foundry':foundry}


def run(route,nonce):
    commitment=json.loads((HERE/'VERIFICATION_PROTOCOL.json').read_text())['hidden_case_commitment_sha256']
    if hashlib.sha256(nonce.encode()).hexdigest()!=commitment:
        raise ValueError('independent nonce commitment mismatch')
    before=source_inventory(route)
    rng=np.random.default_rng(int.from_bytes(hashlib.sha256((nonce+':'+route).encode()).digest()[:8],'big'))
    checks=Checks();started=time.time();cpu=time.process_time()
    try:
        ROUTES[route](checks,rng)
    except Exception as error:
        checks.add('independent_checker_completed',False,error_type=type(error).__name__,message=str(error))
    after=source_inventory(route)
    checks.add('source_unchanged_during_verification',before==after)
    return {'schema':'public-portfolio-independent-science/v1','route':route,'source_hashes':before,
            'checker_sha256':digest(__file__),'protocol_sha256':digest(HERE/'VERIFICATION_PROTOCOL.json'),
            'annex_sha256':digest(HERE/'SCIENTIFIC_ANNEX.json'),'nonce_commitment_sha256':commitment,
            'checks':checks.rows,'passed':all(r['passed'] for r in checks.rows),
            'wall_seconds':time.time()-started,'cpu_seconds':time.process_time()-cpu,
            'scope':'Computational contract only; no physical validation, external demand or industry-creation superiority inferred'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--route',choices=list(ROUTES),required=True)
    parser.add_argument('--nonce',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of existing independent result')
    result=run(args.route,args.nonce);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'route':args.route,'passed':result['passed'],'checks':len(result['checks']),'output':str(output)}))
    raise SystemExit(0 if result['passed'] else 1)
