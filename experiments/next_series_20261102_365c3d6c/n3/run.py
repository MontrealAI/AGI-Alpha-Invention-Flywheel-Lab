import argparse, hashlib, itertools, json, math, pathlib, resource, time
import numpy as np
from instrument import observation, certificate, compact_stress, elastic_strain, centered_rmse

def run():
    root = pathlib.Path(__file__).parent
    E, nu = 200000., .3
    axes = np.eye(3); qx = np.array([math.cos(math.radians(3.450991)),math.sin(math.radians(3.450991)),0.])
    qz = np.array([0.,math.sin(math.radians(3.2238065)),math.cos(math.radians(3.2238065))])
    six = np.vstack([axes, [1/2**.5,1/2**.5,0], [1/2**.5,0,1/2**.5], [0,1/2**.5,1/2**.5]])
    xx = np.array([1,0,0,0,0,0.]); diff = np.array([1,0,-1,0,0,0.]); shear = np.array([0,0,0,1,0,0.])
    specs = [('exact_xz_xx',axes[[0,2]],xx,False,nu),('exact_xz_difference',axes[[0,2]],diff,True,nu),('exact_xyz_xx',axes,xx,True,nu),('tilted_xz_difference',np.vstack([qx,qz]),diff,False,nu),('six_xx',six,xx,True,nu),('six_xy',six,shear,True,nu),('zero_nu_exact_xz_xx',axes[[0,2]],xx,True,0.)]
    truth = np.array([120,-40,70,25,-15,10.]); operators=[]
    for name,q,target,expected,case_nu in specs:
        H=observation(q,E,case_nu); y=H@truth; r=certificate(H,y,target,1e-6)
        identified=r['status']=='IDENTIFIED_MODEL_ONLY'; ok=identified==expected
        if identified:
            errors=[abs(certificate(H,y+1e-6*np.array(signs),target,1e-6)['estimate_mpa']-float(target@truth)) for signs in itertools.product((-1,1),repeat=len(q))]
            r.update(target_truth_mpa=float(target@truth),maximum_corner_error_mpa=max(errors),noise_corners=len(errors))
            ok=ok and max(errors)<=r['radius_mpa']+1e-8 and abs(r['estimate_mpa']-target@truth)<1e-8
        else:
            v=np.asarray(r['null_direction']); r.update(witness_shift_mpa=(200*v).tolist(),witness_target_change_mpa=float(target@(200*v)))
            ok=ok and np.max(np.abs(H@(truth+200*v)-y))<1e-12 and abs(target@(200*v))>1e-6
        operators.append({'case':name,'pass':bool(ok),'result':r})
    nodes,weights=np.polynomial.legendre.leggauss(32); spatial=[]
    for widths in ((1.,1.,1.),(1.,.5,2.),(2.,1.,.5)):
        a,b,c=widths
        for amplitude in (-100.,100.):
            means=[]; divergences=[]; energy=0.
            for x,z in itertools.product((-.4,0.,.4),repeat=2):
                mean=sum(w*compact_stress(x*a,t*b,z*c,widths,amplitude) for t,w in zip(nodes,weights))/2
                means.append(float(np.max(np.abs(mean))))
            for x,y,z in itertools.product((-.3,0.,.3),repeat=3):
                p=np.array([x*a,y*b,z*c]); h=1e-5*min(widths); div=np.zeros(3)
                for j in range(3):
                    d=np.zeros(3); d[j]=h
                    div+=(compact_stress(*(p+d),widths,amplitude)[:,j]-compact_stress(*(p-d),widths,amplitude)[:,j])/(2*h)
                divergences.append(float(np.max(np.abs(div))))
                s=compact_stress(*p,widths,amplitude); energy+=float(np.sum(s*elastic_strain(s))/2)
            boundary=max(float(np.max(np.abs(compact_stress(*(np.eye(3)[j]*sign*np.array(widths)),widths,amplitude)))) for j in range(3) for sign in (-1,1))
            center=float(compact_stress(0,0,0,widths,amplitude)[0,0])
            ok=max(means)<1e-9 and max(divergences)<1e-3 and boundary==0 and abs(center-amplitude)<1e-10 and math.isfinite(energy) and energy>=0
            spatial.append({'halfwidths_mm':widths,'center_xx_mpa':center,'uniform_average_max_abs_mpa':max(means),'finite_difference_divergence_max_mpa_per_mm':max(divergences),'boundary_stress_max_mpa':boundary,'sum_sampled_energy_densities_mpa':energy,'pass':bool(ok),'scope':'authored compact eigenstrain model, not NIST gauge or part'})
    v=np.array([-2e-4,0.,3e-4]); centering=[]
    for offset in (-1e-3,0.,1e-3):
        rmse=centered_rmse(v,v+offset); absolute=float(np.sqrt(np.mean((v-(v+offset))**2)))
        centering.append({'offset_strain':offset,'centered_rmse_strain':rmse,'absolute_rmse_strain':absolute,'pass':bool(rmse<1e-15 and abs(absolute-abs(offset))<1e-15)})
    H=observation(axes)
    invalid=[('nonfinite_E',lambda:observation(axes,float('nan'),nu)),('zero_E',lambda:observation(axes,0,nu)),('nu_half',lambda:observation(axes,E,.5)),('nu_minus_one',lambda:observation(axes,E,-1)),('nonunit_q',lambda:observation([[2.,0.,0.]])),('nonfinite_strain',lambda:certificate(H,[float('nan'),0,0],xx)),('negative_uncertainty',lambda:certificate(H,[0,0,0],xx,-1)),('nonfinite_target',lambda:certificate(H,[0,0,0],[float('inf'),0,0,0,0,0])),('zero_width',lambda:compact_stress(0,0,0,(1,0,1))),('nonfinite_amplitude',lambda:compact_stress(0,0,0,center_xx_mpa=float('nan')))]
    rejections=[]
    for name,action in invalid:
        try:action(); rejected=False
        except ValueError:rejected=True
        rejections.append({'case':name,'pass':rejected})
    groups={'operator_cases':operators,'spatial_cases':spatial,'centering_cases':centering,'invalid_input_cases':rejections}
    return {'schema':'n3-metrology-365c/v1','source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'instrument.py',root/'run.py',root/'CONTRACT.md']},'model_pass':all(r['pass'] for group in groups.values() for r in group),'denominators':{k:len(v) for k,v in groups.items()},**groups,'source_admission':{'status':'HOLD_DATASET_PREREQUISITES','datasets_assessed':1,'nominal_locations_reported_by_source':2248,'raw_rows_retrieved':0,'empirical_target_errors_measured':0,'missing':['effective diffraction to bulk constitutive calibration','direction/shear closure','known matching gauge kernels','absolute systematic reference uncertainty','same-specimen independent local stress truth','supported beneficiary release criterion']},'physical_admission':False,'commercial_admission':False,'k2_executed':False,'native_accounts_opened':0}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();p=pathlib.Path(a.output)
    if p.exists():raise FileExistsError('new attempt path required')
    start=time.monotonic();before=resource.getrusage(resource.RUSAGE_SELF);r=run();after=resource.getrusage(resource.RUSAGE_SELF)
    r['resources']={'wall_seconds':time.monotonic()-start,'process_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'economic_resource_cost':'UNKNOWN','inference_research_and_verification_not_in_program_timer':True}
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+'\n');print(json.dumps({'model_pass':r['model_pass'],'denominators':r['denominators'],'source_admission':r['source_admission']['status']}));raise SystemExit(0 if r['model_pass'] else 1)
