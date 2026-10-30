"""Source-pinned independent reconstruction of the complete finite RCL artifact."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from fractions import Fraction as F
from pathlib import Path
import resource
import time

spec = importlib.util.spec_from_file_location('independent_kcl', Path(__file__).with_name('analog_check.py'))
kcl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kcl)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def box(z, policy):
    lower, upper = map(F, policy['gain'])
    error = F(policy['absolute_coordinate_error'])
    if lower <= 0 or upper < lower or error < 0:
        raise ValueError('INVALID_UNCERTAINTY_POLICY')
    return tuple((min(x * lower, x * upper) - error, max(x * lower, x * upper) + error) for x in z)


def separate(a, b):
    return any(lo_a > hi_b or lo_b > hi_a for (lo_a, hi_a), (lo_b, hi_b) in zip(a, b))


def finite_cohort(parts, variables):
    result = []
    for switches in itertools.product([0, 1], repeat=len(variables)):
        tolerance = {name: F(9 + 2 * switch, 10) for name, switch in zip(variables, switches)}
        for scale in [F(1, 2), F(1), F(2)]:
            values = {name: str(x * tolerance.get(name, F(1)) * (F(1) / scale if kind == 'c' else scale)) for kind, name, _, _, x in parts}
            result.append({'id': 't' + ''.join(map(str, switches)) + '-a' + str(scale).replace('/', '_'),
                           'values': values, 'impedance_scale': str(scale), 'tolerance_multipliers': {k: str(v) for k, v in tolerance.items()}})
    return result


def action_universe(parts, source, frequencies):
    nodes = sorted({n for _, _, a, b, _ in parts for n in [a, b]} - {'0', 'gnd', source[0]})
    actions = []
    for w in frequencies:
        for node in nodes:
            actions.append({'id': f'v:{node}:{w}', 'kind': 'voltage_ratio', 'node': node, 'omega_rad_s': w, 'relative_acquisition_units': 1, 'units': '1'})
    for w in frequencies:
        actions.append({'id': f'y:input:{w}', 'kind': 'input_admittance', 'node': source[0], 'omega_rad_s': w, 'relative_acquisition_units': 2, 'units': 'siemens'})
    return actions


def all_responses(parts, source, cohort, actions):
    result = {a['id']: [] for a in actions}
    frequencies = list(dict.fromkeys(a['omega_rad_s'] for a in actions))
    for case in cohort:
        physical = [(k, name, a, b, F(case['values'][name])) for k, name, a, b, _ in parts]
        solved = {w: kcl.solve(physical, source, F(w)) for w in frequencies}
        for action in actions:
            volts, y = solved[action['omega_rad_s']]
            response = y if action['kind'] == 'input_admittance' else kcl.divide(volts[action['node']], (source[2], F(0)))
            result[action['id']].append(response)
    return result


def coverings(cohort, actions, responses, policies):
    pairs = set(itertools.combinations(range(len(cohort)), 2))
    covered = {}
    for action in actions:
        regions = [box(z, policies[action['kind']]) for z in responses[action['id']]]
        covered[action['id']] = {pair for pair in pairs if separate(regions[pair[0]], regions[pair[1]])}
    return pairs, covered


def minimum_full_plan(actions, covered):
    full = set().union(*covered.values())
    for size in range(len(actions) + 1):
        for chosen in itertools.combinations(actions, size):
            if set().union(*(covered[a['id']] for a in chosen)) == full:
                return chosen, full
    raise AssertionError('FULL_UNIVERSE_NOT_SELF_COVERING')


def inspect_stage(root, directory, protocol, name, check):
    primary = name == 'primary'
    source_name = 'rc-meas-ac.sp' if primary else 'MonteCarlo.sp'
    source_path = root / 'research/consequential009/analog' / source_name
    raw = source_path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    check(blob == protocol['sources'][source_name], name + ': pinned upstream raw bytes')
    parts, source = kcl.parse(source_path)
    variables = protocol['original_tolerance_elements' if primary else 'successor_tolerance_elements']
    frequencies = protocol['omega_rad_s' if primary else 'successor_omega_rad_s']
    cohort = finite_cohort(parts, variables)
    submitted_cohort = read(directory / (name + '-COHORT.json'))
    check(submitted_cohort['hypotheses'] == cohort, name + ': complete frozen cohort values and order')
    check(submitted_cohort['source_sha256'] == sha(source_path), name + ': cohort source identity')
    actions = action_universe(parts, source, frequencies)
    generated = read(directory / (name + '-GENERATED.json'))
    check(generated['actions'] == actions, name + ': complete typed action universe')
    responses = all_responses(parts, source, cohort, actions)
    policies = protocol['policies']
    pairs, covered = coverings(cohort, actions, responses, policies)
    exhaustive, full = minimum_full_plan(actions, covered)
    ids = [h['id'] for h in cohort]
    results = {}
    for suffix in ['constructed', 'voltage-only', 'unknown-gain-stress']:
        artifact = read(directory / (name + '-' + suffix + '.json'))
        used = [a['id'] for a in artifact['selected_actions']]
        check(len(used) == len(set(used)) and all(a in actions for a in artifact['selected_actions']), name + ':' + suffix + ': admitted unique actions')
        wanted_policy = json.loads(json.dumps(policies))
        if suffix == 'unknown-gain-stress':
            wanted_policy['input_admittance']['gain'] = protocol['unknown_current_gain_stress']
        check(artifact['policies'] == wanted_policy, name + ':' + suffix + ': exact frozen uncertainty')
        arm_actions = [a for a in actions if suffix != 'voltage-only' or a['kind'] == 'voltage_ratio']
        if suffix == 'voltage-only':
            check(all(a['kind'] == 'voltage_ratio' for a in artifact['selected_actions']), name + ': voltage-only grammar')
        _, arm_covered = coverings(cohort, arm_actions, responses, wanted_policy)
        expected_signatures = {a['id']: [kcl.encode(z) for z in responses[a['id']]] for a in arm_actions}
        check(artifact['exact_responses'] == expected_signatures, name + ':' + suffix + ': every exact response independently recomputed')
        chosen_coverage = set().union(*(arm_covered[a] for a in used))
        all_coverage = set().union(*arm_covered.values())
        unresolved = [[ids[i], ids[j]] for i, j in sorted(pairs - chosen_coverage)]
        check(artifact['admitted_pairs'] == len(pairs), name + ':' + suffix + ': original denominator')
        check(artifact['separated_pairs'] == len(chosen_coverage) and artifact['unresolved_pairs'] == unresolved, name + ':' + suffix + ': exact selected-plan coverage and abstentions')
        check(artifact['complete_finite_model_acceptance'] is (len(chosen_coverage) == len(pairs)), name + ':' + suffix + ': endpoint label')
        check(artifact['strong_full_experiment_unresolved_pairs'] == len(pairs - all_coverage), name + ':' + suffix + ': strongest complete experiment')
        remaining = pairs.copy()
        for revision, (entry, action_id) in enumerate(zip(artifact['generated_ancestry'], used), start=1):
            new = arm_covered[action_id] & remaining
            check(entry['revision'] == revision and entry['generated_action']['id'] == action_id and entry['newly_separated_pairs'] == len(new), name + ':' + suffix + ': ancestry selection and coverage ' + str(revision))
            if 'action_demonstrated_pair' in entry:
                actual = tuple(ids.index(x) for x in entry['action_demonstrated_pair'])
                blocker = tuple(ids.index(x) for x in entry['blocking_witness'])
                check(actual in new and blocker in remaining and entry['resolves_blocking_witness'] is (blocker in new), name + ':' + suffix + ': causally accurate ancestry ' + str(revision))
            else:
                claimed = tuple(ids.index(x) for x in entry['consequential_unresolved_pair'])
                check(claimed in new, name + ':' + suffix + ': legacy ancestry witness actually resolved ' + str(revision))
            remaining -= new
        results[suffix] = {'admitted_pairs': len(pairs), 'separated_pairs': len(chosen_coverage), 'unresolved_pairs': len(unresolved), 'complete': not unresolved, 'selected_actions': used}
    ordinary = read(directory / (name + '-ordinary-exhaustive.json'))
    ordinary_choice = ordinary['selected_actions']
    check(all(a in actions for a in ordinary_choice), name + ': ordinary admitted actions')
    ordinary_coverage = set().union(*(covered[a['id']] for a in ordinary_choice))
    check(ordinary_coverage == full and ordinary['minimum_cardinality_to_equal_full_experiment'] == len(exhaustive) and len(ordinary_choice) == len(exhaustive), name + ': independently exhaustive ordinary optimum')
    check(ordinary['separated_pairs'] == len(full) and ordinary['admitted_pairs'] == len(pairs) and ordinary['unresolved_pairs'] == len(pairs - full) and ordinary['complete_finite_model_acceptance'] is (pairs == full), name + ': ordinary full endpoint')
    results['ordinary'] = {'admitted_pairs': len(pairs), 'separated_pairs': len(full), 'minimum_actions': len(exhaustive), 'one_optimal_plan': [a['id'] for a in exhaustive]}
    results['cohort'] = len(cohort)
    results['source_blob'] = blob
    return results


def run(root, directory, expected_protocol, expected_artifact, output):
    wall, before = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
    checks = []
    def check(condition, name):
        checks.append({'name': name, 'passed': bool(condition)})
    protocol_path = root / 'research/consequential009/analog/PROTOCOL.json'
    artifact_path = directory / 'REPORT.json'
    if sha(protocol_path) != expected_protocol or sha(artifact_path) != expected_artifact:
        raise ValueError('EXTERNAL_FROZEN_AUTHORITY_MISMATCH')
    protocol, artifact = read(protocol_path), read(artifact_path)
    consumed = [p for p in directory.iterdir() if p.is_file()] + [protocol_path, root / 'research/consequential009/analog/rc-meas-ac.sp', root / 'research/consequential009/analog/MonteCarlo.sp']
    consumed += [root / path for path in artifact['source_hashes']]
    before_hashes = {str(p.relative_to(root)): sha(p) for p in consumed}
    for path, expected in artifact['source_hashes'].items():
        check(sha(root / path) == expected, 'candidate source matches executed report: ' + path)
    check(artifact['protocol_sha256'] == expected_protocol and sha(directory / 'PROTOCOL.json') == expected_protocol, 'artifact bound to same frozen protocol')
    results = {name: inspect_stage(root, directory, protocol, name, check) for name in ['primary', 'fresh_successor']}
    for name, result in results.items():
        summary = artifact[name]
        check(summary['cohort'] == result['cohort'] and summary['pairs'] == result['constructed']['admitted_pairs'] and summary['constructed_separated'] == result['constructed']['separated_pairs'] and summary['voltage_only_separated'] == result['voltage-only']['separated_pairs'] and summary['ordinary_separated'] == result['ordinary']['separated_pairs'] and summary['unknown_gain_stress_unresolved'] == result['unknown-gain-stress']['unresolved_pairs'], name + ': report complete numerical summary')
        check(summary['strong_technical_advantage'] is False, name + ': ordinary control advantage preserved')
    after_hashes = {str(p.relative_to(root)): sha(p) for p in consumed}
    check(before_hashes == after_hashes, 'all consumed candidate artifact and source bytes unchanged')
    after = resource.getrusage(resource.RUSAGE_SELF)
    result = {'schema': 'agi-alpha/consequential009-complete-independent-acceptance/v1', 'accepted': all(x['passed'] for x in checks),
              'artifact_sha256': expected_artifact, 'verifier_sha256': sha(__file__), 'protocol_sha256': expected_protocol,
              'candidate_sha256': artifact['source_hashes']['inventions/consequential009/circuit.py'],
              'independent_arithmetic_sha256': sha(Path(__file__).with_name('analog_check.py')),
              'candidate_source_hashes': artifact['source_hashes'], 'consumed_hashes': before_hashes,
              'checks': checks, 'complete_cohort_results': results,
              'scope': 'Complete source-bound finite ideal-network development report and conservative rectangular uncertainty experiment; no physical specimen or calibrated sensor has been measured, no customer has accepted a service. Same model family/host, independently implemented arithmetic; procedural verification only.',
              'confirmation': False, 'alpha_spent': 0, 'technical_novelty': 'NOT_ESTABLISHED_KNOWN_IMPEDANCE_MEASUREMENT_CONTROL_STRONGER',
              'commercial_admission': False, 'resources': {'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 'wall_seconds': time.monotonic() - wall, 'max_rss_kib': after.ru_maxrss, 'complete_monetary_cost': None}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
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
    print(json.dumps({'accepted': result['accepted'], 'checks': len(result['checks']), 'failed': [c['name'] for c in result['checks'] if not c['passed']]}))
    raise SystemExit(0 if result['accepted'] else 1)
