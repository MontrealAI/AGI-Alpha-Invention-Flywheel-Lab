from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from pathlib import Path

from portfolio071 import thermal
from portfolio071.verification import check_delivery, receipt


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def reference_request(task="heat_delivery"):
    n = 6
    continuity = task == "thermal_continuity"
    return {"schema": "portfolio071/thermal-request/v1", "task": task, "hours": n,
            "source_heat_kw": [150, 150, 0, 0, 150, 150] if continuity else [130] * n,
            "source_temp_c": 45.0, "sink_temp_c": 90.0, "heat_demand_kw": [80.0] * n,
            "electric_limit_kw": [70.0 if continuity else 40.0] * n, "approach_c": 5.0,
            "carnot_fraction": 0.45, "pump_capacity_kw": 180.0, "recovery_capacity_kw": 150.0,
            "storage_capacity_kwh": 220.0 if continuity else 0.0,
            "storage_charge_limit_kw": 100.0 if continuity else 0.0,
            "storage_discharge_limit_kw": 100.0 if continuity else 0.0,
            "storage_eta": 0.92, "storage_loss_per_hour": 0.003,
            "initial_storage_kwh": 0.0, "final_storage_min_kwh": 25.0 if continuity else 0.0}


def one_hour_max(request):
    source = min(request["source_heat_kw"][0], request["recovery_capacity_kw"])
    direct = request["source_temp_c"] >= request["sink_temp_c"] + request["approach_c"]
    denominator = request["sink_temp_c"] - request["source_temp_c"] + 2 * request["approach_c"]
    performance = request["carnot_fraction"] * (request["sink_temp_c"] + request["approach_c"] + 273.15) / denominator if denominator > 0 else 0
    if performance <= 1:
        return source if direct else 0.0
    hot = min(request["pump_capacity_kw"], performance * request["electric_limit_kw"][0], source * performance / (performance - 1))
    return source + hot / performance if direct else hot


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    producer_hash = hashlib.sha256(Path(thermal.__file__).read_bytes()).hexdigest()
    frozen = {"public_source_freeze": "cecbe47f408290fb7acf9a62521c5ed86a7743ae", "producer_sha256": producer_hash,
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "seed": 71130219,
              "scope": "Finite independently specified engineering cases, no measured physical qualification."}
    (output / "FREEZE.json").write_text(json.dumps(frozen, indent=2) + "\n")
    rows, examples = [], {}
    for label, task in (("k1", "heat_delivery"), ("k2", "thermal_continuity")):
        req = reference_request(task)
        artifact = thermal.construct(req)
        verdict = receipt(req, artifact)
        if not verdict["accepted"]:
            raise AssertionError((label, verdict))
        value = {"request": req, "artifact": artifact, "independent_receipt": verdict,
                 "scope": "One actual runnable design; no installed equipment or actual industrial production."}
        (output / (label + ".json")).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        examples[label] = value
        rows.append({"case": label, "expected": "feasible", "source_hash": hashed(req), "artifact_hash": hashed(artifact), "accepted": True})
    req = examples["k1"]["request"]
    factorial = []
    for recovery, pump in ((False, False), (True, False), (False, True), (True, True)):
        changed = copy.deepcopy(req)
        if not recovery:
            changed["recovery_capacity_kw"] = 0
        if not pump:
            changed["pump_capacity_kw"] = 0
        artifact = thermal.construct(changed)
        feasible = artifact["status"] == "feasible"
        expected = recovery and pump
        if feasible != expected or (feasible and not check_delivery(changed, artifact)["accepted"]):
            raise AssertionError("factorial disagreement")
        factorial.append({"recovery": recovery, "pump": pump, "feasible": feasible, "expected": expected})
    rng = random.Random(71130219)
    for index in range(32):
        req = reference_request()
        req["hours"] = 1
        req["source_temp_c"] = rng.uniform(15, 145)
        req["sink_temp_c"] = rng.uniform(60, 140)
        req["source_heat_kw"] = [rng.uniform(0, 180)]
        req["electric_limit_kw"] = [rng.uniform(0, 80)]
        req["carnot_fraction"] = rng.uniform(0.2, 0.6)
        req["pump_capacity_kw"] = rng.uniform(20, 220)
        req["recovery_capacity_kw"] = rng.uniform(20, 180)
        attainable = one_hour_max(req)
        wanted = attainable * (0.83 if index % 2 == 0 else 1.12) if attainable else 1.0
        req["heat_demand_kw"] = [wanted]
        expected = wanted <= attainable + 1e-9
        artifact = thermal.construct(req)
        feasible = artifact["status"] == "feasible"
        verified = check_delivery(req, artifact)["accepted"] if feasible else False
        rows.append({"case": "independent_one_hour_" + str(index), "request": req, "analytic_max_heat_kw": attainable,
                     "expected_feasible": expected, "returned_feasible": feasible, "independent_acceptance": verified})
        if feasible != expected or (feasible and not verified):
            raise AssertionError(rows[-1])
    k2 = examples["k2"]
    no_storage = copy.deepcopy(k2["request"])
    no_storage.update(storage_capacity_kwh=0.0, storage_charge_limit_kw=0.0, storage_discharge_limit_kw=0.0, final_storage_min_kwh=0.0)
    no_storage_result = thermal.construct(no_storage)
    if no_storage_result["status"] != "infeasible":
        raise AssertionError("outage with no storage accepted")
    mutation_results = []
    for mutation in ("free_heat", "free_electricity", "negative_inventory", "terminal_shortfall", "invented_initial_storage", "lost_hour"):
        altered = copy.deepcopy(k2["artifact"])
        if mutation == "free_heat":
            altered["delivered_kw"][3] += 10
        elif mutation == "free_electricity":
            altered["electric_kw"][0] = 0
        elif mutation == "negative_inventory":
            altered["storage_kwh"][3] = -5
        elif mutation == "terminal_shortfall":
            altered["storage_kwh"][-1] = 0
        elif mutation == "invented_initial_storage":
            altered["storage_kwh"][0] += 100
        else:
            altered["delivered_kw"].pop()
        verdict = check_delivery(k2["request"], altered)
        if verdict["accepted"]:
            raise AssertionError("corrupted design accepted: " + mutation)
        mutation_results.append({"case": mutation, "rejected": True, "reason": verdict["reason"]})
    malformed = []
    for field, value in (("storage_eta", 1.1), ("carnot_fraction", -1), ("source_temp_c", -274), ("storage_loss_per_hour", 1.1)):
        changed = copy.deepcopy(k2["request"]); changed[field] = value
        try:
            thermal.construct(changed)
            refused = False
        except (ValueError, TypeError):
            refused = True
        if not refused:
            raise AssertionError("invalid contract not refused")
        malformed.append({"field": field, "refused": refused})
    independent = thermal.construct(copy.deepcopy(k2["request"]))
    value_fields = ("direct_heat_kw", "pump_hot_kw", "electric_kw", "charge_kw", "discharge_kw", "storage_kwh", "delivered_kw")
    ordinary_equal = all(independent[name] == k2["artifact"][name] for name in value_fields)
    resistance = {label: thermal.resistance_baseline(value["request"]) for label, value in examples.items()}
    report = {"schema": "portfolio071/thermal-independent-evaluation/v1", "freeze": frozen,
              "k1_accepted": True, "k2_accepted": True, "factorial": factorial, "fresh_cases": rows,
              "no_inherited_storage_k2": {"status": no_storage_result["status"], "meaning": "Asset removal makes outage continuity infeasible; an unrestricted conventional engineer may build the same storage."},
              "tampering": mutation_results, "invalid_contracts": malformed, "resistance_control": resistance,
              "ordinary_reuse_and_fresh_complete_design_equal": ordinary_equal,
              "conventional_scope": "Same deterministic LP and construction permissions available to ordinary engineering; exact tie in returned physical dispatch.",
              "physical_qualification": False, "new_industry_or_discovery_advantage": False,
              "capital_and_economic_scope": "Technical output only. Equipment cost, sites, fabrication, qualification and customer adoption are absent from this model and must be separately modeled.",
              "limitations": ["Fixed-COP constant-temperature approximation", "One-hour discretization with no subhour control validation", "No measured engineering parameter fit", "Storage permits simultaneous charge and discharge; no complementarity or cycling-wear guarantee", "No piping/pressure/transient/hygiene or field equipment qualification", "Finite cases cannot certify arbitrary physical systems"]}
    (output / "RESULTS.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"k1_accepted": True, "k2_accepted": True, "one_hour_cases": 32, "tamper_rejections": len(mutation_results), "conventional_tie": ordinary_equal}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); run(args.output)
