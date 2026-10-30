"""Recompute all twelve successor controls and replay read-only native retrieval."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('own_frozen_complete_checker', Path(__file__).with_name('cohort_check.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def run(root, directory, expected_result, output):
    wall, cpu = time.monotonic(), time.process_time()
    report_path = directory / 'RESULT.json'
    if c.sha(report_path) != expected_result:
        raise ValueError('EXTERNAL_RESULT_AUTHORITY_MISMATCH')
    result = c.read(report_path)
    protocol_path = root / 'research/consequential009/analog/PROTOCOL.json'
    if c.sha(protocol_path) != '9a28e4202fecbe46769f82a20a8aeedb92020cdd2701a6d941b6694d5363d7ad':
        raise ValueError('ORIGINAL_PROTOCOL_CHANGED')
    protocol = c.read(protocol_path)
    checks = []
    def check(condition, name):
        checks.append({'name': name, 'passed': bool(condition)})
    parts, source = c.kcl.parse(root / 'research/consequential009/analog/MonteCarlo.sp')
    cohort = c.finite_cohort(parts, protocol['successor_tolerance_elements'])
    universe = c.action_universe(parts, source, protocol['successor_omega_rad_s'])
    responses = c.all_responses(parts, source, cohort, universe)
    pairs, covered = c.coverings(cohort, universe, responses, protocol['policies'])
    expected_triples = {(p, t, m) for p in ['old-greedy', 'new-reverse-delete'] for t in ['old-voltage', 'new-current'] for m in ['retained', 'equal-content-ordinary-reuse', 'reset']}
    check({(a['policy'], a['toolbox'], a['memory']) for a in result['arms']} == expected_triples and len(result['arms']) == 12, 'all twelve crossed policy/toolbox/memory arms')
    groups = {}
    for arm in result['arms']:
        label = arm['policy'] + '__' + arm['toolbox'] + '__' + arm['memory']
        plan = c.read(directory / 'plans' / (label + '.json'))
        selected = plan['selected_actions']
        permitted = [a for a in universe if arm['toolbox'] != 'old-voltage' or a['kind'] == 'voltage_ratio']
        check(all(a in permitted for a in selected), label + ': admitted observations')
        achieved = set().union(*(covered[a['id']] for a in selected))
        units = sum(a['relative_acquisition_units'] for a in selected)
        check(arm['admitted_hypotheses'] == len(cohort) and arm['admitted_pairs'] == len(pairs) and arm['separated_pairs'] == len(achieved) and arm['accepted'] is (achieved == pairs), label + ': original complete cohort endpoint')
        check(arm['actions'] == len(selected) and arm['relative_acquisition_units'] == units and plan['selected_relative_acquisition_units'] == units, label + ': actual selected actions and relative cost')
        expected = {a['id']: [c.kcl.encode(z) for z in responses[a['id']]] for a in permitted}
        check(plan['exact_responses'] == expected, label + ': every numerical response independently reconstructed')
        check(arm['generated_inherited_flag'] is (arm['memory'] != 'reset' and arm['toolbox'] == 'new-current'), label + ': inherited content flag scope')
        groups.setdefault((arm['policy'], arm['toolbox']), []).append((arm['accepted'], len(achieved), len(selected), units))
    tied = all(len(set(group)) == 1 for group in groups.values())
    check(tied and result['equal_content_and_reset_tie'] is True, 'equal-content ordinary reuse and reset tie retained memory')
    ordinary, full = c.minimum_full_plan(universe, covered)
    check(result['strong_ordinary']['separated_pairs'] == len(full) and result['strong_ordinary']['minimum_cardinality_to_equal_full_experiment'] == len(ordinary), 'independent complete ordinary control retained')
    native = root / 'flywheel/retention.py'
    raw = native.read_bytes()
    if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != '09044700a172f35f55e2ef9cfaf879894d2108ed':
        raise ValueError('NATIVE_RETRIEVAL_SOURCE_CHANGED')
    native_spec = importlib.util.spec_from_file_location('pinned_native_read_only_retention', native)
    memory = importlib.util.module_from_spec(native_spec)
    native_spec.loader.exec_module(memory)
    target = {'schema_version': 1, 'conditions': {'model_family': 'passive-RCL-one-port', 'observable': 'coherent-normalized-admittance', 'sensor_gain': 'bounded'}}
    store = directory / 'memory'
    before = {p.name: c.sha(p) for p in store.glob('*.json')}
    retrieved = memory.retrieve(store, target, root)
    refused = memory.retrieve(store, {'schema_version': 1, 'conditions': {**target['conditions'], 'sensor_gain': 'unbounded'}}, root)
    check(retrieved == c.read(directory / 'RETRIEVAL.json') and refused == c.read(directory / 'NEGATIVE_RETRIEVAL.json'), 'actual native read-only retrieval reproduces source and failure-scope decisions')
    check(len(retrieved['records']) == 1 and not refused['records'] and bool(refused['failures']), 'bounded applicability returns record and unbounded gain refuses')
    check(before == {p.name: c.sha(p) for p in store.glob('*.json')}, 'retained evidence bytes unchanged')
    record = retrieved['records'][0]
    check(record['id'] == result['record_sha256'] and record['record']['instrument']['sha256'] == result['instrument_sha256'] == c.sha(root / 'inventions/consequential009/circuit.py'), 'retrieved instrument identity matches current exact candidate')
    check(result['decision']['retained_discovery_advantage'] == 'NOT_ESTABLISHED_EQUAL_CONTENT_AND_RESET_TIE' and result['decision']['earned_funding'].startswith('NONE'), 'no discovery or earned-funding advantage manufactured')
    report = {'schema': 'agi-alpha/consequential009-independent-retention-review/v1', 'passed': all(x['passed'] for x in checks),
              'result_sha256': expected_result, 'verifier_sha256': c.sha(__file__), 'independent_math_sha256': c.sha(Path(__file__).with_name('analog_check.py')),
              'native_memory_source_sha256': c.sha(native), 'checks': checks, 'arms': 12, 'cohort': len(cohort), 'pairs_per_arm': len(pairs),
              'scope': 'Independent numerical reconstruction plus actual read-only source-checked native retrieval. Store/construction invocation is inspected in original monitored source/evidence, not rerun here. Fixed source grammar already contains the discovery rule; reset ties, so actual retrieval is not a causal discovery benefit. Different topology cohort was exposed in development, not untouched confirmation.',
              'resources': {'cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - wall, 'complete_monetary_cost': None}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--expected-result', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root.resolve(), args.directory.resolve(), args.expected_result, args.output)
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks']), 'failed': [c['name'] for c in result['checks'] if not c['passed']]}))
    raise SystemExit(0 if result['passed'] else 1)
