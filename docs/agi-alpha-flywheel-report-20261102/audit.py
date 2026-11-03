import argparse,json
from fractions import Fraction as F
from pathlib import Path

HERE=Path(__file__).resolve().parent
def audit(d):
    assert d['schema']=='agi-alpha-flywheel-report/evidence/v1'
    f=d['foundry'];assert f['record_count']==144 and f['registered_requests_per_arm']==36
    expected={'fresh':51633,'frozen_first':49041,'accumulating':48141,'conventional':13566}
    for arm,total in expected.items():
        row=f['summary']['all'][arm];assert row['arithmetic']==total==sum(row['by_generation'].values())
        assert row['requests']==36 and row['statuses']=={'ACCEPTED':30,'NONIDENTIFIABLE':6}
    assert len(f['controls'])==7 and all(f['controls'].values())
    assert expected['frozen_first']-expected['accumulating']==900
    r=d['r2'];cases=r['cases'];assert len(cases)==110 and len({x['case_id'] for x in cases})==110
    routes=['purpose','interface','complementarity','arrangement','foundry']
    assert {x['route'] for x in cases}==set(routes)
    for route in routes:assert sum(x['route']==route for x in cases)==22
    for x in cases:
        keys=['opening_microUSD','cumulative_company_profit_microUSD','final_cash_microUSD','final_available_microUSD','protected_cash_microUSD','payables_microUSD','revenue_microUSD','expenses_microUSD','final_365_day_company_profit_microUSD']
        assert all(type(x[k]) is int for k in keys)
        assert x['cumulative_company_profit_microUSD']==x['revenue_microUSD']-x['expenses_microUSD']
        assert x['final_cash_microUSD']==x['opening_microUSD']+x['cumulative_company_profit_microUSD']+x['payables_microUSD']
        assert 0<=x['final_available_microUSD']<=x['final_cash_microUSD']
        assert x['protected_cash_microUSD']==x['final_cash_microUSD']-x['final_available_microUSD']
        assert x['window_calendar_utc']==r['window']
        assert x['target_3b']==(x['final_365_day_company_profit_microUSD']>=3_000_000_000_000_000)
    assert sum(not x['account_summary_covered'] for x in cases)==23
    assert max(x['final_365_day_company_profit_microUSD'] for x in cases)==0
    assert min(x['final_365_day_company_profit_microUSD'] for x in cases)==-36_000_000_000
    assert r['verdict']['actual_revenue_usd']==0 and r['verdict']['goal_3b_accounts']==0
    assert 8*3*40000==960000
    p=d['paired'];assert p['bulk_passed']==p['registered_case_counts']['bulk_cases']==80
    assert p['spatial_passed']==p['registered_case_counts']['spatial_fields']==12
    assert p['control_checks_passed']==8 and p['limitation_witnesses_observed']==4
    assert p['actual_revenue_usd']==0 and p['native_account_actions']==0 and p['physical_qualification'] is False
    k=d['outlearning073']['K2'];assert k['retained']['accepted']==k['ordinary']['accepted']==21
    assert k['retained']['tasks']==k['ordinary']['tasks']==24
    assert k['retained']['diagnostic_units']-k['ordinary']['diagnostic_units']==51
    assert k['retained']['sum_maximum_executor_units']==k['ordinary']['sum_maximum_executor_units']==240
    scenarios=d['outlearning073']['native_scope']['cases'];assert len(scenarios)==7
    expected_profits={'positive':1079680000,'weak-demand':-500000000,'adverse-cost':-1000000000,'delayed-collection':-600200000,'no-entry':-480000000,'positive-1000-underfunded':-500000000,'positive-100k-reference':1079680000}
    assert {r['case_id'] for r in scenarios}==set(expected_profits)
    for r in scenarios:
        z=r['snapshot']['summary'];assert z['profit']==z['revenue']-z['expenses']==expected_profits[r['case_id']]
    assert d['operational075']['paired_total_driving_seconds_retained_minus_ordinary']==-68012
    assert not d['operational075']['native_account_operated'] and not d['operational075']['native_target_achieved']
    assert not d['grid074']['learned_advantage'] and not d['grid074']['newly_enabled_business']
    return {'status':'PASS','checks':'Exact compact-data arithmetic, complete case denominators and stated scopes; not full native-account or physical verification','R2_cases':110,'R2_uncovered':23,'foundry_records':144,'foundry_controls':7,'source_count':18}
def witness():
    E=F(200000);nu=F(3,10)
    H=[[F(1)/E,-nu/E,-nu/E],[-nu/E,-nu/E,F(1)/E]]
    v=[F(1),F(7,3),F(1)]
    assert all(sum(a*b for a,b in zip(row,v))==0 for row in H)
    assert v[0]!=0 and v[0]-v[2]==0
    weights=[E/(1+nu),-E/(1+nu)]
    assert [sum(weights[i]*H[i][j] for i in range(2)) for j in range(3)]==[1,0,-1]
    return {'scope':'Report-authored exact linear illustration, not a fresh physical result','null_direction':[str(x) for x in v],'observations_unchanged':True,'absolute_x_stress_identifiable':False,'x_minus_z_identifiable':True}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=audit(json.loads((HERE/'evidence/observations.json').read_text()));result['exact_witness']=witness()
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
