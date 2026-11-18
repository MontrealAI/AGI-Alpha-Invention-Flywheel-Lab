"""Optional published SDK acceptance check; this does not run the competition metric."""

import argparse
import importlib.metadata
import json
import random
from pathlib import Path


def check(path):
    import kickmix as km

    if importlib.metadata.version("kickmix") != "1.0.0":
        raise ValueError("These observations require kickmix 1.0.0")

    seed = 20261118
    rng = random.Random(seed)
    cases = [(0, 0, 0), (4095, 4095, 4095), (1, 4095, 4095)] + [
        tuple(rng.randrange(4096) for _ in range(3)) for _ in range(253)
    ]
    regs = [
        km.array([km.q(i) for i in range(start, start + 12)]) for start in (0, 12, 24)
    ]
    circuit = km.Circuit.from_file(str(path))
    simulator = km.Simulator(batch_size=len(cases))
    for idx, case in enumerate(cases):
        for reg, value in zip(regs, case):
            simulator.write_within_shot(reg, idx, value)
    simulator.do(circuit)
    for idx, (x, y, target) in enumerate(cases):
        product = 0
        a, b = x, y
        while b:
            if b & 1:
                product ^= a
            a <<= 1
            if a & 4096:
                a ^= 4179
            b >>= 1
        got = tuple(simulator.read_within_shot(reg, idx, out=int) for reg in regs)
        if got != (x, y, product ^ target):
            raise ValueError("kickmix multiplication test failed")
    counts = circuit.operation_statistics()
    return {
        "kickmix_version": "1.0.0",
        "input_trials": len(cases),
        "seed": seed,
        "qubits": circuit.num_qubits,
        "toffoli_like": counts.num_toffoli_like,
        "instructions": counts.num_instructions,
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("path", type=Path)
    print(json.dumps(check(cli.parse_args().path), sort_keys=True, indent=2))
