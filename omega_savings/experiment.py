"""Registered finite technical comparisons for the savings-contract experiment.

Run development independently of confirmation. All outcomes, including refusal
and losses to direct work, are retained. Native commerce is owned by runner.py;
this module never creates accounts, pools balances or converts CPU time to cash.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import scipy

from .kernel import (FAMILIES, METHODS, build_request, construct, digest, execute,
                     retained_assets, solve)
from .verify import qualify, verify

POLICIES = ("adaptive", "conventional", "ordinary_reuse", "no_learning",
            "weak_analogy", "random_analogy")
CONFIRMATION_SEEDS = (701, 702, 703)
SUCCESSORS = ("successor_rhs", "successor_low_rank")
DIMENSION = 32
CASES = 8
RANK = 2


def _write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def source_metadata():
    root = Path(__file__).resolve().parents[1]
    paths = ["omega_savings/kernel.py", "omega_savings/verify.py", "omega_savings/experiment.py",
             "omega_savings/interval.py", "omega_savings/interval.c"]
    files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    return {"files": files, "source_sha256": digest(files), "git_head_navigation": head,
            "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(),
            "thread_environment": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
            "identity_note": "file digests bind executed technical source; Git HEAD is navigation and may precede uncommitted changes"}


def protocol(seeds, role):
    if role not in ("development", "confirmation", "reproduction"):
        raise ValueError("ROLE_MUST_BE_DEVELOPMENT_CONFIRMATION_OR_REPRODUCTION")
    seeds = list(seeds)
    if not seeds or any(type(s) is not int or s < 0 for s in seeds) or len(seeds) != len(set(seeds)):
        raise ValueError("DISTINCT_NONNEGATIVE_INTEGER_SEEDS_REQUIRED")
    if role == "development" and any(s in CONFIRMATION_SEEDS for s in seeds):
        raise ValueError("CONFIRMATION_SEED_CANNOT_BE_DEVELOPMENT")
    if role == "confirmation" and tuple(seeds) != CONFIRMATION_SEEDS:
        raise ValueError("EXACT_REGISTERED_CONFIRMATION_SEEDS_REQUIRED")
    return {"schema": "omega-savings/technical-protocol/v1", "role": role, "seeds": seeds,
            "role_scope": ("Repeated or independently rerun known inputs; not fresh independent confirmation"
                           if role == "reproduction" else
                           "Development inputs only" if role == "development" else
                           "Prospectively registered confirmation inputs; repetitions must use reproduction role"),
            "families": list(FAMILIES), "policies": list(POLICIES),
            "dimensions": DIMENSION, "cases": CASES, "rank": RANK,
            "successor_cross": {"families": list(SUCCESSORS),
                                "capabilities": {"old": ["direct"], "new": list(METHODS)},
                                "policies": ["direct", "adaptive", "conventional"]},
            "stopping_rule": "execute every registered cell and first-seed predeclared diagnostics once; resume missing cells after interruption; no favorable-seed replacement",
            "numpy_timing": "one independently timed direct NumPy solve per case, plus the same production verification; no GPU, billing, speed or cash inference",
            "cost_scope": "constructor, selected-method guards, production, production verification, and separate one-time full qualification; scalar proxies and measured CPU wall are different metrics",
            "hypotheses": ["observed structure permits accepted lower-work execution than an installed repeated-direct route",
                           "same-means conventional and ordinary reuse may fully explain the result",
                           "noise, changed matrices, ill conditioning or strong existing capability can remove the advantage"],
            "preconfirmation_development_decision": "n=16 low-rank proxy gains could disappear after inspection and verification; n=32 was selected before confirmation as a finite engineering workload, not a demand or scale assumption",
            "diagnostics": ["known-method connector on first seed low_rank; old direct/reuse versus new Woodbury menu with same-means control",
                            "first-seed rhs and low_rank repeated-use proxy break-even with one-time qualification charged; actual execution and verification repeated through that threshold",
                            "development only: compare first-seed n16/n32 low-rank complete proxy without selecting confirmation outcomes"]}


def cell_specs(spec):
    for seed in spec["seeds"]:
        for family in FAMILIES:
            for policy in POLICIES:
                yield {"kind": "main", "seed": seed, "family": family,
                       "policy": policy, "capability": "new", "methods": list(METHODS)}
        for family in SUCCESSORS:
            for capability, methods in (("old", ["direct"]), ("new", list(METHODS))):
                for policy in ("direct", "adaptive", "conventional"):
                    yield {"kind": "successor_cross", "seed": seed, "family": family,
                           "policy": policy, "capability": capability, "methods": methods}


def cell_id(cell):
    return "/".join(str(cell[k]) for k in ("kind", "seed", "family", "capability", "policy"))


def _finite(value):
    return value if value is None or type(value) not in (float, np.float64) or math.isfinite(value) else None


def numpy_reference(request):
    """Strong direct implementation timing, without our constructor/compiler."""
    start = time.perf_counter()
    try:
        solutions = [np.linalg.solve(np.asarray(c["matrix"], dtype=float),
                                    np.asarray(c["rhs"], dtype=float)).tolist()
                     for c in request["cases"]]
        elapsed = time.perf_counter() - start
        artifact = {"schema": "omega-savings/linear-result/v1", "status": "executed",
                    "request_sha256": digest(request), "solutions": solutions}
        checked = verify(request, artifact)
        return {"wall_seconds": elapsed, "verification_wall_seconds": checked["wall_seconds"],
                "accepted": checked["accepted"], "reasons": checked["reasons"],
                "solution_sha256": digest(solutions)}
    except (ValueError, np.linalg.LinAlgError) as exc:
        return {"wall_seconds": time.perf_counter() - start, "verification_wall_seconds": 0.0,
                "accepted": False, "reasons": [type(exc).__name__ + ":" + str(exc)], "solution_sha256": None}


def execute_cell(cell):
    """Execute a registered cell; errors remain an outcome, never a skipped row."""
    start = time.perf_counter()
    row = {**cell, "row_id": cell_id(cell), "n": DIMENSION, "cases": CASES}
    sample = None
    try:
        request = build_request(cell["seed"], cell["family"], n=DIMENSION, cases=CASES, rank=RANK)
        plan = construct(request, cell["policy"], retained_assets(cell["methods"]))
        artifact = execute(request, plan)
        checked = verify(request, artifact)
        qualification = qualify(request, artifact)
        reference = numpy_reference(request)
        cost = artifact["count_model"]
        row.update(status=artifact["status"], method=plan["method"], accepted=checked["accepted"],
                   qualified=qualification["accepted"], reasons=sorted(set(artifact["reasons"] + checked["reasons"] + qualification["reasons"])),
                   request_sha256=digest(request), program_sha256=plan["program_sha256"],
                   solution_sha256=digest(artifact["solutions"]), hypotheses=plan["hypotheses"],
                   count_model=cost, verification_ops=checked["verification_ops"],
                   qualification_float_ops=qualification["qualification_float_ops"],
                   max_relative_error_bound=checked["max_relative_error_bound"],
                   max_oracle_relative_error=qualification["max_oracle_relative_error"],
                   max_condition_bound=checked["max_condition_bound"],
                   constructor_wall_seconds=plan["constructor_wall_seconds"],
                   execution_wall_seconds=artifact["wall_seconds"],
                   production_verify_wall_seconds=checked["wall_seconds"],
                   qualification_wall_seconds=qualification["wall_seconds"], numpy_direct=reference)
        sample = {"request": request, "plan": plan, "artifact": artifact,
                  "acceptance": checked, "qualification": qualification}
    except Exception as exc:
        row.update(status="exception", method=None, accepted=False, qualified=False,
                   reasons=[type(exc).__name__ + ":" + str(exc)], count_model=None,
                   missing_cost_note="failed cell timing measured; exact work unavailable, no zero-cost claim")
    row["total_wall_seconds"] = time.perf_counter() - start
    return row, sample


def _summary(rows, spec, source):
    main = [r for r in rows if r["kind"] == "main"]
    by = {(r["seed"], r["family"], r["policy"]): r for r in main}
    pairs = []
    for seed in spec["seeds"]:
        for family in FAMILIES:
            a, c, o = (by[(seed, family, p)] for p in ("adaptive", "conventional", "ordinary_reuse"))
            pairs.append({"seed": seed, "family": family,
                          "conventional_tie": a["status"] != "exception" and c["status"] != "exception" and all(a.get(k) == c.get(k) for k in ("accepted", "qualified", "method", "solution_sha256", "count_model")),
                          "ordinary_reuse_tie": a["status"] != "exception" and o["status"] != "exception" and all(a.get(k) == o.get(k) for k in ("accepted", "qualified", "method", "solution_sha256", "count_model"))})
    return {"schema": "omega-savings/technical-summary/v1", "role": spec["role"],
            "source_sha256": source["source_sha256"], "expected_rows": len(list(cell_specs(spec))),
            "completed_rows": len(rows), "accepted_rows": sum(r["accepted"] for r in rows),
            "qualified_rows": sum(r["qualified"] for r in rows),
            "exceptions": sum(r["status"] == "exception" for r in rows),
            "by_policy": {p: {"registered_main": sum(r["policy"] == p for r in main),
                              "accepted": sum(r["policy"] == p and r["accepted"] for r in main),
                              "qualified": sum(r["policy"] == p and r["qualified"] for r in main)} for p in POLICIES},
            "matched_pairs": pairs,
            "invention_verdict": "No special method advantage established when same-means conventional/equal-content controls tie; known methods remain usable.",
            "economic_scope": "Technical experiment only. No revenue, profit, account or real cloud savings inferred.",
            "timing_scope": "Single-host observations with uncontrolled scheduling and heterogeneous operation costs; do not infer general speedup from scalar proxy savings."}


def adaptation_diagnostic(seed):
    request = build_request(seed, "low_rank", n=DIMENSION, cases=CASES, rank=RANK)
    old = solve(request, "adaptive", retained_assets(("direct", "reuse")))
    new = solve(request, "adaptive", retained_assets())
    conventional = solve(request, "conventional", retained_assets())
    checks = {name: qualify(request, result) for name, result in (("old", old), ("new", new), ("conventional", conventional))}
    return {"request_sha256": digest(request), "seed": seed,
            "observed_low_rank": old["plan"]["hypotheses"]["declared_low_rank_updates"],
            "old_method": old["plan"]["method"], "new_method": new["plan"]["method"],
            "old_complete_proxy": old["count_model"]["candidate_complete_proxy_units"],
            "new_complete_proxy": new["count_model"]["candidate_complete_proxy_units"],
            "new_program_sha256": new["program_sha256"],
            "qualified": {name: checked["accepted"] for name, checked in checks.items()},
            "qualification_float_ops": {name: checked["qualification_float_ops"] for name, checked in checks.items()},
            "conventional_equal_content_tie": new["solutions"] == conventional["solutions"] and new["count_model"] == conventional["count_model"],
            "interpretation": "Finite known-adaptation replay installs an already available Woodbury template into a previously missing connector menu and generates executable source. Ordinary code with equal content performs the same adaptation. No autonomous numerical discovery or exclusive capability claim.",
            "scope": "The old-menu arm is an installed-capability diagnostic, not the strongest incumbent."}


def repetition_diagnostic(seed, family):
    """Actually repeat accepted work through a precomputed cost-proxy threshold."""
    request = build_request(seed, family, n=DIMENSION, cases=CASES, rank=RANK)
    plan = construct(request)
    first = execute(request, plan)
    qualification = qualify(request, first)
    costs = first["count_model"]
    delta = costs["saved_proxy_units"]
    upfront = qualification["qualification_float_ops"] + qualification["verification_ops"]
    threshold = upfront // delta + 1 if delta > 0 and qualification["accepted"] else None
    receipt = {"seed": seed, "family": family, "request_sha256": digest(request),
               "qualification_accepted": qualification["accepted"],
               "candidate_complete_proxy_per_batch": costs["candidate_complete_proxy_units"],
               "installed_direct_complete_proxy_per_batch": costs["direct_complete_proxy_units"],
               "extra_one_time_qualification_proxy": upfront,
               "proxy_break_even_batches": threshold,
               "definition": "Smallest integer k with k*(direct-complete minus candidate-complete)>extra qualification proxy. Complete per-batch proxy conservatively charges construction again; no persistent numerical cache across program runs.",
               "same_means_incumbent_break_even": None,
               "same_means_note": "The strong conventional/equal-content route has the same methods and cost proxy; no incremental algorithmic saving over it.",
               "monetary_scope": "Analytic work-proxy threshold only; no revenue annualization, demand extrapolation or measured avoidable cash."}
    if threshold is None:
        return {**receipt, "executed_repetitions": 0, "accepted_repetitions": 0}
    accepted = 0
    candidate_seconds = 0.0
    reference_seconds = 0.0
    transcript = []
    for i in range(threshold):
        # Alternate order to avoid assigning a fixed warm-cache ordering benefit.
        def candidate():
            nonlocal accepted, candidate_seconds
            started = time.perf_counter()
            result = solve(request)
            checked = verify(request, result)
            candidate_seconds += time.perf_counter() - started
            accepted += bool(checked["accepted"])
            return digest(result["solutions"])
        def reference():
            nonlocal reference_seconds
            observed = numpy_reference(request)
            reference_seconds += observed["wall_seconds"] + observed["verification_wall_seconds"]
            return observed
        if i % 2:
            ref = reference()
            output_sha = candidate()
        else:
            output_sha = candidate()
            ref = reference()
        transcript.append({"index": i, "solution_sha256": output_sha, "reference_accepted": ref["accepted"]})
    return {**receipt, "executed_repetitions": threshold, "accepted_repetitions": accepted,
            "all_reference_accepted": all(r["reference_accepted"] for r in transcript),
            "transcript_sha256": digest(transcript), "distinct_solution_hashes": len({r["solution_sha256"] for r in transcript}),
            "proxy_net_at_previous_batch": (threshold - 1) * delta - upfront,
            "proxy_net_at_threshold": threshold * delta - upfront,
            "candidate_measured_wall_seconds": candidate_seconds,
            "numpy_direct_plus_verifier_measured_wall_seconds": reference_seconds,
            "one_time_qualification_measured_wall_seconds": qualification["wall_seconds"],
            "candidate_wins_observed_complete_wall": candidate_seconds + qualification["wall_seconds"] < reference_seconds,
            "timing_caution": "Observed single-host result only; exact rational checks and program overhead can outweigh floating-point work savings."}


def diagnostics(seeds, role):
    result = {"schema": "omega-savings/technical-diagnostics/v1",
              "known_adaptation": adaptation_diagnostic(seeds[0]),
              "repeated_use": [repetition_diagnostic(seeds[0], family) for family in ("rhs", "low_rank")]}
    if role == "development":
        result["dimension_diagnosis"] = []
        for n in (16, 32):
            request = build_request(seeds[0], "low_rank", n=n, cases=CASES, rank=RANK)
            artifact = solve(request)
            result["dimension_diagnosis"].append({"n": n, "method": artifact["plan"]["method"],
                                                   "accepted": verify(request, artifact)["accepted"],
                                                   "count_model": artifact["count_model"]})
    return result


def _csv(path, rows):
    fields = ["row_id", "kind", "seed", "family", "policy", "capability", "n", "cases",
              "method", "status", "accepted", "qualified", "reasons", "request_sha256", "program_sha256",
              "candidate_complete_proxy_units", "direct_complete_proxy_units", "saved_proxy_units",
              "qualification_float_ops", "verification_ops", "max_relative_error_bound", "max_oracle_relative_error",
              "constructor_wall_seconds", "execution_wall_seconds", "production_verify_wall_seconds",
              "qualification_wall_seconds", "numpy_direct_wall_seconds", "numpy_direct_verification_wall_seconds", "total_wall_seconds"]
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = {k: _finite(row.get(k)) for k in fields}
            flat["reasons"] = "|".join(row["reasons"])
            costs = row.get("count_model") or {}
            for k in ("candidate_complete_proxy_units", "direct_complete_proxy_units", "saved_proxy_units"):
                flat[k] = costs.get(k)
            flat["numpy_direct_wall_seconds"] = row.get("numpy_direct", {}).get("wall_seconds")
            flat["numpy_direct_verification_wall_seconds"] = row.get("numpy_direct", {}).get("verification_wall_seconds")
            writer.writerow(flat)


def run(directory, seeds, role):
    directory = Path(directory).resolve()
    spec = protocol(seeds, role)
    source = source_metadata()
    identity = {"protocol": spec, "technical_source_sha256": source["source_sha256"]}
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory / "registration.json"
    if metadata_path.exists():
        prior = json.loads(metadata_path.read_text())
        if prior["identity"] != identity:
            raise ValueError("EXISTING_TECHNICAL_RUN_SOURCE_OR_PROTOCOL_CHANGED")
    elif any(directory.iterdir()):
        raise ValueError("NONEMPTY_UNREGISTERED_OUTPUT_DIRECTORY")
    else:
        _write(metadata_path, {"identity": identity, "source": source})
    completed_path = directory / "results.json"
    checkpoint = directory / "checkpoint.jsonl"
    rows = json.loads(completed_path.read_text())["rows"] if completed_path.exists() else []
    if checkpoint.exists():
        rows.extend(json.loads(line) for line in checkpoint.read_text().splitlines() if line)
    # A crash after atomic results publication but before checkpoint deletion
    # may expose the same receipt twice. Exact duplicates are idempotent;
    # conflicting receipts for an already observed cell are never overwritten.
    by_id = {}
    for row in rows:
        if row["row_id"] in by_id and by_id[row["row_id"]] != row:
            raise ValueError("CONFLICTING_TECHNICAL_CELL")
        by_id[row["row_id"]] = row
    rows = list(by_id.values())
    seen = set(by_id)
    expected = list(cell_specs(spec))
    if not seen <= {cell_id(c) for c in expected}:
        raise ValueError("UNREGISTERED_TECHNICAL_CELL")
    with checkpoint.open("a") as stream:
        for cell in expected:
            if cell_id(cell) in seen:
                continue
            row, sample = execute_cell(cell)
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            rows.append(row)
            seen.add(row["row_id"])
            if sample and cell == expected[0]:
                sample_dir = directory / "standalone_example"
                sample_dir.mkdir(exist_ok=True)
                _write(sample_dir / "request.json", sample["request"])
                (sample_dir / "plan.py").write_text(sample["plan"]["program"])
                _write(sample_dir / "accepted_result.json", sample["artifact"])
                _write(sample_dir / "acceptance.json", sample["acceptance"])
                _write(sample_dir / "qualification.json", sample["qualification"])
    order = {cell_id(cell): i for i, cell in enumerate(expected)}
    rows.sort(key=lambda r: order[r["row_id"]])
    _write(completed_path, {"schema": "omega-savings/technical-results/v1", "rows": rows})
    checkpoint.unlink(missing_ok=True)
    _csv(directory / "comparison.csv", rows)
    if not (directory / "diagnostics.json").exists():
        _write(directory / "diagnostics.json", diagnostics(spec["seeds"], role))
    summary = _summary(rows, spec, source)
    _write(directory / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seeds", required=True, help="Comma-separated explicit seeds")
    parser.add_argument("--role", required=True, choices=("development", "confirmation", "reproduction"))
    args = parser.parse_args()
    summary = run(args.output, [int(s) for s in args.seeds.split(",")], args.role)
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
