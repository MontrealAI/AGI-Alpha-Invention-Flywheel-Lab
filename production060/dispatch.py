"""Public operational concrete dispatch: best-fit construction and OR-Tools CP-SAT.

This is a logistical planning model, not concrete-quality or driver-law certification.
The optional CP-SAT search is deliberately bounded: successive target-ordered windows,
candidate trucks and increasing load-index paths. Its bounds are local, never day bounds.
All published truck travel inputs are already adjusted; no multiplier is applied here.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any


SCALE = 10  # exact 0.1 minute clock; source values are multiples of 1.4 minutes


def _ticks(value: float) -> int:
    return int(math.ceil(float(value) * SCALE - 1e-7))


def _minutes(value: int) -> float:
    return value / SCALE


@dataclass(frozen=True)
class DispatchConfig:
    loading_min: float = 10
    plant_cleaning_min: float = 10
    driver_preparation_min: float = 15
    unloading_min: float = 10
    site_cleaning_min: float = 15
    driver_break_min: float = 15
    driver_meal_min: float = 30
    default_load_m3: float = 7.5
    activation_weight: int = 120
    travel_weight: int = 1
    lateness_weight: int = 10
    window_size: int = 3
    candidate_trucks: int = 6
    time_limit_s: float = 10
    random_seed: int = 60
    missing_travel: str = "refuse"

    def __post_init__(self):
        for key in ("loading_min", "plant_cleaning_min", "driver_preparation_min",
                    "unloading_min", "site_cleaning_min", "driver_break_min", "driver_meal_min", "default_load_m3"):
            if not math.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be finite and positive")
        if min(self.activation_weight, self.travel_weight, self.lateness_weight) < 0:
            raise ValueError("objective weights must be nonnegative")
        if self.window_size < 1 or self.candidate_trucks < 1 or self.time_limit_s < 0:
            raise ValueError("invalid bounded solver configuration")
        if self.missing_travel not in ("refuse", "exclude"):
            raise ValueError("missing_travel must be refuse or exclude")


class InputDataError(ValueError):
    """Incomplete or inconsistent operational input, rather than invented travel."""


def _finite(value: Any) -> bool:
    return not isinstance(value,bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _prepare(resources: dict, day: dict, cfg: DispatchConfig):
    if day.get("travel_row_mapping_verified") is False:
        raise InputDataError("unverified order-to-travel-row mapping")
    plants = [p["id"] for p in resources["plants"]
              if p.get("source_mean_loading_rate") != 0]
    if not plants:
        raise InputDataError("no operational loading plant")
    trucks = {t["id"]: t for t in resources["trucks"]}
    if not trucks or any(not _finite(t.get("capacity_m3")) or t["capacity_m3"] <= 0
                         for t in trucks.values()):
        raise InputDataError("truck capacities must be positive")
    matrix = resources.get("plant_travel_minutes", [])
    all_plants = [p["id"] for p in resources["plants"]]
    if all_plants != list(range(1, len(all_plants) + 1)):
        raise InputDataError("expected contiguous source plant pseudo IDs")
    if len(matrix) != len(all_plants) or any(len(row) != len(all_plants) for row in matrix):
        raise InputDataError("complete directed plant travel matrix is required")
    if any(not _finite(v) or v < 0 for row in matrix for v in row):
        raise InputDataError("invalid or missing directed plant travel")
    if any(t["home_plant"] not in all_plants for t in trucks.values()):
        raise InputDataError("unknown home plant")
    travel = day.get("travel_minutes", [])
    excluded, missing_mix, loads = [], [], []
    seen = set()
    for i, order in enumerate(day["orders"]):
        oid = order["id"]
        if oid in seen:
            raise InputDataError("duplicate order id")
        seen.add(oid)
        row = travel[i] if i < len(travel) else None
        missing = (oid in day.get("missing_travel_order_ids", []) or row is None
                   or len(row) != len(all_plants)
                   or any(not _finite(v) or v < 0 for v in row))
        if missing:
            excluded.append({"order_id": oid, "reason": "missing_or_invalid_order_plant_travel",
                             "volume_m3": order.get("volume_m3")})
            continue
        if not order.get("mix_id"):
            missing_mix.append(oid)
        for field in ("volume_m3", "requested_min", "release_min", "interval_min"):
            if not _finite(order.get(field)) or order[field] < 0:
                raise InputDataError(f"order {oid}: invalid {field}")
        remaining = Decimal(str(order["volume_m3"]))
        if remaining <= 0:
            raise InputDataError(f"order {oid}: volume must be positive")
        q = order.get("default_load_m3")
        q = Decimal(str(q if _finite(q) and q > 0 else cfg.default_load_m3))
        ix = 0
        while remaining > 0:
            volume = min(q, remaining)
            loads.append({"load_id": f"{oid}:{ix}", "order_id": oid, "load_index": ix,
                          "client_id": order.get("client_id"), "mix_id": order.get("mix_id"),
                          "volume_m3": float(volume), "release_min": order["release_min"],
                          "target_unload": _minutes(_ticks(order["requested_min"])
                              + ix * _ticks(order["interval_min"])),
                          "travel": {p: _ticks(row[p - 1]) for p in plants}})
            remaining -= volume
            ix += 1
    if excluded and cfg.missing_travel == "refuse":
        raise InputDataError("missing travel for orders " + ",".join(str(x["order_id"]) for x in excluded))
    return plants, trucks, [[_ticks(x) for x in row] for row in matrix], loads, excluded, missing_mix


def _slot(calendar: list[tuple[int, int]], earliest: int, duration: int) -> int:
    start = earliest
    for a, b in sorted(calendar):
        if start + duration <= a:
            break
        if start < b:
            start = b
    return start


def _initial_state(trucks, plants, frozen):
    state = {t: {"available": 0, "plant": v["home_plant"], "last": None,
                 "active": False} for t, v in trucks.items()}
    bays = {p: [] for p in plants}
    order_ready = {}
    for row in sorted(frozen, key=lambda x: (x["return_time"], str(x["load_id"]))):
        t, p = row["truck_id"], row["plant_id"]
        state[t] = {"available": _ticks(row["return_time"]), "plant": p,
                    "last": row["load_id"], "active": True}
        bays[p].append((_ticks(row["bay_start"]), _ticks(row["bay_end"])))
        order_ready[row["order_id"]] = max(order_ready.get(row["order_id"], 0),
                                              _ticks(row["unload_end"]))
    return state, bays, order_ready


def _make_row(load, truck, plant, start, previous, reposition, cfg):
    bay = _ticks(cfg.loading_min + cfg.plant_cleaning_min)
    prep = _ticks(cfg.driver_preparation_min)
    out = load["travel"][plant]
    unload = start + bay + prep + out
    row = {k: v for k, v in load.items() if k != "travel"}
    row.update({"truck_id": truck, "plant_id": plant, "previous_load_id": previous,
                "loading_start": _minutes(start), "loading_end": _minutes(start + _ticks(cfg.loading_min)),
                "bay_start": _minutes(start), "bay_end": _minutes(start + bay),
                "dispatch_time": _minutes(start + bay + prep),
                "site_arrival": _minutes(unload), "unload_start": _minutes(unload),
                "unload_end": _minutes(unload + _ticks(cfg.unloading_min)),
                "site_clear": _minutes(unload + _ticks(cfg.unloading_min + cfg.site_cleaning_min)),
                "return_time": _minutes(unload + _ticks(cfg.unloading_min + cfg.site_cleaning_min) + out),
                "outbound_travel_min": _minutes(out), "return_travel_min": _minutes(out),
                "reposition_min": _minutes(reposition), "reposition_start": _minutes(start - reposition),
                "reposition_end": _minutes(start),
                "driver_break_start": _minutes(start-reposition-_ticks(cfg.driver_break_min+cfg.driver_meal_min)) if previous else None,
                "driver_break_end": _minutes(start-reposition-_ticks(cfg.driver_meal_min)) if previous else None,
                "driver_meal_start": _minutes(start-reposition-_ticks(cfg.driver_meal_min)) if previous else None,
                "driver_meal_end": _minutes(start-reposition) if previous else None,
                "lateness_min": _minutes(max(0, unload - _ticks(load["target_unload"]))),
                "quality_status": "logistics_only_mix_not_certified"})
    return row


def _apply(rows, state, bays, order_ready):
    for r in rows:
        state[r["truck_id"]] = {"available": _ticks(r["return_time"]), "plant": r["plant_id"],
                                    "last": r["load_id"], "active": True}
        bays[r["plant_id"]].append((_ticks(r["bay_start"]), _ticks(r["bay_end"])))
        order_ready[r["order_id"]] = _ticks(r["unload_end"])


def _objective(rows, initially_active, cfg):
    activation = len({r["truck_id"] for r in rows} - initially_active)
    travel = sum(r["outbound_travel_min"] + r["return_travel_min"] + r["reposition_min"] for r in rows)
    late = sum(r["lateness_min"] for r in rows)
    return cfg.activation_weight * activation + cfg.travel_weight * travel + cfg.lateness_weight * late


def _greedy(loads, plants, trucks, matrix, state, bays, order_ready, cfg, now, nearest=False):
    state, bays, order_ready = copy.deepcopy(state), copy.deepcopy(bays), dict(order_ready)
    rows = []
    baydur = _ticks(cfg.loading_min + cfg.plant_cleaning_min)
    pre = baydur + _ticks(cfg.driver_preparation_min)
    for load in loads:
        options = sorted(plants, key=lambda p: (load["travel"][p], p))[:1] if nearest else plants
        best = None
        for p in options:
            travel = load["travel"][p]
            for tid, truck in trucks.items():
                if truck["capacity_m3"] + 1e-9 < load["volume_m3"]:
                    continue
                prev = state[tid]
                reposition = matrix[prev["plant"] - 1][p - 1]
                pause = _ticks(cfg.driver_break_min+cfg.driver_meal_min) if prev["active"] else 0
                ready = max(prev["available"] + pause, _ticks(now)) + reposition
                # Waiting before an order is released is permitted only for an
                # already known offline order; movement always follows its release.
                ready = max(ready, _ticks(load["release_min"]) + reposition)
                earliest = max(ready, _ticks(load["release_min"]),
                               _ticks(load["target_unload"]) - pre - travel,
                               order_ready.get(load["order_id"], 0) - pre - travel)
                start = _slot(bays[p], earliest, baydur)
                lateness = max(0, start + pre + travel - _ticks(load["target_unload"]))
                score = (cfg.activation_weight * (not prev["active"])
                         + cfg.travel_weight * _minutes(2 * travel + reposition)
                         + cfg.lateness_weight * _minutes(lateness))
                key = (score, lateness, truck["capacity_m3"] - load["volume_m3"], start, p, tid)
                if best is None or key < best[0]:
                    best = (key, _make_row(load, tid, p, start, prev["last"], reposition, cfg))
        if best is None:
            raise InputDataError(f"no truck can carry load {load['load_id']}")
        rows.append(best[1])
        _apply([best[1]], state, bays, order_ready)
    return rows


def _cp_window(loads, incumbent, plants, trucks, matrix, state, bays, order_ready, cfg, now, limit, hints):
    from ortools.sat.python import cp_model

    m = cp_model.CpModel()
    n = len(loads)
    incumbent_by_id={r["load_id"]:r for r in incumbent}
    incumbent_rows=[incumbent_by_id[l["load_id"]] for l in loads]
    route_indices={t:[i for i,r in enumerate(incumbent_rows) if r["truck_id"]==t] for t in trucks}
    candidate = {r["truck_id"] for r in incumbent}
    # Exact search inside this disclosed finite truck subset; always includes incumbent.
    ranked = sorted(trucks, key=lambda t: (
        not state[t]["active"], state[t]["available"], trucks[t]["capacity_m3"], t))
    for t in ranked:
        if len(candidate) >= max(cfg.candidate_trucks, len(candidate)):
            break
        candidate.add(t)
    for p in plants:
        local = sorted((t for t in trucks if state[t]["plant"] == p),
                       key=lambda t: (not state[t]["active"], state[t]["available"], t))
        candidate.update(local[:1])
    candidate = sorted(candidate)
    maximum = max([_ticks(r["return_time"]) for r in incumbent]
                  + [_ticks(now), *[s["available"] for s in state.values()]])
    horizon = maximum + n * (max(max(row) for row in matrix) + 10000)
    baydur = _ticks(cfg.loading_min + cfg.plant_cleaning_min)
    pre = baydur + _ticks(cfg.driver_preparation_min)
    site = _ticks(cfg.unloading_min + cfg.site_cleaning_min)
    start, plant, outbound, unload, ret, late = [], [], [], [], [], []
    bayintervals = {p: [m.NewFixedSizeIntervalVar(a, b-a, f"fixed_{p}_{k}")
                        for k, (a,b) in enumerate(bays[p])] for p in plants}
    assign = {}
    for i, load in enumerate(loads):
        start.append(m.NewIntVar(max(_ticks(now), _ticks(load["release_min"])), horizon, f"start{i}"))
        plant.append(m.NewIntVarFromDomain(cp_model.Domain.FromValues(plants), f"plant{i}"))
        out = m.NewIntVar(0, max(load["travel"].values()), f"out{i}")
        m.AddElement(plant[i]-1, [load["travel"].get(p, 0) for p in range(1,len(matrix)+1)], out)
        m.AddHint(out,_ticks(incumbent_rows[i]["outbound_travel_min"]))
        outbound.append(out)
        u = m.NewIntVar(0, horizon + 10000, f"unload{i}")
        m.Add(u == start[i] + pre + out)
        m.Add(u >= _ticks(load["target_unload"]))
        m.Add(u >= order_ready.get(load["order_id"], 0))
        prior = [j for j in range(i) if loads[j]["order_id"] == load["order_id"]]
        if prior:
            m.Add(u >= unload[prior[-1]] + _ticks(cfg.unloading_min))
        unload.append(u)
        m.AddHint(u,_ticks(incumbent_rows[i]["unload_start"]))
        r = m.NewIntVar(0, horizon + 20000, f"return{i}")
        m.Add(r == u + site + out)
        ret.append(r)
        m.AddHint(r,_ticks(incumbent_rows[i]["return_time"]))
        l = m.NewIntVar(0, horizon + 10000, f"late{i}")
        m.Add(l == u - _ticks(load["target_unload"]))
        late.append(l)
        m.AddHint(l,_ticks(incumbent_rows[i]["lateness_min"]))
        chosen = []
        for p in plants:
            b = m.NewBoolVar(f"plant{i}_{p}")
            m.Add(plant[i] == p).OnlyEnforceIf(b)
            m.Add(plant[i] != p).OnlyEnforceIf(b.Not())
            bayintervals[p].append(m.NewOptionalFixedSizeIntervalVar(start[i], baydur, b, f"bay{i}_{p}"))
            chosen.append(b)
            m.AddHint(b,int(p==incumbent_rows[i]["plant_id"]))
        m.AddExactlyOne(chosen)
        eligible=[]
        for t in candidate:
            if trucks[t]["capacity_m3"] + 1e-9 >= load["volume_m3"]:
                assign[i,t] = m.NewBoolVar(f"assign{i}_{t}")
                eligible.append(assign[i,t])
        m.AddExactlyOne(eligible)
    for intervals in bayintervals.values():
        m.AddNoOverlap(intervals)
    transitions = {}
    for i in range(n):
        for j in range(i+1,n):
            idx = m.NewIntVar(0,len(matrix)**2-1,f"idx{i}_{j}")
            m.Add(idx == (plant[i]-1)*len(matrix) + plant[j]-1)
            d = m.NewIntVar(0,max(max(row) for row in matrix),f"move{i}_{j}")
            m.AddElement(idx, [x for row in matrix for x in row], d)
            ip,jp=incumbent_rows[i]["plant_id"],incumbent_rows[j]["plant_id"]
            m.AddHint(idx,(ip-1)*len(matrix)+jp-1);m.AddHint(d,matrix[ip-1][jp-1])
            transitions[i,j] = d
    travel_cost = [2*x for x in outbound]
    activations=[]
    arcvars={}
    for t in candidate:
        eligible=[i for i in range(n) if (i,t) in assign]
        first, last, incoming, outgoing = {}, {}, {i:[] for i in eligible}, {i:[] for i in eligible}
        used=m.NewBoolVar(f"used{t}")
        route=route_indices[t]
        m.AddHint(used,int(bool(route)))
        for i in eligible:
            first[i]=m.NewBoolVar(f"first{i}_{t}")
            last[i]=m.NewBoolVar(f"last{i}_{t}")
            is_first=bool(route) and route[0]==i
            m.AddHint(first[i],int(is_first));m.AddHint(last[i],int(bool(route) and route[-1]==i))
            incoming[i].append(first[i]); outgoing[i].append(last[i])
            d=m.NewIntVar(0,max(matrix[state[t]["plant"]-1]),f"initial_move{i}_{t}")
            m.AddElement(plant[i]-1, matrix[state[t]["plant"]-1], d)
            initial_distance=matrix[state[t]["plant"]-1][incumbent_rows[i]["plant_id"]-1]
            m.AddHint(d,initial_distance)
            pause = _ticks(cfg.driver_break_min+cfg.driver_meal_min) if state[t]["active"] else 0
            m.Add(start[i] >= max(state[t]["available"]+pause,_ticks(now),_ticks(loads[i]["release_min"])) + d).OnlyEnforceIf(first[i])
            cost=m.NewIntVar(0,max(max(row) for row in matrix),f"initial_cost{i}_{t}")
            m.Add(cost==d).OnlyEnforceIf(first[i]); m.Add(cost==0).OnlyEnforceIf(first[i].Not())
            m.AddHint(cost,initial_distance if is_first else 0)
            travel_cost.append(cost)
        for i in eligible:
            for j in eligible:
                if i>=j: continue
                a=m.NewBoolVar(f"arc{i}_{j}_{t}")
                arcvars[i,j,t]=a
                is_arc=any(aidx==i and bidx==j for aidx,bidx in zip(route,route[1:]))
                m.AddHint(a,int(is_arc))
                outgoing[i].append(a); incoming[j].append(a)
                m.Add(start[j] >= ret[i]+_ticks(cfg.driver_break_min+cfg.driver_meal_min)+transitions[i,j]).OnlyEnforceIf(a)
                m.Add(start[j] >= _ticks(loads[j]["release_min"])+transitions[i,j]).OnlyEnforceIf(a)
                cost=m.NewIntVar(0,max(max(row) for row in matrix),f"move_cost{i}_{j}_{t}")
                m.Add(cost==transitions[i,j]).OnlyEnforceIf(a);m.Add(cost==0).OnlyEnforceIf(a.Not())
                m.AddHint(cost,matrix[incumbent_rows[i]["plant_id"]-1][incumbent_rows[j]["plant_id"]-1] if is_arc else 0)
                travel_cost.append(cost)
        for i in eligible:
            m.Add(sum(incoming[i])==assign[i,t]); m.Add(sum(outgoing[i])==assign[i,t])
        m.Add(sum(first.values())==used);m.Add(sum(last.values())==used)
        if not state[t]["active"]: activations.append(used)
    objective=(cfg.activation_weight*SCALE*sum(activations)
               + cfg.travel_weight*sum(travel_cost)+cfg.lateness_weight*sum(late))
    m.Minimize(objective)
    byid={r["load_id"]:r for r in incumbent}
    if hints:
        byid.update({r["load_id"]:r for r in hints if r["load_id"] in byid})
    for i,l in enumerate(loads):
        r=byid[l["load_id"]]
        if r["plant_id"] in plants and max(_ticks(now),_ticks(l["release_min"])) <= _ticks(r["bay_start"]) <= horizon:
            m.AddHint(start[i],_ticks(r["bay_start"]));m.AddHint(plant[i],r["plant_id"])
        for t in candidate:
            if (i,t) in assign: m.AddHint(assign[i,t],int(t==r["truck_id"]))
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=max(0.001,limit)
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=cfg.random_seed
    status=solver.Solve(m)
    feasible=status in (cp_model.OPTIMAL,cp_model.FEASIBLE)
    receipt={"status":solver.StatusName(status),"scope":"restricted_window",
             "load_ids":[l["load_id"] for l in loads],"candidate_truck_ids":candidate,
             "wall_time_s":solver.WallTime(),"objective_bound":solver.BestObjectiveBound()/SCALE,
             "incumbent_objective":_objective(incumbent,{t for t,s in state.items() if s["active"]},cfg),
             "solver_objective":solver.ObjectiveValue()/SCALE if feasible else None,
             "relative_gap":((solver.ObjectiveValue()-solver.BestObjectiveBound())/max(1,abs(solver.ObjectiveValue()))) if feasible else None}
    if not feasible:
        receipt["selected"]="best_fit_fallback"
        return incumbent,receipt
    nextstate=copy.deepcopy(state)
    rows=[]
    for i,load in enumerate(loads):
        t=next(t for t in candidate if (i,t) in assign and solver.Value(assign[i,t]))
        p=solver.Value(plant[i]);prev=nextstate[t]
        rows.append(_make_row(load,t,p,solver.Value(start[i]),prev["last"],matrix[prev["plant"]-1][p-1],cfg))
        nextstate[t]={"available":_ticks(rows[-1]["return_time"]),"plant":p,"last":load["load_id"],"active":True}
    active={t for t,s in state.items() if s["active"]}
    if _objective(rows,active,cfg)>_objective(incumbent,active,cfg)+1e-6:
        receipt["selected"]="best_fit_better"
        return incumbent,receipt
    receipt["selected"]="cp_sat"
    return rows,receipt


def _freeze(prior, now):
    rows=prior.get("loads",[]) if prior else []
    keep={r["load_id"] for r in rows if min(r["reposition_start"],r["bay_start"]) <= now+1e-9}
    # Freeze route predecessors and order prefixes too: preserving an underway trip
    # must not remove the earlier work on which its availability depends.
    changed=True
    while changed:
        before=len(keep)
        ordermax={}
        for r in rows:
            if r["load_id"] in keep:
                ordermax[r["order_id"]]=max(ordermax.get(r["order_id"],-1),r["load_index"])
                if r["previous_load_id"] is not None: keep.add(r["previous_load_id"])
        keep.update(r["load_id"] for r in rows if r["load_index"]<=ordermax.get(r["order_id"],-1))
        changed=len(keep)!=before
    return [copy.deepcopy(r) for r in rows if r["load_id"] in keep]


def solve(resources: dict, day: dict, *, mode: str="cold", config: DispatchConfig|None=None,
          now: float=0, prior_schedule: dict|None=None, scope: str="offline") -> dict:
    """Produce complete load/truck/plant times; raise rather than invent missing travel.

    nearest = nearest-plant, bay-aware best fit; ordinary/cold = same all-plant CP-SAT;
    retained/warm = same model with prior load assignment/time hints; ordinary can
    use identical prior hints for an equal-content control. In rolling scope,
    only release-visible orders are accepted and underway actions are immutable.
    """
    cfg=config or DispatchConfig()
    if mode not in ("nearest","ordinary","cold","retained","warm") or scope not in ("offline","rolling"):
        raise ValueError("unknown dispatch mode or planning scope")
    if scope=="rolling" and any(o["release_min"]>now+1e-9 for o in day["orders"]):
        raise InputDataError("rolling solve was given unreleased future orders")
    started=time.monotonic()
    plants,trucks,matrix,loads,excluded,missingmix=_prepare(resources,day,cfg)
    frozen=_freeze(prior_schedule,now) if scope=="rolling" else []
    known={l["load_id"]:l for l in loads}
    for r in frozen:
        if r["load_id"] not in known or any(r[k]!=known[r["load_id"]][k] for k in ("order_id","load_index","volume_m3","target_unload","release_min")):
            raise InputDataError("prior commitment does not match visible current input")
    fixed={r["load_id"] for r in frozen}
    pending=sorted((l for l in loads if l["load_id"] not in fixed),
                   key=lambda l: (l["target_unload"],str(l["order_id"]),l["load_index"]))
    state,bays,order_ready=_initial_state(trucks,plants,frozen)
    rows=list(frozen); receipts=[]; solver_available=True
    windows=max(1,math.ceil(len(pending)/cfg.window_size))
    for offset in range(0,len(pending),cfg.window_size):
        chunk=pending[offset:offset+cfg.window_size]
        incumbent=_greedy(chunk,plants,trucks,matrix,state,bays,order_ready,cfg,now,nearest=mode=="nearest")
        selected=incumbent
        if mode!="nearest" and cfg.time_limit_s>0:
            try:
                remaining=max(0,cfg.time_limit_s-(time.monotonic()-started))
                if remaining<=0:
                    receipts.append({"status":"BUDGET_EXHAUSTED","selected":"best_fit_fallback","scope":"restricted_window"})
                else:
                    selected,receipt=_cp_window(chunk,incumbent,plants,trucks,matrix,state,bays,order_ready,cfg,now,
                                             min(remaining,max(0.01,cfg.time_limit_s/windows)),
                                             prior_schedule.get("loads",[]) if prior_schedule and mode in ("ordinary","retained","warm") else [])
                    receipts.append(receipt)
            except ImportError:
                solver_available=False
                receipts.append({"status":"ORTOOLS_UNAVAILABLE","selected":"best_fit_fallback","scope":"restricted_window"})
        _apply(selected,state,bays,order_ready);rows.extend(selected)
    rows.sort(key=lambda r:(r["bay_start"],str(r["load_id"])))
    active={r["truck_id"] for r in rows}
    travel=sum(r["outbound_travel_min"]+r["return_travel_min"]+r["reposition_min"] for r in rows)
    lateness=sum(r["lateness_min"] for r in rows)
    maximum=max((r["lateness_min"] for r in rows),default=0)
    for r in rows:
        if r["load_id"] not in fixed:
            r["decision_time"] = now if scope=="rolling" else r["release_min"]
    duty_flags=[]
    for t in sorted(active):
        trips=sorted((r for r in rows if r["truck_id"]==t),key=lambda r:r["bay_start"])
        span=trips[-1]["return_time"]-trips[0]["reposition_start"]
        if span>720+1e-9:
            duty_flags.append({"truck_id":t,"reason":"duty_span_exceeds_declared_720_min_review_limit","minutes":span})
        for r in trips:
            continuous=r["return_time"]-r["reposition_start"]
            if continuous>240+1e-9:
                duty_flags.append({"truck_id":t,"load_id":r["load_id"],"reason":"continuous_block_exceeds_declared_240_min_review_limit","minutes":continuous})
    conventions={"profile_id":"fixed-durations-rest45-v1",
                 "clock":"minutes since operational midnight; 0.1 minute grid rounded upward",
                 "travel":"normalized truck minutes used once; return equals outbound by source symmetric assumption",
                 "bay":"one bay per operational plant; loading and plant cleaning occupy bay; driver prep after bay",
                 "driver":"all trucks available at home at minute0; after every trip reserve 15min break plus30min meal at return plant before next reposition; blocks>240min or span>720min require driver review; no legal compliance claim",
                 "dispatch":"just-in-time or late arrival; unloading starts immediately on arrival; one unloading operation per order",
                 "routing":"return to loading plant, then directed reposition to next loading plant",
                 "release":"reposition and production begin after order release; in rolling mode reposition begins no earlier than planning event",
                 "quality":"no concrete lifetime threshold invented; mix compatibility and material quality are not certified",
                 "plant_rates":"source units unspecified; fixed10min default loading used; source zero-rate plant excluded",
                 "search":"target-ordered windows; increasing task-order truck paths; finite candidate trucks; local bounds only",
                 "commitment":"rolling mode freezes started reposition/loading, route predecessors and order prefixes"}
    result={"schema_version":"production060-dispatch-v1","instance_id":day.get("id"),"mode":mode,
            "planning_scope":scope,"planning_min":now,"config":asdict(cfg),"conventions":conventions,
            "source_binding":make_source_binding(day,resources),
            "loads":rows,"trucks":[{"truck_id":t,"home_plant":trucks[t]["home_plant"],
                                       "capacity_m3":trucks[t]["capacity_m3"],
                                       "load_ids":[r["load_id"] for r in sorted(rows,key=lambda x:x["bay_start"]) if r["truck_id"]==t]}
                                      for t in sorted(active)],
            "objective":{"value":cfg.activation_weight*len(active)+cfg.travel_weight*travel+cfg.lateness_weight*lateness,
                         "activated_trucks":len(active),"travel_min":round(travel,8),"total_lateness_min":round(lateness,8),
                         "max_lateness_min":maximum,"late_loads":sum(r["lateness_min"]>1e-9 for r in rows),
                         "global_bound":None,"global_gap":None},
            "solver":{"name":"OR-Tools CP-SAT + best fit" if mode!="nearest" else "nearest-plant bay-aware best fit",
                      "available":solver_available,"wall_time_s":time.monotonic()-started,"windows":receipts,
                      "global_optimality_claim":False},
            "diagnostics":{"excluded_orders":excluded,"missing_mix_order_ids":missingmix,
                           "excluded_zero_rate_plants":[p["id"] for p in resources["plants"] if p.get("source_mean_loading_rate")==0],
                           "frozen_load_ids":sorted(fixed),"operating_end_min":max((r["return_time"] for r in rows),default=0),
                           "driver_review_flags":duty_flags,
                           "shift_break_feasibility":"requires_review" if duty_flags else "declared_rest_profile_satisfied_not_legal_certification",
                           "quality_feasibility":"unverified"}}
    return result


produce_schedule=solve


def rolling_schedule(resources: dict, day: dict, *, mode="retained", config=None) -> dict:
    """Replay actual release events; each planner invocation receives only visible rows."""
    cfg=config or DispatchConfig()
    started=time.monotonic()
    prior=None;events=[]
    releases=sorted({float(o["release_min"]) for o in day["orders"]})
    for release in releases:
        indices=[i for i,o in enumerate(day["orders"]) if o["release_min"]<=release]
        visible_orders=[day["orders"][i] for i in indices]
        visible_ids={o["id"] for o in visible_orders}
        # Do not pass full-day counts, quantities, instance specifications or other
        # aggregate metadata into the release-visible planner.
        visible={"id":day.get("id"),"orders":visible_orders,
                 "travel_minutes":[day["travel_minutes"][i] if i<len(day.get("travel_minutes",[])) else None for i in indices],
                 "travel_row_mapping_verified":day.get("travel_row_mapping_verified"),
                 "missing_travel_order_ids":[oid for oid in day.get("missing_travel_order_ids",[]) if oid in visible_ids]}
        remaining=max(0,cfg.time_limit_s-(time.monotonic()-started))
        eventcfg=replace(cfg,time_limit_s=remaining)
        nextplan=solve(resources,visible,mode=mode,config=eventcfg,now=release,prior_schedule=prior,scope="rolling")
        frozen=set(nextplan["diagnostics"]["frozen_load_ids"])
        committed=[r for r in nextplan["loads"] if r["load_id"] in frozen]
        events.append({"planning_min":release,"visible_order_ids":[o["id"] for o in visible["orders"]],
                       "committed_loads":committed,"previous_plan_sha256":_hash(prior) if prior else None,
                       "solver_budget_remaining_s":remaining,"wall_time_s":nextplan["solver"]["wall_time_s"],
                       "plan_sha256":_hash(nextplan)})
        prior=nextplan
    if prior is None:
        prior=solve(resources,day,mode=mode,config=cfg,scope="rolling")
    prior["config"]=asdict(cfg)
    # All requests are now released; bind the completed plan to the complete
    # public instance without showing its future metadata to earlier decisions.
    prior["source_binding"]=make_source_binding(day,resources)
    prior["solver"]["rolling_total_wall_time_s"]=time.monotonic()-started
    if events:
        events[-1]["plan_sha256"]=_hash(prior)
    prior["rolling_events"]=events
    return prior


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def make_source_binding(instance, resources):
    return {"instance_sha256":_hash(instance),"resources_sha256":_hash(resources),
            "instance_source_sha256":instance.get("source",{}).get("sha256"),
            "resource_source_sha256":{r["filename"]:r["sha256"] for r in resources.get("source_files",[])}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources",type=Path,required=True)
    parser.add_argument("--day",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--mode",choices=("nearest","ordinary","cold","retained","warm"),default="cold")
    parser.add_argument("--time-limit",type=float,default=10)
    parser.add_argument("--missing-travel",choices=("refuse","exclude"),default="refuse")
    parser.add_argument("--rolling",action="store_true")
    parser.add_argument("--prior",type=Path)
    args=parser.parse_args(argv)
    cfg=DispatchConfig(time_limit_s=args.time_limit,missing_travel=args.missing_travel)
    resources=json.loads(args.resources.read_text());day=json.loads(args.day.read_text())
    if args.rolling:
        result=rolling_schedule(resources,day,mode=args.mode,config=cfg)
    else:
        prior=json.loads(args.prior.read_text()) if args.prior else None
        result=solve(resources,day,mode=args.mode,config=cfg,prior_schedule=prior)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"output":str(args.output),"objective":result["objective"],"loads":len(result["loads"])}))


if __name__=="__main__":
    main()
