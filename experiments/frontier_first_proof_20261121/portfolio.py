"""Source-bound reaction portfolio construction. Only Python's standard library.

Run: python portfolio.py --csv /path/amidation.csv --output /new/result.json
Yields are recorded measurements, not predictions or validated future outcomes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from decimal import Decimal
from pathlib import Path

from cover import solve_cover, canonical_problem

SOURCE_COMMIT = "ae3e910dcea27cfd1631a28b793b6c63607baedd"
SOURCE_URL = f"https://raw.githubusercontent.com/doyle-lab-ucla/bandit-optimization/{SOURCE_COMMIT}/datasets/amidation.csv"
SOURCE_SHA256 = "e77f6a498387888eec63423265d6feb9d8b1ff9299b8afbc3bcc1218a7e5857a"
RECIPE_FIELDS = ("base_name", "solvent_name", "activator_name")


def load_matrix(path, *, require_pinned=True):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if require_pinned and digest != SOURCE_SHA256:
        raise ValueError("source bytes differ from registered study")
    data = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not data:
        raise ValueError("empty source")
    required = set(RECIPE_FIELDS) | {"nucleophile_id", "nucleophile_name", "yield"}
    if not required <= set(data[0]):
        raise ValueError("missing required fields")
    conditions = sorted({tuple(row[k] for k in RECIPE_FIELDS) for row in data})
    substrates = sorted({row["nucleophile_id"] for row in data})
    labels, measurements = {}, {}
    for row_number, row in enumerate(data, 2):
        recipe = tuple(row[k] for k in RECIPE_FIELDS)
        sub = row["nucleophile_id"]
        if any(not x for x in recipe) or not sub:
            raise ValueError("empty identity")
        y = Decimal(row["yield"])
        if not y.is_finite():
            raise ValueError("nonfinite yield")
        key = (sub, recipe)
        if key in measurements:
            raise ValueError("duplicate measurement; no aggregation assumed")
        if sub in labels and labels[sub] != row["nucleophile_name"]:
            raise ValueError("inconsistent substrate identity")
        labels[sub] = row["nucleophile_name"]
        measurements[key] = (y, row_number)
    if len(measurements) != len(conditions) * len(substrates):
        raise ValueError("incomplete matrix; no missing value imputed")
    matrix = [[measurements[(s, c)][0] for c in conditions] for s in substrates]
    if any(max(row) <= 0 for row in matrix):
        raise ValueError("relative coverage undefined for a nonpositive recorded maximum")
    return {"conditions": conditions, "substrates": substrates, "labels": labels,
            "matrix": matrix, "records": measurements, "sha256": digest, "row_count": len(data)}


def build_portfolio(data, fraction_percent):
    if type(fraction_percent) is not int or not 0 < fraction_percent <= 100:
        raise ValueError("fraction must be an integer in (0, 100]")
    ratio = Decimal(fraction_percent) / Decimal(100)
    option_ids = [json.dumps(dict(zip(RECIPE_FIELDS, c)), sort_keys=True, ensure_ascii=False) for c in data["conditions"]]
    requirements = [[j for j, v in enumerate(row) if v >= ratio * max(row)] for row in data["matrix"]]
    problem = canonical_problem(option_ids, requirements)
    solved = solve_cover(option_ids, requirements)
    if solved["status"] != "OPTIMAL":
        raise ValueError("registered positive relative coverage should be feasible")
    selected = solved["selected"]
    assignment = []
    for i, sub in enumerate(data["substrates"]):
        j = max(selected, key=lambda c: (data["matrix"][i][c], -c))
        value, line = data["records"][(sub, data["conditions"][j])]
        assignment.append({"substrate_id": sub, "substrate_name": data["labels"][sub],
            "condition_index": j, "recorded_yield_percent": str(value),
            "recorded_maximum_percent": str(max(data["matrix"][i])),
            "required_yield_percent": str(ratio * max(data["matrix"][i])), "csv_line": line})
    single_coverage = [sum(j in row for row in requirements) for j in range(len(option_ids))]
    best_single = max(range(len(option_ids)), key=lambda j: (single_coverage[j], -j))
    return {"objective": "minimum recorded-condition portfolio", "fraction_percent": fraction_percent,
            "problem": problem, "result": solved, "assignments": assignment,
            "recipes": [{"index": j, **dict(zip(RECIPE_FIELDS, data["conditions"][j]))} for j in selected],
            "best_single_condition_coverage": single_coverage[best_single],
            "best_single_condition_index": best_single,
            "covered_substrates": len(assignment),
            "interpretation": "Finite recorded-data relative coverage; no prospective or physical guarantee."}


def run(path):
    wall, cpu = time.perf_counter(), time.process_time()
    data = load_matrix(path)
    cases = [build_portfolio(data, p) for p in [50, 70, 80, 90, 95]]
    return {"schema": "frontier-reaction-portfolio/v1", "source_url": SOURCE_URL,
        "source_sha256": data["sha256"], "source_rows": data["row_count"],
        "condition_count": len(data["conditions"]), "substrate_count": len(data["substrates"]),
        "recorded_yield_range_percent": [str(min(min(r) for r in data["matrix"])), str(max(max(r) for r in data["matrix"]))],
        "primary_fraction_percent": 90, "cases": cases,
        "resources": {"wall_seconds": time.perf_counter()-wall, "cpu_seconds": time.process_time()-cpu},
        "scope": "Assistant-constructed instrument applied to real published data; no new reaction, observed laboratory saving or revenue."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = run(args.csv)
    target = Path(args.output)
    if target.exists():
        raise FileExistsError("use a new output path to preserve prior evidence")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(target), "source_rows": result["source_rows"],
        "results": [{"fraction": x["fraction_percent"], "cardinality": x["result"]["cardinality"],
            "best_single_coverage": x["best_single_condition_coverage"], "proof_nodes": x["result"]["stats"]["proof_nodes"]} for x in result["cases"]]}, indent=2))


if __name__ == "__main__":
    main()
