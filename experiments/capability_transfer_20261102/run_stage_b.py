import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from . import instrument, verifier

HERE=Path(__file__).resolve().parent
FILES=['PREREGISTRATION.md','STAGE_B.md','instrument.py','verifier.py','run_stage_b.py']

def file_hash(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def freeze(path):
    data={'schema':'agi-alpha/numerical-capability-freeze/v1','scope':'prospective synthetic numerical experiment only','sources':{name:file_hash(HERE/name) for name in FILES},'pair_spec':verifier.PAIR,'pair_spec_sha256':verifier.sha(verifier.PAIR),'heldout_physical_measurements_accessed':False}
    with Path(path).open('x') as f: json.dump(data,f,indent=2,sort_keys=True); f.write('\n')
    return {'freeze':str(path),'sha256':file_hash(path)}

def evaluate(frozen,output):
    spec=json.loads(Path(frozen).read_text())
    if spec['sources']!={name:file_hash(HERE/name) for name in FILES} or spec['pair_spec_sha256']!=verifier.sha(verifier.PAIR): raise ValueError('REGISTERED_SOURCE_OR_PAIR_CHANGED')
    dest=Path(output); dest.mkdir(parents=True,exist_ok=False)
    cpu=time.process_time(); wall=time.monotonic()
    numerical=verifier.check_constructor(instrument)
    cells=verifier.make_constructor_cells(instrument,[2.,3.])
    short=[instrument.isolated_trace(c,.75,600) for c in cells]
    short_difference=float(np.max(np.abs(short[0]['voltage_v']-short[1]['voltage_v'])))
    probe=instrument.minimum_separating_probe(cells)
    selected=probe['selected']
    ref=verifier.reference_trace([3.,2.,2.,2.])
    zero=instrument.Ladder(verifier.make_constructor_cells(instrument,[3.,2.,2.,2.]),[0,0,0]).simulate(8,2100,step_s=.5)
    ablations={'equal_sharing':verifier.trace_metrics(np.full_like(ref['current_a'],2),ref['current_a'])}
    if zero['completed']: ablations['no_interconnect']=verifier.trace_metrics(zero['current_a'],ref['current_a'])
    else: ablations['no_interconnect']={'requested_horizon_completed':False,'verdict':'ABSTAIN_OUTSIDE_SOC_DOMAIN'}
    probe_check=numerical['probe_check']
    uncertainty={'action':'ABSTAIN_ON_UNIDENTIFIED_WHOLE_DISCHARGE_PREDICTION','observed_short_difference_v':short_difference,'candidate_capacity_ah':[2,3],'physical_prior_qualified':False,'next_measurement':selected,'remaining_costs':['initial600s characterization','SOC preparation and reset','prior construction and qualification','temperature and aging qualification','independent physical confirmation']}
    result={'schema':'agi-alpha/cell-pack-stage-b-result/v1','freeze_sha256':file_hash(frozen),'source_hashes':spec['sources'],'evidence_class':'EXECUTED_SYNTHETIC_NUMERICAL_EXPERIMENT','physical_measurement_count':0,'cost_bound':verifier.cost_bound(),'short_trace':{'current_a':.75,'duration_s':600,'max_difference_v':short_difference},'stronger_short_trace':verifier.short_trace_pair(),'numerical_verification':numerical,'ablations':ablations,'probe':probe,'probe_independent_check':probe_check,'constructed_artifact':uncertainty,'claims':{'physical_K1_qualified':False,'physical_K2_qualified':False,'new_industry_established':False,'revenue_established':False,'scientific_transfer_advantage_over_incumbent':False,'finite_numerical_implementation_accepted':numerical['numerical_constructor_accepted'],'finite_identifiability_counterexample':numerical['identifiability_counterexample']['peak_10_percent_both_world_guarantee_impossible'],'finite_observation_design':probe_check.get('accepted',False)},'resources':{'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'actual_model_tokens':None,'actual_model_cost_usd':None}}
    for name,data in [('RESULT.json',result),('CAPABILITY.json',uncertainty)]:
        (dest/name).write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')
    curves=[]
    for caps in [[2.,2.,2.,2.],[3.,2.,2.,2.]]:
        r=instrument.Ladder(verifier.make_constructor_cells(instrument,caps),[.002]*3).simulate(8,2100,step_s=1)
        curves.append(r)
    matrix=np.column_stack([curves[0]['time_s'],curves[0]['current_a'],curves[1]['current_a']])
    np.savetxt(dest/'current_worlds.csv',matrix,delimiter=',',header='time_s,a_cell0,a_cell1,a_cell2,a_cell3,b_cell0,b_cell1,b_cell2,b_cell3',comments='')
    summary={'output':str(dest),'result_sha256':file_hash(dest/'RESULT.json'),'cost_saving_fraction':result['cost_bound']['maximum_fraction_saved_at_shared_lower_bound'],'short_voltage_difference_v':short_difference,'numerical_accepted':numerical['numerical_constructor_accepted'],'counterexample':result['claims']['finite_identifiability_counterexample'],'selected_probe':selected,'probe_independently_accepted':probe_check.get('accepted',False)}
    print(json.dumps(summary,sort_keys=True)); return 0 if numerical['numerical_constructor_accepted'] and probe_check.get('accepted',False) else 2

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['freeze','run']); p.add_argument('--freeze',type=Path,required=True); p.add_argument('--output',type=Path); a=p.parse_args()
    if a.command=='freeze': print(json.dumps(freeze(a.freeze))); return 0
    if a.output is None: p.error('--output required for run')
    return evaluate(a.freeze,a.output)

if __name__=='__main__': raise SystemExit(main())
