#!/usr/bin/env python3
"""Independent conventional decisions from original published CSV bytes.

No production module is imported. Exact arithmetic creates the finite problems;
HiGHS, deterministic greedy, and independent exact methods solve them.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path


EXPECTED = {
    "amidation.csv": "e77f6a498387888eec63423265d6feb9d8b1ff9299b8afbc3bcc1218a7e5857a",
    "nib-etoh.csv": "d5216a673eefbaacc4ae961f4ff6acb73dbc1c83e37d0548fa7eaf84bbe5607c",
    "nib-meoh.csv": "be9fccf4c4bee7fa2b868cbbf5e813d2a29765e4ffc1f92c84b450c8381d5f99",
}


@dataclass
class Problem:
    name: str
    options: list
    required: list
    rows: list[list[int]]
    source_sha256: str
    details: dict

    def mathematical_digest(self):
        data = {"n_options": len(self.options), "rows": self.rows}
        return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _source(path):
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if path.name not in EXPECTED or digest != EXPECTED[path.name]:
        raise ValueError("UNRECOGNIZED_OR_CHANGED_PRIMARY_SOURCE")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("BAD_CSV_HEADERS")
        records = list(reader)
    if not records:
        raise ValueError("EMPTY_SOURCE")
    return records, digest


def _number(text):
    x = Decimal(text)
    if not x.is_finite():
        raise ValueError("NONFINITE_YIELD")
    return x


def amidation(path, fraction):
    if fraction not in (50, 70, 80, 90, 95):
        raise ValueError("UNREGISTERED_FRACTION")
    records, digest = _source(path)
    values, option_meta, substrate_meta = {}, {}, {}
    for r in records:
        required = ("nucleophile_id", "base_name", "solvent_name", "activator_name", "yield",
                    "nucleophile_name", "nucleophile_smiles", "base_smiles", "solvent_smiles", "activator_smiles")
        if any(k not in r or not r[k] for k in required):
            raise ValueError("MISSING_FIELD")
        substrate = r["nucleophile_id"]
        option = (r["base_name"], r["solvent_name"], r["activator_name"])
        chemical = (r["base_smiles"], r["solvent_smiles"], r["activator_smiles"])
        submeta = (r["nucleophile_name"], r["nucleophile_smiles"])
        if option in option_meta and option_meta[option] != chemical:
            raise ValueError("CONDITION_CHEMICAL_IDENTITY_CONFLICT")
        if substrate in substrate_meta and substrate_meta[substrate] != submeta:
            raise ValueError("SUBSTRATE_CHEMICAL_IDENTITY_CONFLICT")
        option_meta[option], substrate_meta[substrate] = chemical, submeta
        if (substrate, option) in values:
            raise ValueError("DUPLICATE_CELL")
        values[substrate, option] = _number(r["yield"])
    options, substrates = sorted(option_meta), sorted(substrate_meta)
    if len(values) != len(options) * len(substrates):
        raise ValueError("INCOMPLETE_MATRIX")
    maxima = {s: max(values[s, o] for o in options) for s in substrates}
    if any(v <= 0 for v in maxima.values()):
        raise ValueError("NONPOSITIVE_MAXIMUM_REQUIRES_NEW_ACCEPTANCE_RULE")
    rows = [[j for j, o in enumerate(options) if 100 * values[s, o] >= fraction * maxima[s]]
            for s in substrates]
    details = {
        "criterion": "100*yield >= fraction_percent*maximum_recorded_yield",
        "fraction_percent": fraction,
        "recorded_rows": len(records),
        "minimum_recorded_yield": str(min(values.values())),
        "maximum_recorded_yield": str(max(values.values())),
        "maxima": {s: str(maxima[s]) for s in substrates},
        "substrates": {s: {"name": substrate_meta[s][0], "smiles": substrate_meta[s][1]} for s in substrates},
        "option_smiles": [list(option_meta[o]) for o in options],
        "source_values": {s: [str(values[s, o]) for o in options] for s in substrates},
    }
    return Problem(f"amidation-{fraction}", [list(o) for o in options], substrates, rows, digest, details)


def diagnostic(path, gap):
    if gap not in (10, 15, 20, 25, 30):
        raise ValueError("UNREGISTERED_GAP")
    records, digest = _source(path)
    values, substrate_set, condition_set = {}, set(), set()
    for r in records:
        if any(k not in r or not r[k] for k in ("electrophile_id", "ligand_name", "yield")):
            raise ValueError("MISSING_FIELD")
        s, c = r["electrophile_id"], r["ligand_name"]
        if (s, c) in values:
            raise ValueError("DUPLICATE_CELL")
        values[s, c] = _number(r["yield"])
        substrate_set.add(s)
        condition_set.add(c)
    options, conditions = sorted(substrate_set), sorted(condition_set)
    if len(values) != len(options) * len(conditions):
        raise ValueError("INCOMPLETE_MATRIX")
    rows, required, indistinguishable = [], [], []
    for a, b in itertools.combinations(conditions, 2):
        witnesses = [i for i, s in enumerate(options) if abs(values[s, a] - values[s, b]) >= gap]
        if witnesses:
            rows.append(witnesses)
            required.append([a, b])
        else:
            indistinguishable.append([a, b])
    details = {
        "criterion": "abs(recorded_yield_a-recorded_yield_b) >= gap_percentage_points",
        "gap_percentage_points": gap,
        "cohort": Path(path).name,
        "recorded_rows": len(records),
        "condition_count": len(conditions),
        "conditions": conditions,
        "all_condition_pair_count": len(conditions) * (len(conditions) - 1) // 2,
        "distinguishable_pair_count": len(required),
        "indistinguishable_pair_count": len(indistinguishable),
        "indistinguishable_pairs": indistinguishable,
        "minimum_recorded_yield": str(min(values.values())),
        "maximum_recorded_yield": str(max(values.values())),
        "source_values": {s: [str(values[s, c]) for c in conditions] for s in options},
        "interpretation": "Recorded response separation only; no calibrated noise model or prospective assay-saving claim.",
    }
    return Problem(f"{Path(path).stem}-{gap}", options, required, rows, digest, details)


def _masks(problem):
    masks = [0] * len(problem.options)
    for r, row in enumerate(problem.rows):
        if not row:
            raise ValueError("INFEASIBLE_EMPTY_REQUIREMENT")
        for j in row:
            masks[j] |= 1 << r
    return masks, (1 << len(problem.rows)) - 1


def validate(problem, selected):
    if not isinstance(selected, list) or any(type(i) is not int for i in selected):
        raise ValueError("NONINTEGER_SELECTION")
    if len(set(selected)) != len(selected) or any(i < 0 or i >= len(problem.options) for i in selected):
        raise ValueError("BAD_SELECTION")
    chosen = set(selected)
    uncovered = [r for r, row in enumerate(problem.rows) if not any(j in chosen for j in row)]
    if uncovered:
        raise ValueError("UNCOVERED_REQUIREMENTS")
    out = {"accepted": True, "cardinality": len(selected), "selected_indices": selected,
           "selected_identifiers": [problem.options[i] for i in selected]}
    if problem.name.startswith("amidation"):
        yields = {s: max(Decimal(problem.details["source_values"][s][j]) for j in selected)
                  for s in problem.required}
        out["best_selected_recorded_yield_by_substrate"] = {s: str(y) for s, y in yields.items()}
        out["minimum_selected_best_recorded_yield"] = str(min(yields.values()))
    return out


def greedy(problem):
    masks, full = _masks(problem)
    uncovered, selected = full, []
    while uncovered:
        best = min(range(len(masks)), key=lambda j: (-(masks[j] & uncovered).bit_count(), j))
        if not masks[best] & uncovered:
            raise ValueError("INFEASIBLE")
        selected.append(best)
        uncovered &= ~masks[best]
    for j in reversed(selected.copy()):
        keep = [x for x in selected if x != j]
        union = 0
        for x in keep:
            union |= masks[x]
        if union == full:
            selected = keep
    return sorted(selected), {"optimality": "NOT_CLAIMED"}


def coverage_dp(problem):
    masks, full = _masks(problem)
    if len(problem.rows) > 20:
        raise ValueError("DP_OUTSIDE_DECLARED_SMALL_UNIVERSE")
    states = {0: ()}
    for option, coverage in enumerate(masks):
        for state, selected in list(states.items()):
            reached = state | coverage
            candidate = selected + (option,)
            current = states.get(reached)
            if current is None or (len(candidate), candidate) < (len(current), current):
                states[reached] = candidate
    if full not in states:
        raise ValueError("INFEASIBLE")
    return list(states[full]), {"optimality": "EXACT_DP", "reachable_masks": len(states),
                               "state_space_bound": 1 << len(problem.rows)}


def exact_search(problem):
    masks, full = _masks(problem)
    if not full:
        return [], {"optimality": "EXACT_MEMOIZED_SEARCH", "states_evaluated": 1}
    upper, _ = greedy(problem)
    row_sets = [frozenset(r) for r in problem.rows]
    state_count = 0

    @lru_cache(maxsize=None)
    def decision(uncovered, budget):
        nonlocal state_count
        state_count += 1
        if not uncovered:
            return ()
        if budget <= 0:
            return None
        gains = [m & uncovered for m in masks]
        largest = max(g.bit_count() for g in gains)
        if largest == 0 or (uncovered.bit_count() + largest - 1) // largest > budget:
            return None
        active_rows = [r for r in range(len(row_sets)) if uncovered & (1 << r)]
        active_rows.sort(key=lambda r: (len(row_sets[r]), r))
        used, lower = set(), 0
        for r in active_rows:
            if not (used & row_sets[r]):
                lower += 1
                used.update(row_sets[r])
        if lower > budget:
            return None
        branch = row_sets[active_rows[0]]
        # Every omitted choice is replaceable by another branch choice covering
        # a superset of current remaining requirements at identical unit cost.
        choices = [i for i in branch if not any(i != j and gains[i] | gains[j] == gains[j]
                   and (gains[i] != gains[j] or j < i) for j in branch)]
        choices.sort(key=lambda i: (-gains[i].bit_count(), i))
        for option in choices:
            suffix = decision(uncovered & ~masks[option], budget - 1)
            if suffix is not None:
                return (option,) + suffix
        return None

    for k in range(len(upper) + 1):
        result = decision(full, k)
        if result is not None:
            return sorted(result), {"optimality": "EXACT_MEMOIZED_SEARCH", "states_evaluated": state_count,
                                   "all_smaller_cardinalities_rejected": True,
                                   "cache_hits": decision.cache_info().hits}
    raise AssertionError("GREEDY_WITNESS_MISSING_FROM_EXACT_SEARCH")


def highs(problem):
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csc_matrix
    n = len(problem.options)
    if not problem.rows:
        return [], {"optimality": "EMPTY_UNIVERSE", "mip_gap": 0.0}
    rr, cc = [], []
    for r, row in enumerate(problem.rows):
        rr.extend([r] * len(row))
        cc.extend(row)
    a = csc_matrix((np.ones(len(rr)), (rr, cc)), shape=(len(problem.rows), n))
    result = milp(c=np.ones(n), integrality=np.ones(n), bounds=Bounds(np.zeros(n), np.ones(n)),
                  constraints=LinearConstraint(a, np.ones(len(problem.rows)), np.full(len(problem.rows), np.inf)),
                  options={"mip_rel_gap": 0.0})
    if result.status != 0 or not result.success or result.x is None:
        raise ValueError(f"HIGHS_NOT_OPTIMAL_{result.status}_{result.message}")
    chosen = [int(i) for i, value in enumerate(result.x) if value > .5]
    validate(problem, chosen)
    if abs(float(result.fun) - len(chosen)) > 1e-7:
        raise ValueError("NONINTEGRAL_OBJECTIVE")
    return chosen, {"optimality": "HIGHS_OPTIMAL_STATUS", "status": int(result.status),
                   "mip_gap": float(result.mip_gap), "mip_node_count": int(result.mip_node_count),
                   "mip_dual_bound": float(result.mip_dual_bound)}


def measured_case(builder, path, parameter, solver):
    begin_wall, begin_cpu = time.perf_counter_ns(), time.process_time_ns()
    problem = builder(path, parameter)
    built_wall, built_cpu = time.perf_counter_ns(), time.process_time_ns()
    selected, diagnostics = solver(problem)
    solved_wall, solved_cpu = time.perf_counter_ns(), time.process_time_ns()
    verdict = validate(problem, selected)
    done_wall, done_cpu = time.perf_counter_ns(), time.process_time_ns()
    return problem, {
        "method": solver.__name__, "verdict": verdict, "solver_diagnostics": diagnostics,
        "timing_seconds": {
            "source_parse_problem_construction_wall": (built_wall - begin_wall) / 1e9,
            "solve_wall": (solved_wall - built_wall) / 1e9,
            "verification_wall": (done_wall - solved_wall) / 1e9,
            "complete_wall": (done_wall - begin_wall) / 1e9,
            "source_parse_problem_construction_cpu": (built_cpu - begin_cpu) / 1e9,
            "solve_cpu": (solved_cpu - built_cpu) / 1e9,
            "verification_cpu": (done_cpu - solved_cpu) / 1e9,
            "complete_cpu": (done_cpu - begin_cpu) / 1e9,
        },
    }


def run(stage, source_root, repeats):
    import importlib.metadata
    t0 = time.perf_counter_ns()
    import numpy
    import scipy.optimize
    import_seconds = (time.perf_counter_ns() - t0) / 1e9
    tasks = []
    if stage == "first":
        tasks = [(amidation, source_root / "amidation.csv", p) for p in (50, 70, 80, 90, 95)]
    elif stage == "successor":
        tasks = [(diagnostic, source_root / name, p)
                 for name in ("nib-etoh.csv", "nib-meoh.csv") for p in (10, 15, 20, 25, 30)]
    else:
        raise ValueError("BAD_STAGE")
    cases = []
    for builder, path, parameter in tasks:
        methods = (greedy, highs, coverage_dp if stage == "first" else exact_search)
        methods_results = []
        for method in methods:
            records = []
            for repeat in range(repeats):
                problem, record = measured_case(builder, path, parameter, method)
                record["repeat"] = repeat
                records.append(record)
            methods_results.append({"method": method.__name__, "runs": records})
        exact = {m["runs"][0]["verdict"]["cardinality"] for m in methods_results if m["method"] != "greedy"}
        if len(exact) != 1:
            raise AssertionError("INDEPENDENT_EXACT_METHODS_DISAGREE")
        cases.append({
            "name": problem.name,
            "source_file": path.name,
            "source_sha256": problem.source_sha256,
            "mathematical_problem_sha256": problem.mathematical_digest(),
            "option_count": len(problem.options), "requirement_count": len(problem.rows),
            "details": {k: v for k, v in problem.details.items() if k not in ("source_values", "option_smiles")},
            "methods": methods_results,
            "accepted_optimal_cardinality": exact.pop(),
        })
    return {
        "schema": "frontier-independent-chemistry-results/v1", "stage": stage,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(Path(__file__).with_name("PROTOCOL.json").read_bytes()).hexdigest(),
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": importlib.metadata.version("numpy"), "scipy": importlib.metadata.version("scipy")},
        "numpy_scipy_import_wall_seconds": import_seconds,
        "timing_scope": "Repeated warm-library CSV-read-to-accepted-decision timing; process startup omitted, library import measured separately. Not developer effort or cash cost.",
        "repeats": repeats, "cases": cases,
        "costs": {"model_tokens_dollars": "UNKNOWN", "host_dollars": "UNKNOWN", "lab_runs_performed": 0,
                  "collected_revenue": 0, "prospective_assay_savings": "NOT_MEASURED"},
        "claim": "Exact retrospective decisions independently reproduced; useful ordinary optimization is not an invention-method superiority claim.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("first", "successor"), required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    result = run(args.stage, args.source_root, args.repeats)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "stage": args.stage,
                      "cases": [{"name": x["name"], "optimal_cardinality": x["accepted_optimal_cardinality"],
                                 "requirements": x["requirement_count"]} for x in result["cases"]]}, indent=2))


if __name__ == "__main__":
    main()
