"""Finite thermal design constructor; declared model, not qualified equipment."""
from __future__ import annotations

import math
import time
import numpy as np
from scipy.optimize import linprog


def cop(request):
    hot = float(request["sink_temp_c"]) + float(request["approach_c"]) + 273.15
    lift = float(request["sink_temp_c"]) - float(request["source_temp_c"]) + 2 * float(request["approach_c"])
    value = float(request["carnot_fraction"]) * hot / lift if lift > 0 else 0.0
    return value if value > 1 else 0.0


def validate(request):
    if request.get("schema") != "portfolio071/thermal-request/v1":
        raise ValueError("unsupported thermal request")
    if request.get("task") not in ("heat_delivery", "thermal_continuity"):
        raise ValueError("unsupported purpose")
    n = request["hours"]
    if type(n) is not int or n < 1:
        raise ValueError("positive integer horizon required")
    for key in ("source_heat_kw", "heat_demand_kw", "electric_limit_kw"):
        a = request[key]
        if len(a) != n or any(not math.isfinite(float(v)) or v < 0 for v in a):
            raise ValueError("invalid hourly boundary: " + key)
    scalars = ("source_temp_c", "sink_temp_c", "approach_c", "carnot_fraction", "pump_capacity_kw", "recovery_capacity_kw", "storage_capacity_kwh", "storage_charge_limit_kw", "storage_discharge_limit_kw", "storage_eta", "storage_loss_per_hour", "initial_storage_kwh", "final_storage_min_kwh")
    if any(not math.isfinite(float(request[k])) for k in scalars):
        raise ValueError("nonfinite boundary")
    if min(request["source_temp_c"], request["sink_temp_c"]) <= -273.15 or request["approach_c"] <= 0:
        raise ValueError("invalid temperature")
    if not 0 < request["carnot_fraction"] <= 1 or not 0 < request["storage_eta"] <= 1:
        raise ValueError("invalid efficiency")
    if not 0 <= request["storage_loss_per_hour"] < 1:
        raise ValueError("invalid storage loss")
    if any(request[k] < 0 for k in scalars[4:9] + scalars[11:]):
        raise ValueError("negative equipment or inventory")
    if max(request["initial_storage_kwh"], request["final_storage_min_kwh"]) > request["storage_capacity_kwh"]:
        raise ValueError("storage obligation exceeds capacity")
    return n


def construct(request):
    start = time.process_time()
    n = validate(request)
    performance = cop(request)
    dimension = 5 * n + 1
    objective = np.zeros(dimension)
    objective[n:2*n] = 1 / performance if performance else 1
    objective[2*n:4*n] = 1e-7
    direct = request["source_temp_c"] >= request["sink_temp_c"] + request["approach_c"]
    bounds = [(0, request["recovery_capacity_kw"] if direct else 0)] * n
    bounds += [(0, request["pump_capacity_kw"] if performance else 0)] * n
    bounds += [(0, request["storage_charge_limit_kw"])] * n
    bounds += [(0, request["storage_discharge_limit_kw"])] * n
    bounds += [(0, request["storage_capacity_kwh"])] * (n+1)
    bounds[4*n] = (request["initial_storage_kwh"], request["initial_storage_kwh"])
    bounds[5*n] = (request["final_storage_min_kwh"], request["storage_capacity_kwh"])
    inequalities, rhs, equalities, erhs = [], [], [], []
    for t in range(n):
        row = np.zeros(dimension)
        row[t] = 1
        row[n+t] = (1 - 1 / performance) if performance else 0
        inequalities.append(row)
        rhs.append(min(request["source_heat_kw"][t], request["recovery_capacity_kw"]))
        row = np.zeros(dimension)
        row[n+t] = 1 / performance if performance else 0
        inequalities.append(row)
        rhs.append(request["electric_limit_kw"][t])
        row = np.zeros(dimension)
        row[t], row[n+t], row[2*n+t], row[3*n+t] = -1, -1, 1, -1
        inequalities.append(row)
        rhs.append(-request["heat_demand_kw"][t])
        row = np.zeros(dimension)
        row[4*n+t+1], row[4*n+t] = 1, -(1-request["storage_loss_per_hour"])
        row[2*n+t], row[3*n+t] = -request["storage_eta"], 1/request["storage_eta"]
        equalities.append(row)
        erhs.append(0)
    result = linprog(objective, A_ub=np.asarray(inequalities), b_ub=rhs, A_eq=np.asarray(equalities), b_eq=erhs, bounds=bounds, method="highs")
    meta = {"schema":"portfolio071/thermal-design/v1", "task":request["task"], "status":"feasible" if result.success else "infeasible", "solver_status":int(result.status), "cpu_seconds":time.process_time()-start, "model":"fixed COP, hourly mixing, explicit storage loss; physical qualification absent"}
    if not result.success:
        return meta
    x = result.x
    d, h, c, q, s = x[:n], x[n:2*n], x[2*n:3*n], x[3*n:4*n], x[4*n:]
    w = h/performance if performance else np.zeros(n)
    meta.update(direct_heat_kw=d.tolist(), pump_hot_kw=h.tolist(), electric_kw=w.tolist(), charge_kw=c.tolist(), discharge_kw=q.tolist(), storage_kwh=s.tolist(), delivered_kw=(d+h-c+q).tolist(), electricity_kwh=float(w.sum()), cop=performance)
    return meta


def resistance_baseline(request, efficiency=.98):
    validate(request)
    required = [d/efficiency for d in request["heat_demand_kw"]]
    return {"method":"ordinary electric resistance without storage", "efficiency_assumption":efficiency, "feasible":all(w <= lim+1e-9 for w,lim in zip(required,request["electric_limit_kw"])), "electricity_kwh":sum(required), "scope":"Same hourly power constraint; unrestricted conventional co-design may build the same heat pump and storage."}


def development_request(task="heat_delivery"):
    n = 8 if task == "thermal_continuity" else 4
    return {"schema":"portfolio071/thermal-request/v1", "task":task, "hours":n, "source_heat_kw":([160,160,160,0,0,160,160,160] if n==8 else [120]*n), "source_temp_c":45., "sink_temp_c":90., "heat_demand_kw":[70.]*n, "electric_limit_kw":[55.]*n, "approach_c":5., "carnot_fraction":.45, "pump_capacity_kw":160., "recovery_capacity_kw":160., "storage_capacity_kwh":200. if n==8 else 0., "storage_charge_limit_kw":100. if n==8 else 0., "storage_discharge_limit_kw":100. if n==8 else 0., "storage_eta":.95, "storage_loss_per_hour":.005, "initial_storage_kwh":0., "final_storage_min_kwh":0.}
