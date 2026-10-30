from fractions import Fraction as F
from itertools import combinations, product
from pathlib import Path
import argparse, hashlib, json, resource, time
from .circuit import Q, parse_netlist, apply_symmetry, solve, coordinate_box, separated


ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'research/consequential009/analog'


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')


def make_protocol():
    return {'schema':'consequential009-switched-reference-development-v1',
      'status':'DEVELOPMENT; new model-derived cases exposed; no protected confirmation',
      'funding':'Original campaign allocation only. Qualified unrestricted simulated earnings0; not earned-funded.',
      'primary_source':'rc-meas-ac.sp','successor_source':'MonteCarlo.sp',
      'source_commit':'032b1c32c4dbad45ff132bcfac1dbecadbd8abb0',
      'source_git_blobs':{'rc-meas-ac.sp':'2d464ba58ee46f4f88cb319debe5e90d396e06ad','MonteCarlo.sp':'608dc4cfdda5d168952a6319d87a9d63f4f6cb84'},
      'primary_omega_rad_s':['100000','300000','1000000','3000000'],
      'successor_omega_rad_s':['300000','1000000','3000000','10000000'],
      'primary_scale':['1','2'],'successor_scales':['1/2','1','2'],
      'successor_tolerance_elements':['r1','c3','l2'],'successor_tolerance_multipliers':['7/8','9/8'],
      'reference_nominal_siemens':'1/1000','reference_multiplier_bounds':['99/100','101/100'],
      'gain_magnitude_lower_bound':'1/2','absolute_coordinate_error_siemens':'1/10000000000',
      'raw_gain_grid':[['1/2','0'],['1','0'],['2','0'],['1/2','1/2'],['1','1/4']],
      'raw_reference_multiplier_grid':['99/100','1','101/100'],
      'noise_patterns':['zero','equal-opposite-diagonal','opposite-equal-diagonal','equal-opposite-antidiagonal','opposite-equal-antidiagonal'],
      'high_noise_stress_siemens':'1/1000',
      'retained_constraint':{'kind':'unbounded_sensor_gain_confounding',
        'witness':'impedance-scale2 halves Y; doubling unknown channel gain preserves every old current reading',
        'adaptation':'Add switched known parallel reference conductance and normalize paired readings from the same stable sensor transfer.'},
      'assumptions':['Author-specified reference conductance range, not measured calibration.',
        'Same complex sensor transfer g during the two paired observations at each frequency, |g|>=1/2.',
        'Input-current signals normalized by actual coherent input voltage; remaining coordinate error bounded as stated.',
        'Lumped linear passive network and known source/load model.',
        'Reference loading, source current limit, thermal effects and switching transients must be qualified on hardware; no hardware is qualified here.'],
      'endpoint':'Every pair of admitted finite network hypotheses must have disjoint conditional normalized-admittance rectangles at one chosen frequency; unresolved pairs cause abstention.',
      'ordinary_control':'Known ratiometric/switched-reference normalization plus exhaustive frequency selection, same information and envelopes; no novelty or superiority from parity.',
      'not_measured':['physical specimens','reference precision or drift','sensor noise or gain stability','buyer participation','prices or complete monetary costs'],
      'statistical_scope':'Exact finite-model engineering comparison and analytic conditional nuisance bound. New names/cases do not reset any campaign error budget.'}


def cohorts(protocol):
    c0=parse_netlist((SOURCE/protocol['primary_source']).read_text())
    primary=[{'id':'nominal-a'+a.replace('/','_'),'values':apply_symmetry(c0,{},a)} for a in protocol['primary_scale']]
    c1=parse_netlist((SOURCE/protocol['successor_source']).read_text());fresh=[]
    names=protocol['successor_tolerance_elements']
    for bits in product(protocol['successor_tolerance_multipliers'],repeat=len(names)):
        vals={e.name:str(e.value) for e in c1.elements}
        for n,m in zip(names,bits):vals[n]=str(F(vals[n])*F(m))
        for a in protocol['successor_scales']:
            fresh.append({'id':'fresh-'+','.join(bits)+'-a'+a,'values':apply_symmetry(c1,vals,a),
                'impedance_scale':a,'component_multipliers':dict(zip(names,bits))})
    return [('primary',c0,primary,protocol['primary_omega_rad_s']),
            ('new_rlc_family',c1,fresh,protocol['successor_omega_rad_s'])]


def normalize(z0,z1,Gnom): return F(Gnom)*z0/(z1-z0)


