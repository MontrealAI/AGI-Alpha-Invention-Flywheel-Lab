from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np


TOL = 1e-6


def vertices(B, b, equality=None):
    B, b = np.asarray(B, dtype=float), np.asarray(b, dtype=float)
    n = B.shape[1]
    E, e = (np.empty((0, n)), np.empty(0)) if equality is None else equality
    E, e = np.asarray(E, dtype=float), np.asarray(e, dtype=float)
    result = []
    for active in itertools.combinations(range(len(B)), n - len(E)):
        M = np.vstack((E, B[list(active)]))
        rhs = np.concatenate((e, b[list(active)]))
        if np.linalg.matrix_rank(M, tol=1e-10) < n:
            continue
        x = np.linalg.solve(M, rhs)
        if (B @ x <= b + 1e-8).all() and (not len(E) or np.max(np.abs(E @ x - e)) <= 1e-8):
            if not any(np.max(np.abs(x - old)) < 1e-8 for old in result):
                result.append(x)
    return result


def observation_polytope(request):
    A = np.asarray(request["A"], dtype=float)
    y = np.asarray(request["observed"], dtype=float)
    error = np.asarray(request["measurement_error"], dtype=float)
    bounds = np.asarray(request["concentration_bounds"], dtype=float)
    I = np.eye(len(bounds))
    return np.vstack((A, -A, I, -I)), np.concatenate((y + error, -y + error, bounds[:, 1], -bounds[:, 0]))


def reference_certificate(request):
    B, b = observation_polytope(request)
    candidates = vertices(B, b)
    if not candidates:
        return {"decision": "inconsistent", "intervals": [], "vertex_count": 0}
    q = np.asarray(request["queries"], dtype=float)
    values = np.asarray(candidates) @ q.T
    intervals = np.column_stack((values.min(axis=0), values.max(axis=0)))
    limits = np.asarray(request["limits"])
    decision = ("safe" if (intervals[:, 1] <= limits + 1e-8).all()
                else "unsafe" if (intervals[:, 0] > limits + 1e-8).any() else "abstain")
    return {"decision": decision, "intervals": intervals.tolist(), "vertex_count": len(candidates)}


def check_certificate(request, artifact):
    reference = reference_certificate(request)
    if artifact["decision"] != reference["decision"]:
        raise AssertionError("Decision disagrees with vertex reference")
    if reference["decision"] == "inconsistent":
        if artifact["query_intervals"] or artifact["witnesses"]:
            raise AssertionError("Empty uncertainty carries false witnesses")
        return reference
    intervals = np.asarray(artifact["query_intervals"], dtype=float)
    if intervals.shape != np.asarray(reference["intervals"]).shape or not np.isfinite(intervals).all():
        raise AssertionError("Malformed intervals")
    if np.max(np.abs(intervals - reference["intervals"])) > TOL:
        raise AssertionError("Endpoint does not match independent extremum")
    B, b = observation_polytope(request)
    for index, q in enumerate(request["queries"]):
        for k, key in enumerate(("minimum", "maximum")):
            x = np.asarray(artifact["witnesses"][index][key], dtype=float)
            if x.shape != (B.shape[1],) or not np.isfinite(x).all() or not (B @ x <= b + TOL).all():
                raise AssertionError("Infeasible witness")
            if abs(np.asarray(q) @ x - intervals[index, k]) > TOL:
                raise AssertionError("Witness does not attain endpoint")
    return reference


def reference_blend(request):
    uppers = []
    for source in request["sources"]:
        r = reference_certificate(source["observation"])
        if not r["intervals"]:
            return {"status": "refused", "cost": None}
        uppers.append([pair[1] for pair in r["intervals"]])
    upper = np.asarray(uppers)
    n = len(uppers)
    target = float(request["target_volume"])
    caps = np.asarray([s["available_volume"] for s in request["sources"]])
    costs = np.asarray([s["unit_cost"] for s in request["sources"]])
    B = np.vstack((upper.T, np.eye(n), -np.eye(n)))
    b = np.concatenate((np.asarray(request["limits"]) * target, caps, np.zeros(n)))
    points = vertices(B, b, (np.ones((1, n)), np.asarray([target])))
    if not points:
        return {"status": "infeasible", "cost": None}
    best = min(points, key=lambda x: float(x @ costs))
    return {"status": "feasible", "cost": float(best @ costs), "volumes": best.tolist(),
            "upper": upper.tolist(), "vertex_count": len(points)}


