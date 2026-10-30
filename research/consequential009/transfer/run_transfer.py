from pathlib import Path
from fractions import Fraction as F
import hashlib,json,resource,sys,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from mechanisms.mapping import discover,check_mapping,compile_mapping,MappingRefused
from inventions.consequential009.circuit import parse_netlist,derive_symmetry,apply_symmetry,solve,compile_plan,coordinate_box,separated

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def graph(name,ids):
 pair,old,change,new,decision=ids
 return {'id':name,'nodes':[{'id':pair,'kind':'latent_pair','unit':'pair'},{'id':old,'kind':'observation_partition','unit':'dimensionless'},{'id':change,'kind':'measurement_refinement','unit':'dimensionless'},{'id':new,'kind':'observation_partition','unit':'dimensionless'},{'id':decision,'kind':'pair_identification','unit':'boolean'}],
 'relations':[[pair,'indistinguishable_under',old],[old,'refined_by',change],[change,'produces',new],[pair,'distinguishable_under',new],[new,'permits',decision]],
 'conditions':{'finite_pair_witness':True,'added_information_checked':True,'physical_calibration_claim':False},
 'strategy_recipe':[{'kind':'refine_observation_partition','role_ids':[old,change,new]}]}

def main():
 started=time.perf_counter();cpu=time.process_time();base=ROOT/'research/consequential009';out=base/'transfer'
 paths=[base/'alternatives/diffraction/RESULT.json',base/'alternatives/diffraction/probe.py',base/'analog/rc-meas-ac.sp',ROOT/'inventions/consequential009/circuit.py',ROOT/'mechanisms/mapping.py',Path(__file__)]
 hashes={str(p.relative_to(ROOT)):digest(p) for p in paths}
 d=json.loads(paths[0].read_text());a,b=d['a'],d['b']
 def ac(s,mask=False):return [sum((x+1)*(y+1) if mask else 1 for x in s for y in s if x-y==z) for z in range(-17,18)]
 assert ac(a)==ac(b) and ac(a,True)!=ac(b,True)
 circuit=parse_netlist(paths[2].read_text());v0={e.name:str(e.value) for e in circuit.elements};v1=apply_symmetry(circuit,v0,F(2))
 frequencies=[F(10)**k for k in range(3,8)]
 responses=[]
 for w in frequencies:
  va,ia=solve(circuit,v0,w);vb,ib=solve(circuit,v1,w)
  assert va==vb and ia!=ib
  responses.append({'omega_rad_s':str(w),'nominal_voltages':{k:v.json() for k,v in va.items()},'scaled_voltages':{k:v.json() for k,v in vb.items()},'nominal_input_admittance_S':ia.json(),'scaled_input_admittance_S':ib.json()})
 hypotheses=[{'id':'nominal','values':v0},{'id':'scale2','values':v1}]
 actions=[{'id':'V_'+n,'kind':'voltage_ratio','node':n,'omega_rad_s':'1000000','relative_acquisition_units':1} for n in circuit.nodes]
 actions.append({'id':'Y_input','kind':'input_admittance','omega_rad_s':'1000000','relative_acquisition_units':2})
 policies={kind:{'gain':['99/100','101/100'],'absolute_coordinate_error':'1/100000000'} for kind in ('voltage_ratio','input_admittance')}
 old=compile_plan(circuit,hypotheses,actions,policies,allow_extension=False)
 assert not old['complete_finite_model_acceptance']
 va,ia=solve(circuit,v0,F(1000000));vb,ib=solve(circuit,v1,F(1000000));p=policies['input_admittance']
 assert separated(coordinate_box(ia,p['gain'],p['absolute_coordinate_error']),coordinate_box(ib,p['gain'],p['absolute_coordinate_error']))
 donor=graph('diffraction_integer_witness',['config_pair','uncoded_intensity','amplitude_mask','coded_intensity','distinguished_pair'])
 target=graph('passive_network_scale_witness',['parameter_pair','voltage_ratios','current_sense','input_admittance','identified_pair'])
 maps=discover([donor],target)
 assert maps[0]['status']=='unique';role_map=maps[0]['correspondences'][0]
 check_mapping(donor,target,role_map)
 try:compile_mapping(donor,target,role_map)
 except MappingRefused as exc:legacy_refusal=str(exc)
 else:raise AssertionError('inherited compiler unexpectedly permits new primitive')
 raw_donor=json.loads(json.dumps(donor));raw_target=json.loads(json.dumps(target))
 raw_donor['nodes'][1]['unit']='detector_intensity';raw_donor['nodes'][2]['unit']='mask_transmission'
 raw_target['nodes'][1]['unit']='volt';raw_target['nodes'][2]['unit']='ampere'
 try:check_mapping(raw_donor,raw_target,role_map)
 except MappingRefused as exc:unit_refusal=str(exc)
 else:raise AssertionError('invalid dimensional mapping accepted')
 hint={'operator':'refine_observation_partition','source_graph':donor['id'],'target_graph':target['id'],'mapped_intervention':role_map['amplitude_mask'],'normalization':'Only equivalence/separation transferred; no intensity-to-voltage/current numeric conversion','proof_obligation':'new observable robustly separates the witnessed pair under the same declared uncertainty policy'}
 transferred=compile_plan(circuit,hypotheses,actions,policies,allow_extension=maps[0]['applicable'])
 ordinary=compile_plan(circuit,hypotheses,actions,policies,allow_extension=True)
 assert transferred['complete_finite_model_acceptance'] and transferred['selected_actions']==ordinary['selected_actions']
 result={'scope':'exposed two-state authored DEVELOPMENT diagnostic on source-bound real example topology; no physical specimens or protected confirmation','ontology_origin':'research role supplied source choices, abstraction ontology and extraction; existing bounded search inferred the unique relation-preserving role map','source_sha256':hashes,'source_unchanged':all(digest(p)==hashes[str(p.relative_to(ROOT))] for p in paths),
 'diffraction_integer_signatures':{'uncoded_a':ac(a),'uncoded_b':ac(b),'masked_a':ac(a,True),'masked_b':ac(b,True)},'analog_symmetry':derive_symmetry(circuit),'analog_responses':responses,
 'physical_units':{'raw_voltage':'V','raw_current':'A','candidate_voltage_ratio':'V/V','candidate_input_admittance':'A/V = S','transfer_relations':'dimensionless equality/separation; no conversion of different physical quantities'},
 'mapping_discovery':maps,'inherited_compile_refusal':legacy_refusal,'raw_unit_mapping_refusal':unit_refusal,'transferred_hint':hint,
 'restricted_voltage_only':old,'transferred_extension_enabled':transferred,'equal_action_ordinary_no_transfer_hint':ordinary,
 'decision':{'extension_changes_executed_finite_model_acceptance':True,'transferred_hint_beats_equal_action_ordinary':False,'causal_scope':'Availability of input-admittance observation changes two-state acceptance; ordinary equal-action control ties. No discovery superiority or novel physical law established.'},
 'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-started,'maximum_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'protected_confirmation_alpha_spent':0}
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'extension_acceptance':[old['complete_finite_model_acceptance'],transferred['complete_finite_model_acceptance']],'ordinary_tie':transferred['selected_actions']==ordinary['selected_actions'],'mapping_status':maps[0]['status'],'legacy_refusal':legacy_refusal,'unit_refusal':unit_refusal,'cpu_seconds':result['cpu_seconds'],'source_unchanged':result['source_unchanged']}))
if __name__=='__main__':main()
