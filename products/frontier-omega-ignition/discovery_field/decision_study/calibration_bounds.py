"""Sharp equal-site rate differences from two methods' site sizes and pooled pass totals."""
from __future__ import annotations

import argparse
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import sqlite3

EXAMPLE = {"A": {"trials": [8, 2], "passes": 8}, "B": {"trials": [2, 8], "passes": 7}}


def allocation(method, highest):
    if not isinstance(method, dict) or set(method) != {"trials", "passes"}:
        raise ValueError("Each method needs a trials array and a pooled passes count")
    trials, passes = method["trials"], method["passes"]
    if (not isinstance(trials, list) or not trials or any(type(n) is not int or n <= 0 for n in trials)
            or type(passes) is not int or not 0 <= passes <= sum(trials)):
        raise ValueError("Use positive integer site counts and a feasible integer pooled pass total")
    counts = [0] * len(trials)
    # Each pass contributes 1 / (site count * number of sites). Fill the
    # smallest denominators first to maximize, or the largest to minimize.
    left = passes
    for site in sorted(range(len(trials)), key=trials.__getitem__, reverse=not highest):
        counts[site] = min(trials[site], left)
        left -= counts[site]
    return counts, sum(Fraction(k, n) for k, n in zip(counts, trials)) / len(trials)


def bounds(data):
    if not isinstance(data, dict) or set(data) != {"A", "B"}:
        raise ValueError("Supply both A and B")
    low_a, low_rate_a = allocation(data["A"], False)
    high_a, high_rate_a = allocation(data["A"], True)
    low_b, low_rate_b = allocation(data["B"], False)
    high_b, high_rate_b = allocation(data["B"], True)
    if len(low_a) != len(low_b):
        raise ValueError("Both methods must cover the same ordered sites")
    return {"minimum": {"difference": str(low_rate_a - high_rate_b), "A": low_a, "B": high_b},
            "maximum": {"difference": str(high_rate_a - low_rate_b), "A": high_a, "B": low_b}}


def check():
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE integers (n INTEGER PRIMARY KEY)")
        db.executemany("INSERT INTO integers VALUES (?)", [(x,) for x in range(9)])
        def reference(data):
            a, b = data["A"], data["B"]
            a0, a1 = a["trials"]
            b0, b1 = b["trials"]
            # Independently enumerate every pair of first-site pass counts.
            # Evaluate a common integer numerator to avoid floating-point extrema.
            row = db.execute("""
                SELECT min(v), max(v), count(*) FROM (
                    SELECT (x.n*:a1+(:pa-x.n)*:a0)*:b0*:b1
                           -(y.n*:b1+(:pb-y.n)*:b0)*:a0*:a1 AS v
                    FROM integers x CROSS JOIN integers y
                    WHERE x.n<=:a0 AND :pa-x.n BETWEEN 0 AND :a1
                      AND y.n<=:b0 AND :pb-y.n BETWEEN 0 AND :b1)
            """, dict(a0=a0, a1=a1, b0=b0, b1=b1, pa=a["passes"], pb=b["passes"])).fetchone()
            denominator = 2 * a0 * a1 * b0 * b1
            got = bounds(data)
            for side, integer_value in zip(("minimum", "maximum"), row[:2]):
                witness = got[side]
                rates = []
                for label in ("A", "B"):
                    method = data[label]
                    vector = witness[label]
                    if sum(vector) != method["passes"] or any(
                            not 0 <= x <= n for x, n in zip(vector, method["trials"], strict=True)):
                        raise AssertionError("Infeasible witness")
                    rates.append(sum(Fraction(x, n) for x, n in zip(vector, method["trials"])) / len(vector))
                if Fraction(witness["difference"]) != Fraction(integer_value, denominator) or (
                        rates[0] - rates[1] != Fraction(witness["difference"])):
                    raise AssertionError("Disagreement with direct enumeration")
            return row[2]
        example = bounds(EXAMPLE)
        expected = {"minimum": {"difference": "-5/16", "A": [8, 0], "B": [2, 5]},
                    "maximum": {"difference": "7/16", "A": [6, 2], "B": [0, 7]}}
        if example != expected or reference(EXAMPLE) != 9:
            raise AssertionError("Original proposed witness failed")
        methods = [{"trials": [x, y], "passes": count} for x, y in product(range(1, 4), repeat=2)
                   for count in range(x+y+1)]
        table_count = sum(reference({"A": a, "B": b}) for a, b in product(methods, repeat=2))
    return {"proposed_margins": EXAMPLE, "sharp_bounds": example, "original_joint_allocations": 9,
            "additional_two_site_margin_cases": len(methods)**2, "additional_joint_allocations": table_count,
            "comparator": "exact SQLite enumeration", "observed_facility_data": False}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    choice = cli.add_mutually_exclusive_group()
    choice.add_argument("--check", action="store_true")
    choice.add_argument("--margins", type=Path, help='JSON example: {"A":{"trials":[8,2],"passes":8},"B":{"trials":[2,8],"passes":7}}')
    args = cli.parse_args()
    result = check() if args.check else bounds(json.loads(args.margins.read_text()) if args.margins else EXAMPLE)
    print(json.dumps(result, indent=2))
