from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import random
import time
from pathlib import Path

import numpy as np

from portfolio071 import foundry


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def step(matrix, vector):
    return [sum(matrix[i][j] * vector[j] for j in range(len(vector))) for i in range(len(vector))]


def treatment_reference(matrix, sources, protected, horizon, fractions):
    exposures, total_removed, mass_error = [], [], 0.0
    for source in sources:
        mass = [float(i == source) for i in range(len(matrix))]
        removed, decay, exposure = 0.0, 0.0, 0.0
        for _ in range(horizon):
            lost = [mass[i] * fractions[i] for i in range(len(matrix))]
            removed += sum(lost)
            surviving = [mass[i] - lost[i] for i in range(len(matrix))]
            next_mass = step(matrix, surviving)
            decay += sum(surviving) - sum(next_mass)
            mass = next_mass
            exposure += sum(mass[i] for i in protected)
            mass_error = max(mass_error, abs(sum(mass) + removed + decay - 1))
        exposures.append(exposure); total_removed.append(removed)
    return {"maximum_exposure": max(exposures), "per_source_exposure": exposures,
            "maximum_removed_mass": max(total_removed), "max_mass_error": mass_error}


def best_treatment(matrix, task):
    n = len(matrix)
    allowed = [task["removal_choices"] if i in task["eligible_nodes"] else (0.0,) for i in range(n)]
    best, count = None, 0
    for fractions in itertools.product(*allowed):
        count += 1
        result = treatment_reference(matrix, task["source_nodes"], task["protected_nodes"], task["horizon"], fractions)
        if result["maximum_exposure"] > task["exposure_limit"] + 1e-9:
            continue
        installation = sum(task["installation_costs"][i] for i in range(n) if fractions[i] > 0)
        operation = task["horizon"] * sum(task["operating_costs"][i] * fractions[i] for i in range(n))
        cost = installation + operation + task["disposal_cost"] * result["maximum_removed_mass"]
        key = cost, sum(f > 0 for f in fractions), fractions
        if best is None or key < best[0]:
            best = key, result
    return {"accepted": best is not None, "cost_units": best[0][0] if best else None,
            "fractions": list(best[0][2]) if best else None, "candidate_count": count}


def best_sensors(matrix, sources, horizon, costs, minimum):
    n = len(matrix)
    signatures = []
    for source in sources:
        mass = [float(i == source) for i in range(n)]
        history = []
        for _ in range(horizon):
            mass = step(matrix, mass)
            history.append(mass)
        signatures.append(history)
    best = None
    for size in range(n + 1):
        for selected in itertools.combinations(range(n), size):
            separation = min((max((abs(signatures[a][t][i] - signatures[b][t][i])
                                   for t in range(horizon) for i in selected), default=0.0)
                              for a in range(len(sources)) for b in range(a + 1, len(sources))), default=float("inf"))
            if separation < minimum:
                continue
            key = sum(costs[i] for i in selected), len(selected), selected
            if best is None or key < best[0]:
                best = key, separation
    return {"accepted": best is not None, "cost_units": best[0][0] if best else None,
            "sensor_nodes": list(best[0][2]) if best else [], "separation": best[1] if best else None}