def conditional_box(Y,protocol,eps_override=None):
    Gnom=F(protocol['reference_nominal_siemens']);ml,mh=map(F,protocol['reference_multiplier_bounds'])
    Gl,Gh=Gnom*ml,Gnom*mh;gmin=F(protocol['gain_magnitude_lower_bound'])
    eps=F(eps_override if eps_override is not None else protocol['absolute_coordinate_error_siemens'])
    dmin=gmin*Gl-4*eps
    if not (0<Gl<=Gh) or gmin<=0 or eps<0 or dmin<=0:
        return {'decision':'ABSTAIN','reason':'No positive lower bound for noisy reference-difference denominator.',
            'denominator_modulus_lower_bound':str(dmin)}
    E=(Gnom/Gl)*2*(Gh*eps+2*eps*(abs(Y.re)+abs(Y.im)))/dmin
    box=coordinate_box(Y,[Gnom/Gh,Gnom/Gl],E)
    return {'decision':'CONDITIONAL_MODEL_BOUND','box':[[str(a),str(b)] for a,b in box],
       'denominator_modulus_lower_bound':str(dmin),'coordinate_error_bound':str(E),
       'reference_scale_bounds':[str(Gnom/Gh),str(Gnom/Gl)],
       'proof_identity':'estimate-(Gnom/G)Y = (Gnom/G)*(G*e0-Y*(e1-e0))/(g*G+e1-e0)',
       'scope':'Conditional on authored reference, stable transfer and noise bounds. Not measured hardware assurance.'}


def plan(circuit,hs,freqs,protocol):
    pairs=set(combinations(range(len(hs)),2));covers={};bounds={};ys={}
    for omega in freqs:
        ys[omega]=[solve(circuit,h['values'],omega)[1] for h in hs]
        bs=[conditional_box(y,protocol) for y in ys[omega]];bounds[omega]=bs
        if any(b['decision']=='ABSTAIN' for b in bs):covers[omega]=set();continue
        boxes=[[(F(a),F(b)) for a,b in z['box']] for z in bs]
        covers[omega]={(i,j) for i,j in pairs if separated(boxes[i],boxes[j])}
    uncovered=set(pairs);selected=[];ancestry=[]
    while uncovered:
        candidates=[x for x in freqs if x not in selected]
        if not candidates:break
        best=max(candidates,key=lambda x:(len(covers[x]&uncovered),-freqs.index(x)))
        new=covers[best]&uncovered
        if not new:break
        ancestry.append({'frequency_rad_s':best,'actual_newly_separated_pair':[hs[i]['id'] for i in min(new)],
            'newly_separated_pairs':len(new),'known_rule':'greedy cover over paired-reference observations'})
        selected.append(best);uncovered-=new
    full=set().union(*covers.values());ordinary=[]
    for k in range(len(freqs)+1):
        choices=[c for c in combinations(freqs,k) if set().union(*(covers[x] for x in c))==full]
        if choices:ordinary=list(choices[0]);break
    return {'schema':'switched-reference-strategy-v1','source_sha256':circuit.source_sha256,
      'generated_from':protocol['retained_constraint'],
      'dsl':{'op':'paired_reference_normalization','actions':[{'op':'measure_normalized_input_current','reference':'off'},
        {'op':'measure_normalized_input_current','reference':'parallel_known_G'}],
        'expression':'Gnom*z0/(z1-z0)','frequency_rad_s':selected,
        'requires':['known_reference_range','stable_shared_sensor_transfer','bounded_noise','qualified_loading']},
      'ancestry':ancestry,'admitted_cases':len(hs),'admitted_pairs':len(pairs),
      'separated_pairs':len(pairs-uncovered),'unresolved_pairs':[[hs[i]['id'],hs[j]['id']] for i,j in sorted(uncovered)],
      'conditional_complete_acceptance':not uncovered,'ordinary_same_reference':{'frequency_rad_s':ordinary,
        'separated_pairs':len(full),'conditional_complete_acceptance':full==pairs},
      'bounds':bounds,'true_network_admittance':{w:[z.json() for z in zs] for w,zs in ys.items()},
      'novelty':'Not established; switched-reference/ratiometric normalization is known.',
      'physical_validation':'Absent; all obligations conditional and model-derived.'}


def noises(eps):
    z=Q();a=Q(eps,eps);b=Q(eps,-eps)
    return [(z,z),(a,-a),(-a,a),(b,-b),(-b,b)]


