"""Verify released KMX arithmetic independently using packed Boolean truth tables.

For each x, one bit per y represents every possible input pair at z=0.
A separate calculation tests the output dependence on z for every input.
Run ``python3 -IB truth_table.py multiplier.kmx`` from this directory.
"""
import argparse
import hashlib
import json
from pathlib import Path

WIDTH = 12
FIELD_SIZE = 1 << WIDTH
MODULUS_LOW_TERMS = (0, 1, 4, 6)


def parse_gates(data):
    sizes = {"CX": 2, "CCX": 3}
    gates = []
    for line in data.decode("ascii").splitlines():
        opcode, *names = line.split()
        if len(names) != sizes.get(opcode) or any(not s.startswith("q") for s in names):
            raise ValueError("Unknown instruction or wrong arity")
        wires = tuple(int(name[1:]) for name in names)
        if len(set(wires)) != len(wires) or any(i < 0 or i >= 3 * WIDTH for i in wires):
            raise ValueError("Invalid wire")
        gates.append(wires)
    return gates


def prove_target_affinity(gates):
    # A 12-bit coefficient mask gives each wire's dependence on the initial z.
    initial = [0] * (2 * WIDTH) + [1 << i for i in range(WIDTH)]
    coefficients = initial.copy()
    for gate in gates:
        if len(gate) == 2:
            control, target = gate
            coefficients[target] ^= coefficients[control]
        else:
            a, b, _target = gate
            if coefficients[a] or coefficients[b]:
                raise ValueError("Nonlinear target dependence requires a different proof")
    if coefficients != initial:
        raise ValueError("Final target dependence differs from the identity map")


def horner(x, y_columns):
    # Evaluate y's binary expansion from its highest coefficient, multiplying
    # the partial product by X, reducing, then adding x times the new bit.
    product = [0] * WIDTH
    for column in reversed(y_columns):
        carry = product[-1]
        product = [0] + product[:-1]
        for degree in MODULUS_LOW_TERMS:
            product[degree] ^= carry
        for i in range(WIDTH):
            if x >> i & 1:
                product[i] ^= column
    return product


def verify(data):
    gates = parse_gates(data)
    prove_target_affinity(gates)
    columns = [sum(1 << y for y in range(FIELD_SIZE) if y >> i & 1) for i in range(WIDTH)]
    every_y = (1 << FIELD_SIZE) - 1
    for x in range(FIELD_SIZE):
        x_columns = [every_y if x >> i & 1 else 0 for i in range(WIDTH)]
        wires = x_columns + columns + [0] * WIDTH
        for gate in gates:
            if len(gate) == 2:
                control, target = gate
                wires[target] ^= wires[control]
            else:
                a, b, target = gate
                wires[target] ^= wires[a] & wires[b]
        if wires != x_columns + columns + horner(x, columns):
            raise ValueError(f"Truth table differs at x={x}")
    return {"circuit_sha256": hashlib.sha256(data).hexdigest(), "gates": len(gates),
            "exhaustive_input_pairs_at_zero_target": FIELD_SIZE**2,
            "arbitrary_target_identity_proved": True, "assignments_covered": FIELD_SIZE**3}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("circuit", type=Path)
    print(json.dumps(verify(parser.parse_args().circuit.read_bytes()), indent=2))
