"""Independent exact switched-reference calculation, complete cohort and drift audit."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from fractions import Fraction as F
from pathlib import Path
import resource
import time

spec = importlib.util.spec_from_file_location('reference_independent_kcl', Path(__file__).with_name('analog_check.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def expected_cohort(parts, protocol, primary):
    cases = []
    multipliers = protocol['successor_tolerance_multipliers']
    variables = protocol['successor_tolerance_elements']
    templates = [()] if primary else list(itertools.product(multipliers, repeat=len(variables)))
    for template in templates:
        factors = {} if primary else dict(zip(variables, template))
        for a in protocol['primary_scale' if primary else 'successor_scales']:
            scale = F(a)
            values = {name: str(x * F(factors.get(name, '1')) * (F(1) / scale if kind == 'c' else scale)) for kind, name, _, _, x in parts}
            if primary:
                case = {'id': 'nominal-a' + a.replace('/', '_'), 'values': values}
            else:
                case = {'id': 'fresh-' + ','.join(template) + '-a' + a, 'values': values,
                        'impedance_scale': a, 'component_multipliers': factors}
            cases.append(case)
    return cases


def bound(y, protocol, epsilon=None):
    nominal = F(protocol['reference_nominal_siemens'])
    low_factor, high_factor = map(F, protocol['reference_multiplier_bounds'])
    low, high = nominal * low_factor, nominal * high_factor
    gain_min = F(protocol['gain_magnitude_lower_bound'])
    error = F(protocol['absolute_coordinate_error_siemens'] if epsilon is None else epsilon)
    minimum = gain_min * low - 4 * error
    if low <= 0 or high < low or gain_min <= 0 or error < 0 or minimum <= 0:
        return {'decision': 'ABSTAIN', 'denominator_modulus_lower_bound': str(minimum)}
    radius = nominal / low * (2 * high * error + 4 * error * (abs(y[0]) + abs(y[1]))) / minimum
    factors = [nominal / high, nominal / low]
    rectangle = [[str(min(x * f for f in factors) - radius), str(max(x * f for f in factors) + radius)] for x in y]
    return {'decision': 'CONDITIONAL_MODEL_BOUND', 'box': rectangle, 'denominator_modulus_lower_bound': str(minimum),
            'coordinate_error_bound': str(radius), 'reference_scale_bounds': list(map(str, factors))}


def separate(a, b):
    return any(F(x[1]) < F(y[0]) or F(y[1]) < F(x[0]) for x, y in zip(a, b))


def normalize(z0, z1, nominal):
    return q.times((nominal, F(0)), q.divide(z0, q.plus(z1, q.neg(z0))))


def verify_stage(root, directory, protocol, primary, check):
    name = 'primary' if primary else 'new_rlc_family'
    filename = protocol['primary_source' if primary else 'successor_source']
    source_path = root / 'research/consequential009/analog' / filename
    raw = source_path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    check(blob == protocol['source_git_blobs'][filename], name + ': exact upstream raw source')
    parts, source = q.parse(source_path)
    cases = expected_cohort(parts, protocol, primary)
    cohort = read(directory / (name + '-COHORT.json'))
    check(cohort['hypotheses'] == cases and cohort['source_sha256'] == sha(source_path), name + ': unchanged complete finite cohort')
    frequencies = protocol['primary_omega_rad_s' if primary else 'successor_omega_rad_s']
    all_pairs = set(itertools.combinations(range(len(cases)), 2))
    values, bounds, covered = {}, {}, {}
    for w in frequencies:
        values[w] = [q.solve([(kind, n, a, b, F(case['values'][n])) for kind, n, a, b, _ in parts], source, F(w))[1] for case in cases]
        bounds[w] = [bound(y, protocol) for y in values[w]]
        covered[w] = {pair for pair in all_pairs if bounds[w][pair[0]]['decision'] != 'ABSTAIN' and bounds[w][pair[1]]['decision'] != 'ABSTAIN' and separate(bounds[w][pair[0]]['box'], bounds[w][pair[1]]['box'])}
    strategy = read(directory / (name + '-STRATEGY.json'))
    check(strategy['true_network_admittance'] == {w: [q.encode(y) for y in ys] for w, ys in values.items()}, name + ': every true response independently solved')
    for w in frequencies:
        check(len(strategy['bounds'][w]) == len(cases), name + ': every bound present at ' + w)
        for index, expected in enumerate(bounds[w]):
            check(all(strategy['bounds'][w][index].get(k) == v for k, v in expected.items()), name + ': exact analytic bound ' + w + '/' + str(index))
    full = set().union(*covered.values())
    minimum = next(choice for count in range(len(frequencies) + 1) for choice in itertools.combinations(frequencies, count) if set().union(*(covered[w] for w in choice)) == full)
    selected = strategy['dsl']['frequency_rad_s']
    check(len(selected) == len(set(selected)) and all(w in frequencies for w in selected), name + ': admitted unique paired-reference actions')
    actual = set().union(*(covered[w] for w in selected))
    unresolved = [[cases[i]['id'], cases[j]['id']] for i, j in sorted(all_pairs - actual)]
    check(strategy['admitted_cases'] == len(cases) and strategy['admitted_pairs'] == len(all_pairs) and strategy['separated_pairs'] == len(actual) and strategy['unresolved_pairs'] == unresolved and strategy['conditional_complete_acceptance'] is (actual == all_pairs), name + ': full denominator, acceptance and abstentions')
    ordinary = strategy['ordinary_same_reference']
    check(ordinary['frequency_rad_s'] == list(minimum) and ordinary['separated_pairs'] == len(full) and ordinary['conditional_complete_acceptance'] is (full == all_pairs), name + ': independent exhaustive known-ratiometric control')
    remaining = all_pairs.copy()
    check(len(strategy['ancestry']) == len(selected), name + ': complete action ancestry')
    for entry, w in zip(strategy['ancestry'], selected):
        new = covered[w] & remaining
        check(entry['frequency_rad_s'] == w and entry['newly_separated_pairs'] == len(new) and entry['actual_newly_separated_pair'] == [cases[i]['id'] for i in min(new)], name + ': ancestry action resolves its witnessed pair ' + w)
        remaining -= new
    nominal, eps = F(protocol['reference_nominal_siemens']), F(protocol['absolute_coordinate_error_siemens'])
    gains = [tuple(map(F, gain)) for gain in protocol['raw_gain_grid']]
    reference_grid = list(map(F, protocol['raw_reference_multiplier_grid']))
    noises = [(q.ZERO, q.ZERO), ((eps, eps), (-eps, -eps)), ((-eps, -eps), (eps, eps)), ((eps, -eps), (-eps, eps)), ((-eps, eps), (eps, -eps))]
    check(all(g[0] ** 2 + g[1] ** 2 >= F(protocol['gain_magnitude_lower_bound']) ** 2 for g in gains), name + ': admitted complex gains satisfy magnitude floor')
    rows_checked, raw_exact, inside_all = 0, True, True
    for index, case in enumerate(cases):
        path = directory / 'raw' / name / (str(index).zfill(3) + '.json')
        raw_rows = read(path)
        expected_rows = []
        for w in frequencies:
            y = values[w][index]
            rectangle = bounds[w][index]['box']
            for gi, gain in enumerate(gains):
                for ri, reference_factor in enumerate(reference_grid):
                    known_g = nominal * reference_factor
                    for ni, (e0, e1) in enumerate(noises):
                        z0 = q.plus(q.times(gain, y), e0)
                        z1 = q.plus(q.times(gain, q.plus(y, (known_g, F(0)))) , e1)
                        estimate = normalize(z0, z1, nominal)
                        expected_rows.append({'hypothesis': case['id'], 'omega_rad_s': w, 'gain_index': gi, 'reference_index': ri, 'noise_index': ni,
                                              'z0': q.encode(z0), 'z1': q.encode(z1), 'estimate': q.encode(estimate)})
                        inside_all &= all(F(lo) <= x <= F(hi) for (lo, hi), x in zip(rectangle, estimate))
        raw_exact &= raw_rows == expected_rows
        rows_checked += len(expected_rows)
    check(raw_exact and inside_all, name + ': every raw observation and normalized estimate exact and inside analytic box')
    check(len(list((directory / 'raw' / name).glob('*.json'))) == len(cases), name + ': no raw cohort units omitted or added')
    drift_rows = read(directory / (name + '-DRIFT.json'))
    check(len(drift_rows) == len(frequencies), name + ': complete gain-drift witness cohort')
    for row, w in zip(drift_rows, frequencies):
        y = q.solve(parts, source, F(w))[1]
        changed = q.solve(q.transformed(parts, F(2)), source, F(w))[1]
        gain_b = q.divide(q.plus(y, (nominal, F(0))), q.plus(changed, (nominal, F(0))))
        raw_a0, raw_a1 = y, q.plus(y, (nominal, F(0)))
        raw_b0, raw_b1 = q.times((F(2), F(0)), changed), q.times(gain_b, q.plus(changed, (nominal, F(0))))
        expected = {'original_Y': y, 'scaled_Y': changed, 'world_a_g0': q.ONE, 'world_a_g1': q.ONE, 'world_b_g0': (F(2), F(0)), 'world_b_g1': gain_b,
                    'world_a_z0': raw_a0, 'world_a_z1': raw_a1, 'world_b_z0': raw_b0, 'world_b_z1': raw_b1}
        check(row['omega_rad_s'] == w and all(row[k] == q.encode(v) for k, v in expected.items()) and raw_a0 == raw_b0 and raw_a1 == raw_b1 and y != changed and gain_b != (F(2), F(0)) and row['same_raw_observations'] is True and row['distinct_networks'] is True and row['stable_transfer_condition_violated'] is True and row['decision'] == 'ABSTAIN_REQUIRED_WITHOUT_STABILITY_EVIDENCE', name + ': exact observationally indistinguishable drift witness ' + w)
    high = bound(values[frequencies[0]][0], protocol, protocol['high_noise_stress_siemens'])
    submitted_high = read(directory / (name + '-HIGH_NOISE.json'))
    check(high['decision'] == 'ABSTAIN' and all(submitted_high.get(k) == v for k, v in high.items()), name + ': high-noise denominator gate abstains')
    return {'cases': len(cases), 'pairs': len(all_pairs), 'separated_pairs': len(actual), 'ordinary_pairs': len(full), 'selected_frequency_count': len(selected),
            'ordinary_frequency_count': len(minimum), 'raw_rows_independently_checked': rows_checked, 'all_raw_rows_inside_analytic_envelope': bool(inside_all),
            'gain_drift_witnesses': len(drift_rows), 'high_noise': high['decision'], 'conditional_complete_acceptance': actual == all_pairs}


def run(root, directory, expected_protocol, expected_artifact, output):
    wall, cpu = time.monotonic(), time.process_time()
    protocol_path = root / 'research/consequential009/analog/REFERENCE_PROTOCOL.json'
    artifact_path = directory / 'REPORT.json'
    if sha(protocol_path) != expected_protocol or sha(artifact_path) != expected_artifact:
        raise ValueError('EXTERNAL_FROZEN_REFERENCE_AUTHORITY_MISMATCH')
    protocol, artifact = read(protocol_path), read(artifact_path)
    checks = []
    def check(condition, name):
        checks.append({'name': name, 'passed': bool(condition)})
    consumed = [p for p in directory.rglob('*') if p.is_file()] + [protocol_path]
    consumed += [root / path for path in artifact['source_hashes']]
    consumed += [root / 'research/consequential009/analog' / protocol['primary_source'], root / 'research/consequential009/analog' / protocol['successor_source']]
    before = {str(p.relative_to(root)): sha(p) for p in consumed}
    check(artifact['protocol_sha256'] == expected_protocol and sha(directory / 'PROTOCOL.json') == expected_protocol, 'same frozen protocol authority')
    for path, expected in artifact['source_hashes'].items():
        check(sha(root / path) == expected, 'candidate source matches executed artifact ' + path)
    results = {name: verify_stage(root, directory, protocol, primary, check) for name, primary in [('primary', True), ('new_rlc_family', False)]}
    for name, result in results.items():
        record = artifact[name]
        check(record['cases'] == result['cases'] and record['pairs'] == result['pairs'] and record['separated_pairs'] == result['separated_pairs'] and record['ordinary_separated_pairs'] == result['ordinary_pairs'] and record['raw_rows'] == result['raw_rows_independently_checked'] and record['raw_rows_within_conditional_bound'] == result['raw_rows_independently_checked'], name + ': report complete numerical summary')
    check(artifact['raw_rows'] == sum(r['raw_rows_independently_checked'] for r in results.values()), 'all raw observation denominator retained')
    check(before == {str(p.relative_to(root)): sha(p) for p in consumed}, 'all candidate artifacts and source bytes unchanged')
    result = {'schema': 'agi-alpha/consequential009-reference-independent-acceptance/v1', 'accepted': all(c['passed'] for c in checks),
              'artifact_sha256': expected_artifact, 'protocol_sha256': expected_protocol, 'verifier_sha256': sha(__file__),
              'independent_arithmetic_sha256': sha(Path(__file__).with_name('analog_check.py')), 'candidate_source_hashes': artifact['source_hashes'],
              'consumed_hashes': before, 'checks': checks, 'results': results,
              'scope': 'Independent rational KCL, algebraic nuisance-bound reconstruction and every released raw observation; conditional ideal networks with authored reference/noise/stable-sensor assumptions. Known ratiometry is a full ordinary control. Same host/model-family procedural verification, not hardware or outside certification.',
              'bound_derivation': 'estimate-(Gnom/G)Y=(Gnom/G)(G e0-Y(e1-e0))/(gG+e1-e0). Coordinate errors <=eps give |e0|<=2eps and |e1-e0|<=4eps; denominator >=gmin*Glo-4eps. Triangle inequality and |Y|<=|ReY|+|ImY| imply declared radius. Reference scale remains [Gnom/Ghi,Gnom/Glo].',
              'consequential_counterexample': 'When gain may drift between reference-off and reference-on observations, distinct networks have exactly identical raw readings. Stability requires external evidence; these observations cannot certify it.',
              'confirmation': False, 'alpha_spent': 0, 'physical_calibration': 'UNMEASURED', 'funding': protocol['funding'],
              'resources': {'cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - wall, 'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'complete_monetary_cost': None}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--expected-protocol', required=True)
    parser.add_argument('--expected-artifact', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root.resolve(), args.directory.resolve(), args.expected_protocol, args.expected_artifact, args.output)
    print(json.dumps({'accepted': result['accepted'], 'checks': len(result['checks']), 'failed': [c['name'] for c in result['checks'] if not c['passed']], 'resources': result['resources']}))
    raise SystemExit(0 if result['accepted'] else 1)
