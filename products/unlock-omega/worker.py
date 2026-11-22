"""Isolated executable protocol. Run only in a disposable sandbox for untrusted code."""
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path


def main():
    name = sys.argv[1]
    if name not in ('reference', 'candidate'):
        raise ValueError('invalid module')
    job = json.load(sys.stdin)
    path = Path(sys.argv[2]).resolve()
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    solve = getattr(mod, 'solve')
    rows = []
    for case in job['cases']:
        payload = case['input']
        for _ in range(job['warmups']):
            solve(payload)
        times = []
        result = None
        for _ in range(job['repeats']):
            before = time.perf_counter_ns()
            result = solve(payload)
            times.append(time.perf_counter_ns() - before)
        # Canonical wire serialization also rejects NaN and unserializable values.
        response = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)
        rows.append({'id': case['id'], 'response': response, 'median_ns': statistics.median(times)})
    print(json.dumps({'rows': rows}, separators=(',', ':')))


if __name__ == '__main__':
    main()

