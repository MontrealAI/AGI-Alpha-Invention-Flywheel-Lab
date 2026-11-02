from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path
import importlib.util

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix


def _number(value, name, low=0.0, high=math.inf):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(name)
    return float(value)


def carnot_cop(source_c, sink_c, approach_c=5.0, fraction=0.45):
    source = _number(source_c, "source_c", -100, 200) + 273.15 - _number(approach_c, "approach_c", 0, 30)
    sink = _number(sink_c, "sink_c", -50, 250) + 273.15 + approach_c
    fraction = _number(fraction, "fraction", 0.01, 1)
    if sink <= source:
        raise ValueError("heat pump model requires positive temperature lift")
    cop = fraction * sink / (sink - source)
    if cop <= 1:
        raise ValueError("declared heat pump performance cannot recover source heat")
    return cop


def validate_case(case):
    required = {"schema", "name", "dt_h", "demand_kw", "source_kw", "source_c", "sink_c", "carnot_fraction", "approach_c", "grid_limit_kw", "hp_heat_limit_kw", "store_kwh", "store_power_kw", "charge_efficiency", "discharge_efficiency", "hourly_retention", "electricity_usd_kwh"}
    if not isinstance(case, dict) or set(case) != required or case["schema"] != "thermal-dispatch/v1" or not isinstance(case["name"], str):
        raise ValueError("case schema")
    n = len(case["demand_kw"])
    if not 1 <= n <= 8760 or any(len(case[k]) != n for k in ("source_kw", "source_c", "electricity_usd_kwh")):
        raise ValueError("time-series lengths")
    out = copy.deepcopy(case)
    for key in ("dt_h", "grid_limit_kw", "hp_heat_limit_kw", "store_kwh", "store_power_kw"):
        out[key] = _number(case[key], key)
    if not 0 < out["dt_h"] <= 24:
        raise ValueError("dt_h")
    for key in ("charge_efficiency", "discharge_efficiency", "hourly_retention"):
        out[key] = _number(case[key], key, 0.01, 1)
    for key in ("demand_kw", "source_kw", "electricity_usd_kwh"):
        out[key] = [_number(v, key) for v in case[key]]
    out["cop"] = [carnot_cop(t, case["sink_c"], case["approach_c"], case["carnot_fraction"]) for t in case["source_c"]]
    return out


def solve_dispatch(case, use_heat_pump=True, use_storage=True, method="highs"):
    c = validate_case(case)
    n, dt = len(c["demand_kw"]), c["dt_h"]
    size = 5 * n + 1
    objective = np.zeros(size)
    objective[:n] = np.array(c["electricity_usd_kwh"]) * dt
    objective[n:2*n] = objective[:n]
    objective[2*n:4*n] = 1e-10 * dt
    equality, rhs = lil_matrix((2*n,size)), np.zeros(2*n)
    for i in range(n):
        equality[2*i,i], equality[2*i,n+i], equality[2*i,2*n+i], equality[2*i,3*n+i] = c["cop"][i], 1, -1, 1
        rhs[2*i]=c["demand_kw"][i]
        equality[2*i+1,4*n+i+1], equality[2*i+1,4*n+i] = 1, -(c["hourly_retention"] ** dt)
        equality[2*i+1,2*n+i], equality[2*i+1,3*n+i] = -dt*c["charge_efficiency"], dt/c["discharge_efficiency"]
    inequality, upper = lil_matrix((n,size)), [c["grid_limit_kw"]]*n
    for i in range(n):
        inequality[i,i], inequality[i,n+i] = 1, 1
    bounds = []
    for i in range(n):
        hp_max = min(c["hp_heat_limit_kw"]/c["cop"][i], c["source_kw"][i]/(c["cop"][i]-1)) if use_heat_pump else 0
        bounds.append((0, hp_max))
    bounds += [(0, c["grid_limit_kw"])] * n
    bounds += [(0, c["store_power_kw"] if use_storage else 0)] * (2*n)
    bounds += [(0, c["store_kwh"] if use_storage else 0)] * (n+1)
    bounds[4*n] = bounds[5*n] = (0, 0)
    t0, cpu0 = time.perf_counter(), time.process_time()
    result = linprog(objective, A_ub=inequality.tocsr(), b_ub=upper, A_eq=equality.tocsr(), b_eq=rhs, bounds=bounds, method=method)
    report = {"schema":"thermal-result/v1", "case":c["name"], "feasible":bool(result.success), "solver_status":int(result.status), "solver_message":result.message, "use_heat_pump":bool(use_heat_pump), "use_storage":bool(use_storage), "wall_seconds":time.perf_counter()-t0, "cpu_seconds":time.process_time()-cpu0, "method":method}
    if result.success:
        v = result.x
        report.update({"hp_electric_kw":v[:n].tolist(), "boiler_electric_kw":v[n:2*n].tolist(), "charge_kw":v[2*n:3*n].tolist(), "discharge_kw":v[3*n:4*n].tolist(), "soc_kwh":v[4*n:].tolist(), "electric_kwh":float(sum(v[:n]+v[n:2*n])*dt), "electricity_cost_usd":float(np.dot(np.array(c["electricity_usd_kwh"]),v[:n]+v[n:2*n])*dt), "source_heat_kwh":float(np.dot(np.array(c["cop"])-1, v[:n])*dt)})
        report["acceptance"] = analyze_dispatch(case, report)
    return report


