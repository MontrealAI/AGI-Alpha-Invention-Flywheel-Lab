"""Deterministic illustrative workload; does not establish novel mathematics or demand."""
import json
import random
from pathlib import Path

REFERENCE = '''def solve(payload):
    a = payload["values"]
    k = payload["distance"]
    return sum(1 for i in range(len(a)) for j in range(i+1, len(a)) if abs(a[i]-a[j]) <= k)
'''

CANDIDATE = '''def solve(payload):
    a = sorted(payload["values"])
    k = payload["distance"]
    count = 0
    left = 0
    for right, value in enumerate(a):
        while left < right and value - a[left] > k:
            left += 1
        count += right - left
    return count
'''


def make_demo(path):
    path = Path(path)
    path.mkdir(exist_ok=True, parents=True)
    (path / 'reference.py').write_text(REFERENCE)
    (path / 'candidate.py').write_text(CANDIDATE)
    (path / 'examples.json').write_text(json.dumps([{'values': [1, 3, 4, 8], 'distance': 2}]))
    (path / 'acceptance.json').write_text(json.dumps({'min_speedup': 3, 'max_perf_regression': 1.1}))
    rng = random.Random(20261116)
    cases = [
        {'id': 'duplicates', 'kind': 'correctness', 'input': {'values': [0, 0, -1, 9, -1], 'distance': 0}},
        {'id': 'negative', 'kind': 'correctness', 'input': {'values': [-100, 30, 1000, 0], 'distance': 50}},
        {'id': 'empty', 'kind': 'correctness', 'input': {'values': [], 'distance': 5}},
        {'id': 'all-equal', 'kind': 'correctness', 'input': {'values': [7] * 10, 'distance': 0}},
    ]
    for i, n in enumerate([2500, 3500]):
        cases.append({'id': f'holdout-perf-{i}', 'kind': 'performance',
                      'input': {'values': [rng.randrange(-100000, 100000) for _ in range(n)],
                                'distance': [13, 971][i]}})
    (path / 'heldout.json').write_text(json.dumps(cases, separators=(',', ':')))
    return path

