from __future__ import annotations
import argparse, hashlib, json, math, re, sys, time
from pathlib import Path
import numpy as np
import verify_science as base

HERE=Path(__file__).resolve().parent
PORTFOLIO=HERE.parent


def read(path):
    return json.loads(Path(path).read_text())


def check_certificate(row,field,targets,invariant=None):
    certificate=row[field]
    expected=base.independent_wins(row['game'],set(row['safe']),set(targets),len(certificate['layers'])-1,invariant)
    if [set(v) for v in certificate['layers']]!=expected:
        return False
    policy={(t,s):a for t,s,a in certificate['policy']}
    for t,winners in enumerate(expected[1:],1):
        for s in winners-set(targets):
            a=policy.get((t,s))
            if a not in row['game'][s] or not all(v in expected[t-1] for v in row['game'][s][a]):
                return False
    return True


def purpose():
    root=PORTFOLIO/'purpose';summary=read(root/'results/RESULTS.json')
    records=[]
    for stage in ('K1','K2'):
        for entry in summary[stage]:
            path=root/'results'/entry['artifact_path'];row=read(path)
            recovery_ok=check_certificate(row,'recovery',row['emergency'])
            invariant=set(row['recovery']['layers'][-1])
            field,target=('delivery',row['targets']) if stage=='K1' else ('diagnosis',row['diagnosed'])
            accepted=recovery_ok and check_certificate(row,field,target,invariant) and base.digest(path)==entry['artifact_sha256']
            records.append({'stage':stage,'path':str(path.relative_to(base.ROOT)),'passed':accepted})
    central=read(root/'results/K2_00.json')
    initial=summary['K2'][0]['initial']
    return {'checks':records,'passed':all(v['passed'] for v in records),
            'k1_accepted':summary['K1'][0]['initial'] in read(root/'results/K1_00.json')['delivery']['layers'][-1],
            'k2_accepted':initial in central['diagnosis']['layers'][-1],
            'scope':'All10 saved delivery and4 diagnosis certificates independently reconstructed on their authored finite graphs; no continuous physical validity'}


def interface():
    root=PORTFOLIO/'interface';first=read(root/'results/K1_ARTIFACT.json');second=read(root/'results/K2_ARTIFACT.json')
    mu=np.array([[.3681,2.613],[.1704,.4584],[.1378,.2217]])
    def invert(row):
        sample,reference,dark=[np.asarray(row[k]) for k in ('sample','reference','dark')]
        attenuation=np.log(reference-dark)-np.log(sample-dark)
        return np.linalg.lstsq(mu,attenuation.T,rcond=None)[0].T
    masses=invert(first);output=first['output'];truth=np.asarray(first['truth'])
    k1_error=float(np.max(abs(masses-np.asarray(output['mass_areal_density_g_cm2']))))
    k1_ok=k1_error<1e-10 and np.asarray(output['accepted']).all() and np.all(abs(masses-truth)<=np.asarray(output['component_error_bound_g_cm2'])+1e-10)
    geometry=np.asarray(second['projection_matrix_cm']);lines=invert(second)
    density=np.linalg.lstsq(geometry,lines,rcond=None)[0].reshape(4,4,2)
    output=second['output'];k2_error=float(np.max(abs(density-np.asarray(output['density_g_cm3']))))
    defect=int(np.argmin(density.sum(axis=-1)))
    k2_ok=bool(output['accepted']) and k2_error<1e-9 and defect==second['defective_pixel'] and np.all(abs(density-np.asarray(second['truth_density_g_cm3']))<=np.asarray(output['component_error_bound_g_cm3'])+1e-9)
    return {'passed':bool(k1_ok and k2_ok),'k1_accepted':bool(k1_ok),'k2_accepted':bool(k2_ok),
            'k1_saved_spectra':len(masses),'k1_independent_output_error':k1_error,'k2_saved_rays':len(geometry),
            'k2_independent_output_error':k2_error,'localized_cell':defect,
            'scope':'Independent replay of saved64-spectrum K1 artifact and one99-ray K2 artifact; producer aggregate192/16-case counts are not independently measured physical reliability'}


