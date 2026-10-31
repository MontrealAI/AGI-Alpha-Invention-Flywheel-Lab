"""Finite declared comparison; report failures and equal-content ties without tuning."""
import copy,json,time
from pathlib import Path
from .physics import SCHEMA,evaluate,check_trace,independent_check,useful_digest,dependency_identity
from .construct import construct

def run(output):
    output=Path(output)
    if output.exists():raise ValueError('FRESH_STUDY_RECEIPT_REQUIRED')
    base={'schema':SCHEMA,'parameter_set':'Ai2020','initial_soc':.1,'target_soc':.8,'maximum_seconds':1800,'maximum_current_A':8,'maximum_voltage_V':4.2,'maximum_temperature_K':313.15,'minimum_anode_potential_V':.02}
    controls=[{'kind':'cccv','current_A':x} for x in [2,2.5,3,3.25,3.5,3.75,4,5,6,8]]
    controls += [{'kind':'staged','currents_A':[4,3.5],'soc_breakpoints':[.7]}, {'kind':'staged','currents_A':[6,3],'soc_breakpoints':[.5]}]
    controls += [{'kind':'anode','current_A':4},{'kind':'anode','current_A':8}]
    protocol={'training_temperatures_K':[293.15,308.15],'evaluation_temperatures_K':[300.15,305.15],'controls':controls,'base':base,'prediction':'Observable interpolated envelope should meet modeled constraints inside trained range; oracle likely faster; tuned staged controls may tie or beat. Equal-content ordinary reuse expected exact tie. No new retained-method advantage presumed.','scope':'DECLARED_DEVELOPMENT_COMPARISON_NOT_UNTOUCHED_CONFIRMATION'}
    start=time.monotonic();cpu=time.process_time();rows=[]
    acquired=construct([{**base,'temperature_K':t} for t in protocol['training_temperatures_K']])
    for temp in protocol['evaluation_temperatures_K']:
        r={**base,'temperature_K':temp}
        for arm,policy in [('acquired_envelope',acquired['policy']),('ordinary_equal_content',copy.deepcopy(acquired['policy']))]+[('control-'+str(i),p) for i,p in enumerate(controls)]:
            row_start=time.monotonic();row_cpu=time.process_time()
            try:
                out=evaluate(r,policy);checked=check_trace(r,out)
                rows.append({'temperature_K':temp,'arm':arm,'policy':policy,'check':checked,'useful_digest':useful_digest(out),'resources':out['resources']})
            except Exception as exc:rows.append({'temperature_K':temp,'arm':arm,'policy':policy,'error_type':type(exc).__name__,'accepted':False,'resources':{'process_cpu_seconds':time.process_time()-row_cpu,'wall_seconds':time.monotonic()-row_start}})
    receipt={'protocol':protocol,'dependency_identity':dependency_identity(),'acquired':acquired,'rows':rows,'wall_seconds':time.monotonic()-start,'process_cpu_seconds':time.process_time()-cpu,'transformational_breakthrough':'NOT_ESTABLISHED','actual_revenue':0,'physical_validation':False}
    output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return receipt

if __name__=='__main__':
    import sys
    result=run(sys.argv[1])
    for row in result['rows']:print(row['temperature_K'],row['arm'],row.get('check',row.get('error_type')),flush=True)
