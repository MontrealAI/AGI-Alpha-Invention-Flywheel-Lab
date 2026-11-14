"""Frozen calibration-informed experiment; no new physical acquisitions."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .core import relative_error, signature
from .calibrated import compile_calibrated, calibration_hash, response_basis
from .run import archive, payload, reference, signal, source_hashes, EXPECTED, adjacent_order
from .core import compile_plan

COUNTS=(16,20,24,31,36,40,48,64,76)


def evaluate(plan,I,M,U0,delta):
    acquired=np.array(delta[:,plan.selected],copy=True)
    start=time.perf_counter(); cpu=time.process_time()
    prediction=plan.predict(I,M,U0,acquired)
    wall=time.perf_counter()-start; cpu=time.process_time()-cpu
    missing=[j for j in range(I.shape[1]) if j not in plan.selected]
    err=relative_error(prediction,delta)
    return {'contrast_relative_rms':err,
            'unacquired_relative_rms':relative_error(prediction[:,missing],delta[:,missing]) if missing else None,
            'raw_voltage_relative_rms':relative_error(prediction+U0,delta+U0),
            'prediction_wall_seconds':wall,'prediction_cpu_seconds':cpu,
            'within_5_percent':err<=.05,'within_10_percent':err<=.10},prediction


def develop(data,out):
    start=time.perf_counter(); cpu=time.process_time()
    z=archive(data/'Codes_Python.zip')
    I,M,U0=reference(payload(z,'Codes_Python/TrainingData/ref.mat'))
    targets={str(j):signal(payload(z,f'Codes_Python/TrainingData/data{j}.mat'),I,M,U0) for j in range(1,5)}
    rows=[]
    for mode in ['physics_plus_one','reference_svd']:
        for count in COUNTS:
            begin=time.perf_counter(); plan=compile_calibrated(I,M,U0,count,mode)
            compile_time=time.perf_counter()-begin
            errors={name:evaluate(plan,I,M,U0,d)[0] for name,d in targets.items()}
            rows.append({'mode':mode,'count':count,'selected':list(plan.selected),
                         'compile_seconds':compile_time,'targets':errors,
                         'all_training_pass':all(x['within_5_percent'] for x in errors.values())})
    selected=min((r['count'] for r in rows if r['mode']=='physics_plus_one' and r['all_training_pass']),default=None)
    result={'stage':'calibrated_development','source_hashes':source_hashes(),'data_sha256':EXPECTED,
            'primary_mode':'physics_plus_one','selected_count':selected,'rows':rows,
            'selection_reads_evaluation':False,'geometry_sha256':signature(I,M),
            'calibration_sha256':calibration_hash(U0),
            'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu}
    (out/'development.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'stage':result['stage'],'selected_count':selected,'worst_training_errors':[
        {'mode':r['mode'],'count':r['count'],'error':max(v['contrast_relative_rms'] for v in r['targets'].values())} for r in rows]}))


def nearest_reference(name,refs):
    parent=Path(name).parent
    for ancestor in [parent,*parent.parents]:
        matching=[n for n in refs if Path(n).parent==ancestor]
        if len(matching)==1: return matching[0]
    if len(refs)==1: return refs[0]
    raise ValueError(f'Ambiguous reference for {name}')


def confirm(data,out,freeze):
    frozen=json.loads(freeze.read_text())
    if frozen['source_hashes']!=source_hashes(): raise ValueError('Changed source since freeze')
    count=frozen['selected_count']
    if count is None: raise ValueError('No training-qualified candidate')
    start=time.perf_counter(); cpu=time.process_time()
    z=archive(data/'EvaluationData_full.zip')
    names=sorted(z.namelist())
    refs=[n for n in names if Path(n).name.lower()=='ref.mat']
    targets=[n for n in names if Path(n).name.startswith('data') and n.endswith('.mat')]
    if len(targets)!=21: raise ValueError(f'Expected 21 targets, found {len(targets)}: {names}')
    training=archive(data/'Codes_Python.zip')
    I,M,U0=reference(payload(training,'Codes_Python/TrainingData/ref.mat'))
    # Freeze the actual training calibration and indices: no evaluation recalibration.
    plans={}
    resources=[]
    for mode in ['physics_plus_one','reference_svd','current_only']:
        begin=time.perf_counter(); ccpu=time.process_time()
        ids=plans['physics_plus_one'].selected if mode=='current_only' else None
        p=compile_calibrated(I,M,U0,count,mode,ids)
        plans[mode]=p
        resources.append({'arm':mode,'selected':list(p.selected),'count':count,
                          'compile_wall_seconds':time.perf_counter()-begin,
                          'compile_cpu_seconds':time.process_time()-ccpu,'operator_bytes':p.operator.nbytes})
    adjacent=compile_plan(I,M,int(np.linalg.matrix_rank(I)),'linear',adjacent_order(I))
    rows=[]; predictions={}
    for name in targets:
        ref=nearest_reference(name,refs)
        eI,eM,eU0=reference(payload(z,ref))
        if signature(eI,eM)!=signature(I,M): raise ValueError('Different evaluation geometry')
        # A dataset may repeat the identical homogeneous calibration in directories.
        if calibration_hash(eU0)!=frozen['calibration_sha256']:
            raise ValueError('Changed calibration requires a prospectively registered new setup')
        delta=signal(payload(z,name),I,M,U0)
        row={'target':name,'reference':ref,'arms':{}}
        for mode,p in plans.items():
            stats,pred=evaluate(p,I,M,U0,delta)
            row['arms'][mode]=stats
            if mode=='physics_plus_one': predictions[name]=pred
        baseline=adjacent.predict(I,M,delta[:,adjacent.selected])
        row['arms']['adjacent_linear']={'count':len(adjacent.selected),'contrast_relative_rms':relative_error(baseline,delta)}
        row['arms']['full_direct']={'count':76,'contrast_relative_rms':0.0,'scope':'measurement reference, not independent physical truth'}
        # Same physics and calibration available to a conventional specialist.
        p=plans['physics_plus_one']
        B=response_basis(I,M,U0)
        coefficients=np.linalg.lstsq(B[:,p.selected].T,delta[:,p.selected].T,rcond=1e-11)[0].T
        independent_algebra=coefficients@B
        independent_algebra[:,p.selected]=delta[:,p.selected]
        row['ordinary_same_algebra_max_difference']=float(np.max(np.abs(independent_algebra-predictions[name])))
        rows.append(row)
    errors=[r['arms']['physics_plus_one']['contrast_relative_rms'] for r in rows]
    successes=sum(e<=.05 for e in errors)
    accepted=count<=40 and successes>=20 and max(errors)<=.10
    result={'stage':'calibrated_physical_data_confirmation','verdict':'PASS' if accepted else 'REJECT',
       'scope':'offline recovery of measured boundary responses; not tomography or industrial qualification',
       'count':count,'original_patterns':76,'pattern_reduction_fraction':1-count/76,
       'targets':len(rows),'within_5_percent':successes,'worst_relative_rms':max(errors),
       'median_relative_rms':float(np.median(errors)),'rows':rows,'compilation':resources,
       'full_reference_patterns_per_setup':76,'check_requires_full_measurements':True,
       'calibration_reused_without_target_retraining':True,
       'source_hashes':source_hashes(),'data_sha256':EXPECTED,
       'frozen_development_sha256':hashlib.sha256(freeze.read_bytes()).hexdigest(),
       'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,
       'actual_customers':0,'actual_receipts':0,'native_account_operations':0,
       'human_productivity_comparison':'unmeasured','external_review':False}
    (out/'confirmation.json').write_text(json.dumps(result,indent=2)+'\n')
    np.savez_compressed(out/'predicted_signals.npz',**{name.replace('/','__'):v for name,v in predictions.items()})
    print(json.dumps({k:result[k] for k in ['verdict','count','targets','within_5_percent','worst_relative_rms','median_relative_rms','wall_seconds']}))


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['develop','confirm'])
    p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--freeze',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    if a.stage=='develop':develop(a.data,a.output)
    else:
        if a.freeze is None:raise ValueError('Freeze required')
        confirm(a.data,a.output,a.freeze)

if __name__=='__main__':main()