def check_blend(request, artifact):
    reference = reference_blend(request)
    if reference["status"] != artifact["status"]:
        raise AssertionError("Blend feasibility disagrees with vertex reference")
    if reference["status"] != "feasible":
        return reference
    v = np.asarray(artifact["volumes"], dtype=float)
    cap = np.asarray([s["available_volume"] for s in request["sources"]])
    costs = np.asarray([s["unit_cost"] for s in request["sources"]])
    target = float(request["target_volume"])
    if not np.isfinite(v).all() or (v < -TOL).any() or (v > cap + TOL).any() or abs(v.sum() - target) > TOL:
        raise AssertionError("Volume obligation violated")
    concentration = v @ np.asarray(reference["upper"]) / target
    if (concentration > np.asarray(request["limits"]) + TOL).any():
        raise AssertionError("Robust concentration obligation violated")
    if abs(float(v @ costs) - artifact["total_cost"]) > TOL or abs(artifact["total_cost"] - reference["cost"]) > TOL:
        raise AssertionError("Cost/optimality mismatch")
    if np.max(np.abs(concentration - artifact["worst_concentration"])) > TOL:
        raise AssertionError("Reported concentration mismatch")
    for source, certificate in zip(request["sources"], artifact["source_certificates"]):
        check_certificate(source["observation"], certificate)
    return reference


def observation(A, y, error, queries, limits, bounds):
    return {"schema": "portfolio071/water-observation/v1", "A": A, "observed": y,
            "measurement_error": error, "queries": queries, "limits": limits, "concentration_bounds": bounds}


