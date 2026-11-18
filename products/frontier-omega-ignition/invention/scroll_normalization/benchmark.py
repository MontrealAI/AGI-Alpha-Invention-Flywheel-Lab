"""Replay the frozen real-data CPU operator comparison using an acquired manifest."""
import argparse
from array import array
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('scroll_tool', root / 'scroll_tool.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def middle(histogram):
    n = sum(histogram.values())
    left = (n - 1) // 2
    right = n // 2
    cumulative = 0
    first = None
    for value, count in sorted(histogram.items()):
        cumulative += count
        if first is None and left < cumulative:
            first = value
        if right < cumulative:
            return (first + value) / 2


def measure(data, libraries):
    values = array('f', memoryview(data))
    counts = Counter(data)
    center = middle(counts)
    distance = Counter()
    for value, count in counts.items():
        distance[abs(value - center)] += count
    zero_mad = middle(distance) == 0
    arms = list(libraries)
    times = {arm: [] for arm in arms}
    hashes = {}
    for k in range(8):
        order = arms[k % len(arms):] + arms[:k % len(arms)]
        if k % 2:
            order = list(reversed(order))
        for arm in order:
            copy = array('f', values)
            t = time.perf_counter_ns()
            tool.call(libraries[arm], copy)
            elapsed = time.perf_counter_ns() - t
            sha = tool.digest(tool.little_bytes(copy))
            if k:
                times[arm].append(elapsed)
            if arm in hashes and hashes[arm] != sha:
                raise ValueError('nondeterministic result')
            hashes[arm] = sha
    med = {arm: median(xs) for arm, xs in times.items()}
    return {'constant': len(counts) == 1, 'zero_mad': zero_mad, 'byte_identical': len(set(hashes.values())) == 1,
            'output_sha256': hashes, 'operator_ns': times, 'median_ns': med,
            'incumbent_over_candidate': med['incumbent'] / med['candidate']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='directory produced by acquire.py')
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    manifest = json.loads((args.directory/'manifest.json').read_text())
    cases = []
    with tempfile.TemporaryDirectory() as cache:
        libraries = {arm: tool.compiled(arm, Path(cache)) for arm in tool.ARMS}
        for case in manifest['cases']:
            copy = dict(case)
            if case['available']:
                raw = (args.directory/f"{case['row']}_{case['col']}.raw").read_bytes()
                if hashlib.sha256(raw).hexdigest() != case['crop_sha256']:
                    raise ValueError('CT source digest mismatch')
                copy.update(measure(raw, libraries))
            cases.append(copy)
        self_check = tool.self_check(list(libraries.values()))
    used = [x for x in cases if x['available']]
    groups = [[x['incumbent_over_candidate'] for x in used if not x['constant'] and x['zero_mad'] == which]
              for which in (True, False)]
    sparse, other = groups
    passed = (all(x['byte_identical'] for x in used) and sum(x >= 1.25 for x in sparse) >= 2 and median(sparse) >= 1.25 and
              len(other) >= 2 and median(other) >= 1 / 1.10)
    out = {'registration_sha256':tool.digest((root/'REGISTRATION.md').read_bytes()),
           'as_of': datetime.now(timezone.utc).date().isoformat(), 'source_zarray':manifest['source'],'platform':platform.platform(),
           'compiler':subprocess.check_output(['c++','--version'],text=True).splitlines()[0],
           'variants':{'base':'14d4e725df8b569e6fc8ceb3c04d130f705c1565',
                       'incumbent':'4c0a117f4ae983992bbe2ce134c0389d7280f120',
                       'candidate_patch':tool.digest((root/'candidate.patch').read_bytes())},
           'summary':{'registered':len(cases),'retrieved':len(used),'absent':len(cases)-len(used),
                      'all_equal':all(x['byte_identical'] for x in used),'real_nonconstant_zero_mad':len(sparse),
                      'real_nonconstant_other':len(other),'zero_mad_median_speedup':median(sparse) if sparse else None,
                      'other_median_speedup':median(other) if other else None,'component_gate_passed':passed,
                      'benchmark_wall_seconds_including_compile':round(time.perf_counter()-start,3)},
           'self_check':self_check,'cases':cases}
    args.receipt.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out['summary']))
    return 0 if passed else 2


if __name__ == '__main__':
    sys.exit(main())
