"""Independent ready-mix dispatch acceptance.

This module deliberately has no dependency on the schedule constructor.  It
reconstructs required loads and every resource timeline from public inputs.
Acceptance means feasibility within the declared benchmark model, never a
physical concrete-quality, driving-law, or site-safety certification.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA = "production060-acceptance-v1"
EPS = 1e-6


def canonical_sha256(value: Any) -> str:
    """Hash normalized JSON values, independently of file whitespace."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_binding(instance: dict, resources: dict) -> dict:
    return {
        "instance_sha256": canonical_sha256(instance),
        "resources_sha256": canonical_sha256(resources),
        "instance_source_sha256": instance.get("source", {}).get("sha256"),
        "resource_source_sha256": {
            s["filename"]: s["sha256"] for s in resources.get("source_files", [])
        },
    }


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean quantity")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid decimal quantity") from exc
    if not result.is_finite():
        raise ValueError("nonfinite quantity")
    return result


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected numeric minute")
    if not math.isfinite(value):
        raise ValueError("nonfinite numeric minute")
    return float(value)


def _same(left: Any, right: Any) -> bool:
    try:
        return abs(_number(left) - _number(right)) <= EPS
    except ValueError:
        return False


def _required_loads(instance: dict, resources: dict) -> list[dict]:
    """Decimal arithmetic prevents dropping fractional terminal deliveries."""
    default = _decimal(resources["parameters"]["DefaultQuantityPerTrip"])
    if default <= 0:
        raise ValueError("default quantity must be positive")
    loads = []
    for order in instance["orders"]:
        remainder = _decimal(order["volume_m3"])
        client_size = order.get("default_load_m3")
        size = _decimal(client_size) if client_size is not None else Decimal(0)
        if size <= 0:
            size = default
        if remainder <= 0:
            raise ValueError("order quantity must be positive")
        i = 0
        while remainder > 0:
            amount = min(size, remainder)
            loads.append({"load_id": f"{order['id']}:{i}",
                          "order_id": order["id"], "load_index": i,
                          "volume_m3": amount,
                          "target_unload": _grid(order["requested_min"]) +
                          i * _grid(order["interval_min"])})
            remainder -= amount
            i += 1
    return loads


# This profile is owned by the checker.  Neither an artifact nor a caller may
# relax it by replacing the durations, quantity rules, weights, or conventions.
OPERATING_CONFIG = {
    "loading_min": 10, "plant_cleaning_min": 10,
    "driver_preparation_min": 15, "unloading_min": 10,
    "site_cleaning_min": 15, "driver_break_min": 15, "driver_meal_min": 30,
    "default_load_m3": 7.5, "activation_weight": 120,
    "travel_weight": 1, "lateness_weight": 10, "missing_travel": "refuse",
}
CONVENTIONS = {
    "profile_id": "fixed-durations-rest45-v1",
    "clock": "minutes since operational midnight; 0.1 minute grid rounded upward",
    "travel": "normalized truck minutes used once; return equals outbound by source symmetric assumption",
    "bay": "one bay per operational plant; loading and plant cleaning occupy bay; driver prep after bay",
    "driver": "all trucks available at home at minute0; after every trip reserve 15min break plus30min meal at return plant before next reposition; blocks>240min or span>720min require driver review; no legal compliance claim",
    "dispatch": "just-in-time or late arrival; unloading starts immediately on arrival; one unloading operation per order",
    "routing": "return to loading plant, then directed reposition to next loading plant",
    "release": "reposition and production begin after order release; in rolling mode reposition begins no earlier than planning event",
    "quality": "no concrete lifetime threshold invented; mix compatibility and material quality are not certified",
    "plant_rates": "source units unspecified; fixed10min default loading used; source zero-rate plant excluded",
    "search": "target-ordered windows; increasing task-order truck paths; finite candidate trucks; local bounds only",
    "commitment": "rolling mode freezes started reposition/loading, route predecessors and order prefixes",
}
MODES = {"nearest", "ordinary", "cold", "retained", "warm"}


def _grid(value: Any) -> float:
    # Source binary floating point around exact tenths must not add a second tick.
    return math.ceil(_number(value) * 10 - 1e-7) / 10