def run(output):
    from portfolio071.purpose import blend, certify
    start, cpu = time.perf_counter(), time.process_time()
    rng = np.random.default_rng(202611027101)
    controls, scientific, blends = [], [], []
    base = observation([[1, 1]], [1], [0], [[1, 1]], [1.1], [[0, 2], [0, 2]])
    probes = {
        "safe_underdetermined_sum": base,
        "unsafe_underdetermined_sum": dict(base, limits=[0.9]),
        "future_constituent_abstention": dict(base, queries=[[1, 0]], limits=[0.6]),
        "inconsistent_measurement": dict(base, observed=[5]),
        "shifted_calibration": dict(base, observed=[1.6], measurement_error=[0.1], limits=[1.5]),
        "zero_limit": observation([[1, 1]], [0], [0], [[1, 0], [0, 1]], [0, 0], [[0, 2], [0, 2]]),
    }
    for i in range(32):
        n = 2 + i % 3
        m = 1 + i % n
        A = rng.uniform(0.1, 1.5, (m, n))
        truth = rng.uniform(0.1, 2.0, n)
        error = rng.uniform(0.01, 0.12, m)
        y = A @ truth + rng.uniform(-1, 1, m) * error
        q = rng.uniform(0, 1.5, (2, n))
        limits = rng.uniform(0.4, 1.6, 2) * (q @ truth)
        probes[f"fresh_{i:02d}"] = observation(A.tolist(), y.tolist(), error.tolist(), q.tolist(), limits.tolist(), [[0, 3]] * n)
    for name, request in probes.items():
        artifact = certify(request)
        ref = check_certificate(request, artifact)
        scientific.append({"id": name, "request": request, "artifact": artifact, "vertex_count": ref["vertex_count"],
                           "independent_acceptance": True})
    old = certify(base)
    stale = copy.deepcopy(old)
    stale["query_intervals"][0][1] += 0.2
    rejected = False
    try:
        check_certificate(base, stale)
    except AssertionError:
        rejected = True
    controls.append({"id": "mutated_endpoint", "rejected": rejected})
    invalid = dict(base, queries=[[1, 0, 1]])
    rejected = False
    try:
        certify(invalid)
    except ValueError:
        rejected = True
    controls.append({"id": "unobserved_extra_analyte", "rejected": rejected})
    for name, field, value in (("negative_noise", "measurement_error", [-0.1]), ("nonfinite", "observed", [float("nan")])):
        bad = dict(base, **{field: value})
        rejected = False
        try:
            certify(bad)
        except ValueError:
            rejected = True
        controls.append({"id": name, "rejected": rejected})
    point = np.linalg.lstsq(np.array(base["A"]), np.array(base["observed"]), rcond=None)[0]
    point_false_safe = bool(point[0] <= 0.6 and certify(probes["future_constituent_abstention"])["decision"] == "abstain")
    controls.append({"id": "point_estimate_loses_uncertainty", "counterexample_observed": point_false_safe,
                     "point_estimate": point.tolist(), "valid_adversarial_concentration": [1.0, 0.0]})
    additional = dict(base, A=[[1, 1], [1, 0]], observed=[1, 0.4], measurement_error=[0, 0])
    factorial = {
        "unchanged_full_reconstruction": {"identifiable": False, "observation_count": 1},
        "purpose_query_change_only": {"decision": certify(base)["decision"], "observation_count": 1},
        "information_change_only": {"identifiable": True, "decision": certify(additional)["decision"], "observation_count": 2},
        "both": {"decision": certify(additional)["decision"], "observation_count": 2},
        "unrestricted_conventional": {"decision": reference_certificate(base)["decision"], "observation_count": 1},
        "conclusion": "Purpose-relative querying is sufficient here; the unrestricted conventional control ties. Complementarity is not forced. Extra physical sampling prices are unmeasured."
    }
    for i in range(24):
        n_sources = 2 + i % 3
        sources = []
        for j in range(n_sources):
            total = float(rng.uniform(0.2, 3.0))
            obs = observation([[1, 1]], [total], [0.02], [[1, 1], [1, 0]], [10, 10], [[0, 3], [0, 3]])
            sources.append({"observation": obs, "available_volume": float(rng.uniform(1, 5)), "unit_cost": float(rng.uniform(1, 10))})
        request = {"schema": "portfolio071/water-blend/v1", "sources": sources, "target_volume": float(3 + i % 5),
                   "limits": [float(0.5 + (i % 4) * 0.6), float(0.4 + (i % 3) * 0.7)]}
        artifact = blend(request)
        ref = check_blend(request, artifact)
        retained = [certify(s["observation"]) for s in sources]
        reused = blend(request, retained=copy.deepcopy(retained))
        fresh = blend(request)
        if artifact != reused or artifact != fresh:
            raise AssertionError("Ordinary/fresh reuse changed the result")
        blends.append({"id": f"fresh_successor_{i:02d}", "request": request, "artifact": artifact,
                       "independent_acceptance": True, "ordinary_reuse_tie": True, "fresh_construction_tie": True,
                       "vertex_count": ref.get("vertex_count", 0)})
    mutation_request = copy.deepcopy(blends[0]["request"])
    retained = [certify(s["observation"]) for s in mutation_request["sources"]]
    retained[0]["decision"] = "fabricated"
    rejected = False
    try:
        blend(mutation_request, retained)
    except ValueError:
        rejected = True
    controls.append({"id": "mutated_retained_certificate", "rejected": rejected})
    mismatch = copy.deepcopy(mutation_request)
    mismatch["sources"][1]["observation"]["queries"] = [[1, 1], [0, 1]]
    rejected = False
    try:
        blend(mismatch)
    except ValueError:
        rejected = True
    controls.append({"id": "incompatible_future_query", "rejected": rejected})
    stale_request = copy.deepcopy(mutation_request)
    stale_certificates = [certify(s["observation"]) for s in stale_request["sources"]]
    stale_request["sources"][0]["observation"]["observed"][0] += 0.3
    rejected = False
    try:
        blend(stale_request, stale_certificates)
    except ValueError:
        rejected = True
    controls.append({"id": "changed_observation_requalification", "rejected": rejected})
    if not all(r.get("rejected", r.get("counterexample_observed", False)) for r in controls):
        raise AssertionError("A required adversarial control failed")
    result = {"schema": "portfolio071.purpose.independent.v1", "seed": 202611027101,
              "constructor_sha256": hashlib.sha256(Path(__file__).with_name("purpose.py").read_bytes()).hexdigest(),
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "method": "Independent bounded-polytope vertex enumeration with NumPy linear equations; no SciPy optimization in the reference.",
              "acceptance_tolerance": TOL, "scientific_cases": len(scientific), "successor_cases": len(blends),
              "scientific_verdict_counts": {d: sum(r["artifact"]["decision"] == d for r in scientific) for d in ("safe", "unsafe", "abstain", "inconsistent")},
              "successor_verdict_counts": {d: sum(r["artifact"]["status"] == d for r in blends) for d in ("feasible", "infeasible", "refused")},
              "all_checked": True, "controls": controls, "factorial": factorial, "scientific": scientific, "successors": blends,
              "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - start,
              "claim": "Computational purpose preservation and bounded optimality verified on declared fresh cases; conventional and equal-content controls tie.",
              "unresolved": ["real water chemistry", "unmeasured species", "physical sampling costs", "new economically attainable outcome", "market demand", "retained discovery superiority"]}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Refuse overwrite of independent receipt")
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return {k: result[k] for k in ("scientific_cases", "successor_cases", "scientific_verdict_counts", "successor_verdict_counts", "all_checked", "cpu_seconds", "wall_seconds")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), sort_keys=True))
