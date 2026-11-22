"""Separate training selection from physical-data confirmation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import time
import zipfile
import numpy as np
from scipy.io import loadmat
from .core import compile_plan, decode, geometry, signature, relative_error

COUNTS=(15,20,24,31,36,40,48,64,76)
EXPECTED={
 'Codes_Python.zip':'330d76f3c7148d2840f7f207cd90d7a98eb1d972867b70188096043c9e3261a2',
 'EvaluationData_full.zip':'85c47f91c0cd15889a96108b389550edafd8bba46b40fd84447e63a62534ce42'}


def source_hashes():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob('*.py'))}


def archive(path):
    content=path.read_bytes()
    if hashlib.sha256(content).hexdigest()!=EXPECTED[path.name]:
        raise ValueError('Archive differs from registered source')
    return zipfile.ZipFile(io.BytesIO(content))


def payload(z,name):
    return loadmat(io.BytesIO(z.read(name)))


def reference(d):
    I,M,C,D=geometry(d['Injref'],d['Mpat'])
    return I,M,decode(d['Uelref'],M.shape[1],I.shape[1])


def signal(d,I,M,U0):
    if signature(d['Inj'],d['Mpat'])!=signature(I,M):
        raise ValueError('Target geometry differs from reference')
    U=decode(d['Uel'],M.shape[1],I.shape[1])
    return U-U0


def compare(plan,I,M,delta,U0):
    acquired=np.array(delta[:,plan.selected],copy=True)
    started=time.perf_counter(); cpu=time.process_time()
    prediction=plan.predict(I,M,acquired)
    elapsed=time.perf_counter()-started; cpu=time.process_time()-cpu
    missing=[j for j in range(I.shape[1]) if j not in plan.selected]
    return {
        'contrast_relative_rms':relative_error(prediction,delta),
        'unacquired_relative_rms':relative_error(prediction[:,missing],delta[:,missing]) if missing else None,
        'raw_voltage_relative_rms':relative_error(prediction+U0,delta+U0),
        'prediction_wall_seconds':elapsed,'prediction_cpu_seconds':cpu,
        'counts_as_within_5_percent':relative_error(prediction,delta)<=.05,
        'counts_as_within_10_percent':relative_error(prediction,delta)<=.10},prediction


def adjacent_order(I):
    indices=[]
    active_electrodes=list(np.flatnonzero(np.any(np.abs(I)>1e-14,axis=1)))
    positions={electrode:pos for pos,electrode in enumerate(active_electrodes)}
    n=len(positions)
    for j in range(I.shape[1]):
        active=np.flatnonzero(np.abs(I[:,j])>1e-14)
        if len(active)==2 and abs(positions[active[0]]-positions[active[1]]) in [1,n-1]:
            indices.append(j)
    return indices+[j for j in range(I.shape[1]) if j not in indices]


def develop(data,out):
    start=time.perf_counter(); cpu=time.process_time()
    z=archive(data/'Codes_Python.zip')
    ref='Codes_Python/TrainingData/ref.mat'
    I,M,U0=reference(payload(z,ref))
    targets={str(j):signal(payload(z,f'Codes_Python/TrainingData/data{j}.mat'),I,M,U0) for j in range(1,5)}
    rows=[]
    for mode in ['reciprocal','linear']:
        for count in COUNTS:
            begin=time.perf_counter(); plan=compile_plan(I,M,count,mode)
            compile_time=time.perf_counter()-begin
            errors={name:compare(plan,I,M,d,U0)[0] for name,d in targets.items()}
            rows.append({'mode':mode,'count':count,'selected':list(plan.selected),
                         'compile_seconds':compile_time,'targets':errors,
                         'all_training_pass':all(x['counts_as_within_5_percent'] for x in errors.values())})
    admissible=[r for r in rows if r['mode']=='reciprocal' and r['all_training_pass']]
    selected=min((r['count'] for r in admissible),default=None)
    result={'stage':'development','source_hashes':source_hashes(),'data_sha256':EXPECTED,
            'primary_mode':'reciprocal','selected_count':selected,'rows':rows,
            'selection_reads_evaluation':False,'geometry_sha256':signature(I,M),
            'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,
            'python':platform.python_version(),'numpy':np.__version__}
    (out/'development.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'stage':'development','selected_count':selected,
        'worst_training_errors':[{ 'mode':r['mode'],'count':r['count'],
          'error':max(v['contrast_relative_rms'] for v in r['targets'].values())} for r in rows]}))


def confirm(data,out,freeze):
    frozen=json.loads(freeze.read_text())
    if frozen['source_hashes']!=source_hashes():
        raise ValueError('Source changed after development selection')
    count=frozen['selected_count']
    if count is None: raise ValueError('No development-qualified candidate')
    start=time.perf_counter(); cpu=time.process_time()
    z=archive(data/'EvaluationData_full.zip')
    names=sorted(z.namelist())
    refs=[n for n in names if Path(n).name.lower()=='ref.mat']
    target_names=[n for n in names if Path(n).name.startswith('data') and n.endswith('.mat')]
    if len(target_names)!=21: raise ValueError(f'Expected 21 targets, found {len(target_names)}: {names}')
    rows=[]; resources=[]; predictions={}; geometry_receipts=[]
    plan_cache={}
    for name in target_names:
        parent=str(Path(name).parent)
        matching=[n for n in refs if str(Path(n).parent)==parent]
        if len(matching)!=1: raise ValueError(f'Ambiguous target reference: {name}, {refs}')
        I,M,U0=reference(payload(z,matching[0]))
        if signature(I,M)!=frozen['geometry_sha256']:
            raise ValueError('Evaluation geometry is outside frozen scope')
        delta=signal(payload(z,name),I,M,U0)
        geometry_receipts.append({'target':name,'reference':matching[0],'geometry_sha256':signature(I,M)})
        modes=[('primary',count,'reciprocal',None),('same_patterns_linear',count,'linear',None),
               ('adjacent_linear',int(np.linalg.matrix_rank(I)),'linear',adjacent_order(I)),
               ('full_reciprocal',76,'reciprocal',None)]
        row={'target':name,'arms':{}}
        for label,k,mode,order in modes:
            if label not in plan_cache:
                begin=time.perf_counter(); ccpu=time.process_time()
                plan_cache[label]=compile_plan(I,M,k,mode,order)
                resources.append({'arm':label,'compile_wall_seconds':time.perf_counter()-begin,
                    'compile_cpu_seconds':time.process_time()-ccpu,'operator_bytes':plan_cache[label].operator.nbytes,
                    'count':k,'selected':list(plan_cache[label].selected)})
            metrics,pred=compare(plan_cache[label],I,M,delta,U0)
            row['arms'][label]=metrics
            if label=='primary': predictions[name]=pred
        # The conventional specialist gets the same known physics, basis and data.
        p=plan_cache['primary']; ordinary=p.predict(I,M,np.array(delta[:,p.selected],copy=True))
        row['ordinary_same_arrangement_equal']=bool(np.array_equal(ordinary,predictions[name]))
        row['arms']['full_direct']={'count':76,'contrast_relative_rms':0.0,
            'scope':'same measured voltages as reference, not independent physical truth'}
        rows.append(row)
    successes=sum(r['arms']['primary']['counts_as_within_5_percent'] for r in rows)
    worst=max(r['arms']['primary']['contrast_relative_rms'] for r in rows)
    accepted=count<=40 and successes>=20 and worst<=.10
    result={'stage':'physical_data_confirmation','verdict':'PASS' if accepted else 'REJECT',
       'scope':'offline recovery of measured boundary responses; not tomography or industrial qualification',
       'count':count,'original_patterns':76,'pattern_reduction_fraction':1-count/76,
       'targets':len(rows),'within_5_percent':successes,'worst_relative_rms':worst,
       'median_relative_rms':float(np.median([r['arms']['primary']['contrast_relative_rms'] for r in rows])),
       'full_reference_patterns_per_setup':76,'check_requires_full_measurements':True,
       'source_hashes':source_hashes(),'data_sha256':EXPECTED,
       'frozen_development_sha256':hashlib.sha256(freeze.read_bytes()).hexdigest(),
       'rows':rows,'compilation':resources,'geometry_receipts':geometry_receipts,
       'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,
       'actual_customers':0,'actual_receipts':0,'native_account_operations':0,
       'human_productivity_comparison':'unmeasured','external_review':False}
    (out/'confirmation.json').write_text(json.dumps(result,indent=2)+'\n')
    np.savez_compressed(out/'predicted_signals.npz',**{name.replace('/','__'):v for name,v in predictions.items()})
    print(json.dumps({k:result[k] for k in ['verdict','count','targets','within_5_percent','worst_relative_rms','median_relative_rms','wall_seconds']}))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['develop','confirm'])
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--freeze',type=Path)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=False)
    if a.stage=='develop': develop(a.data,a.output)
    else:
        if a.freeze is None: raise ValueError('Confirmation requires frozen development')
        confirm(a.data,a.output,a.freeze)

if __name__=='__main__': main()
