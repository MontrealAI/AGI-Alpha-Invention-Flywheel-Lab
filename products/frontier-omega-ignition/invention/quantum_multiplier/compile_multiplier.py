"""Compile a rank decomposition into an ancilla-free multiply-add circuit."""

import argparse
import itertools
import json
import time
from hashlib import sha256
from pathlib import Path

WIDTH = 12


def bits(mask):
    return [i for i in range(WIDTH) if mask & (1 << i)]


def transitions(mask, pivot, other_mask, other_pivot):
    if pivot == other_pivot:
        return (mask ^ other_mask).bit_count()
    return (mask.bit_count() - bool(mask)) + (other_mask.bit_count() - bool(other_mask))


def tour_distance(terms):
    # All three register transforms use conventional lowest set bit pivots.
    table = []
    for source in terms:
        row = []
        for target in terms:
            cost = 0
            for before, after in zip(source, target):
                p = (before & -before).bit_length() - 1
                q = (after & -after).bit_length() - 1
                cost += transitions(before, p, after, q)
            row.append(cost)
        table.append(row)
    return table


def best_two_opt(path, distances):
    while True:
        best = 0
        change = None
        for i in range(1, len(path) - 2):
            a, b = path[i - 1 : i + 1]
            for j in range(i + 1, len(path) - 1):
                c, d = path[j : j + 2]
                saving = (
                    distances[a][b]
                    + distances[c][d]
                    - distances[a][c]
                    - distances[b][d]
                )
                if saving > best:
                    best = saving
                    change = (i, j + 1)
        if not change:
            return tuple(path)
        i, end = change
        path[i:end] = reversed(path[i:end])


def schedules(count, distances):
    start = count  # identity at both ends
    for first in range(count):
        order = [start, first]
        remaining = set(range(count)) - {first}
        while remaining:
            next_term = min(remaining, key=lambda j: (distances[order[-1]][j], j))
            remaining.remove(next_term)
            order.append(next_term)
        yield best_two_opt(order + [start], distances)


def choose_pivots(masks, flexible):
    choices = [(bits(mask) or [-1]) for mask in masks]
    if not flexible:
        return [options[0] for options in choices]
    # Small dynamic program for minimum linear transitions on a fixed order.
    states = {-1: (0, [-1])}
    for index, options in enumerate(choices[1:], start=1):
        next_states = {}
        for q in options:
            value, prefix = min(
                (cost + transitions(masks[index - 1], p, masks[index], q), path)
                for p, (cost, path) in states.items()
            )
            next_states[q] = (value, prefix + [q])
        states = next_states
    return states[-1][1]


def emit(terms, order, flexible):
    masks = [[terms[i][r] for i in order] for r in range(3)]
    pivots = [choose_pivots(reg, flexible) for reg in masks]
    gates = []
    for i in range(1, len(order)):
        for register in range(3):
            m, n = masks[register][i - 1 : i + 1]
            p, q = pivots[register][i - 1 : i + 1]
            parts = [(m ^ n, p)] if p == q else [(m, p), (n, q)]
            offset = WIDTH * register
            for support, pivot in parts:
                for wire in bits(support):
                    if wire != pivot:
                        # x/y use parity collection, z uses dual fan-out.
                        c, t = (wire, pivot) if register < 2 else (pivot, wire)
                        gates.append(f"CX q{c + offset} q{t + offset}")
        if i + 1 < len(order):
            x, y, z = (p[i] for p in pivots)
            gates.append(f"CCX q{x} q{WIDTH + y} q{2 * WIDTH + z}")
    return gates


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("tensor", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    t0 = time.process_time()
    data = args.tensor.read_bytes()
    terms = [tuple(int(s, 16) for s in row.split(",")) for row in data.decode().split()]
    if len(terms) != 42 or any(
        len(t) != 3 or any(not 0 < n < 4096 for n in t) for t in terms
    ):
        raise ValueError("Expected 42 nonzero twelve-bit rank-one terms")
    n = len(terms)
    terms.append((0, 0, 0))
    distances = tour_distance(terms)
    orders = sorted(set(schedules(n, distances)))
    controls = min(
        orders,
        key=lambda path: sum(distances[a][b] for a, b in itertools.pairwise(path)),
    )
    runs = {
        "conventional": emit(terms, [n, *range(n), n], False),
        "conventional_2opt": emit(terms, controls, False),
        "flexible_pivots": min((emit(terms, path, True) for path in orders), key=len),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name, gates in runs.items():
        encoded = ("\n".join(gates) + "\n").encode("ascii")
        (args.output / (name + ".kmx")).write_bytes(encoded)
        summary[name] = {
            "sha256": sha256(encoded).hexdigest(),
            "cx": sum(op.startswith("CX ") for op in gates),
            "ccx": sum(op.startswith("CCX ") for op in gates),
            "qubits": len({w for op in gates for w in op.split()[1:]}),
        }
    print(
        json.dumps(
            {
                "input_sha256": sha256(data).hexdigest(),
                "cpu_seconds": time.process_time() - t0,
                "distinct_2opt_orders": len(orders),
                "circuits": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