def analyze_dispatch(case, result, tolerance=1e-6):
    c = validate_case(case)
    if not result.get("feasible"):
        return {"accepted":False,"reason":"no schedule"}
    n, dt = len(c["demand_kw"]), c["dt_h"]
    names = ("hp_electric_kw", "boiler_electric_kw", "charge_kw", "discharge_kw", "soc_kwh")
    values = []
    for name in names:
        expected = n+1 if name == "soc_kwh" else n
        if len(result.get(name,[])) != expected:
            return {"accepted":False,"reason":"shape"}
        try:
            values.append(np.array([_number(v,name,-tolerance) for v in result[name]]))
        except ValueError:
            return {"accepted":False,"reason":"invalid number"}
    p,b,ch,dis,soc = values
    cop = np.array(c["cop"])
    violations = {
        "heat_balance_kw":float(max(abs(cop*p+b+dis-ch-np.array(c["demand_kw"])))),
        "storage_balance_kwh":float(max(abs(soc[1:]-c["hourly_retention"]**dt*soc[:-1]-dt*c["charge_efficiency"]*ch+dt*dis/c["discharge_efficiency"]))),
        "grid_kw":float(max(0,max(p+b-c["grid_limit_kw"]))),
        "source_heat_kw":float(max(0,max((cop-1)*p-np.array(c["source_kw"])))),
        "hp_heat_kw":float(max(0,max(cop*p-c["hp_heat_limit_kw"]))),
        "store_energy_kwh":float(max(0,max(soc-c["store_kwh"]))),
        "store_power_kw":float(max(0,max(ch-c["store_power_kw"]),max(dis-c["store_power_kw"]))),
        "free_initial_or_remaining_kwh":float(max(abs(soc[0]),abs(soc[-1]))),
        "unavailable_hp_kw":float(max(p)) if not result.get("use_heat_pump") else 0,
        "unavailable_storage_kw":float(max(max(ch),max(dis))) if not result.get("use_storage") else 0,
    }
    electrical = float(sum(p+b)*dt)
    violations["reported_electric_kwh"] = abs(electrical-result.get("electric_kwh",-1))
    return {"accepted":all(v<=tolerance for v in violations.values()), "violations":violations, "tolerance":tolerance}


def recover_brine(feed_kg_h, salt_fraction, target_fraction, temp_c, gor, hx_effectiveness):
    feed = _number(feed_kg_h,"feed_kg_h",0,1e9)
    salt = _number(salt_fraction,"salt_fraction",1e-8,0.26)
    target = _number(target_fraction,"target_fraction",salt,0.26)
    temp = _number(temp_c,"temp_c",40,100)
    gor = _number(gor,"gor",1,16)
    hx = _number(hx_effectiveness,"hx_effectiveness",0,0.95)
    brine = feed*salt/target
    water = feed-brine
    latent_kj_kg = 2500.9-2.36*temp
    latent_heat_kw = water*latent_kj_kg/(3600*gor)
    sensible_heat_kw = feed*4.18*(temp-20)*(1-hx)/3600
    return {"feed_kg_h":feed,"feed_salt_kg_h":feed*salt,"brine_kg_h":brine,"brine_salt_kg_h":brine*target,"product_water_kg_h":water,"water_recovery":water/feed if feed else 0,"evaporation_temp_c":temp,"latent_kj_kg":latent_kj_kg,"assumed_gained_output_ratio":gor,"sensible_heat_kw":sensible_heat_kw,"latent_heat_kw":latent_heat_kw,"required_heat_kw":latent_heat_kw+sensible_heat_kw,"scope":"screening balance only; no salt rejection, scaling, corrosion, fouling or potable-water qualification"}


