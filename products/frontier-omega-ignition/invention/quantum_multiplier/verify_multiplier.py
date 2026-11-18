"""Exact Boolean-polynomial verification of an ancilla-free GF(4096) circuit."""

import argparse
import hashlib
import json
import re
from pathlib import Path

# Polynomial basis x^12 + x^6 + x^4 + x + 1 (decimal 4179).
WIDTH = 12
MOD = (1 << 12) | (1 << 6) | (1 << 4) | (1 << 1) | 1


def reduce_monomial(degree):
    word = 1 << degree
    while word.bit_length() > WIDTH:
        word ^= MOD << (word.bit_length() - WIDTH - 1)
    return word


def verify(data):
    # Each set contains ANF monomials with odd coefficients. Variables in a
    # monomial are bits in its integer mask. Inputs include the arbitrary z.
    original = [{1 << j} for j in range(3 * WIDTH)]
    wires = [v.copy() for v in original]
    expected = [v.copy() for v in original]
    for i in range(WIDTH):
        for j in range(WIDTH):
            remainder = reduce_monomial(i + j)
            for k in range(WIDTH):
                if remainder & (1 << k):
                    expected[2 * WIDTH + k].add((1 << i) | (1 << (j + WIDTH)))
    qubits_used = set()
    counts = {"CX": 0, "CCX": 0}
    for line in data.decode("ascii").splitlines():
        op = line.split()
        if (
            not op
            or op[0] not in ("CX", "CCX")
            or len(op) != (3 if op[0] == "CX" else 4)
        ):
            raise ValueError(f"Unexpected gate {line!r}")
        if any(not re.fullmatch(r"q(0|[1-9][0-9]?)", s) for s in op[1:]):
            raise ValueError("Invalid wire")
        ids = [int(s[1:]) for s in op[1:]]
        if len(ids) != len(set(ids)) or max(ids) >= 3 * WIDTH:
            raise ValueError("Invalid wire range or aliased operands")
        if op[0] == "CX":
            wires[ids[1]] ^= wires[ids[0]]
        else:
            a, b, target = ids
            if any(m.bit_count() != 1 for m in wires[a] | wires[b]):
                raise ValueError("Expected linear Toffoli controls")
            for u in wires[a]:
                for v in wires[b]:
                    wires[target].symmetric_difference_update((u | v,))
        qubits_used.update(ids)
        counts[op[0]] += 1
    if wires != expected:
        raise ValueError("Symbolic relation rejected")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "symbolic_inputs": 36,
        "assignments_covered": 2**36,
        "gates_checked": sum(counts.values()),
        "cnot": counts["CX"],
        "toffolis": counts["CCX"],
        "qubits": len(qubits_used),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("circuits", nargs="+", type=Path)
    args = cli.parse_args()
    output = {}
    for path in args.circuits:
        data = path.read_bytes()
        receipt = verify(data)
        # Mutate the first nonlinear product. At least one coefficient changes.
        lines = data.splitlines(keepends=True)
        lines.pop(next(i for i, line in enumerate(lines) if line.startswith(b"CCX ")))
        try:
            verify(b"".join(lines))
        except ValueError as exc:
            if str(exc) != "Symbolic relation rejected":
                raise
        else:
            raise RuntimeError("A deliberately wrong circuit passed")
        receipt["removed_product_rejected"] = True
        output[path.name] = receipt
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