def make_contract(instance: dict, resources: dict, *, mode: str = "cold",
                  planning_scope: str = "offline", config: dict | None = None) -> dict:
    """Freeze request metadata before construction; optional config freezes search too.

    Computational search budgets may vary.  Physical and objective conventions
    always remain the checker-owned profile above.
    """
    if mode not in MODES or planning_scope not in {"offline", "rolling"}:
        raise ValueError("unknown requested dispatch mode or scope")
    if config is not None:
        for key, value in OPERATING_CONFIG.items():
            if config.get(key) != value:
                raise ValueError(f"unsupported operating convention: {key}")
    return {
        "schema_version": SCHEMA,
        "instance_id": instance.get("id"),
        "mode": mode,
        "planning_scope": planning_scope,
        "source_binding": source_binding(instance, resources),
        "conventions": dict(CONVENTIONS),
        "operating_config": dict(OPERATING_CONFIG),
        "search_config": dict(config) if config is not None else None,
    }


def verify(instance: dict, resources: dict, artifact: dict, contract: dict) -> dict:
    """Return a fail-closed feasibility receipt, without invoking the producer.

    The caller must provide its frozen request contract, rather than recover one
    from the delivered artifact.  Timing tolerance is 1e-6 minutes; volumes are
    compared exactly as Decimal values.  Driver review flags are obligations to
    disclose, not a claim that an invented review limit is a driving law.
    """
    errors: list[str] = []
    kpis: dict = {}

    def require(condition, message):
        if not condition:
            errors.append(message)

    def eq(actual, expected, message):
        require(_same(actual, expected), message)

    try:
        if not all(isinstance(v, dict) for v in (instance, resources, artifact, contract)):
            raise ValueError("instance, resources, artifact and contract must be objects")
        expected_contract = make_contract(instance, resources,
                                         mode=contract.get("mode"),
                                         planning_scope=contract.get("planning_scope"),
                                         config=contract.get("search_config"))
        require(contract == expected_contract, "request contract does not match frozen checker profile or input hashes")
        require(artifact.get("schema_version") == "production060-dispatch-v1", "artifact schema mismatch")
        for key in ("instance_id", "mode", "planning_scope", "source_binding", "conventions"):
            require(artifact.get(key) == expected_contract[key], f"artifact {key} mismatch")
        cfg = artifact.get("config", {})
        require(isinstance(cfg, dict), "config must be an object")
        for key, value in OPERATING_CONFIG.items():
            require(cfg.get(key) == value, f"operating convention mismatch: {key}")
        if contract.get("search_config") is not None:
            require(cfg == contract["search_config"], "search config differs from frozen request")
        for key in ("window_size", "candidate_trucks"):
            require(isinstance(cfg.get(key), int) and not isinstance(cfg.get(key), bool)
                    and cfg[key] > 0, f"invalid search config: {key}")
        require(_number(cfg.get("time_limit_s")) >= 0, "invalid solver time limit")
        require(isinstance(cfg.get("random_seed"), int) and not isinstance(cfg.get("random_seed"), bool), "invalid random seed")
        require(instance.get("schema_version") == "cdp060-normalized-v1" and
                resources.get("schema_version") == "cdp060-normalized-v1", "normalized input schema mismatch")
        binding = source_binding(instance, resources)
        hashes = [binding["instance_source_sha256"], *binding["resource_source_sha256"].values()]
        require(bool(binding["resource_source_sha256"]), "resource source hashes missing")
        require(all(isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
                    for v in hashes), "raw source hashes missing or malformed")
        require(instance.get("travel_row_mapping_verified") is True, "order travel row mapping is unverified")
        require(not instance.get("missing_travel_order_ids"), "missing source order travel; full request refused")
        require(instance.get("operating_data_complete") is True, "incomplete operational input; full request refused")
        eq(instance.get("travel_minutes_multiplier_applied"), 1.4, "instance travel conversion provenance mismatch")
        eq(resources.get("travel_minutes_multiplier_applied"), 1.4, "plant travel conversion provenance mismatch")
        source_parameters = {
            "DefaultQuantityPerTrip": 7.5, "DefaultLoadingTime": 10,
            "DefaultPlantCleaningTime": 10, "DefaultUnloadingTime": 10,
            "CleaningTimeAtTheDefaultSite": 15, "DriversPreparationTime": 15,
            "DriverBreakTime": 15, "DriverMealTime": 30,
            "GoogleTravelTimeMultiplier": 1.4,
        }
        for key, value in source_parameters.items():
            eq(resources["parameters"].get(key), value, f"source parameter is outside fixed profile: {key}")
        plants = {p["id"]: p for p in resources["plants"]}
        trucks = {t["id"]: t for t in resources["trucks"]}
        orders = {o["id"]: o for o in instance["orders"]}
        require(len(plants) == len(resources["plants"]), "duplicate plant ID")
        require(len(trucks) == len(resources["trucks"]), "duplicate truck ID")
        require(len(orders) == len(instance["orders"]), "duplicate order ID")
        require(list(plants) == list(range(1, len(plants) + 1)), "invalid source plant pseudo-ID mapping")
        require(bool(trucks) and bool(plants), "empty fleet or plants")
        for tid, truck in trucks.items():
            require(_decimal(truck["capacity_m3"]) > 0, f"truck {tid}: invalid capacity")
            require(truck["home_plant"] in plants, f"truck {tid}: unknown home plant")
        for pid, plant in plants.items():
            require(plant.get("loading_decks") == 1, f"plant {pid}: unsupported loading dock count")
        input_total = sum((_decimal(o["volume_m3"]) for o in instance["orders"]), Decimal(0))
        if "n_orders" in instance:
            require(instance["n_orders"] == len(orders), "normalized order-count metadata mismatch")
        if "total_quantity_m3" in instance:
            require(_decimal(instance["total_quantity_m3"]) == input_total, "normalized quantity metadata mismatch")
        if "dynamic_order_count" in instance:
            require(instance["dynamic_order_count"] == sum(o["release_min"] > 0 for o in instance["orders"]),
                    "normalized dynamic-order count mismatch")
        if "missing_mix_order_ids" in instance:
            require(instance["missing_mix_order_ids"] == [o["id"] for o in instance["orders"] if not o.get("mix_id")],
                    "normalized missing-mix metadata mismatch")
        for oid, order in orders.items():
            for key in ("release_min", "requested_min", "interval_min"):
                require(_number(order[key]) >= 0, f"order {oid}: invalid {key}")
        travel = instance["travel_minutes"]
        matrix = resources["plant_travel_minutes"]
        require(len(travel) == len(orders), "order travel row count mismatch")
        for name, matrix_value, row_count in (("order", travel, len(orders)), ("plant", matrix, len(plants))):
            require(len(matrix_value) == row_count, f"{name} travel row count mismatch")
            for row in matrix_value:
                require(isinstance(row, list) and len(row) == len(plants), f"{name} travel column count mismatch")
                require(all(_number(v) >= 0 for v in row), f"{name} travel missing or invalid")
        # Invalid input must stop here; indexing a malformed matrix would obscure
        # the substantive refusal behind an accidental Python exception.
        if errors:
            return {"accepted": False, "errors": errors, "kpis": kpis}
        required = {r["load_id"]: r for r in _required_loads(instance, resources)}
        rows = artifact.get("loads")
        require(isinstance(rows, list), "loads must be a list")
        if not isinstance(rows, list):
            return {"accepted": False, "errors": errors, "kpis": kpis}
        require(all(isinstance(row, dict) for row in rows), "each load must be an object")
        if not all(isinstance(row, dict) for row in rows):
            return {"accepted": False, "errors": errors, "kpis": kpis}
        actual_ids = [r.get("load_id") for r in rows]
        require(all(isinstance(x, str) for x in actual_ids), "invalid load ID type")
        require(len(actual_ids) == len(set(actual_ids)), "duplicate load IDs")
        require(set(actual_ids) == set(required), "missing or extra required loads")
        by_id = {r["load_id"]: r for r in rows}
        by_plant, by_truck, by_order = defaultdict(list), defaultdict(list), defaultdict(list)
        order_rows = {o["id"]: i for i, o in enumerate(instance["orders"])}
        timing = ("bay_start", "bay_end", "loading_start", "loading_end", "dispatch_time",
                  "site_arrival", "unload_start", "unload_end", "site_clear", "return_time",
                  "reposition_start", "reposition_end", "decision_time", "target_unload",
                  "lateness_min", "outbound_travel_min", "return_travel_min", "reposition_min")
        total_travel = total_late = max_late = 0.0
        delivered = Decimal(0)
        late_count = 0
        for r in rows:
            lid = r.get("load_id")
            if lid not in required:
                continue
            need = required[lid]
            oid, tid, pid = r.get("order_id"), r.get("truck_id"), r.get("plant_id")
            require(all(isinstance(v, int) and not isinstance(v, bool) for v in (oid, tid, pid, r.get("load_index"))), f"{lid}: identifiers must be integers")
            require(oid == need["order_id"] and r.get("load_index") == need["load_index"], f"{lid}: wrong order or load index")
            require(tid in trucks and pid in plants, f"{lid}: unknown truck or plant")
            if tid not in trucks or pid not in plants or oid not in orders:
                continue
            order = orders[oid]
            require(plants[pid].get("source_mean_loading_rate") != 0, f"{lid}: disabled zero-rate plant")
            amount = _decimal(r.get("volume_m3"))
            require(amount == need["volume_m3"], f"{lid}: load volume mismatch")
            require(amount <= _decimal(trucks[tid]["capacity_m3"]), f"{lid}: truck capacity exceeded")
            delivered += amount
            for key in timing:
                require(_number(r.get(key)) >= 0, f"{lid}: negative {key}")
                if key != "decision_time":
                    eq(r[key], _grid(r[key]), f"{lid}: {key} is outside declared tenth-minute grid")
            out = _grid(travel[order_rows[oid]][pid - 1])
            eq(r["release_min"], order["release_min"], f"{lid}: release metadata mismatch")
            eq(r["target_unload"], need["target_unload"], f"{lid}: target unload mismatch")
            require(r["decision_time"] + EPS >= order["release_min"], f"{lid}: hidden future decision before release")
            require(r["reposition_start"] + EPS >= r["decision_time"], f"{lid}: reposition precedes decision")
            require(r["bay_start"] + EPS >= order["release_min"], f"{lid}: production before release")
            eq(r["loading_start"], r["bay_start"], f"{lid}: loading/bay start mismatch")
            eq(r["loading_end"], r["bay_start"] + 10, f"{lid}: loading duration mismatch")
            eq(r["bay_end"], r["bay_start"] + 20, f"{lid}: plant cleaning or bay duration mismatch")
            eq(r["dispatch_time"], r["bay_end"] + 15, f"{lid}: preparation duration mismatch")
            eq(r["site_arrival"], r["dispatch_time"] + out, f"{lid}: outbound travel mismatch")
            eq(r["unload_start"], r["site_arrival"], f"{lid}: declared immediate unload mismatch")
            require(r["unload_start"] + EPS >= need["target_unload"], f"{lid}: unloading before target")
            eq(r["unload_end"], r["unload_start"] + 10, f"{lid}: unload duration mismatch")
            eq(r["site_clear"], r["unload_end"] + 15, f"{lid}: site cleaning duration mismatch")
            eq(r["return_time"], r["site_clear"] + out, f"{lid}: return travel mismatch or teleport")
            eq(r["outbound_travel_min"], out, f"{lid}: outbound travel metadata mismatch")
            eq(r["return_travel_min"], out, f"{lid}: return travel metadata mismatch")
            late = max(0, r["unload_start"] - need["target_unload"])
            eq(r["lateness_min"], late, f"{lid}: lateness metadata mismatch")
            require(r.get("mix_id") == order.get("mix_id"), f"{lid}: mix identifier mismatch")
            require(r.get("client_id") == order.get("client_id"), f"{lid}: client identifier mismatch")
            require(r.get("quality_status") == "logistics_only_mix_not_certified", f"{lid}: unsupported quality certification")
            total_travel += 2 * out
            total_late += late
            max_late = max(max_late, late)
            late_count += late > EPS
            by_plant[pid].append(r)
            by_truck[tid].append(r)
            by_order[oid].append(r)
        for pid, plant_rows in by_plant.items():
            ordered = sorted(plant_rows, key=lambda r: (r["bay_start"], r["load_id"]))
            for left, right in zip(ordered, ordered[1:]):
                require(right["bay_start"] + EPS >= left["bay_end"], f"plant {pid}: loading bay overlap {left['load_id']}/{right['load_id']}")
        for oid, order_loads in by_order.items():
            ordered = sorted(order_loads, key=lambda r: r["load_index"])
            for left, right in zip(ordered, ordered[1:]):
                require(right["unload_start"] + EPS >= left["unload_end"], f"order {oid}: unloading overlap or delivery sequence violation")
        review_flags = []
        truck_summaries = []
        rest_fields = ("driver_break_start", "driver_break_end", "driver_meal_start", "driver_meal_end")
        for tid in sorted(by_truck):
            ordered = sorted(by_truck[tid], key=lambda r: (r["bay_start"], r["load_id"]))
            prev = None
            for r in ordered:
                lid = r["load_id"]
                origin = prev["plant_id"] if prev else trucks[tid]["home_plant"]
                reposition = _grid(matrix[origin - 1][r["plant_id"] - 1])
                eq(r["reposition_min"], reposition, f"{lid}: directed reposition metadata mismatch")
                eq(r["reposition_end"], r["bay_start"], f"{lid}: reposition must end at loading bay")
                eq(r["reposition_start"] + reposition, r["reposition_end"], f"{lid}: directed reposition duration mismatch")
                require(r.get("previous_load_id") == (prev["load_id"] if prev else None), f"{lid}: truck predecessor discontinuity")
                if prev:
                    for key in rest_fields:
                        require(_number(r.get(key)) >= 0, f"{lid}: missing or negative driver rest")
                    require(r["driver_break_start"] + EPS >= prev["return_time"], f"{lid}: truck reuse before return")
                    eq(r["driver_break_end"], r["driver_break_start"] + 15, f"{lid}: driver break duration mismatch")
                    eq(r["driver_meal_start"], r["driver_break_end"], f"{lid}: driver break/meal discontinuity")
                    eq(r["driver_meal_end"], r["driver_meal_start"] + 30, f"{lid}: driver meal duration mismatch")
                    eq(r["driver_meal_end"], r["reposition_start"], f"{lid}: rest must precede reposition")
                else:
                    require(all(r.get(key) is None for key in rest_fields), f"{lid}: first trip has invented prior rest")
                    require(r["reposition_start"] >= -EPS, f"{lid}: truck departs home before availability")
                total_travel += reposition
                prev = r
            span = ordered[-1]["return_time"] - ordered[0]["reposition_start"]
            if span > 720 + EPS:
                review_flags.append({"truck_id": tid, "reason": "duty_span_exceeds_declared_720_min_review_limit", "minutes": span})
            for r in ordered:
                block = r["return_time"] - r["reposition_start"]
                if block > 240 + EPS:
                    review_flags.append({"truck_id": tid, "load_id": r["load_id"], "reason": "continuous_block_exceeds_declared_240_min_review_limit", "minutes": block})
            truck_summaries.append({"truck_id": tid, "home_plant": trucks[tid]["home_plant"],
                                    "capacity_m3": trucks[tid]["capacity_m3"], "load_ids": [r["load_id"] for r in ordered]})
        require(artifact.get("trucks") == truck_summaries, "truck summary differs from independently reconstructed routes or capacities")
        expected_volume = sum((_decimal(o["volume_m3"]) for o in instance["orders"]), Decimal(0))
        require(delivered == expected_volume, "total delivered quantity mismatch")
        objective = {
            "value": 120 * len(by_truck) + total_travel + 10 * total_late,
            "activated_trucks": len(by_truck), "travel_min": total_travel,
            "total_lateness_min": total_late, "max_lateness_min": max_late,
            "late_loads": late_count,
        }
        claimed = artifact.get("objective", {})
        for key, value in objective.items():
            eq(claimed.get(key), value, f"false objective component: {key}")
        require(claimed.get("global_bound", "missing") is None and claimed.get("global_gap", "missing") is None,
                "restricted search cannot claim a global bound or gap")
        solver = artifact.get("solver", {})
        require(solver.get("global_optimality_claim") is False, "unsupported global optimality claim")
        require(isinstance(solver.get("windows"), list), "solver window receipts missing")
        require(_number(solver.get("wall_time_s")) >= 0, "invalid solver elapsed time")
        for window in solver.get("windows", []):
            require(window.get("scope") == "restricted_window", "solver bound has unsupported scope")
            for key in ("objective_bound", "solver_objective", "incumbent_objective"):
                if window.get(key) is not None:
                    _number(window[key])
            if window.get("solver_objective") is not None and window.get("objective_bound") is not None:
                require(window["objective_bound"] <= window["solver_objective"] + EPS, "solver local lower bound exceeds incumbent")
        diag = artifact.get("diagnostics", {})
        require(diag.get("excluded_orders") == [], "full request cannot exclude orders")
        missing_mix = [o["id"] for o in instance["orders"] if not o.get("mix_id")]
        require(diag.get("missing_mix_order_ids") == missing_mix, "missing mix identifiers were not disclosed")
        require(diag.get("excluded_zero_rate_plants") == [p for p in plants if plants[p].get("source_mean_loading_rate") == 0], "zero-rate plant disclosure mismatch")
        require(diag.get("quality_feasibility") == "unverified", "unsupported material quality feasibility claim")
        require(diag.get("driver_review_flags") == review_flags, "driver review flags do not match actual duty timelines")
        driver_status = "requires_review" if review_flags else "declared_rest_profile_satisfied_not_legal_certification"
        require(diag.get("shift_break_feasibility") == driver_status, "unsupported driver feasibility claim")
        operating_end = max((r["return_time"] for r in rows), default=0)
        eq(diag.get("operating_end_min"), operating_end, "operating horizon mismatch")
        frozen = diag.get("frozen_load_ids")
        require(isinstance(frozen, list) and len(frozen) == len(set(frozen)) and set(frozen) <= set(required), "invalid commitment load IDs")
        planning_min = _number(artifact.get("planning_min"))
        require(planning_min >= 0, "negative planning time")
        if contract["planning_scope"] == "offline":
            require(frozen == [], "offline plan claims rolling commitments")
            for r in rows:
                eq(r["decision_time"], orders[r["order_id"]]["release_min"], f"{r['load_id']}: offline decision metadata mismatch")
        else:
            _verify_rolling(instance, artifact, by_id, require, eq)
        kpis = {**objective, "load_count": len(rows), "order_count": len(orders),
                "delivered_m3": str(delivered), "operating_end_min": operating_end,
                "missing_mix_order_ids": missing_mix, "driver_review_flags": review_flags,
                "physical_quality_certified": False, "driver_legal_compliance_certified": False,
                "scope": "benchmark_dispatch_planning"}
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, InvalidOperation, OverflowError) as exc:
        errors.append(f"malformed or unsupported schedule/input: {type(exc).__name__}: {exc}")
    return {"accepted": not errors, "errors": errors, "kpis": kpis}


