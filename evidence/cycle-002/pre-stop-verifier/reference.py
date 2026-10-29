import argparse,hashlib,json
from decimal import Decimal,localcontext
from pathlib import Path

D=Decimal
ROOT=Path('/workspace/scratch/396195bee4b8/cycle2-research/battery')
SOURCE_SHA={'Kenya_GIZ_2025.pdf':'c995f47a66224663f92dbf00aedb2cb8092e783525a4cbd0f39b7d6187a8e428','CEC_2024_056.pdf':'e7882bc6b92333a436c35d477d05ae391fac9a96fb40e239c5b6149d811f9007'}

def reference():
    checks=[]
    for name,sha in SOURCE_SHA.items():
        actual=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if actual!=sha:raise ValueError('Independent primary source mismatch '+name)
        checks.append({'name':'primary-source-'+name,'passed':True,'sha256':actual})
    components={'cells':D(14000),'BMS':D(10500),'casing':D(16500),'labelling':D(400),'testing':D(14000),'labour':D(10500)}
    total=sum(components.values()); residual=total-components['testing']
    if total!=D(65900) or residual!=D(51900):raise AssertionError('Published BOM arithmetic')
    price_new=D(187000)/D(5)
    scenarios=[]
    for capacity in [D('2.4'),D('51.2')*D('52')/1000]:
        for remove_testing in [False,True]:
            cost=residual if remove_testing else total
            new_unit=price_new/D(3500)
            used_unit=cost/capacity/D(2000)
            scenarios.append({'capacity_kWh':float(capacity),'capacity_status':'source price basis' if capacity==D('2.4') else 'nameplate voltage-times-Ah identity, not verified usable capacity','testing_removed_completely':remove_testing,'used_upfront_KES_per_nominal_lifetime_kWh':float(used_unit),'new_upfront_KES_per_nominal_lifetime_kWh':float(new_unit),'used_minus_new_fraction':float(used_unit/new_unit-1),'used_cycle_breakeven':float(cost/capacity/new_unit)})
    if not (scenarios[1]['used_minus_new_fraction']>0 and scenarios[3]['used_minus_new_fraction']<0):raise AssertionError('Expected identity-sensitivity sign flip absent')
    pairs=[('BESS1',30,'146.4','138.6','122.4','122.1'),('BESS1',60,'145.1','136.6','125.1','122.8'),('BESS2',30,'148.4','135.1','123.9','97.9'),('BESS2',60,'149.3','146.5','123.9','125.6')]
    computed=[]
    expected=[D('5.33'),D('5.86'),D('8.96'),D('1.88')]
    for row,published in zip(pairs,expected):
        asset,current,q0,q1,m0,m1=row
        loss=(D(q0)-D(q1))/D(q0)*100
        raw=(D(m0)-D(m1))/D(m0)*100
        if abs(loss-published)>D('.01'):raise AssertionError('Source narrative fraction mismatch')
        computed.append({'asset':asset,'current_A':current,'equivalent_min_loss_percent':float(loss),'raw_Ah_change_percent':float(raw),'claimed_actual_degradation':None,'measurement_comparability':'UNKNOWN; voltage/SOC/temperature endpoints differ and calibration mapping absent'})
    return {'schema':'cycle2-independent-reference/v1','spec_sha256':'29d96e90471e827f73b1eeeda1d51f0296362f6b918630fe009eec3f36322d2a','primary_sources':SOURCE_SHA,'checks':checks,'costs':{'reported_BOM_sum_KES':int(total),'all_testing_removed_upper_bound_KES':int(components['testing']),'testing_share_of_BOM_percent':float(components['testing']/total*100),'residual_BOM_KES':int(residual),'reported_basis_kWh':2.4,'voltage_times_Ah_kWh':float(D('51.2')*52/1000),'reported_Table10_GreenCell_total_KES':69500,'Table10_total_implied_KES_per_kWh':float(D(69500)/D('2.4')),'Table9_total_implied_KES_per_kWh':float(total/D('2.4'))},'conditional_scenarios':scenarios,'scenario_assumptions':['used2000cycles, new3500cycles from generic source ranges, not matched field certification','Felicity187000KES5kWh quoted source example, not accepted live order','identical DoD, efficiency and economic timing','fractional kWh scaling ignores module indivisibility and capacity mismatch','all unmeasured downstream costs assumed equal per lifetime unit only for this sensitivity; actual complete costs UNKNOWN'],'measurement_pairs':computed,'sampling':{'distinct_CEC_assets':2,'paired_test_routes':4,'independent_battery_replications_not_equal_to_rows':True,'Kenya_selected_modules_released':14,'Kenya_tested_modules':48,'all_remaining_module_dispositions_released':False,'selected_modules_are_not_acceptance_yield':True},'verdict':{'demand_for_ALPHAdiagnostic':'UNKNOWN','matched_complete_service_cost':'UNKNOWN','cohort_economic_admission':'BLOCKED','diagnostic_superiority':'NOT_ESTABLISHED','true_degradation_from_aggregate':'UNKNOWN','sign_flip':'DEMONSTRATED_IN_CONDITIONAL_ARITHMETIC_ONLY','new_confirmation_alpha_spent':0},'limits':['This reference audits observed source arithmetic and uncertainty; it does not simulate demand, confirm capacity or deliver an operational battery qualification','Removing every test cost is an unrealistically favorable upper bound and still leaves safety/quality obligations','Conflicts in price, chemistry and usable capacity must resolve before any cohort decision']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    with localcontext() as c:c.prec=40;r=reference()
    (a.output/'REFERENCE.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(a.output),'full_service_admission':'BLOCKED','source_identity_sensitivity_sign_flip':True}))