def make_case(name, demand_kw, sink_c, grid_limit_kw, source_on_hours, source_kw, hp_heat_limit_kw, store_kwh, hours=48, dt_h=1.0):
    n = int(hours/dt_h)
    return {"schema":"thermal-dispatch/v1","name":name,"dt_h":dt_h,"demand_kw":[demand_kw]*n,"source_kw":[source_kw if (i*dt_h)%24 < source_on_hours else 0.0 for i in range(n)],"source_c":[55.0]*n,"sink_c":sink_c,"carnot_fraction":0.45,"approach_c":5.0,"grid_limit_kw":grid_limit_kw,"hp_heat_limit_kw":hp_heat_limit_kw,"store_kwh":store_kwh,"store_power_kw":hp_heat_limit_kw,"charge_efficiency":0.97,"discharge_efficiency":0.97,"hourly_retention":0.999,"electricity_usd_kwh":[0.10]*n}


def cases():
    k1 = make_case("K1-continuous-process-heat",500,110,300,12,800,1000,4000)
    water = recover_brine(5000,0.07,0.20,70,6,0.75)
    k2 = make_case("K2-hypersaline-water-recovery",water["required_heat_kw"],75,170,12,700,800,3500)
    return k1,k2,water


def run_experiment(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True,exist_ok=False)
    k1,k2,water = cases()
    records = []
    for case in (k1,k2):
        for label,hp,store,method in (("baseline",False,False,"highs"),("A-heat-pump",True,False,"highs"),("B-storage",False,True,"highs"),("A+B-retained",True,True,"highs"),("conventional-unrestricted",True,True,"highs-ds"),("equal-content-ordinary-reuse",True,True,"highs-ipm")):
            result=solve_dispatch(case,hp,store,method)
            result["arm"]=label
            records.append(result)
        spec=importlib.util.spec_from_file_location("complementarity_fresh",Path(__file__).with_name("fresh.py"))
        fresh=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        result=fresh.solve_fresh(case)
        result["arm"]="no-inheritance-fresh-build"
        if result["feasible"]:
            result["acceptance"]=analyze_dispatch(case,result)
        records.append(result)
    for name,update in (("source-failure",{"source_kw":[0]*48}),("low-grid",{"grid_limit_kw":50}),("unqualified-heatpump",{"carnot_fraction":0.20}),("storage-loss",{"hourly_retention":0.90})):
        case=copy.deepcopy(k2)
        case.update(update)
        case["name"]=name
        result=solve_dispatch(case)
        result["arm"]="adverse"
        records.append(result)
    converged=[]
    for dt in (1.0,0.5,0.25):
        c=make_case("K1-time-step-"+str(dt),500,110,300,12,800,1000,4000,dt_h=dt)
        r=solve_dispatch(c)
        converged.append({"dt_h":dt,"feasible":r["feasible"],"electric_kwh":r.get("electric_kwh"),"accepted":r.get("acceptance",{}).get("accepted",False)})
    properties=[{"temp_c":temp,"nist_delta_h_kj_kg":reference,"linear_delta_h_kj_kg":2500.9-2.36*temp,"relative_error":abs((2500.9-2.36*temp)/reference-1)} for temp,reference in ((40,2406.0),(70,2333.0),(100,2256.4))]
    summary={"schema":"complementarity-evidence/v1","source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"fresh_source_sha256":hashlib.sha256(Path(__file__).with_name("fresh.py").read_bytes()).hexdigest(),"cases":[k1,k2],"water_balance":water,"runs":records,"time_step_check":converged,"pure_water_property_checks":properties,"physical_validation":"not performed; pure-water property reference check does not qualify hypersaline brine or equipment","blue_sky_admission":"unresolved; conventional complete design is intentionally unrestricted and may tie","retained_means":"same thermodynamic/dispatch source; no learned or cached answer","no_inheritance_limit":"fresh solver builds a different thermal-output formulation without importing the retained kernel; same constructor supplied its math, so no measured independent reinvention or discovery advantage","actual_customers":0,"actual_revenue_usd":0}
    (output/"RESULTS.json").write_text(json.dumps(summary,indent=2,allow_nan=False)+"\n")
    return summary


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=run_experiment(args.output)
    print(json.dumps({"runs":len(result["runs"]),"feasible":sum(r["feasible"] for r in result["runs"]),"physical_validation":result["physical_validation"]}))