def raw_rows(circuit,hs,freqs,protocol,bounds):
    Gnom=F(protocol['reference_nominal_siemens']);eps=F(protocol['absolute_coordinate_error_siemens'])
    gains=[Q(F(a),F(b)) for a,b in protocol['raw_gain_grid']];rows=[];contained=0
    for hi,h in enumerate(hs):
        for omega in freqs:
            Y=solve(circuit,h['values'],omega)[1]
            bb=bounds[omega][hi]
            if bb['decision']=='ABSTAIN':raise ValueError('raw grid cannot assert a missing bound')
            box=[tuple(map(F,x)) for x in bb['box']]
            for gi,g in enumerate(gains):
                for ri,m in enumerate(protocol['raw_reference_multiplier_grid']):
                    G=Gnom*F(m)
                    for ni,(e0,e1) in enumerate(noises(eps)):
                        z0=g*Y+e0;z1=g*(Y+G)+e1;est=normalize(z0,z1,Gnom)
                        ok=box[0][0]<=est.re<=box[0][1] and box[1][0]<=est.im<=box[1][1]
                        if not ok:raise ValueError('normalization escaped exact declared envelope')
                        contained+=1
                        rows.append({'hypothesis':h['id'],'omega_rad_s':omega,'gain_index':gi,'reference_index':ri,
                            'noise_index':ni,'z0':z0.json(),'z1':z1.json(),'estimate':est.json()})
    return rows,contained


def drift_witness(circuit,omega,protocol):
    G=F(protocol['reference_nominal_siemens']);Y=solve(circuit,{},omega)[1]
    vals=apply_symmetry(circuit,{},2);Yb=solve(circuit,vals,omega)[1]
    g0a=g1a=Q(F(1));g0b=Q(F(2));g1b=(Y+G)/(Yb+G)
    a0=g0a*Y;a1=g1a*(Y+G);b0=g0b*Yb;b1=g1b*(Yb+G)
    return {'omega_rad_s':omega,'original_Y':Y.json(),'scaled_Y':Yb.json(),
       'world_a_g0':g0a.json(),'world_a_g1':g1a.json(),'world_b_g0':g0b.json(),'world_b_g1':g1b.json(),
       'world_a_z0':a0.json(),'world_a_z1':a1.json(),'world_b_z0':b0.json(),'world_b_z1':b1.json(),
       'same_raw_observations':a0==b0 and a1==b1,'distinct_networks':Y!=Yb,
       'stable_transfer_condition_violated':g0b!=g1b,'decision':'ABSTAIN_REQUIRED_WITHOUT_STABILITY_EVIDENCE',
       'scope':'Drifting complex transfer can fit both raw observations; stability is not inferred from those observations or detected by a magical flag.'}


def run(output,protocol_path):
    start=time.perf_counter();cpu=time.process_time();out=Path(output);out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads(Path(protocol_path).read_text());write(out/'PROTOCOL.json',protocol)
    results={};raw_count=0
    for name,c,hs,freqs in cohorts(protocol):
        write(out/(name+'-COHORT.json'),{'hypotheses':hs,'source_sha256':c.source_sha256})
        strategy=plan(c,hs,freqs,protocol);write(out/(name+'-STRATEGY.json'),strategy)
        rows,contained=raw_rows(c,hs,freqs,protocol,strategy['bounds']);raw_count+=len(rows)
        for hi,h in enumerate(hs):
            selected=[r for r in rows if r['hypothesis']==h['id']]
            write(out/'raw'/name/(str(hi).zfill(3)+'.json'),selected)
        drift=[drift_witness(c,w,protocol) for w in freqs];write(out/(name+'-DRIFT.json'),drift)
        high_noise=conditional_box(solve(c,hs[0]['values'],freqs[0])[1],protocol,protocol['high_noise_stress_siemens'])
        write(out/(name+'-HIGH_NOISE.json'),high_noise)
        results[name]={'cases':len(hs),'pairs':strategy['admitted_pairs'],'separated_pairs':strategy['separated_pairs'],
          'conditional_complete_acceptance':strategy['conditional_complete_acceptance'],
          'ordinary_separated_pairs':strategy['ordinary_same_reference']['separated_pairs'],
          'selected_frequency_count':len(strategy['dsl']['frequency_rad_s']),
          'ordinary_frequency_count':len(strategy['ordinary_same_reference']['frequency_rad_s']),
          'raw_rows':len(rows),'raw_rows_within_conditional_bound':contained,
          'gain_drift_witnesses_identical':[w['same_raw_observations'] for w in drift],
          'gain_drift_decision':'ABSTAIN_REQUIRED_WITHOUT_STABILITY_EVIDENCE','high_noise_decision':high_noise['decision']}
    results.update({'protocol_sha256':hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
      'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'inventions/consequential009/circuit.py']},
      'raw_rows':raw_count,'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-start,
      'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      'funding':protocol['funding'],'novelty':'Not established','physical_calibration':'Not performed',
      'buyer_participation':'Not established','complete_monetary_cost':'UNKNOWN',
      'conditional_scope':'Exact source-bound model results under authored calibration, stable-transfer and noise envelope; not physical or commercial assurance.'})
    write(out/'REPORT.json',results);return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--protocol',required=True)
    a=p.parse_args();print(json.dumps(run(a.output,a.protocol),indent=2,sort_keys=True))
