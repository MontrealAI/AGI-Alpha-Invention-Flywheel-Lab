"""Execute an equal-content ordinary-reuse control and bind fresh alternatives.

The control receives the same source, inputs and permissions. An identical
ordinary asset is expected to tie. This establishes transfer of a useful
instrument and explicitly tests against claiming a better invention procedure.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "independent"))
from verify_certificate import verify
from audit import check_provenance

CASE_KEYS = [(name, str(gap)) for name in ("nib-etoh.csv", "nib-meoh.csv")
             for gap in (10, 15, 20, 25, 30)]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def check_receipts(successor, baseline):
    check_provenance(successor)
    require(successor.get("registered_denominator") == len(CASE_KEYS) and
            successor.get("completed_case_count") == len(CASE_KEYS) and successor.get("failures") == [],
            "SUCCESSOR_CASE_DENOMINATOR")
    require(isinstance(successor.get("results"), list) and
            [c.get("case_id") for c in successor["results"]] == [f"{n}:{g}" for n, g in CASE_KEYS],
            "SUCCESSOR_CASE_SEQUENCE")
    require(baseline.get("stage") == "successor", "BASELINE_STAGE")
    require(baseline.get("source_sha256") == hashlib.sha256((HERE / "independent/baselines.py").read_bytes()).hexdigest(),
            "BASELINE_SOURCE_BINDING")
    require(baseline.get("protocol_sha256") == hashlib.sha256((HERE / "independent/PROTOCOL.json").read_bytes()).hexdigest(),
            "BASELINE_PROTOCOL_BINDING")
    require(type(baseline.get("repeats")) is int and baseline["repeats"] > 0, "BASELINE_REPETITIONS")
    cases = baseline.get("cases")
    require(isinstance(cases, list) and len(cases) == len(CASE_KEYS), "BASELINE_CASE_DENOMINATOR")
    keys = [(c.get("source_file"), str(c.get("details", {}).get("gap_percentage_points"))) for c in cases]
    require(keys == CASE_KEYS, "BASELINE_CASE_SEQUENCE")
    return dict(zip(keys, cases))


def check_fresh_case(case, comparison, repeats):
    from baselines import EXPECTED
    problem = case["problem"]
    require(comparison.get("source_sha256") == case["source"]["sha256"] == EXPECTED[case["source"]["filename"]],
            "BASELINE_DATA_BINDING")
    numerical_problem = {"n_options": len(problem["option_ids"]), "rows": problem["requirements"]}
    problem_hash = hashlib.sha256(json.dumps(numerical_problem, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(comparison.get("mathematical_problem_sha256") == problem_hash, "BASELINE_PROBLEM_BINDING")
    require(type(comparison.get("accepted_optimal_cardinality")) is int and
            comparison["accepted_optimal_cardinality"] == case["answer"]["cardinality"], "BASELINE_OPTIMUM")
    methods = comparison.get("methods")
    require(isinstance(methods, list) and [m.get("method") for m in methods] == ["greedy", "highs", "exact_search"],
            "BASELINE_METHOD_DENOMINATOR")
    for method in methods:
        runs = method.get("runs")
        require(isinstance(runs, list) and len(runs) == repeats, "BASELINE_RUN_DENOMINATOR")
        require([r.get("repeat") for r in runs] == list(range(repeats)), "BASELINE_REPEAT_SEQUENCE")
        for run in runs:
            require(run.get("method") == method["method"], "BASELINE_RUN_METHOD")
            verdict = run.get("verdict", {})
            selected = verdict.get("selected_indices")
            require(verdict.get("accepted") is True and isinstance(selected, list) and
                    all(type(j) is int and 0 <= j < len(problem["option_ids"]) for j in selected),
                    "BASELINE_SELECTION")
            require(len(set(selected)) == len(selected) == verdict.get("cardinality"), "BASELINE_SELECTION_CARDINALITY")
            require(verdict.get("selected_identifiers") == [problem["option_ids"][j] for j in selected],
                    "BASELINE_SELECTED_LABELS")
            chosen = set(selected)
            require(all(chosen.intersection(row) for row in problem["requirements"]), "BASELINE_SELECTION_INFEASIBLE")
            if method["method"] != "greedy":
                require(len(selected) == comparison["accepted_optimal_cardinality"], "BASELINE_EXACT_NOT_OPTIMAL")
            diagnostics = run.get("solver_diagnostics", {})
            if method["method"] == "highs":
                bound, gap = diagnostics.get("mip_dual_bound"), diagnostics.get("mip_gap")
                # Solver telemetry is floating-point. Exact optimality still
                # comes from the independently checked finite certificate.
                require(diagnostics.get("optimality") == "HIGHS_OPTIMAL_STATUS" and diagnostics.get("status") == 0 and
                        type(bound) in (int, float) and math.isfinite(bound) and
                        math.isclose(bound, len(selected), rel_tol=0, abs_tol=1e-7) and
                        type(gap) in (int, float) and math.isfinite(gap) and 0 <= gap <= 1e-7,
                        "BASELINE_HIGHS_STATUS")
            if method["method"] == "exact_search":
                require(diagnostics.get("optimality") == "EXACT_MEMOIZED_SEARCH" and
                        diagnostics.get("all_smaller_cardinalities_rejected") is True, "BASELINE_EXACT_STATUS")
            values = run.get("timing_seconds", {})
            require(isinstance(values, dict) and "complete_wall" in values and
                    all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values.values()),
                    "BASELINE_INVALID_TIMINGS")


def mathematical(result):
    return {k: result[k] for k in ("status", "selected", "cardinality", "certificate")}


def run(successor_file, baseline_file, repeats=5):
    if type(repeats) is not int or repeats < 1:
        raise ValueError("positive integer repetitions required")
    successor = json.loads(Path(successor_file).read_text())
    baseline = json.loads(Path(baseline_file).read_text())
    fresh = check_receipts(successor, baseline)
    source = (HERE / "cover.py").read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    if source_hash != successor["retained_cover_sha256"]:
        raise ValueError("retained source identity mismatch")
    # Import executable source only after checking its frozen identity.
    from cover import solve_cover
    rows = []
    with tempfile.TemporaryDirectory(prefix="frontier-ordinary-reuse-") as temporary:
        ordinary_path = Path(temporary) / "ordinary_cover.py"
        ordinary_path.write_bytes(source)
        spec = importlib.util.spec_from_file_location("ordinary_cover_control", ordinary_path)
        ordinary = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ordinary)
        for case in successor["results"]:
            problem = case["problem"]
            comparison = fresh[(case["source"]["filename"], case["gap_percentage_points"])]
            check_fresh_case(case, comparison, baseline["repeats"])
            timings = {"retained": [], "ordinary_reuse": []}
            expected = mathematical(case["answer"])
            for repeat in range(repeats):
                arms = [("retained", solve_cover), ("ordinary_reuse", ordinary.solve_cover)]
                if repeat % 2:
                    arms.reverse()
                for name, solver in arms:
                    wall, cpu = time.perf_counter(), time.process_time()
                    result = solver(problem["option_ids"], problem["requirements"])
                    verified = verify(problem, result["certificate"])
                    timings[name].append({"wall_seconds": time.perf_counter() - wall,
                                          "cpu_seconds": time.process_time() - cpu})
                    if mathematical(result) != expected or not verified["accepted"]:
                        raise ValueError("ordinary or retained arm failed equal-content acceptance")
            if comparison["accepted_optimal_cardinality"] != case["answer"]["cardinality"]:
                raise ValueError("fresh competent alternative disagrees")
            rows.append({"case_id": case["case_id"], "optimum": case["answer"]["cardinality"],
                "retained_accepted": True, "ordinary_reuse_accepted": True,
                "fresh_conventional_accepted": True, "identical_mathematical_outputs": True,
                "timings": timings,
                "median_solve_and_proof_check_wall_seconds": {name: statistics.median(x["wall_seconds"] for x in values)
                                                              for name, values in timings.items()}})
    return {"schema": "frontier-equal-content-transfer-control/v1", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "retained_asset_sha256": source_hash, "ordinary_source_sha256": hashlib.sha256(source).hexdigest(),
        "successor_result_sha256": hashlib.sha256(Path(successor_file).read_bytes()).hexdigest(),
        "fresh_baseline_result_sha256": hashlib.sha256(Path(baseline_file).read_bytes()).hexdigest(),
        "cases": rows, "registered_cases": len(CASE_KEYS), "repeats_per_arm": repeats,
        "retained_scope": "New domain adapter calls a frozen generic instrument on different source data and a different objective.",
        "timing_scope": "Only solving supplied incidence and independently replaying the mathematical proof; excludes data loading, adapter construction, human/model acquisition effort and complete source semantic audit.",
        "fresh_receipt_scope": "Binds baseline code, source, problem and complete method/run denominators, and rechecks all supplied baseline selections. Execution times are supplied receipts, not independently remeasured here.",
        "findings": {"unchanged_capability_reused": True, "different_objective_executed": True,
            "ordinary_reuse_ties": True, "fresh_exact_alternatives_match": True,
            "superior_invention_method": "NOT_ESTABLISHED", "complete_cost_advantage": "NOT_ESTABLISHED",
            "physical_or_commercial_value": "NOT_ESTABLISHED"},
        "interpretation": "A useful working instrument transferred to a different decision. Ordinary reuse gives the same result; competent fresh methods also solve it. This is a bounded engineering transfer, not evidence that the second invention was unavailable conventionally."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--successor", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new control output path")
    result = run(args.successor, args.baseline, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": len(result["cases"]), "findings": result["findings"], "output": str(args.output)}, indent=2))
