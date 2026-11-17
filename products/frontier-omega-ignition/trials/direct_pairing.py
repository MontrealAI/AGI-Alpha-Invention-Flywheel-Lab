"""Independent included-Codex construction from the registered decision rule.

Use Python 3.12 with the five-column licensed runs.csv. This implementation
reads no Pairing Lab modules, recorded winners, model weights or network data.
"""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path


def read_table(path):
    matrix = {}
    with path.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream)
        if rows.fieldnames != ["task", "model", "harness", "solved", "tokens"]:
            raise ValueError("Expected task,model,harness,solved,tokens")
        for row in rows:
            if None in row or not all(row.values()):
                raise ValueError("Incomplete measurement")
            task = row["task"]
            config = row["model"] + "/" + row["harness"]
            if row["solved"] not in {"0", "1"} or not row["tokens"].isascii() or not row["tokens"].isdigit():
                raise ValueError("Invalid observed resolution or token charge")
            cells = matrix.setdefault(task, {})
            if config in cells:
                raise ValueError("Duplicate issue and configuration")
            cells[config] = (int(row["solved"]), int(row["tokens"]))
    if len(matrix) < 2:
        raise ValueError("Need separate calibration and audit issues")
    reference = set(next(iter(matrix.values())))
    if any(set(cells) != reference for cells in matrix.values()):
        raise ValueError("Unpaired or missing observations")
    return matrix


def summarize(data, ids, policy, budget, floor_percent):
    resolved = 0
    charged = 0
    for issue in ids:
        measured = [data[issue][name] for name in policy]
        resolved += max(value for value, _ in measured)
        charged += sum(tokens for _, tokens in measured)
    return {"tasks": len(ids), "solved": resolved, "tokens": charged,
            "qualifies": charged <= budget * len(ids) and 100 * resolved >= floor_percent * len(ids)}


def decide(data, budget, width, floor_percent, repository="", model=""):
    if budget < 0 or width not in (1, 2) or not 0 <= floor_percent <= 100:
        raise ValueError("Invalid decision parameters")
    def split_key(task):
        return hashlib.sha256(("pairing-lab-v1/" + task).encode()).digest(), task
    ordered = sorted(data, key=split_key)
    cut = 3 * len(ordered) // 5
    def eligible(task):
        return not repository or task.startswith(repository + "-")
    train = [t for t in ordered[:cut] if eligible(t)]
    audit = [t for t in ordered[cut:] if eligible(t)]
    if not train or not audit:
        raise ValueError("Filtered task family lacks a calibration or audit cohort")
    configurations = sorted(c for c in data[train[0]] if not model or c.split("/")[0] == model)
    winner = None
    training = None
    best = None
    for count in range(1, width + 1):
        for policy in itertools.combinations(configurations, count):
            result = summarize(data, train, policy, budget, floor_percent)
            key = (-result["solved"], result["tokens"], policy)
            if result["tokens"] <= budget * len(train) and (best is None or key < best):
                best, winner, training = key, policy, result
    return {"selected": list(winner) if winner else None, "calibration": training,
            "audit": summarize(data, audit, winner, budget, floor_percent) if winner else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--budget", type=int, default=2_000_000)
    parser.add_argument("--width", type=int, choices=[1, 2], default=2)
    parser.add_argument("--floor-percent", type=int, default=45)
    parser.add_argument("--repository", default="", help="Upstream repository task prefix, e.g. django__django")
    parser.add_argument("--model", default="", help="Exact model slug")
    args = parser.parse_args()
    result = decide(read_table(args.data), args.budget, args.width, args.floor_percent, args.repository, args.model)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
