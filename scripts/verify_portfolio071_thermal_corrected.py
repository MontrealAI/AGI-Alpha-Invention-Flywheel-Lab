"""Fresh, prospectively registered R3 confirmation after tolerance correction."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import re
import time

from portfolio071 import thermal
from portfolio071.verification import check_delivery, receipt

ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = ROOT / "experiments/portfolio_20261102/R3_CORRECTION_CONFIRMATION_PREREGISTRATION.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def blank_request(hours=1, task="heat_delivery"):
    return {"schema": "portfolio071/thermal-request/v1", "task": task, "hours": hours,
            "source_heat_kw": [0.0] * hours, "source_temp_c": 40.0, "sink_temp_c": 90.0,
            "heat_demand_kw": [0.0] * hours, "electric_limit_kw": [0.0] * hours,
            "approach_c": 5.0, "carnot_fraction": 0.45, "pump_capacity_kw": 0.0,
            "recovery_capacity_kw": 0.0, "storage_capacity_kwh": 0.0,
            "storage_charge_limit_kw": 0.0, "storage_discharge_limit_kw": 0.0,
            "storage_eta": 0.9, "storage_loss_per_hour": 0.0,
            "initial_storage_kwh": 0.0, "final_storage_min_kwh": 0.0}


def analytic_maximum(request):
    available = min(request["source_heat_kw"][0], request["recovery_capacity_kw"])
    eligible = request["source_temp_c"] >= request["sink_temp_c"] + request["approach_c"]
    lift = request["sink_temp_c"] - request["source_temp_c"] + 2 * request["approach_c"]
    cop = request["carnot_fraction"] * (request["sink_temp_c"] + request["approach_c"] + 273.15) / lift if lift > 0 else 0
    if cop <= 1:
        return available if eligible else 0.0
    pumped = min(request["pump_capacity_kw"], cop * request["electric_limit_kw"][0], available * cop / (cop - 1))
    return available + pumped / cop if eligible else pumped


def storage_fixture(rng, index):
    request = blank_request(8, "thermal_continuity")
    request.update(source_temp_c=rng.uniform(30, 60), sink_temp_c=rng.uniform(80, 110),
                   approach_c=rng.uniform(5, 8), carnot_fraction=rng.uniform(0.35, 0.55),
                   storage_eta=rng.uniform(0.8, 0.97), storage_loss_per_hour=rng.uniform(0, 0.02))
    d, eta, keep = rng.uniform(12, 65), request["storage_eta"], 1 - request["storage_loss_per_hour"]
    outage_length = 1 + index % 2
    outage = set(range(3, 3 + outage_length))
    final = d * rng.uniform(0.3, 0.8)
    after_outage = d / eta * 0.25
    before_outage = after_outage
    for _ in range(outage_length):
        before_outage = (before_outage + d / eta) / keep
    early_charge = before_outage / (eta * (1 + keep + keep**2))
    remaining = 8 - 3 - outage_length
    late_charge = max(0.0, (final - after_outage * keep**remaining) /
                      (eta * sum(keep**i for i in range(remaining))))
    charge = [early_charge if t < 3 else (0.0 if t in outage else late_charge) for t in range(8)]
    discharge = [d if t in outage else 0.0 for t in range(8)]
    hot = [0.0 if t in outage else d + charge[t] for t in range(8)]
    cop = request["carnot_fraction"] * (request["sink_temp_c"] + request["approach_c"] + 273.15) / (request["sink_temp_c"] - request["source_temp_c"] + 2 * request["approach_c"])
    electric = [h / cop for h in hot]
    cold = [h - w for h, w in zip(hot, electric)]
    storage = [0.0]
    for c, q in zip(charge, discharge):
        storage.append(storage[-1] * keep + eta * c - q / eta)
    # This independently constructed witness exists before calling the producer.
    # It uses no optimizer and includes complete terminal restoration.
    request.update(source_heat_kw=[1.1 * c for c in cold], heat_demand_kw=[d] * 8,
                   electric_limit_kw=[1.1 * w for w in electric], pump_capacity_kw=1.1 * max(hot),
                   recovery_capacity_kw=1.1 * max(cold), storage_capacity_kwh=1.1 * max(storage),
                   storage_charge_limit_kw=1.1 * max(charge), storage_discharge_limit_kw=1.1 * d,
                   final_storage_min_kwh=final)
    witness = {"schema": "portfolio071/thermal-design/v1", "status": "feasible",
               "direct_heat_kw": [0.0] * 8, "pump_hot_kw": hot, "electric_kw": electric,
               "charge_kw": charge, "discharge_kw": discharge, "storage_kwh": storage,
               "delivered_kw": [d] * 8}
    return request, witness


def run(output, registration_commit):
    if not re.fullmatch("[0-9a-f]{40}", registration_commit):
        raise ValueError("Public preregistration commit identity required")
    registration = json.loads(REGISTRATION.read_text())
    for path, expected in registration["bound_sources"].items():
        if sha(ROOT / path) != expected:
            raise ValueError("Registered source changed: " + path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cpu, wall = time.process_time(), time.monotonic()
    rng = random.Random(registration["seed"])
    cases, controls, failures = [], [], []
    for index in range(32):
        req = blank_request()
        scale = 10 ** rng.uniform(-1, 3)
        req.update(source_temp_c=rng.uniform(-30, 165), sink_temp_c=rng.uniform(30, 155),
                   approach_c=rng.uniform(2, 9), carnot_fraction=rng.uniform(0.25, 0.65),
                   source_heat_kw=[rng.uniform(0, 200) * scale],
                   electric_limit_kw=[rng.uniform(0, 70) * scale],
                   pump_capacity_kw=rng.uniform(20, 260) * scale,
                   recovery_capacity_kw=rng.uniform(0, 220) * scale)
        maximum = analytic_maximum(req)
        feasible = index % 2 == 0
        req["heat_demand_kw"] = [0.82 * maximum if feasible else 1.18 * maximum + 0.05 * scale]
        artifact = thermal.construct(req)
        verdict = receipt(req, artifact)
        passed = (artifact["status"] == "feasible") == feasible and (verdict["accepted"] if feasible else not verdict["accepted"])
        row = {"case": f"analytic-{index:02d}", "request": req, "analytic_maximum_heat_kw": maximum,
               "expected_feasible": feasible, "artifact": artifact, "independent_receipt": verdict,
               "matched_registered_expectation": passed}
        cases.append(row)
        if not passed:
            failures.append(row["case"])
    for index in range(8):
        req, witness = storage_fixture(rng, index)
        witness_before_producer = canonical_hash(witness)
        witness_verdict = check_delivery(req, witness)
        artifact = thermal.construct(req)
        verdict = receipt(req, artifact)
        passed = witness_verdict["accepted"] and verdict["accepted"]
        row = {"case": f"storage-{index:02d}", "request": req, "independent_constructive_witness": witness,
               "witness_sha256_before_producer": witness_before_producer, "independent_witness_verdict": witness_verdict,
               "artifact": artifact, "independent_receipt": verdict, "matched_registered_expectation": passed}
        cases.append(row)
        if not passed:
            failures.append(row["case"])
            continue
        no_storage = copy.deepcopy(req)
        no_storage.update(storage_capacity_kwh=0.0, storage_charge_limit_kw=0.0,
                          storage_discharge_limit_kw=0.0, final_storage_min_kwh=0.0)
        removed = thermal.construct(no_storage)
        ok = removed["status"] == "infeasible"
        controls.append({"case": f"no-storage-{index:02d}", "matched_expectation": ok,
                         "artifact": removed, "reason": "Positive outage demand, zero source/electricity and no stored energy."})
        if not ok:
            failures.append(controls[-1]["case"])
        altered = copy.deepcopy(artifact)
        altered["storage_kwh"][-1] = req["final_storage_min_kwh"] - req["heat_demand_kw"][0] / 10
        changed = check_delivery(req, altered)
        controls.append({"case": f"terminal-obligation-{index:02d}", "matched_expectation": not changed["accepted"], "verdict": changed})
        if changed["accepted"]:
            failures.append(controls[-1]["case"])
        # Derive the registered tolerance independently from request units.
        scalar = ("pump_capacity_kw", "recovery_capacity_kw", "storage_capacity_kwh", "storage_charge_limit_kw",
                  "storage_discharge_limit_kw", "initial_storage_kwh", "final_storage_min_kwh")
        scale = max([1.0] + req["source_heat_kw"] + req["heat_demand_kw"] + req["electric_limit_kw"] + [req[k] for k in scalar])
        tolerance, old_tolerance = 1e-6 + 1e-8 * scale, 1e-7 * scale
        for label, delta, expected in (("within", tolerance / 4, True),
                                       ("between-old-and-registered", (tolerance + old_tolerance) / 2, False),
                                       ("above", tolerance * 2, False)):
            tampered = copy.deepcopy(artifact)
            tampered["delivered_kw"][0] += delta
            changed = check_delivery(req, tampered)
            ok = changed["accepted"] is expected and changed.get("numeric_tolerance") == tolerance
            controls.append({"case": f"threshold-{label}-{index:02d}", "injected_heat_residual": delta,
                             "independent_registered_tolerance": tolerance, "expected_accepted": expected,
                             "matched_expectation": ok, "verdict": changed})
            if not ok:
                failures.append(controls[-1]["case"])
    report = {"schema": "portfolio071/fresh-corrected-thermal-confirmation/v1",
              "stage": "FRESH_PROSPECTIVELY_REGISTERED_POST_CORRECTION_COMPUTATIONAL_CONFIRMATION",
              "registration_commit": registration_commit, "registration_sha256": sha(REGISTRATION),
              "bound_sources": registration["bound_sources"], "seed": registration["seed"],
              "primary_cases_registered": 40, "primary_cases_completed": len(cases),
              "primary_cases_matching_expectation": sum(r["matched_registered_expectation"] for r in cases),
              "controls_registered": 40, "controls_completed": len(controls),
              "controls_matching_expectation": sum(r["matched_expectation"] for r in controls),
              "accepted": not failures and len(cases) == 40 and len(controls) == 40,
              "failures": failures, "cases": cases, "controls": controls,
              "resource_use": {"process_cpu_seconds": time.process_time() - cpu,
                               "wall_seconds": time.monotonic() - wall, "incremental_purchase_usd": 0},
              "limits": ["Fresh inputs validate only the unchanged supplied thermal model and corrected numerical acceptance implementation.",
                         "No physical plant qualification, new industry, superior algorithm or real commerce is established.",
                         "Original erroneous-tolerance evidence and disclosed same-case recheck remain separately retained; no superseded score is relabeled as blind.",
                         "This supplement does not modify or refinance any financial account or replace its already accepted artifact."]}
    (output / "RESULTS.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("accepted", "primary_cases_completed", "primary_cases_matching_expectation", "controls_completed", "controls_matching_expectation", "failures")}, sort_keys=True))
    if not report["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registration-commit", required=True)
    args = parser.parse_args()
    run(args.output, args.registration_commit)
