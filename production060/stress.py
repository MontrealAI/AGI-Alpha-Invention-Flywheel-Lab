"""Travel adversary and observed-before-execution dispatch recourse.

The adversary changes actual travel, never quantities, targets, objective weights
or the fixed acceptance profile. Fixed delivered times are checked directly
against the changed physical leg durations. A separate delay-only replay preserves
all truck/plant choices and bay/route/order precedences. Optional existing-policy
replanning observes the changed matrices at minute0, before any work starts, then
uses the existing dispatcher. Rolling replans reveal orders only at release;
offline replans know all orders. This is explicitly pre-execution recourse; it does not claim to repair a vehicle already in transit.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
import time

from .acceptance import canonical_sha256, make_contract, source_binding, verify

SHOCK_INCREASES = (0.10, 0.25, 0.50)
EPS = 1e-6


def _ticks(value):
    return math.ceil(float(value) * 10 - 1e-7)


def _minutes(value):
    return value / 10


def shocked_inputs(instance, resources, increase):
    """Declare an additional travel shock; never reapply the car/truck conversion."""
    if isinstance(increase, bool) or not isinstance(increase, (int, float)) or not math.isfinite(increase) or increase < 0:
        raise ValueError("travel increase must be finite and nonnegative")
    day, fleet = copy.deepcopy(instance), copy.deepcopy(resources)
    factor = 1 + increase
    for value, key in ((day, "travel_minutes"), (fleet, "plant_travel_minutes")):
        matrix = value[key]
        for row in matrix:
            for i, minutes in enumerate(row):
                if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or minutes < 0:
                    raise ValueError("travel stress refuses missing or invalid travel")
                row[i] = _minutes(_ticks(minutes * factor))
    declaration = {"kind": "uniform_actual_travel_increase", "increase": increase,
                   "observed_min": 0, "clock": "ceil to0.1min after applying additional factor once",
                   "observation_basis": "authored adversarial condition, not measured traffic",
                   "base_instance_sha256": canonical_sha256(instance),
                   "base_resources_sha256": canonical_sha256(resources)}
    day["stress_scenario"] = copy.deepcopy(declaration)
    fleet["stress_scenario"] = copy.deepcopy(declaration)
    return day, fleet


def fixed_timing_violations(instance, resources, schedule):
    """Independent physical tests; hashes/objective metadata cannot create a pass.

    These constraints test the delivered timestamps without moving any action.
    Actual arrival/return lower bounds are reported separately from a feasible
    propagated replay, since an infeasible fixed plan has no realized objective.
    """
    orders = {o["id"]: i for i, o in enumerate(instance["orders"])}
    trucks = {t["id"]: t for t in resources["trucks"]}
    by_truck = defaultdict(list)
    violations, lower_bounds = [], []

    def check(lid, constraint, scheduled, required):
        if scheduled + EPS < required:
            violations.append({"load_id": lid, "constraint": constraint,
                               "scheduled_min": scheduled, "required_min": required,
                               "shortfall_min": round(required - scheduled, 8)})

    for row in schedule["loads"]:
        out = _minutes(_ticks(instance["travel_minutes"][orders[row["order_id"]]][row["plant_id"] - 1]))
        arrival = row["dispatch_time"] + out
        # If the claimed unloading already precedes arrival, this is only a lower
        # bound. The delay replay below resolves all site/route/bay dependencies.
        unload = max(arrival, row["unload_start"])
        actual_return = unload + 25 + out
        check(row["load_id"], "outbound_arrival", row["site_arrival"], arrival)
        check(row["load_id"], "unload_before_actual_arrival", row["unload_start"], arrival)
        check(row["load_id"], "return_before_actual_return", row["return_time"], actual_return)
        lower_bounds.append({"load_id": row["load_id"], "arrival_min": arrival,
                             "return_min": actual_return,
                             "lateness_min": max(0, unload - row["target_unload"])})
        by_truck[row["truck_id"]].append((row, actual_return))
    for tid, trips in by_truck.items():
        previous, previous_return = None, 0
        for row, actual_return in sorted(trips, key=lambda v: (v[0]["bay_start"], v[0]["load_id"])):
            origin = previous["plant_id"] if previous else trucks[tid]["home_plant"]
            reposition = _minutes(_ticks(resources["plant_travel_minutes"][origin - 1][row["plant_id"] - 1]))
            check(row["load_id"], "reposition_arrival", row["reposition_end"], row["reposition_start"] + reposition)
            if previous:
                check(row["load_id"], "driver_rest_after_actual_return", row["driver_break_start"], previous_return)
                check(row["load_id"], "truck_available_for_next_loading", row["bay_start"], previous_return + 45 + reposition)
            previous, previous_return = row, actual_return
    return {"physical_feasible": not violations, "violations": violations,
            "violations_by_constraint": {key: sum(v["constraint"] == key for v in violations)
                                         for key in sorted({v["constraint"] for v in violations})},
            "affected_loads": len({v["load_id"] for v in violations}),
            "arrival_return_lower_bounds": lower_bounds,
            "infeasible_plan_has_realized_objective": False}


def delay_fixed_assignments(instance, resources, nominal):
    """Delay starts to resolve changed travel while preserving all route choices.

    Difference constraints preserve the original bay order, truck order and
    delivery sequence. Longest-path relaxation either produces feasible times or
    explicitly reports an incompatible positive precedence cycle. No slack,
    volume, target, bay count or operating duration is changed.
    """
    started = time.monotonic()
    result = copy.deepcopy(nominal)
    rows = result["loads"]
    by_id = {r["load_id"]: r for r in rows}
    orders = {o["id"]: o for o in instance["orders"]}
    order_index = {o["id"]: i for i, o in enumerate(instance["orders"])}
    trucks = {t["id"]: t for t in resources["trucks"]}
    out, rep, previous = {}, {}, {}
    groups = {name: defaultdict(list) for name in ("truck", "plant", "order")}
    for row in rows:
        groups["truck"][row["truck_id"]].append(row)
        groups["plant"][row["plant_id"]].append(row)
        groups["order"][row["order_id"]].append(row)
        out[row["load_id"]] = _ticks(instance["travel_minutes"][order_index[row["order_id"]]][row["plant_id"] - 1])
    edges = []
    for tid, trips in groups["truck"].items():
        prev = None
        for row in sorted(trips, key=lambda r: (r["bay_start"], r["load_id"])):
            lid = row["load_id"]
            origin = prev["plant_id"] if prev else trucks[tid]["home_plant"]
            rep[lid] = _ticks(resources["plant_travel_minutes"][origin - 1][row["plant_id"] - 1])
            previous[lid] = prev["load_id"] if prev else None
            if prev:
                edges.append((prev["load_id"], lid, 1050 + 2 * out[prev["load_id"]] + rep[lid]))
            prev = row
    for group, orderkey, edge_weight in ((groups["plant"], lambda r: (r["bay_start"], r["load_id"]),
                                         lambda left, right: 200),
                                        (groups["order"], lambda r: r["load_index"],
                                         lambda left, right: 100 + out[left["load_id"]] - out[right["load_id"]])):
        for trips in group.values():
            ordered = sorted(trips, key=orderkey)
            edges.extend((left["load_id"], right["load_id"], edge_weight(left, right))
                         for left, right in zip(ordered, ordered[1:]))
    starts = {r["load_id"]: max(_ticks(r["bay_start"]), _ticks(orders[r["order_id"]]["release_min"]) + rep[r["load_id"]],
                                      _ticks(r["target_unload"]) - 350 - out[r["load_id"]]) for r in rows}
    for iteration in range(len(rows) + 1):
        changed = False
        for left, right, weight in edges:
            lower = starts[left] + weight
            if starts[right] < lower:
                starts[right] = lower
                changed = True
        if not changed:
            break
    else:
        return {"accepted": False, "reason": "preserved_precedence_positive_cycle", "schedule": None}
    for row in rows:
        lid, start = row["load_id"], starts[row["load_id"]]
        unload, reposition = start + 350 + out[lid], rep[lid]
        row.update({"loading_start": _minutes(start), "loading_end": _minutes(start + 100),
                    "bay_start": _minutes(start), "bay_end": _minutes(start + 200),
                    "dispatch_time": _minutes(start + 350), "site_arrival": _minutes(unload),
                    "unload_start": _minutes(unload), "unload_end": _minutes(unload + 100),
                    "site_clear": _minutes(unload + 250), "return_time": _minutes(unload + 250 + out[lid]),
                    "outbound_travel_min": _minutes(out[lid]), "return_travel_min": _minutes(out[lid]),
                    "reposition_min": _minutes(reposition), "reposition_start": _minutes(start - reposition),
                    "reposition_end": _minutes(start), "previous_load_id": previous[lid],
                    "driver_break_start": _minutes(start-reposition-450) if previous[lid] else None,
                    "driver_break_end": _minutes(start-reposition-300) if previous[lid] else None,
                    "driver_meal_start": _minutes(start-reposition-300) if previous[lid] else None,
                    "driver_meal_end": _minutes(start-reposition) if previous[lid] else None,
                    "decision_time": orders[row["order_id"]]["release_min"],
                    "lateness_min": _minutes(max(0, unload - _ticks(row["target_unload"])))})
    rows.sort(key=lambda r: (r["bay_start"], r["load_id"]))
    travel = sum(2 * out[r["load_id"]] + rep[r["load_id"]] for r in rows) / 10
    lateness = sum(r["lateness_min"] for r in rows)
    result["planning_scope"], result["planning_min"] = "offline", 0
    result.pop("rolling_events", None)
    result["source_binding"] = source_binding(instance, resources)
    result["objective"] = {"value": 120*len(groups["truck"])+travel+10*lateness,
                           "activated_trucks": len(groups["truck"]), "travel_min": travel,
                           "total_lateness_min": lateness, "max_lateness_min": max((r["lateness_min"] for r in rows), default=0),
                           "late_loads": sum(r["lateness_min"] > EPS for r in rows), "global_bound": None, "global_gap": None}
    result["solver"] = {"name": "fixed-assignments precedence delay replay", "available": False,
                        "wall_time_s": time.monotonic()-started, "windows": [], "global_optimality_claim": False}
    result["trucks"] = [{"truck_id": tid, "home_plant": trucks[tid]["home_plant"],
                         "capacity_m3": trucks[tid]["capacity_m3"],
                         "load_ids": [r["load_id"] for r in rows if r["truck_id"] == tid]}
                        for tid in sorted(groups["truck"])]
    flags = []
    for tid in sorted(groups["truck"]):
        trips = [r for r in rows if r["truck_id"] == tid]
        span = trips[-1]["return_time"] - trips[0]["reposition_start"]
        if span > 720+EPS:
            flags.append({"truck_id": tid, "reason": "duty_span_exceeds_declared_720_min_review_limit", "minutes": span})
        for row in trips:
            block = row["return_time"] - row["reposition_start"]
            if block > 240+EPS:
                flags.append({"truck_id": tid, "load_id": row["load_id"],
                              "reason": "continuous_block_exceeds_declared_240_min_review_limit", "minutes": block})
    result["diagnostics"].update(frozen_load_ids=[], driver_review_flags=flags,
                                 operating_end_min=max((r["return_time"] for r in rows), default=0),
                                 shift_break_feasibility="requires_review" if flags else "declared_rest_profile_satisfied_not_legal_certification")
    receipt = verify(instance, resources, result, make_contract(instance, resources, mode=result["mode"],
                                                             planning_scope="offline", config=result["config"]))
    return {"accepted": receipt["accepted"], "receipt": receipt, "schedule": result,
            "scope": "offline_factual_delay_replay_of_preserved_assignments"}


def run_scenario(instance, resources, nominal, contract, increase, *, replan=True):
    """Run one preregistered shock; fixed-plan failures remain failures."""
    scenario_wall, scenario_cpu = time.monotonic(), time.process_time()
    nominal_receipt = verify(instance, resources, nominal, contract)
    if not nominal_receipt["accepted"]:
        raise ValueError("nominal artifact was not accepted: " + "; ".join(nominal_receipt["errors"]))
    day, fleet = shocked_inputs(instance, resources, increase)
    fixed = fixed_timing_violations(day, fleet, nominal)
    delayed = delay_fixed_assignments(day, fleet, nominal)
    report = {"schema": "production060/travel-stress/v1", "instance_id": instance["id"],
              "nominal_artifact_sha256": canonical_sha256(nominal),
              "nominal_contract_sha256": canonical_sha256(contract),
              "scenario": day["stress_scenario"], "nominal_kpis": nominal_receipt["kpis"],
              "fixed_plan": fixed, "delay_replay": {k: v for k, v in delayed.items() if k != "schedule"},
              "replan": None,
              "unchanged_constraints": ["quantities", "targets", "objective_weights", "operating_durations", "fleet", "bay_count"],
              "scope": "benchmark_logistics_preexecution_travel_observation; no_midtrip_or_physical_safety_claim"}
    if replan:
        # Import only for actual production; the physical replay above is independent.
        from .dispatch import DispatchConfig, rolling_schedule, solve
        cfg = DispatchConfig(**nominal["config"])
        started = time.monotonic()
        if nominal["planning_scope"] == "rolling":
            repaired = rolling_schedule(fleet, day, mode=nominal["mode"], config=cfg)
        else:
            repaired = solve(fleet, day, mode=nominal["mode"], config=cfg)
        receipt = verify(day, fleet, repaired,
                         make_contract(day, fleet, mode=nominal["mode"], planning_scope=nominal["planning_scope"], config=nominal["config"]))
        information = ("before_first_action; rolling releases remain hidden until observed"
                       if nominal["planning_scope"] == "rolling" else
                       "before_first_action; offline all-orders-known planning")
        report["replan"] = {"observed_min": 0, "scope": information,
                            "receipt": receipt, "wall_time_s": time.monotonic()-started,
                            "artifact_sha256": canonical_sha256(repaired),
                            "physical_replay": fixed_timing_violations(day, fleet, repaired)}
    report["telemetry"] = {"wall_time_s": time.monotonic()-scenario_wall,
                           "process_cpu_s": time.process_time()-scenario_cpu,
                           "external_model_billing": None}
    return report


def main(argv=None):
    suite_wall, suite_cpu = time.monotonic(), time.process_time()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--day", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-replan", action="store_true")
    args = parser.parse_args(argv)
    resources, day, nominal, contract = (json.loads(p.read_text()) for p in
                                          (args.resources, args.day, args.schedule, args.contract))
    results = [run_scenario(day, resources, nominal, contract, increase, replan=not args.no_replan)
               for increase in SHOCK_INCREASES]
    report = {"schema": "production060/travel-stress-suite/v1", "results": results,
              "telemetry": {"wall_time_s": time.monotonic()-suite_wall,
                            "process_cpu_s": time.process_time()-suite_cpu,
                            "external_model_billing": None},
              "source_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in ("stress.py", "acceptance.py", "dispatch.py")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"output": str(args.output), "scenarios": len(results),
                      "fixed_plan_feasible": sum(r["fixed_plan"]["physical_feasible"] for r in results),
                      "delay_replay_accepted": sum(r["delay_replay"]["accepted"] for r in results),
                      "replan_accepted": sum(bool(r["replan"] and r["replan"]["receipt"]["accepted"]) for r in results)}))


if __name__ == "__main__":
    main()
