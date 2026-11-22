"""Exact finite-population audit mathematics. Not a cryptographic or business proof.

A vendor has already fixed a finite population of N requests, exactly K of which
are improperly routed. A verifier chooses q uniformly without replacement *after*
the vendor has irreversibly committed to all N request/response pairs and the
model identity for each. A detected failure is one sample from the K.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from math import comb
from pathlib import Path


def detection_probability(total: int, substituted: int, sample: int) -> Fraction:
    """P(at least one defective request sampled), exact rational arithmetic."""
    if any(type(v) is not int for v in (total, substituted, sample)):
        raise TypeError("population, substitutions and sample size must be integers")
    if total < 1 or not (0 <= substituted <= total) or not (0 <= sample <= total):
        raise ValueError("require total >= 1, 0 <= substituted,sample <= total")
    if substituted == 0 or sample == 0:
        return Fraction(0)
    if sample > total - substituted:
        return Fraction(1)
    return 1 - Fraction(comb(total - sample, substituted), comb(total, substituted))


def minimum_sample(total: int, substituted: int, detection_target: Fraction) -> int | None:
    """Smallest integer q meeting the target, or None when impossible."""
    if not isinstance(detection_target, Fraction):
        raise TypeError("Use an exact fractions.Fraction detection target")
    if not 0 <= detection_target <= 1:
        raise ValueError("target must be in [0,1]")
    detection_probability(total, substituted, 0)
    if detection_target == 0:
        return 0
    if substituted == 0:
        return None
    low, high = 0, total
    while low < high:
        middle = (low + high) // 2
        if detection_probability(total, substituted, middle) >= detection_target:
            high = middle
        else:
            low = middle + 1
    return low


def evidence_table(total: int = 10000, target: Fraction = Fraction(99, 100)) -> dict:
    counts = (1, 10, 100, 500, 1000)
    rows = []
    for k in counts:
        if k > total:
            continue
        q = minimum_sample(total, k, target)
        probability = detection_probability(total, k, q)
        previous = detection_probability(total, k, q-1) if q else Fraction(0)
        rows.append({
            "substituted": k,
            "substitution_rate": f"{100*k/total:g}%",
            "audit_count": q,
            "audit_fraction": f"{q}/{total}",
            "detection_exact": f"{probability.numerator}/{probability.denominator}",
            "previous_count_detection_exact": f"{previous.numerator}/{previous.denominator}",
            "is_minimum": previous < target <= probability,
        })
    return {
        "title": "Precommitted uniform random audit, without replacement",
        "total_committed_requests": total,
        "target_detection_probability": str(target),
        "model": "Fixed exact K violations, unpredictable uniform audit after binding commitment; no strategic selection or proof failures",
        "claims": [
            "Detection at the stated prevalence only, not individual-request integrity",
            "No independent live inference proof or binding commitment is performed by this program",
            "No prices, enforceable damages, customer participation, or commercial success are established",
            "Verifier may refuse or fail: missing proofs need a separately specified enforcement rule",
        ],
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New JSON result file")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Refusing to overwrite existing evidence")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    evidence = evidence_table()
    assert all(row["is_minimum"] for row in evidence["rows"])
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps([{"rate": r["substitution_rate"], "audit": r["audit_count"]} for r in evidence["rows"]]))


if __name__ == "__main__":
    main()