def oracle_for(matrix, log):
    def oracle(vector):
        x = [float(v) for v in vector]
        if len(x) != len(matrix) or any(v < 0 for v in x):
            raise ValueError("Declared observation input violated")
        y = step(matrix, x)
        log.append({"x": x, "y": y})
        return y
    return oracle


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.perf_counter(), time.process_time()
    rng = random.Random(71151123)
    rows = []
    for index in range(32):
        n = 3 + index % 4
        matrix = [[0.0] * n for _ in range(n)]
        for j in range(n):
            weights = [rng.uniform(0.01, 1.0) for _ in range(n)]
            mass = rng.uniform(0.55, 0.98)
            for i in range(n):
                matrix[i][j] = mass * weights[i] / sum(weights)
        queries = []
        instrument = foundry.identify(oracle_for(matrix, queries), n)
        error = float(np.max(np.abs(np.asarray(instrument["transition"]) - matrix)))
        if error > 1e-8 or len(queries) != n + 3:
            raise AssertionError("Acquisition disagreement")
        sensor_task = {"source_nodes": list(range(n)), "horizon": 3,
                       "sensor_costs": [rng.randint(1, 9) for _ in range(n)], "min_separation": 0.02}
        sensors = foundry.choose_sensors(instrument, **sensor_task)
        ref_sensors = best_sensors(matrix, sensor_task["source_nodes"], 3, sensor_task["sensor_costs"], 0.02)
        if sensors["accepted"] != ref_sensors["accepted"] or (sensors["accepted"] and sensors["cost_units"] != ref_sensors["cost_units"]):
            raise AssertionError("Sensor search does not match independent enumeration")
        frozen_k1 = digest({"instrument": instrument, "sensor_task": sensor_task, "sensor_design": sensors})
        task = {"source_nodes": list(range(n)), "protected_nodes": sorted(rng.sample(range(n), 1 + index % 2)),
                "horizon": rng.randint(4, 8), "exposure_limit": rng.uniform(0.06, 0.25),
                "installation_costs": [float(rng.randint(1, 15)) for _ in range(n)],
                "operating_costs": [rng.choice((0.1, 0.2, 0.4)) for _ in range(n)],
                "eligible_nodes": list(range(n)) if index % 4 else list(range(1, n)),
                "disposal_cost": 0.5, "removal_choices": (0.0, 0.5, 1.0)}
        design = foundry.design_mitigation(instrument, **task)
        ref = best_treatment(matrix, task)
        if design["accepted"] != ref["accepted"] or (design["accepted"] and abs(design["cost_units"] - ref["cost_units"]) > 1e-8):
            raise AssertionError("Mitigation optimum disagrees with independent enumeration")
        replay = treatment_reference(matrix, task["source_nodes"], task["protected_nodes"], task["horizon"], design["fractions"]) if design["accepted"] else None
        if replay and (replay["maximum_exposure"] > task["exposure_limit"] + 1e-8 or replay["max_mass_error"] > 1e-8):
            raise AssertionError("Fresh successor violates declared purpose")
        ordinary = foundry.design_mitigation(copy.deepcopy(instrument), **task)
        cold_queries = []
        cold = foundry.identify(oracle_for(matrix, cold_queries), n)
        fresh = foundry.design_mitigation(cold, **task)
        equivalent = all(x["accepted"] == design["accepted"] and x["cost_units"] == design["cost_units"] and x["fractions"] == design["fractions"] for x in (ordinary, fresh))
        if not equivalent:
            raise AssertionError("Equal-content or fresh control unexpectedly differs")
        rows.append({"system": index, "dimension": n, "hidden_model_sha256": digest(matrix), "matrix_revealed_after_construction": matrix,
            "k1": {"instrument_sha256": digest(instrument), "frozen_before_k2_request_sha256": frozen_k1,
                   "matrix_max_error": error, "query_count": len(queries), "query_receipt_sha256": instrument["query_receipt_sha256"],
                   "sensor_task": sensor_task, "sensor_design": sensors, "independent_reference": ref_sensors},
            "k2": {"request": task, "design": design, "independent_reference": ref, "true_system_replay": replay},
            "controls": {"ordinary_reuse_ties": equivalent, "fresh_reconstruction_ties": equivalent,
                         "cold_additional_queries": len(cold_queries), "retained_additional_queries": 0,
                         "strong_conventional_enumeration_ties": True}})
    negative = []
    zero = [[0.0] * 3 for _ in range(3)]
    identity = [[0.7 * float(i == j) for j in range(3)] for i in range(3)]
    negative.append({"case": "passive_zero_alias", "same_observation": step(zero, [0, 0, 0]) == step(identity, [0, 0, 0]),
                     "different_intervention": step(zero, [1, 0, 0]) != step(identity, [1, 0, 0]), "point_identification_from_zero_only": False})
    alias = [[0.3, 0.3, 0.3], [0.2, 0.2, 0.2], [0.1, 0.1, 0.1]]
    alias_model = foundry.identify(oracle_for(alias, []), 3)
    ambiguity = foundry.choose_sensors(alias_model, [0, 1, 2], 3, [1, 1, 1], 0.02)
    if ambiguity["accepted"]:
        raise AssertionError("Unidentifiable source alias accepted")
    negative.append({"case": "identical_source_columns", "accepted": ambiguity["accepted"]})
    zero_model = foundry.identify(oracle_for(zero, []), 3)
    zero_outcome = foundry.evaluate_treatment(zero_model, [0, 1, 2], [1], 5, [0, 0, 0])
    negative.append({"case": "complete_decay", "exposure": zero_outcome["maximum_exposure"], "mass_error": zero_outcome["max_mass_balance_error"]})
    for name, oracle in (("affine_offset", lambda x: np.asarray(x) * .5 + .001),
                         ("nonlinear_response", lambda x: np.asarray(x) ** 2 * .5),
                         ("negative_mass", lambda x: -np.asarray(x) * .5),
                         ("unaccounted_mass_creation", lambda x: np.asarray(x) * 1.1),
                         ("nonfinite_response", lambda x: [float("nan")] * 3),
                         ("unsupported_noise", lambda x: np.asarray(x) * .5 + np.array([.0001, -.0001, .0001]))):
        try:
            foundry.identify(oracle, 3)
            refused = False
        except foundry.QualificationError:
            refused = True
        if not refused:
            raise AssertionError("Out-of-envelope observation not refused: " + name)
        negative.append({"case": name, "refused": True})
    imodel = foundry.identify(oracle_for(identity, []), 3)
    impossible = foundry.design_mitigation(imodel, [0, 1, 2], [0, 1, 2], 4, 0.0, [1, 1, 1], [0, 0, 0], removal_choices=(0.0, 0.5))
    if impossible["accepted"]:
        raise AssertionError("Insufficient removal falsely accepted")
    negative.append({"case": "insufficient_treatment_catalogue", "accepted": False})
    old_matrix = [[.8, 0, 0], [0, .8, 0], [0, 0, .8]]
    old_model = foundry.identify(oracle_for(old_matrix, []), 3)
    old_design = foundry.design_mitigation(old_model, [0], [1], 4, .01, [1, 1, 1], [0, 0, 0])
    shifted = [[0, 0, 0], [.8, .8, 0], [0, 0, .8]]
    shifted_replay = treatment_reference(shifted, [0], [1], 4, old_design["fractions"])
    expanded_replay = treatment_reference(old_matrix, [0], [0, 1], 4, old_design["fractions"])
    if shifted_replay["maximum_exposure"] <= .01 or expanded_replay["maximum_exposure"] <= .01:
        raise AssertionError("Scope-invalidating negative control was not discriminating")
    negative.extend([{"case": "changed_dynamics", "old_plan_exposure_in_changed_true_system": shifted_replay["maximum_exposure"],
                      "required_maximum": .01, "rejected_by_independent_replay": True, "automatic_unknown_drift_detection_claim": False},
                     {"case": "expanded_protected_purpose", "old_plan_exposure": expanded_replay["maximum_exposure"],
                      "required_maximum": .01, "old_purpose_certificate_invalid": True}])
    result = {"schema": "portfolio071/foundry-independent-evaluation/v1", "source_freeze": "fcc8ec9ae63f3bb1362698ae55884ad0f9384e49",
              "constructor_sha256": hashlib.sha256(Path(foundry.__file__).read_bytes()).hexdigest(),
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "seed": 71151123,
              "systems_registered": 32, "systems_completed": len(rows), "systems": rows, "negative_controls": negative,
              "counts": {"identified": len(rows), "sensor_tasks_accepted": sum(r["k1"]["sensor_design"]["accepted"] for r in rows),
                         "mitigation_tasks_accepted": sum(r["k2"]["design"]["accepted"] for r in rows),
                         "joint_sequences_accepted": sum(r["k1"]["sensor_design"]["accepted"] and r["k2"]["design"]["accepted"] for r in rows),
                         "negative_controls": len(negative), "cold_reacquisition_queries": sum(r["controls"]["cold_additional_queries"] for r in rows)},
              "verdict": {"computational_instruments_constructed": True, "independent_finite_optima_checked": True,
                          "retained_acquisition_saved": True, "equal_content_ordinary_reuse_ties": True,
                          "improved_discovery_procedure": False, "physical_validation": False, "new_industry_qualification": False,
                          "commercial_profit_established_by_this_scientific_run": False},
              "independence": "Separate verifier chose fixtures after constructor freeze; prediction oracle only exposes requested response vectors. Shared filesystem provides procedural separation, not OS-enforced adversarial secrecy.",
              "limitations": ["Supplied time-invariant linear class; finite probes cannot prove unknown physical law", "Synthetic source and treatment units are not field metrology", "Raw kernel inheritance saves content acquisition; conventional procedure ties", "No mass is deleted without decay/removal account"],
              "resource_use": {"cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - started,
                               "paid_model_calls": 0, "actual_incremental_purchase_usd": 0, "agent_inference_cost": None}}
    (output / "RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"counts": result["counts"], "verdict": result["verdict"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); run(args.output)