def _verify_rolling(instance, artifact, final_rows, require, eq):
    events = artifact.get("rolling_events")
    require(isinstance(events, list) and bool(events), "rolling release-event evidence missing")
    if not isinstance(events, list):
        return
    releases = sorted({float(o["release_min"]) for o in instance["orders"]})
    require(len(events) == len(releases), "rolling release-event count mismatch")
    previous_hash = None
    for event, release in zip(events, releases):
        eq(event.get("planning_min"), release, "rolling event time mismatch")
        visible = [o["id"] for o in instance["orders"] if o["release_min"] <= release]
        require(event.get("visible_order_ids") == visible, "hidden future order in rolling information set")
        require(event.get("previous_plan_sha256", "missing") == previous_hash,
                "rolling previous-plan hash chain mismatch")
        plan_hash = event.get("plan_sha256")
        require(isinstance(plan_hash, str) and len(plan_hash) == 64 and
                all(c in "0123456789abcdef" for c in plan_hash), "rolling plan hash missing or malformed")
        previous_hash = plan_hash
        committed = event.get("committed_loads")
        require(isinstance(committed, list), "rolling committed-load evidence missing")
        if not isinstance(committed, list):
            continue
        committed_ids = [r.get("load_id") for r in committed]
        require(len(committed_ids) == len(set(committed_ids)), "duplicate rolling commitments")
        for row in committed:
            lid = row.get("load_id")
            require(lid in final_rows and final_rows[lid] == row, f"{lid}: rolling commitment changed")
            require(row.get("order_id") in visible, f"{lid}: unreleased order committed")
            require(row.get("decision_time", math.inf) <= release + EPS,
                    f"{lid}: rolling commitment predates its decision")
            predecessor = row.get("previous_load_id")
            require(predecessor is None or predecessor in committed_ids,
                    f"{lid}: rolling commitment omits truck predecessor")
            for earlier in final_rows.values():
                if earlier["order_id"] == row.get("order_id") and earlier["load_index"] < row.get("load_index"):
                    require(earlier["load_id"] in committed_ids, f"{lid}: rolling commitment omits order prefix")
    eq(artifact.get("planning_min"), releases[-1] if releases else 0, "final rolling event mismatch")
    if events:
        final_plan = {key: value for key, value in artifact.items() if key != "rolling_events"}
        require(events[-1].get("plan_sha256") == canonical_sha256(final_plan),
                "final rolling plan hash mismatch")
        committed_ids = sorted(row["load_id"] for row in events[-1].get("committed_loads", []))
        require(artifact["diagnostics"].get("frozen_load_ids") == committed_ids,
                "final rolling frozen-load metadata mismatch")
    for row in final_rows.values():
        require(any(_same(row["decision_time"], r) for r in releases), f"{row['load_id']}: decision outside release events")
