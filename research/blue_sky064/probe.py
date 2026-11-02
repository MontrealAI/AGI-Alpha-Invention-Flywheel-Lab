"""Reproduce three bounded source-calibrated prerequisite probes, offline."""
from __future__ import annotations
import argparse
import ast
import hashlib
import itertools
import json
import math
from pathlib import Path
import time
import numpy as np
from scipy.stats import t as student_t

ROOT=Path(__file__).resolve().parents[2]
FIXTURE_SHA256='7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced'
REGISTRATION_HASHES={'REGISTRATION.json':'df25ef7d23f3873fd25b10f1a996d7c35d5611c2d1327e7417c631d295f9290e','MIXED_REGISTRATION.json':'6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa'}
AUTHOR_CODE_SHA256='94da2880d1afdc140f6e8e00bbae4e2a56015bf1511f2dcf76b0eab5d170bb84'


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_json(path,expected):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>100_000 or checksum(path)!=expected:
        raise ValueError('FROZEN_SOURCE_OR_FIXTURE_BYTES_CHANGED:'+path.name)
    return json.loads(path.read_text())


def load_inputs(fixture_path=None,registration_dir=None):
    fixture_path=Path(fixture_path) if fixture_path else Path(__file__).with_name('public_calibration.json')
    registration_dir=Path(registration_dir) if registration_dir else ROOT/'campaign/blue-sky-064/friction-probe'
    fixture=bound_json(fixture_path,FIXTURE_SHA256)
    registrations={name:bound_json(registration_dir/name,sha) for name,sha in REGISTRATION_HASHES.items()}
    if fixture.get('license')!='CC-BY-4.0' or fixture.get('schema')!='blue-sky064/public-calibration-fixture/v1':
        raise ValueError('ATTRIBUTED_PUBLIC_FIXTURE_REQUIRED')
    return fixture,registrations


def scalar_forward(genes,steps):
    maximum=max(float(h) for h,_ in genes);friction=[];pressure=[]
    for delta in np.linspace(0,maximum,steps):
        force=0.;normal=0.
        for height,radius in genes:
            penetration=max(0.,float(delta-(maximum-height)))
            force+=penetration*radius;normal+=penetration**1.5*math.sqrt(radius)
        friction.append(force/len(genes));pressure.append(normal/len(genes))
    return np.array(friction),np.array(pressure)


def formula_vector_forward(genes,steps):
    heights=genes[:,0];radii=genes[:,1];maximum=float(max(heights))
    depth=np.maximum(np.linspace(0,maximum,steps)[:,None]-(maximum-heights)[None,:],0)
    return np.mean(depth*radii,axis=1),np.mean(depth**1.5*np.sqrt(radii),axis=1)


