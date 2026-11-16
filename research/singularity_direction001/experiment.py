"""Find and certify a counterintuitive topology intervention on PGLIB tests.

Exploratory computation, NOT a validated AC power-flow operating instruction.
The sole physics is lossless, linear DC active-power balance under declared
stress. An exact LP redispatch (not a weak heuristic) is the baseline.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from .source import (
    ROOT, SOURCE, STRESS, OUTAGES, canonical, git_blob_sha, _matrix, parse_case,
)

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
