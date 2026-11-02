from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


THERMAL_REQUEST = "portfolio071/thermal-request/v1"
THERMAL_ARTIFACT = "portfolio071/thermal-design/v1"


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("finite numeric value required: " + name)
    return float(value)


def _vector(value, size, name):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError("vector length mismatch: " + name)
    return [_number(v, name) for v in value]


def _thermal(request, artifact):
    if request.get("schema") != THERMAL_REQUEST or artifact.get("schema") != THERMAL_ARTIFACT:
        raise ValueError("unsupported scientific schema")
    if request.get("task") not in ("heat_delivery", "thermal_continuity"):
        raise ValueError("unsupported thermal purpose")
    n = request.get("hours")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("positive integral one-hour horizon required")
    if artifact.get("status") != "feasible":
        raise ValueError("refusal is not an accepted delivery")
    names = ("source_temp_c", "sink_temp_c", "approach_c", "carnot_fraction", "pump_capacity_kw",
             "recovery_capacity_kw", "storage_capacity_kwh", "storage_charge_limit_kw", "storage_discharge_limit_kw",
             "storage_eta", "storage_loss_per_hour", "initial_storage_kwh", "final_storage_min_kwh")
    p = {name: _number(request.get(name), name) for name in names}
    source, demand, limits = (_vector(request.get(name), n, name) for name in ("source_heat_kw", "heat_demand_kw", "electric_limit_kw"))
    if min(source + demand + limits) < 0:
        raise ValueError("negative resource or demand")
    if p["source_temp_c"] <= -273.15 or p["sink_temp_c"] <= -273.15 or p["approach_c"] <= 0:
        raise ValueError("invalid thermodynamic temperatures or approach")
    if not 0 < p["carnot_fraction"] <= 1 or not 0 < p["storage_eta"] <= 1 or not 0 <= p["storage_loss_per_hour"] < 1:
        raise ValueError("invalid efficiency or storage loss")
    nonnegative = ("pump_capacity_kw", "recovery_capacity_kw", "storage_capacity_kwh", "storage_charge_limit_kw",
                   "storage_discharge_limit_kw", "initial_storage_kwh", "final_storage_min_kwh")
    if any(p[name] < 0 for name in nonnegative):
        raise ValueError("negative equipment or storage state")
    if p["initial_storage_kwh"] > p["storage_capacity_kwh"] or p["final_storage_min_kwh"] > p["storage_capacity_kwh"]:
        raise ValueError("initial or terminal state exceeds installed storage")
    output_names = ("direct_heat_kw", "pump_hot_kw", "electric_kw", "charge_kw", "discharge_kw", "delivered_kw")
    flows = {name: _vector(artifact.get(name), n, name) for name in output_names}
    store = _vector(artifact.get("storage_kwh"), n + 1, "storage_kwh")
    scale = max([1.0] + source + demand + limits + [p[name] for name in nonnegative])
    # R1_R3_PREREGISTRATION: absolute 1e-6 plus relative 1e-8.
    # Initial 1e-7*scale implementation was corrected after source audit;
    # original evidence and the identical-case recheck are retained.
    tol = 1e-6 + 1e-8 * scale
    violations = {}

    def enforce(name, violation):
        violations[name] = max(violations.get(name, 0.0), float(violation), 0.0)

    denominator = p["sink_temp_c"] - p["source_temp_c"] + 2 * p["approach_c"]
    cop = p["carnot_fraction"] * (p["sink_temp_c"] + p["approach_c"] + 273.15) / denominator if denominator > 0 else None
    direct_allowed = p["source_temp_c"] >= p["sink_temp_c"] + p["approach_c"]
    enforce("initial_storage", abs(store[0] - p["initial_storage_kwh"]))
    enforce("terminal_storage", p["final_storage_min_kwh"] - store[-1])
    for s in store:
        enforce("nonnegative_storage", -s)
        enforce("storage_capacity", s - p["storage_capacity_kwh"])
    for t in range(n):
        direct, hot, watts, charge, discharge, delivered = (flows[name][t] for name in output_names)
        for name in output_names:
            enforce("nonnegative_" + name, -flows[name][t])
        enforce("electric_limit", watts - limits[t])
        enforce("pump_hot_capacity", hot - p["pump_capacity_kw"])
        enforce("nonnegative_cold_source", watts - hot)
        recovered = direct + hot - watts
        enforce("source_heat_available", recovered - source[t])
        enforce("recovery_equipment_capacity", recovered - p["recovery_capacity_kw"])
        enforce("charge_limit", charge - p["storage_charge_limit_kw"])
        enforce("discharge_limit", discharge - p["storage_discharge_limit_kw"])
        if not direct_allowed:
            enforce("direct_temperature_eligibility", direct)
        if cop is None or cop <= 1:
            enforce("pump_operating_envelope", hot)
            enforce("pump_operating_envelope_electric", watts)
        else:
            enforce("heat_pump_fixed_cop", abs(hot / cop - watts))
        enforce("heat_delivery_conservation", abs(delivered - (direct + hot - charge + discharge)))
        enforce("purpose_demand", demand[t] - delivered)
        expected_storage = store[t] * (1 - p["storage_loss_per_hour"]) + p["storage_eta"] * charge - discharge / p["storage_eta"]
        enforce("storage_energy_conservation", abs(store[t + 1] - expected_storage))
    accepted = all(v <= tol for v in violations.values())
    return {"accepted": accepted, "schema": "portfolio071/independent-scientific-verdict/v1",
            "purpose": request["task"], "hours": n, "checks": violations, "numeric_tolerance": tol,
            "computed_cop_upper_bound": cop, "direct_heat_eligible": direct_allowed,
            "max_violation": max(violations.values(), default=0),
            "reason": "Conservation and declared design envelope satisfied" if accepted else "Declared thermal purpose or physics constraint violated",
            "scope": "Independent arithmetic verification of a supplied one-hour engineering model, not measured plant validation.",
            "physical_qualification": False}


def check_delivery(request, artifact):
    try:
        if not isinstance(request, dict) or not isinstance(artifact, dict):
            raise ValueError("dictionary scientific request and artifact required")
        if request.get("schema") == THERMAL_REQUEST:
            return _thermal(request, artifact)
        raise ValueError("unsupported scientific contract")
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return {"accepted": False, "schema": "portfolio071/independent-scientific-verdict/v1",
                "reason": str(error), "scope": "Scientific contract rejected", "physical_qualification": False}


def identity():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def receipt(request, artifact):
    verdict = check_delivery(request, artifact)
    canonical = lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {**verdict, "request_sha256": hashlib.sha256(canonical(request)).hexdigest(),
            "artifact_sha256": hashlib.sha256(canonical(artifact)).hexdigest(), "verifier_sha256": identity()}
