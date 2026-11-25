import itertools
import json
import time
from pathlib import Path

AXES = ("component", "posture", "interval", "statistic")
ROWS = {
    "8480-6": ("systolic", "unmodified", "point", "unmodified"),
    "8462-4": ("diastolic", "unmodified", "point", "unmodified"),
    "8461-6": ("systolic", "supine", "point", "unmodified"),
    "8492-1": ("systolic", "unmodified", "8h", "min"),
    "8484-8": ("systolic", "unmodified", "12h", "max"),
    "8490-5": ("systolic", "unmodified", "24h", "mean"),
    "8485-5": ("systolic", "unmodified", "24h", "max"),
}


def identify(observed):
    if any(k not in AXES for k in observed):
        raise ValueError("unknown axis")
    return sorted(code for code, row in ROWS.items()
                  if all(row[AXES.index(k)] == v for k, v in observed.items()))


def run():
    wall, cpu = time.perf_counter(), time.process_time()
    masks = [m for n in range(5) for m in itertools.combinations(range(4), n)]
    differences = [{i for i in range(4) if a[i] != b[i]}
                   for a, b in itertools.combinations(ROWS.values(), 2)]
    candidate_sets = [m for m in masks if all(set(m) & d for d in differences)]
    minimal = [m for m in candidate_sets if not any(set(s) < set(m) for s in candidate_sets)]
    reference_separators = []
    results, mismatches, wrong_unique = [], [], []
    for m in masks:
        partition = {}
        for code, row in ROWS.items():
            partition.setdefault(tuple(row[i] for i in m), []).append(code)
        if len(partition) == len(ROWS):
            reference_separators.append(m)
        counts = []
        for code, row in ROWS.items():
            expected = sorted(partition[tuple(row[i] for i in m)])
            actual = identify({AXES[i]: row[i] for i in m})
            if actual != expected:
                mismatches.append([m, code, expected, actual])
            if len(actual) == 1 and actual != [code]:
                wrong_unique.append([m, code, actual])
            counts.append(len(actual))
        results.append({
            "axes": [AXES[i] for i in m],
            "cases": len(ROWS),
            "unique_correct": counts.count(1),
            "ambiguous": sum(c > 1 for c in counts),
            "candidate_counts": counts,
            "forced_correct_uniform_upper_numerator": len(partition),
            "uniform_denominator": len(ROWS),
        })
    ref_minimal = [m for m in reference_separators
                   if not any(set(s) < set(m) for s in reference_separators)]
    checks = {
        "all_112_reference_matches": len(masks) * len(ROWS) == 112 and not mismatches,
        "no_incorrect_unique": not wrong_unique,
        "complete_identity": all(identify(dict(zip(AXES, row))) == [code]
                                 for code, row in ROWS.items()),
        "empty_all": identify({}) == sorted(ROWS),
        "contradiction_refused": identify({"component": "diastolic", "posture": "supine"}) == [],
        "minimal_sets_equal": minimal == ref_minimal,
        "minimality_and_separation": all(
            all(set(m) & d for d in differences) and
            all(any(not (set(m) - {i}) & d for d in differences) for i in m)
            for m in minimal),
    }
    return {
        "scope": "finite exact definition identity; not clinical mapping or SPARK benchmark",
        "codes_in_case_order": list(ROWS),
        "comparisons": len(masks) * len(ROWS),
        "pair_count": len(differences),
        "results": results,
        "minimum_separating_sets": [[AXES[i] for i in m] for m in minimal],
        "mismatches": mismatches,
        "wrong_unique": wrong_unique,
        "checks": checks,
        "accepted": all(checks.values()),
        "wall_seconds": time.perf_counter() - wall,
        "process_cpu_seconds": time.process_time() - cpu,
        "actual_billing_usd": None,
        "native_profit": None,
        "commercial_decision": "NO_DEPLOY",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["accepted"] else 1)