def complementarity():
    result=read(PORTFOLIO/'complementarity/evidence/RESULTS.json')
    cases={c['name']:c for c in result['cases']};rows=[]
    for run in result['runs']:
        if not run['feasible']:
            continue
        c=cases[run['case']];dt=c['dt_h']
        cop=np.array([c['carnot_fraction']*(c['sink_c']+273.15+c['approach_c'])/((c['sink_c']+273.15+c['approach_c'])-(s+273.15-c['approach_c'])) for s in c['source_c']])
        p,b,ch,dis,soc=[np.asarray(run[k]) for k in ('hp_electric_kw','boiler_electric_kw','charge_kw','discharge_kw','soc_kwh')]
        residuals=[np.max(abs(cop*p+b+dis-ch-np.asarray(c['demand_kw']))),
                   np.max(abs(soc[1:]-c['hourly_retention']**dt*soc[:-1]-dt*c['charge_efficiency']*ch+dt*dis/c['discharge_efficiency'])),
                   max(0,np.max(p+b-c['grid_limit_kw'])),max(0,np.max((cop-1)*p-np.asarray(c['source_kw']))),
                   max(0,np.max(cop*p-c['hp_heat_limit_kw'])),max(0,np.max(soc-c['store_kwh'])),
                   max(0,np.max(ch-c['store_power_kw']),np.max(dis-c['store_power_kw'])),abs(soc[0]),abs(soc[-1]),
                   abs(float(np.sum(p+b)*dt)-run['electric_kwh'])]
        nonnegative=min(float(np.min(v)) for v in (p,b,ch,dis,soc))>=-1e-6
        passed=nonnegative and max(residuals)<1e-6
        rows.append({'case':run['case'],'arm':run['arm'],'passed':bool(passed),'max_residual':float(max(residuals))})
    w=result['water_balance'];mass_error=max(abs(w['feed_kg_h']-w['brine_kg_h']-w['product_water_kg_h']),abs(w['feed_salt_kg_h']-w['brine_salt_kg_h']))
    k1=any(r['case']==result['cases'][0]['name'] and r['passed'] for r in rows)
    k2=any(r['case']==result['cases'][1]['name'] and r['passed'] for r in rows) and mass_error<1e-8
    return {'passed':bool(k1 and k2 and all(r['passed'] for r in rows)),'k1_accepted':k1,'k2_accepted':k2,
            'schedules':rows,'mass_balance_error_kg_h':mass_error,
            'scope':'Independent primal energy/storage/source/electrical constraints for all saved feasible schedules and brine mass balance; infeasibility and plant performance are distinct claims'}


def refractive_index(material,w):
    if material=='air':
        return np.ones_like(w,dtype=complex)
    coefficients={'SiO2':(.6961663,.0684043,.4079426,.1162414,.8974794,9.896161),
                  'MgF2':(.48755108,.04338408,.39875031,.09461442,2.3120353,23.793604)}
    if material in coefficients:
        a=coefficients[material];value=np.ones_like(w)
        for b,c in zip(a[::2],a[1::2]):
            value+=b*w*w/(w*w-c*c)
        return np.sqrt(value)+0j
    if material=='Ta2O5':
        rows=np.array([[float(v) for v in line.split()] for line in (PORTFOLIO/'foundry/tantalum_pentoxide.yml').read_text().splitlines() if re.match(r'^\s+[0-9].*E[+-]',line)])
        return np.interp(w,rows[:,0],rows[:,1])+1j*np.interp(w,rows[:,0],rows[:,2])
    raise ValueError('unsupported material')


