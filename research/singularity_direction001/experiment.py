"""Find and certify a counterintuitive topology intervention on PGLIB tests.

Exploratory computation, NOT a validated AC power-flow operating instruction.
The sole physics is lossless, linear DC active-power balance under declared
stress. An exact LP redispatch (not a weak heuristic) is the baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from scipy.optimize import linprog

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


def lp(case, unavailable, stress=STRESS):
    """Build complete fixed-topology min-unserved-load DC dispatch LP."""
    n = len(case['loads_mw']); g = len(case['generators']); m = g + 2 * n
    c = np.zeros(m); c[g:g+n] = 1
    Aeq = np.zeros((n + 1, m)); beq = np.zeros(n + 1)
    Aeq[0, g+n] = 1  # angular reference (not an operational constraint)
    for j, generator in enumerate(case['generators']):
        Aeq[generator['bus']+1, j] += 1
    for bus, load in enumerate(case['loads_mw']):
        Aeq[bus+1, g+bus] = 1
        beq[bus+1] = load * stress['demand_multiplier']
    upper = []; limits = []; line_rows = []
    for i, e in enumerate(case['lines']):
        if i in unavailable:
            continue
        f = case['base_mva'] / (e['reactance'] * e['tap'])
        row = np.zeros(m); row[g+n+e['from']] = f; row[g+n+e['to']] = -f
        Aeq[e['from']+1] -= row
        Aeq[e['to']+1] += row
        # thermal/active-flow proxy and the source's +/-30 degree angle bound
        limit = min(e['rating_mw_proxy']*stress['thermal_rating_multiplier'],
                    f * math.pi / 6)
        upper.extend((row, -row)); limits.extend((limit, limit)); line_rows.append(i)
    Aub = np.array(upper).reshape((-1, m)); bub = np.array(limits)
    bounds = [(p['min_mw'], p['max_mw']) for p in case['generators']]
    bounds += [(0, load*stress['demand_multiplier']) for load in case['loads_mw']]
    bounds += [(None, None)]*n  # no artificial limits on absolute angle gauges
    return {'c': c, 'Aeq': Aeq, 'beq': beq, 'Aub': Aub, 'bub': bub,
            'bounds': bounds, 'line_rows': line_rows,
            'active': [i for i in range(len(case['lines'])) if i not in unavailable]}


def solve(case, unavailable):
    model = lp(case, unavailable)
    result = linprog(model['c'], A_ub=model['Aub'], b_ub=model['bub'],
                     A_eq=model['Aeq'], b_eq=model['beq'], bounds=model['bounds'], method='highs')
    if not result.success:
        raise RuntimeError(f"LP {case['case']} {unavailable}: {result.message}")
    return {'unserved_mw': float(result.fun), 'primal': result.x.tolist(),
            'dual': {'equalities': result.eqlin.marginals.tolist(),
                     'inequalities': result.ineqlin.marginals.tolist(),
                     'lower': result.lower.marginals.tolist(),
                     'upper': result.upper.marginals.tolist()}}


def probe_case(case):
    """Compare full LP redispatch and every one-line corrective opening."""
    outage = OUTAGES[case['case']]
    baseline = solve(case, {outage})
    # Retain a complete primal/dual witness for *every* allowed corrective opening.
    # Reporting only unverified scalar objectives would not certify the ranking.
    responses = []
    for i in range(len(case['lines'])):
        if i == outage:
            continue
        witness = solve(case, {outage, i})
        responses.append({'switch': i, 'unserved_mw': witness['unserved_mw'],
                          'witness': witness})
    winner = min(responses, key=lambda row: (row['unserved_mw'], row['switch']))
    switch = winner['switch']
    after = winner['witness']
    return {'case': case['case'], 'source': {'path':case['source'],
                'git_blob_sha1':case['source_git_blob_sha1'], 'sha256':case['source_sha256']},
            'bus_count':len(case['loads_mw']), 'line_count':len(case['lines']),
            'total_stressed_demand_mw':sum(case['loads_mw'])*STRESS['demand_multiplier'],
            'selected_outage':outage,'selected_additional_switch':switch,
            'responses':responses, 'baseline':baseline,'switched':after,
            'modeled_gain_mw':baseline['unserved_mw']-after['unserved_mw'],
            'scenario_policy':'Outage and stress chosen after exploratory analysis, not prospectively or blinded; all single additional openings exhaustively compared',
            'comparators':'Complete LP redispatch under fixed topology, plus exhaustive certified optimal one-additional-opening dispatch; this is an established optimal transmission switching design class, not a novel competitive advantage'}


def experiment():
    return {'schema':'montreal-ai/reality-probe-001/v2',
            'title':'The counterintuitive switch: a documented DC-model possibility',
            'date':'2026-11-16', 'stress':STRESS,
            'method':'Lossless DC active-power proxy; no AC voltages/reactive power, thermal transients, protection, dynamics or stability; phase limit +/-30 deg; one pre-existing outage and at most one additional opened line',
            'scope':'Mathematical computation on PGLIB IEEE benchmark networks with an exploratory stress selection. NOT new physics, new Braess paradox, safe grid-operating advice, real-world service, economic benefit, or autonomous AI invention.',
            'cases':[probe_case(parse_case(n)) for n in SOURCE]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError('OUTPUT_MUST_NOT_EXIST')
    result = experiment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    for c in result['cases']:
        print(f"IEEE {c['case']}: outage={c['selected_outage']} extra-switch={c['selected_additional_switch']} "
              f"baseline={c['baseline']['unserved_mw']:.6f}MW after={c['switched']['unserved_mw']:.6f}MW")
    print('EVIDENCE:', args.output)


if __name__ == '__main__':
    main()
