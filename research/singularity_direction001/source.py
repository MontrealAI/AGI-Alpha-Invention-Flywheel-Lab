"""Pinned PGLib benchmark inputs and stdlib-only parsing for Ω reality probe.

The scientific constructor and independent scalar verifier share ONLY the
source interpretation. The verifier reconstructs its own constraints and
requires no NumPy, SciPy, optimization package or optimizer execution.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = {
    '14': ('research/pglib_opf_case14_ieee.m', '2c8260fff0311c902c3d36dcabcbe861576fc97c'),
    '30': ('research/pglib_opf_case30_ieee.m', 'd429394621c797fa3893d4e4b6d8efa220a4015a'),
}
# Author-selected stress after exploration, NOT a blind prospective test.
# Demand grows 20%; branch active-flow ratings are reduced to 75%.
STRESS = {'demand_multiplier': 1.20, 'thermal_rating_multiplier': 0.75}
# Fixed *after exploratory analysis*, before the published reproducibility run.
OUTAGES = {'14': 4, '30': 18}


def canonical(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def git_blob_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\x00' + raw).hexdigest()


def _matrix(raw, name):
    match = re.search(r'mpc\.' + re.escape(name) + r'\s*=\s*\[(.*?)\];', raw, re.S)
    if not match:
        raise ValueError('MISSING_PGLIB_MATRIX_' + name)
    rows = []
    for line in match.group(1).splitlines():
        line = line.split('%', 1)[0].strip().rstrip(';')
        if line:
            vals = [float(t) for t in line.split()]
            if not all(math.isfinite(x) for x in vals):
                raise ValueError('NONFINITE_PGLIB_DATA')
            rows.append(vals)
    if not rows or len({len(row) for row in rows}) != 1:
        raise ValueError('INVALID_PGLIB_MATRIX_' + name)
    return rows


def parse_case(case, path=None, *, check_source=True):
    if case not in SOURCE:
        raise ValueError('UNKNOWN_BENCHMARK')
    rel, expected_sha = SOURCE[case]
    path = ROOT / rel if path is None else Path(path)
    raw = path.read_bytes()
    sha = git_blob_sha(raw)
    if check_source and sha != expected_sha:
        raise ValueError('SOURCE_GIT_BLOB_CHANGED_' + case)
    text = raw.decode('utf-8')
    bus, gen, branch = [_matrix(text, n) for n in ('bus', 'gen', 'branch')]
    ids = [int(x[0]) for x in bus]
    if ids != list(range(1, len(bus) + 1)):
        raise ValueError('UNSUPPORTED_BUS_ORDER')
    if any(x[2] < 0 for x in bus):
        raise ValueError('NEGATIVE_LOAD_UNSUPPORTED')
    generators = [{'bus': int(x[0]) - 1, 'min_mw': x[9], 'max_mw': x[8]}
                  for x in gen if int(x[7]) == 1 and x[8] > 0]
    if not generators or any(g['max_mw'] < g['min_mw'] for g in generators):
        raise ValueError('UNSUPPORTED_GENERATORS')
    lines = []
    for x in branch:
        if int(x[10]) != 1 or x[3] <= 0 or x[5] <= 0 or x[8] < 0 or x[9] != 0:
            raise ValueError('UNSUPPORTED_BRANCH_DC')
        if not math.isclose(x[11], -30) or not math.isclose(x[12], 30):
            raise ValueError('UNSUPPORTED_PHASE_BOUND')
        lines.append({'from': int(x[0]) - 1, 'to': int(x[1]) - 1,
                      'reactance': x[3], 'rating_mw_proxy': x[5], 'tap': x[8] or 1})
    if any(not 0 <= e['from'] < len(bus) or not 0 <= e['to'] < len(bus) for e in lines):
        raise ValueError('INVALID_BUS_REFERENCE')
    mpc_base = re.search(r'mpc\.baseMVA\s*=\s*(\d+(?:\.\d+)?)', text)
    if not mpc_base:
        raise ValueError('MISSING_BASE_MVA')
    return {'case': case, 'source': rel, 'source_git_blob_sha1': sha,
            'source_sha256': hashlib.sha256(raw).hexdigest(), 'base_mva': float(mpc_base.group(1)),
            'loads_mw': [x[2] for x in bus], 'generators': generators, 'lines': lines}