def maxwell_response(d,materials,w,theta,polarization):
    indices=[refractive_index(m,w) for m in ['air',*materials,'SiO2']]
    invariant=math.sin(math.radians(theta))
    cosines=[np.sqrt(1-(invariant/n)**2+0j) for n in indices]
    q=[n*c if polarization=='s' else n/c for n,c in zip(indices,cosines)]
    count=len(d);size=2*count+2
    a=np.zeros((len(w),size,size),complex);b=np.zeros((len(w),size),complex)
    a[:,0,0]=1;a[:,1,0]=-q[0];b[:,0]=-1;b[:,1]=-q[0]
    for interface in range(count+1):
        row=2*interface
        if interface:
            phase=np.exp(2j*np.pi*indices[interface]*cosines[interface]*d[interface-1]/w)
            col=2*interface-1
            a[:,row,col]=phase;a[:,row,col+1]=1/phase
            a[:,row+1,col]=q[interface]*phase;a[:,row+1,col+1]=-q[interface]/phase
        if interface==count:
            a[:,row,-1]=-1;a[:,row+1,-1]=-q[-1]
        else:
            col=2*interface+1
            a[:,row,col]=-1;a[:,row,col+1]=-1
            a[:,row+1,col]=-q[interface+1];a[:,row+1,col+1]=q[interface+1]
    amplitudes=np.linalg.solve(a,b[...,None])[...,0]
    r=abs(amplitudes[:,0])**2;t=(q[-1].real/q[0].real)*abs(amplitudes[:,-1])**2
    residual=float(np.max(abs(np.einsum('wij,wj->wi',a,amplitudes)-b)))
    return r,t,1-r-t,residual


def foundry():
    result=read(PORTFOLIO/'foundry/results/RESULTS.json');rows=[]
    designs=[('K1',0,result['K1'])]
    for task in result['K2']:
        for arm,design in task['arms'].items():
            designs.append((task['task_id']+'/'+arm,task['wavelength_shift_um'],design))
    for label,shift,design in designs:
        is_k1=label=='K1';materials=['MgF2','Ta2O5'] if is_k1 else ['Ta2O5','SiO2']*6
        w=np.linspace(.8,1.06,121) if is_k1 else np.r_[np.linspace(.8,1.,60),np.linspace(1.24,1.49,60)]+shift
        minimum=1.;minimum_absorption=1.;residual=0.;disagreement=0.
        cases=design['validation']['cases']
        for item in cases:
            d=np.asarray(design['thickness_um'])*(1+item['thickness_relative_shift'])
            r,t,absorption,err=maxwell_response(d,materials,w,item['angle_deg'],item['polarization'])
            if is_k1:
                metric=float(np.mean(t));expected=item['mean_useful_transmission']
            else:
                metric=min(float(np.mean(t[:60])),float(np.mean(r[60:])))
                expected=min(item['mean_pass_transmission'],item['mean_stop_reflection'])
            minimum=min(minimum,metric);minimum_absorption=min(minimum_absorption,float(np.min(absorption)))
            residual=max(residual,err);disagreement=max(disagreement,abs(metric-expected))
        accepted=minimum>=(.975 if is_k1 else .8) and minimum_absorption>=-1e-10 and residual<1e-8 and disagreement<1e-8
        rows.append({'design':label,'passed':bool(accepted),'worlds':len(cases),'independent_worst_mean':minimum,
                     'minimum_absorption':minimum_absorption,'max_maxwell_residual':residual,'max_producer_metric_difference':disagreement})
    return {'passed':all(r['passed'] for r in rows),'k1_accepted':rows[0]['passed'],'k2_accepted':all(r['passed'] for r in rows[1:]),
            'designs':rows,'scope':'All declared18-world K1 and8 K2 arm/task designs reconstructed through independent batched Maxwell boundary equations; no fabricated-device, continuous-band or industrial-system guarantee'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of prior artifact replay')
    started=time.time();results={}
    for route,check in [('purpose',purpose),('interface',interface),('complementarity',complementarity),('foundry',foundry)]:
        try:
            results[route]=check()
        except Exception as exc:
            results[route]={'passed':False,'k1_accepted':False,'k2_accepted':False,'error':type(exc).__name__+': '+str(exc)}
    value={'schema':'public-portfolio-independent-artifact-replay/v1','checker_sha256':base.digest(__file__),
           'base_checker_sha256':base.digest(base.__file__),'routes':results,'passed':all(r['passed'] for r in results.values()),
           'wall_seconds':time.time()-started,'scope':'Frozen saved output contracts only; actual commerce and physical validation unestablished'}
    output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':value['passed'],'routes':{k:v['passed'] for k,v in results.items()}}))
    raise SystemExit(0 if value['passed'] else 1)
