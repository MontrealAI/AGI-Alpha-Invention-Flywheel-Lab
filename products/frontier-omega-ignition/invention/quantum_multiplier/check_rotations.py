"""Sensitivity to conventional choices of fixed pivot order."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import itertools

from compile_multiplier import WIDTH, bits, emit, schedules, transitions


def rank_pivot(mask, start):
    return min(bits(mask), key=lambda p: (p - start) % WIDTH, default=-1)


def matrix(terms, column, rotation):
    masks = [t[column] for t in terms]
    pivots = [rank_pivot(m, rotation) for m in masks]
    return [
        [transitions(a, p, b, q) for b, q in zip(masks, pivots)]
        for a, p in zip(masks, pivots)
    ]


def fixed_order_circuit(terms, order, r1, r2):
    def rotate(mask, r):
        return ((mask >> r) | (mask << (WIDTH - r))) & ((1 << WIDTH) - 1)

    rotated = [
        tuple(rotate(m, r) for m, r in zip(term, [r1, r1, r2])) for term in terms
    ]
    result = []
    for row in emit(rotated, order, False):
        gate, *wires = row.split()
        corrected = []
        for wire in wires:
            bank, i = divmod(int(wire[1:]), WIDTH)
            start = r2 if bank == 2 else r1
            corrected.append(f"q{bank * WIDTH + (i + start) % WIDTH}")
        result.append(" ".join([gate, *corrected]))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tensor", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    t = time.process_time()
    terms = [
        tuple(int(v, 16) for v in tok.split(","))
        for tok in args.tensor.read_text().split()
    ]
    if any(a != b for a, b, _ in terms):
        raise ValueError("Expected symmetric operand masks")
    n = len(terms)
    terms.append((0, 0, 0))
    matrices = [[matrix(terms, col, r) for r in range(WIDTH)] for col in (0, 2)]
    champion = None
    summary = []
    for r1 in range(WIDTH):
        for r2 in range(WIDTH):
            d = [
                [2 * a + b for a, b in zip(x, y)]
                for x, y in zip(matrices[0][r1], matrices[1][r2])
            ]
            best = min(
                (sum(d[a][b] for a, b in itertools.pairwise(path)), path)
                for path in schedules(n, d)
            )
            cx, order = best
            summary.append(cx)
            if champion is None or cx < champion[0]:
                champion = (cx, order, r1, r2)
    cx, order, r1, r2 = champion
    runs = {
        "stronger_fixed_rotations": fixed_order_circuit(terms, order, r1, r2),
        "flexible_on_stronger_order": emit(terms, order, True),
    }
    if sum(line.startswith("CX ") for line in runs["stronger_fixed_rotations"]) != cx:
        raise AssertionError("Gate counts disagree")
    for name, lines in runs.items():
        (args.output / (name + ".kmx")).write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "cpu_seconds": time.process_time() - t,
                "rotation_pairs": len(summary),
                "conventional_best_cx": cx,
                "conventional_worst_cx": max(summary),
                "rotation_pair": [r1, r2],
                "flexible_on_stronger_order_cx": len(runs["flexible_on_stronger_order"])
                - 42,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