def downloaded_author_forward(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>50_000:
        raise ValueError('DOWNLOADED_AUTHOR_CODE_HASH_MISMATCH')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=AUTHOR_CODE_SHA256:
        raise ValueError('DOWNLOADED_AUTHOR_CODE_HASH_MISMATCH')
    tree=ast.parse(raw.decode())
    node=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_compute_F_P_numba'),None)
    if node is None:raise ValueError('PINNED_FORWARD_FUNCTION_MISSING')
    node.decorator_list=[]
    namespace={'np':np}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace['_compute_F_P_numba']


def monotonic_obstruction(pressure,target,tolerance):
    if len(pressure)!=len(target) or len(target)<2 or any(not math.isfinite(v) for v in [*pressure,*target,tolerance]) or tolerance<0 or any(a>=b for a,b in zip(pressure,pressure[1:])):
        raise ValueError('ORDERED_FINITE_TARGET_REQUIRED')
    decrease,i,j=max([(target[i]-target[j],i,j) for i in range(len(target)) for j in range(i+1,len(target))])
    lower=max(0.,decrease/2)
    return {'uniform_error_lower_bound':lower,'target_tolerance':tolerance,'witness_points':[{'P':pressure[k],'F':target[k]} for k in (i,j)],'impossible_in_increasing_hertz_grammar':lower>tolerance,'proof':'For Pi<Pj an increasing g has g(Pi)<=g(Pj). Uniform error e implies target_i-e<=target_j+e, hence e>=(target_i-target_j)/2. Every loaded fixed-height positive-radius Hertz array has dF/ddelta>0 and dP/ddelta>0.'}


def source_curve_holdout(fixture):
    observed=np.array(fixture['figure4']['published_experimental_static'],dtype=float)
    design=np.array(fixture['figure4']['published_design_curve'],dtype=float)
    x=np.interp(observed[:,0],design[:,0],design[:,1]);y=observed[:,1]
    train=np.arange(len(y))%2==0;hold=~train
    scale=max(0.,float(x[train]@y[train]/(x[train]@x[train])))
    residual=scale*x[hold]-y[hold]
    return {'published_observations':len(y),'train_count':int(sum(train)),'holdout_count':int(sum(hold)),'fitted_nonnegative_scale':scale,'heldout_rmse':float(np.sqrt(np.mean(residual**2))),'heldout_max_abs_error':float(np.max(np.abs(residual))),'scope':'Reused published points from one device; no newly acquired or cross-device evidence.'}


def first_three_fit(rows):
    data=np.array(rows,dtype=float);train=data[:3];hold=data[3:]
    x=train[:,0];y=train[:,2]
    slope=float(x@y/(x@x));res=y-slope*x
    se=math.sqrt(float(res@res)/(len(x)-1)/float(x@x));margin=float(student_t.ppf(.975,len(x)-1))*se
    return {'slope':slope,'CI95_OLS':[max(0.,slope-margin),slope+margin],'train_n':len(train),'holdout_n':len(hold),'holdout_rmse':float(np.sqrt(np.mean((hold[:,2]-slope*hold[:,0])**2))) if len(hold) else None}


def mixed_composition(fixture,registration):
    calibrated={row['id']:row for row in fixture['calibration']};families=[]
    geometry=registration['geometry']
    for index,name in enumerate(registration['families']):
        source=calibrated[name];letter='A' if index==0 else 'B'
        parameters={}
        for phase in ['s','d']:
            parameters['sigma_'+phase]=first_three_fit(source['phases'][phase]['force_rows'])
            parameters['B_'+phase]=first_three_fit(source['phases'][phase]['area_rows'])
        families.append({'id':name,'radius_mm':source['radius_mm'],'E_star_MPa':source['E_star_MPa'],'count':geometry['family_'+letter+'_count'],'height_mm':geometry['family_'+letter+'_height_mm'],'parameters':parameters})
    def forward(delta,endpoints=None):
        normal=0.;forces={'s':0.,'d':0.};areas=[]
        for index,family in enumerate(families):
            depth=max(0.,delta-(geometry['family_A_height_mm']-family['height_mm']))
            area=family['count']*math.pi*family['radius_mm']*depth;areas.append(area)
            normal+=family['count']*4/3*family['E_star_MPa']*math.sqrt(family['radius_mm'])*depth**1.5
            for k,phase in enumerate(['s','d']):
                sigma=family['parameters']['sigma_'+phase];B=family['parameters']['B_'+phase]
                cs=sigma['slope'] if endpoints is None else sigma['CI95_OLS'][endpoints[index*4+k*2]]
                cb=B['slope'] if endpoints is None else B['CI95_OLS'][endpoints[index*4+k*2+1]]
                forces[phase]+=cs*cb*area
        return {'indentation_mm':delta,'normal_force_N':normal,'static_force_N':forces['s'],'dynamic_force_N':forces['d'],'hold_slide_ratio':forces['s']/forces['d'],'family_area_mm2':areas}
    states=[forward(d) for d in registration['test_indentation_mm']]
    deltas=[]
    for endpoints in itertools.product([0,1],repeat=8):
        values=[forward(d,endpoints)['hold_slide_ratio'] for d in registration['test_indentation_mm']]
        deltas.append(values[1]-values[0])
    change=states[1]['hold_slide_ratio']-states[0]['hold_slide_ratio'];threshold=registration['necessary_construction_target']['increase_in_static_dynamic_ratio_at_least']
    return {'families':families,'prescribed_before_after':states,'nominal_ratio_increase':change,'independent_interval_worst_ratio_increase':min(deltas),'independent_interval_best_ratio_increase':max(deltas),'threshold':threshold,'nominal_function_pass':change>=threshold,'interval_function_pass':min(deltas)>=threshold,'homogeneous_exact_no_go':'For every homogeneous positive family, Fs/Fd=cs/cd is constant regardless of the height distribution.','ordinary_composition_control':'An equally resourced ordinary constructor may assemble the same families; no superiority is claimed.','interval_scope':'Approximate independent OLS intervals from three training rows; not simultaneous confidence or valid mixedmaterial physical prediction.','physical_transfer':'NOT_ESTABLISHED; source macro sigma disagreement remains.'}


def coefficient_box(points,extra=0.):
    if not points or not 0<=extra<=1:raise ValueError('BOUNDED_NONEMPTY_CALIBRATION_REQUIRED')
    if any(not all(math.isfinite(v) for v in row) or x<=ex or min(x,ex,y,ey)<0 for row in points for x,ex,y,ey in [row]):
        raise ValueError('POSITIVE_FINITE_CALIBRATION_ROWS_REQUIRED')
    lower=max(max(0.,(y-ey-extra*abs(y))/(x+ex)) for x,ex,y,ey in points)
    upper=min((y+ey+extra*abs(y))/(x-ex) for x,ex,y,ey in points)
    return [lower,upper]


def calibration_consistency(fixture):
    rows=[]
    for family in fixture['calibration']:
        for phase,source in family['phases'].items():
            if len(source['force_rows'])!=len(source['area_rows']):raise ValueError('PAIRED_SOURCE_ROWS_REQUIRED')
            points=[(a[0],a[1],f[2],f[3]) for f,a in zip(source['force_rows'],source['area_rows'])]
            interval=coefficient_box(points);low=0.;high=1.
            for _ in range(60):
                mid=(low+high)/2;lo,hi=coefficient_box(points,mid)
                if lo<=hi:high=mid
                else:low=mid
            rows.append({'family':family['id'],'phase':phase,'paired_rows':len(points),'original_slope_intersection':interval,'consistent_without_extra_discrepancy':interval[0]<=interval[1],'minimum_extra_relative_force_discrepancy':0. if interval[0]<=interval[1] else high})
    return {'results':rows,'interpretation':'Exact coefficient-box consistency under the authored interpretation of published plus/minus errors; not simultaneous confidence, physical falsification or a future discrepancy bound.'}


def run(output,*,fixture_path=None,registration_dir=None,author_code=None):
    output=Path(output)
    if not output.is_absolute() or output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise ValueError('NEW_REGULAR_ABSOLUTE_OUTPUT_REQUIRED')
    fixture,registrations=load_inputs(fixture_path,registration_dir)
    registration=registrations['REGISTRATION.json'];mixed=registrations['MIXED_REGISTRATION.json']
    original=downloaded_author_forward(author_code) if author_code else None
    rng=np.random.default_rng(registration['source_model_probe']['profile_seed']);differences=[];author_differences=[];minimum=math.inf
    started=time.monotonic()
    for _ in range(registration['source_model_probe']['profiles']):
        n=registration['source_model_probe']['asperities'];steps=registration['source_model_probe']['compression_steps']
        genes=np.column_stack([rng.random(n),rng.choice([1.,3.],n)])
        scalar=scalar_forward(genes,steps);vector=formula_vector_forward(genes,steps)
        differences.append(max(float(np.max(np.abs(a-b))) for a,b in zip(scalar,vector)))
        if original:
            reference=original(genes,n,steps)
            author_differences.append(max(float(np.max(np.abs(a-b))) for a,b in zip(scalar,reference)))
        mask=np.diff(scalar[1])>0
        minimum=min(minimum,float(np.min(np.diff(scalar[0])[mask]/np.diff(scalar[1])[mask])))
    report={'schema':'blue-sky064/portable-prerequisite-reproduction/v1','scope':'COMPUTATIONAL_SOURCE_PROBES_NOT_FLAGSHIP_OR_PHYSICAL_VALIDATION','source_hashes':{p.name:checksum(p) for p in Path(__file__).parent.iterdir() if p.is_file() and p.suffix in {'.py','.json'}},'frozen_registration_hashes':REGISTRATION_HASHES,'forward_replay':{'profiles':len(differences),'scalar_vector_formula_max_absolute_difference':max(differences),'minimum_sampled_dF_dP':minimum,'downloaded_author_code_comparison':'EXECUTED' if original else 'NOT_EXECUTED_USE_OPTIONAL_PINNED_AUTHOR_CODE','downloaded_author_code_max_absolute_difference':max(author_differences) if original else None,'author_code_sha256':AUTHOR_CODE_SHA256 if original else None},'published_curve_calibration':source_curve_holdout(fixture),'exact_obstruction':monotonic_obstruction(registration['target_pressure'],registration['target_friction'],registration['uniform_error_tolerance']),'mixed_composition':mixed_composition(fixture,mixed),'calibration_consistency':calibration_consistency(fixture),'blue_sky_verdict':'HOLD_COMPLETE_ALTERNATIVES_BENEFICIARY_AND_PHYSICAL_TRANSFER_UNRESOLVED','native_accounts_or_real_transfers':False,'actual_model_host_billing':'UNKNOWN','wall_seconds':time.monotonic()-started}
    output.mkdir(parents=True)
    (output/'RESULT.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--author-code',type=Path,help='Optional downloaded exact pinned GA source; no automatic network access.')
    args=parser.parse_args();report=run(args.output,author_code=args.author_code)
    print(json.dumps({'output':str(args.output),'blue_sky_verdict':report['blue_sky_verdict'],'nominal_function_pass':report['mixed_composition']['nominal_function_pass'],'interval_function_pass':report['mixed_composition']['interval_function_pass']},sort_keys=True))
