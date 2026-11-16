# SPDX-License-Identifier: Apache-2.0
"""Reuse UNLOCK's known strong implementation as incumbent, not its slow baseline."""
import importlib.util
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('unlock_demo', HERE.parent / 'unlock-omega' / 'make_demo.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_demo(root):
    root = Path(root)
    root.mkdir(exist_ok=False, parents=True)
    (root / 'incumbent.py').write_text(module.CANDIDATE)
    # Equality control: no claim that a known algorithm is a new invention.
    (root / 'candidate.py').write_text(module.CANDIDATE)
    (root / 'wrong.py').write_text('def solve(payload):\n    return -1\n')
    (root / 'examples.json').write_text(json.dumps([{'input': {'values': [1, 3, 4, 8], 'distance': 2}, 'expected': 2}]))
    (root / 'brief.txt').write_text('Optimize exact count of unordered index pairs with absolute integer difference <= nonnegative distance. Integer lists, duplicate values and empty lists are valid. Do not change the result. Standard-library Python only.\n')
    rng = random.Random(8061)
    cases = []
    for n, distance in [(0, 0), (20, 0), (150, 4), (250, 30)]:
        values = [rng.randrange(-100, 100) for _ in range(n)]
        expected = sum(abs(values[i] - values[j]) <= distance for i in range(n) for j in range(i+1, n))
        cases.append({'id': f'case-{n}', 'input': {'values': values, 'distance': distance},
                      'expected': expected, 'weight': 0.25})
    (root / 'heldout.json').write_text(json.dumps(cases))
    (root / 'contract.json').write_text(json.dumps({
        'incumbent_description': 'UNLOCK known O(n log n) sorting/two-pointer implementation; not a proof strongest worldwide',
        'min_speedup': 1.5, 'max_regression': 1.1, 'repeats': 3, 'case_timeout_seconds': 30,
        'annual_jobs': 1000000, 'compute_usd_per_hour': 1,
        'annual_other_cost_usd': 10000, 'minimum_annual_net_usd': 1000}, indent=2))
    return root


if __name__ == '__main__':
    make_demo(sys.argv[1])
