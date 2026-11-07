"""Independent, read-only numerical feasibility checker. No producer imports.

A passing witness establishes the registered hourly DC policy only. Solver summary
numbers are consistency checked, not an independently reconstructed dual proof.
"""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def verify(witness, data_directory, registration_path=None):
    """Return a JSON-serializable report; malformed inputs fail closed."""
    checks = {}
    report = {'accepted': False, 'checks': checks,
              'optimality_independently_verified': False,
              'scope': 'Registered fixed-commitment hourly DC feasibility only; no physical qualification, commercial rights, financing or profit.'}
    def require(name, condition, detail=None):
        checks[name] = {'passed': bool(condition)}
        if detail is not None:
            checks[name]['detail'] = detail
        if not condition:
            raise ValueError(name)
    def residual(name, values, tol):
        val = float(np.max(np.abs(values))) if np.size(values) else 0.0
        require(name, np.isfinite(val) and val <= tol, val)
    def bound(name, values, lower, upper, tol):
        val = float(max(0, np.max(np.asarray(lower)-values), np.max(values-np.asarray(upper))))
        require(name, np.isfinite(val) and val <= tol, val)
    def arr(value, shape, name):
        a = np.asarray(value, dtype=float)
        require(name + '_shape_finite', a.shape == shape and np.all(np.isfinite(a)))
        return a
    try:
        regpath = Path(registration_path) if registration_path else Path(__file__).resolve().parents[1]/'campaign/grid-service-envelope-20261104/REGISTRATION.json'
        reg = json.loads(regpath.read_text())
        amendment_path=regpath.with_name('AMENDMENT_01.json')
        if amendment_path.exists():
            amendment=json.loads(amendment_path.read_text())
            for key,value in amendment['overrides'].items():
                if isinstance(value,dict):reg[key].update(value)
                else:reg[key]=value
        w = json.loads(Path(witness).read_text()) if isinstance(witness, (str, Path)) else witness
        require('solver_success', w['solver_status'] == 0)
        require('registered_dimensions', reg['hours'] == 24 and reg['fault_reveal_hour'] == 8)
        tol = float(reg['acceptance']['residual_tolerance_mw'])
        require('tolerance_valid', 0 < tol <= 1e-5)
        require('registered_day', w['day'] in reg['development_days'] + reg['confirmation_days'])
        require('registered_site_scale', w['site'] in reg['buses'] and w['it_capacity_mw'] in reg['it_capacity_mw'])
        require('known_control', w['control'] in ('primary','no_equipment','fixed_work'))
        scale = float(w['it_capacity_mw']); directory = Path(data_directory)
        manifest_bytes=(directory/'SOURCE_MANIFEST.json').read_bytes()
        # Manifest digest pinned during development, before confirmation runs.
        require('source_manifest_hash', hashlib.sha256(manifest_bytes).hexdigest() == '921a0c56a997ec5f0c1360383f068a787143cb384ea7d1d0c815c42c41780da0')
        manifest = json.loads(manifest_bytes)
        require('dataset_commit', manifest['commit'] == reg['dataset_commit'])
        entries = {e['local_path']: e for e in manifest['files']}
        names = ['bus.csv','branch.csv','gen.csv'] + ['DAY_AHEAD_'+s+'_3days.csv' for s in ('Natural_Inflow','hydro','pv','regional_Load','rtpv','wind')]
        for name in names:
            entry = entries[name]
            digest = hashlib.sha256((directory/name).read_bytes()).hexdigest()
            require('source_hash_'+name, digest == entry.get('selected_sha256', entry['full_sha256']))
        def rows(name):
            with open(directory/name, newline='') as f:
                return list(csv.DictReader(f))
        buses, lines, gens = (rows(s) for s in names[:3])
        require('source_dimensions', (len(buses),len(lines),len(gens)) == (73,120,158))
        require('unique_source_ids', len({b['Bus ID'] for b in buses}) == 73 and len({b['UID'] for b in lines}) == 120 and len({g['GEN UID'] for g in gens}) == 158)
        series = {}
        for name in names[3:]:
            selected = [r for r in rows(name) if '%04d-%02d-%02d' % (int(r['Year']),int(r['Month']),int(r['Day'])) == w['day']]
            require('hour_coverage_'+name, [int(r['Period']) for r in selected] == list(range(1,25)))
            for key in selected[0]:
                if key in ('Year','Month','Day','Period'): continue
                require('profile_unique_'+key, key not in series)
                series[key] = arr([r[key] for r in selected], (24,), 'profile_'+key)
        busidx = {int(b['Bus ID']): i for i,b in enumerate(buses)}
        genbus = [busidx[int(g['Bus ID'])] for g in gens]
        demand = np.zeros((24,73))
        for i,b in enumerate(buses):
            total = sum(float(q['MW Load']) for q in buses if q['Area'] == b['Area'])
            demand[:,i] = series[b['Area']] * float(b['MW Load'])/total + float(b['MW Shunt G'])
        lo = np.zeros((24,158)); hi = lo.copy(); thermal=[]
        for j,g in enumerate(gens):
            typ,uid = g['Unit Type'],g['GEN UID']; pmax=float(g['PMax MW'])
            if typ in ('CSP','STORAGE','SYNC_COND'): pass
            elif typ in ('RTPV','HYDRO','ROR'): lo[:,j]=hi[:,j]=series[uid]
            elif typ in ('PV','WIND'): hi[:,j]=np.minimum(pmax,series[uid])
            else:
                thermal.append(j);lo[:,j]=float(g['PMin MW']);hi[:,j]=pmax
            require('source_generator_bounds_'+uid, np.all(lo[:,j]>=0) and np.all(hi[:,j]<=pmax+1e-7) and np.all(lo[:,j]<=hi[:,j]))
        if 'thermal_commitment' in w:
            require('commitment_registered', 'commitment' in reg['network']['thermal'].lower() or 'binary' in reg['network']['thermal'].lower())
            commitment=arr(w['thermal_commitment'],(158,),'thermal_commitment')
            residual('commitment_binary',commitment-np.round(commitment),1e-8)
            bound('commitment_bounds',commitment,0,1,1e-8)
            residual('nonthermal_commitment_zero',commitment[[j for j in range(158) if j not in thermal]],1e-8)
            lo[:,thermal]*=commitment[thermal]
            hi[:,thermal]*=commitment[thermal]
        else:
            require('all_on_registration', 'all nonzero thermal units committed throughout' in reg['network']['thermal'])
        largest = max(thermal, key=lambda j:float(gens[j]['PMax MW']))
        require('fault_generator_identity', w['largest_thermal_uid'] == gens[largest]['GEN UID'])
        e = reg['equipment']; c = reg['modeled_usd']; pue=reg['pue']
        capacities=w['capacities'];require('capacity_keys',set(capacities)=={'battery_mwh','battery_mw','backup_mw'})
        E,P,K=arr([capacities[k] for k in ('battery_mwh','battery_mw','backup_mw')],(3,),'capacities')
        bound('equipment_capacity_bounds',np.array([E,P,K]),0,scale*np.array([e['battery_mwh_per_it_mw_max'],e['battery_mw_per_it_mw_max'],e['backup_mw_per_it_mw_max']]),tol)
        if w['control']=='no_equipment': residual('no_equipment_control',[E,P,K],tol)
        work=arr(w['work'],(24,),'work');bound('work_rate',work,0,scale,tol)
        # Two disjoint release/deadline windows make each window's aggregate an
        # unambiguous batch allocation; future-batch work cannot move before 12.
        for a,b in zip(reg['work']['release_hours'],reg['work']['deadline_hours']):
            residual('work_batch_%s_%s'%(a,b),work[a:b].sum()-reg['work']['each_batch_capacity_hours']*scale,tol)
        if w['control']=='fixed_work': residual('fixed_work_control',work-scale/2,tol)
        require('scenario_coverage',set(w['plans'])==set(reg['scenarios']))
        parsed={}; operating={}
        expected={'generation','theta','grid','backup','charge','discharge','soc'}
        for scenario in reg['scenarios']:
            z=w['plans'][scenario];require(scenario+'_plan_keys',set(z)==expected)
            plan={k:arr(z[k],(24,158) if k=='generation' else (24,73) if k=='theta' else (25,) if k=='soc' else (24,),scenario+'_'+k) for k in expected}
            parsed[scenario]=plan
            pg,theta,grid,backup,charge,discharge,soc=(plan[k] for k in ('generation','theta','grid','backup','charge','discharge','soc'))
            lower,upper=lo.copy(),hi.copy();loads=demand.copy()
            if scenario=='largest_thermal_out_8_24': lower[8:,largest]=upper[8:,largest]=0
            if scenario=='line_A1_out_load_110pct_8_24': loads[8:]*=1.1
            prefix=scenario+'_'
            bound(prefix+'generation_bounds',pg,lower,upper,tol)
            bound(prefix+'angles',theta,-np.pi,np.pi,tol);residual(prefix+'reference_angle',theta[:,0],tol)
            for j in thermal:
                delta=np.diff(pg[:,j]); allowed=np.full(23,60*float(gens[j]['Ramp Rate MW/Min']))
                if scenario=='largest_thermal_out_8_24' and j==largest: delta=np.delete(delta,7);allowed=np.delete(allowed,7)
                bound(prefix+'ramp_'+gens[j]['GEN UID'],delta,-allowed,allowed,tol)
            nodal=-loads.copy()
            for j,bi in enumerate(genbus): nodal[:,bi]+=pg[:,j]
            nodal[:,busidx[w['site']]]-=grid
            for branch in lines:
                bi,bj=busidx[int(branch['From Bus'])],busidx[int(branch['To Bus'])]
                tap=float(branch['Tr Ratio']) or 1.0
                flow=(theta[:,bi]-theta[:,bj])*100/(float(branch['X'])*tap)
                if scenario=='line_A1_out_load_110pct_8_24' and branch['UID']=='A1': flow[8:]=0
                bound(prefix+'line_'+branch['UID'],flow,-float(branch['Cont Rating']),float(branch['Cont Rating']),tol)
                nodal[:,bi]-=flow;nodal[:,bj]+=flow
            residual(prefix+'nodal_balance',nodal,tol)
            bound(prefix+'grid',grid,0,pue*scale,tol)
            if scenario=='connection_trip_8_14': residual(prefix+'trip_grid',grid[8:14],tol)
            if scenario=='connection_trip_8_20_and_backup_failure': residual(prefix+'trip_grid',grid[8:20],tol)
            bound(prefix+'backup',backup,0,K,tol)
            bound(prefix+'charge',charge,0,P,tol);bound(prefix+'discharge',discharge,0,P,tol)
            bound(prefix+'shared_battery_power',charge+discharge,0,P,tol)
            if scenario in ('backup_failure_8_24','connection_trip_8_20_and_backup_failure'):residual(prefix+'backup_failure',backup[8:],tol)
            if scenario=='battery_failure_8_24':residual(prefix+'battery_failure',np.r_[charge[8:],discharge[8:]],tol)
            bound(prefix+'fuel',np.array([backup.sum()]),0,e['backup_fuel_mwh_per_it_mw_max']*scale,tol)
            bound(prefix+'soc',soc,0,E,tol)
            residual(prefix+'initial_soc',soc[0]-E*e['initial_soc_fraction'],tol)
            bound(prefix+'terminal_soc',np.array([soc[-1]]),E*e['terminal_soc_fraction'],E,tol)
            residual(prefix+'soc_transition',np.diff(soc)-e['charge_efficiency']*charge+discharge/e['discharge_efficiency'],tol)
            residual(prefix+'site_balance',grid+backup+discharge-charge-pue*work,tol)
            operating[scenario]=float(grid.sum()*c['electricity_per_mwh']+backup.sum()*c['backup_per_mwh']+(charge.sum()+discharge.sum())*c['battery_throughput_per_mwh'])
        baseline=parsed[reg['scenarios'][0]]
        for scenario,plan in parsed.items():
            for key in expected:residual(scenario+'_nonanticipativity_'+key,plan[key][:(9 if key=='soc' else 8)]-baseline[key][:(9 if key=='soc' else 8)],tol)
        worst=float(w['worst_daily_opex_usd']);require('opex_finite',np.isfinite(worst))
        moneytol=max(1e-4,abs(worst)*1e-8)
        residual('worst_opex_matches',worst-max(operating.values()),moneytol)
        r=c['capital_opportunity_rate']; crf=r/(1-(1+r)**-c['capital_life_years'])
        multiplier=(1+c['construction_contingency_fraction'])*crf+c['performance_reserve_fraction_of_capex']*r
        objective=worst+multiplier*(E*c['battery_capex_per_mwh']+P*c['battery_power_capex_per_mw']+K*c['backup_capex_per_mw'])/365
        certificate=w['optimization']
        certvals=arr([certificate[k] for k in ('primal_objective','dual_objective','absolute_gap','max_equality_residual','max_inequality_violation')],(5,),'solver_summary')
        residual('reported_objective_matches',certvals[0]-objective,max(1e-4,abs(objective)*1e-8))
        residual('reported_gap_consistent',certvals[2]-abs(certvals[0]-certvals[1]),1e-5)
        bound('reported_residuals_small',certvals[3:],0,tol,tol*0.01)
        bound('reported_gap_small',certvals[2:3],0,max(1e-4,abs(objective)*1e-8),0)
        if 'relative_gap' in certificate:
            relative_gap=float(certificate['relative_gap'])
            require('reported_relative_gap_small',np.isfinite(relative_gap) and 0 <= relative_gap <= 1.01e-8)
        report.update(accepted=True,scenario_operating_cost_usd=operating,reconstructed_objective=objective,solver_certificate_status='Reported summary consistent; dual multipliers not independently supplied or verified')
    except (ValueError,KeyError,TypeError,IndexError,OSError,OverflowError,ZeroDivisionError) as exc:
        report['error']=str(exc)
    return report
