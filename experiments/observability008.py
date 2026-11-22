"""Connected exploratory construction using existing mapping, confinement and memory."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from flywheel.sandbox import run
from flywheel.retention import store, retrieve
from mechanisms.mapping import discover

ROOT = Path(__file__).resolve().parents[1]
INTERPRETER = 'inventions/observability008/interpreter.py'
CONDITIONS = {'algebra': 'rational_linear_ambiguity', 'measurement_contract': 'conditional_absolute_calibration'}
VERIFIER_AUTHORITY = 'verification/observability008_AUTHORITY.json'
VERIFIER_AUTHORITY_SHA256 = '8c2593ed507d605e696e97b7ff72047cf17fbf8ec2e94a22557c2bd3d67ccee7'


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def write(path, x):
    with Path(path).open('x') as stream:
        json.dump(x, stream, indent=2, allow_nan=False)
        stream.write('\n')


def graph(name, names):
    kinds = ['latent_state', 'unknown_gain', 'readout', 'absolute_reference']
    nodes = [{'id': x, 'kind': k, 'unit': 'log_scale'} for x, k in zip(names, kinds)]
    a, b, c, d = names
    return {'id': name, 'nodes': nodes, 'relations': [[a, 'influences', c], [b, 'influences', c], [d, 'fixes', a]],
            'conditions': {'linear_ambiguity_representation': True}}


def mappings(task_id):
    donor = graph('physics_gauge_reference', ['amplitude', 'instrument_gain', 'signal', 'standard'])
    target = graph(task_id, ['biological_abundance', 'reporter_gain', 'fluorescence', 'absolute_assay'])
    wrong = copy.deepcopy(donor)
    wrong['id'] = 'uncontrolled_reference_transfer'
    wrong['conditions']['unmeasured_gain_known'] = True
    reports = discover([donor, wrong], target)
    accepted = [x for x in reports if x['applicable'] and x['status'] == 'unique']
    if len(accepted) != 1:
        raise ValueError('NO_UNIQUE_APPLICABLE_CAUSAL_MAPPING')
    role_map = accepted[0]['correspondences'][0]
    fixes = [[role_map[a], relation, role_map[b]] for a, relation, b in donor['relations'] if relation == 'fixes']
    if fixes != [['absolute_assay', 'fixes', 'biological_abundance']]:
        raise ValueError('REFERENCE_OBLIGATION_NOT_MAPPED')
    return reports, {'requires_absolute_calibration': True,
                     'derivation': 'Mapped reference-fixes-latent relation requires a calibrated measurement; unknown gain cannot be treated as a standard.',
                     'role_map': role_map, 'mapping_sha256': digest(accepted[0]),
                     'origin': 'Researcher supplied gauge-fixing analogy and typed graphs; bounded code discovers correspondences. No autonomous donor search claim.'}


def worker(payload, mode):
    path = ROOT / INTERPRETER
    allowed = {'language', 'dimension', 'constraints', 'measurements', 'requires_absolute_calibration',
               'max_plans', 'mode', 'plan', 'names', 'known_scaling_directions', 'provenance'}
    if set(payload) - allowed:
        raise ValueError('UNSUPPORTED_TASK_FIELD_OR_OBLIGATION')
    body = {k: payload[k] for k in ['language', 'dimension', 'constraints', 'measurements', 'requires_absolute_calibration', 'max_plans']}
    body['mode'] = mode
    if mode == 'execute':
        body['plan'] = payload['plan']
    receipt = run(path, 'interpret', body, hashlib.sha256(path.read_bytes()).hexdigest(),
                  {'wall_seconds': 30, 'cpu_seconds': 20, 'memory_bytes': 256 * 1024**2})
    if receipt['state'] != 'COMPLETE':
        raise RuntimeError('CONFINED_PROGRAM_FAILED ' + json.dumps(receipt))
    return receipt


def construct(task_path, output):
    begin = time.monotonic()
    task_path, output = Path(task_path), Path(output)
    task = json.loads(task_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'PENDING.json', {'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(), 'status': 'INCOMPLETE_UNTIL_REPORT'})
    reports, compiled = mappings(task_path.parent.name)
    write(output / 'MAPPINGS.json', reports)
    write(output / 'COMPILED_OBLIGATION.json', compiled)
    task['requires_absolute_calibration'] = compiled['requires_absolute_calibration']
    built = worker(task, 'construct')
    write(output / 'CONSTRUCTION.json', built)
    strong = worker(task, 'construct')
    write(output / 'STRONG_CONVENTIONAL_GREEDY.json', strong)
    exhaustive = worker(task, 'ordinary')
    write(output / 'ORDINARY_EXHAUSTIVE.json', exhaustive)
    program = copy.deepcopy(task)
    program['plan'] = built['worker']['result']['plan']
    execution = worker(program, 'execute')
    write(output / 'EXECUTION.json', execution)
    result = built['worker']['result']
    artifact = {'schema': 'agi-alpha/linear-ambiguity-delivery008/v1', 'task_sha256': hashlib.sha256(task_path.read_bytes()).hexdigest(),
                'interpreter_sha256': built['interpreter_sha256'], 'mapping_sha256': compiled['mapping_sha256'], 'plan': result['plan'],
                'cost_units': result['cost_units'], 'remaining_detected_ambiguity': result['remaining_ambiguity'],
                'physical_calibration_acquired': False, 'scope': result['scope'],
                'strong_conventional_tie': result['plan'] == strong['worker']['result']['plan'],
                'exhaustive_cost_tie': result['cost_units'] == exhaustive['worker']['result'].get('cost_units'),
                'commercial_cohort_admitted': False, 'scientific_superiority_established': False}
    write(output / 'DELIVERY.json', artifact)
    report = {'artifact_sha256': hashlib.sha256((output / 'DELIVERY.json').read_bytes()).hexdigest(),
              'wall_seconds': time.monotonic() - begin, 'decision': 'RETAIN_CONVENTIONAL: constructed calibrated measurement basis ties ordinary complete methods.',
              'mechanism_provenance': 'Known weighted linear-matroid basis construction; no new mathematical algorithm or autonomous invention claim.',
              'same_checker_disclosure': 'All builder-lane arms share this exact rational interpreter; independent verification is a separate required stage.',
              'substantive_next_action': 'Verify domain counterexamples and practical intervention consequence against attainable calibration; do not promote rank removal to physical identifiability.'}
    write(output / 'REPORT.json', report)
    return report


def retain_and_use(previous, acceptance_path, fresh_path, output):
    previous, output = Path(previous), Path(output)
    acceptance = json.loads(Path(acceptance_path).read_text())
    artifact = json.loads((previous / 'DELIVERY.json').read_text())
    artifact_hash = hashlib.sha256((previous / 'DELIVERY.json').read_bytes()).hexdigest()
    current_hash = hashlib.sha256((ROOT / INTERPRETER).read_bytes()).hexdigest()
    authority_path = ROOT / VERIFIER_AUTHORITY
    if VERIFIER_AUTHORITY_SHA256 is None or hashlib.sha256(authority_path.read_bytes()).hexdigest() != VERIFIER_AUTHORITY_SHA256:
        raise ValueError('PINNED_VERIFIER_AUTHORITY_REQUIRED')
    authority = json.loads(authority_path.read_text())
    if authority.get('schema') != 'agi-alpha/verifier-authority008/v1' or authority.get('scope') != 'supplied-linear-ambiguity-plan-only':
        raise ValueError('VERIFIER_AUTHORITY_SCHEMA')
    permit = authority.get('accepted_artifacts', {}).get(artifact_hash)
    if type(permit) is not dict or permit.get('receipt_sha256') != hashlib.sha256(Path(acceptance_path).read_bytes()).hexdigest():
        raise ValueError('RECEIPT_NOT_AUTHORIZED_FOR_ARTIFACT')
    if permit.get('interpreter_sha256') != current_hash or permit.get('task_sha256') != artifact.get('task_sha256'):
        raise ValueError('AUTHORITY_SOURCE_OR_TASK_MISMATCH')
    verifier_path = Path(authority['verifier_source_path'])
    if verifier_path.is_absolute() or '..' in verifier_path.parts or not verifier_path.parts or verifier_path.parts[0] != 'verification':
        raise ValueError('VERIFIER_SOURCE_SCOPE')
    if (ROOT / verifier_path).is_symlink() or hashlib.sha256((ROOT / verifier_path).read_bytes()).hexdigest() != authority['verifier_source_sha256'] or acceptance.get('verifier_source_sha256') != authority['verifier_source_sha256']:
        raise ValueError('VERIFIER_SOURCE_IDENTITY')
    if acceptance.get('accepted') is not True or acceptance.get('artifact_sha256') != artifact_hash or acceptance.get('interpreter_sha256') != current_hash or artifact['interpreter_sha256'] != current_hash:
        raise ValueError('EXACT_VERIFIER_ACCEPTANCE_REQUIRED')
    if acceptance.get('scope') != 'supplied-linear-ambiguity-plan-only':
        raise ValueError('UNSUPPORTED_ACCEPTANCE_SCOPE')
    output.mkdir(parents=True, exist_ok=False)
    record = {'instrument': {'path': INTERPRETER, 'sha256': current_hash},
              'applicability': {'schema_version': 1, 'conditions': CONDITIONS, 'assumptions': ['Supplied rows faithfully describe the claimed ambiguity family.', 'Calibrated measurements are conditional specifications, not physically acquired evidence.'],
                                'uncertainty': 'No completeness for non-scale symmetries, finite noisy data, physical feasibility or economics.',
                                'failures': [{'conditions': {'unknown_gain_treated_as_known': True}, 'reason': 'Extra uncalibrated readouts preserve scale ambiguity.'}]},
              'generative_operator': {'language': 'linear-ambiguity-plan-v1', 'program': {'mode': 'construct', 'requires_absolute_calibration': True, 'max_plans': 256}},
              'provenance': {'origin': 'Acquired after the executed real-model analysis and independently checked rank/calibration defect.', 'artifact_sha256': artifact_hash, 'acceptance_sha256': hashlib.sha256(Path(acceptance_path).read_bytes()).hexdigest()},
              'verification': {'status': 'verified-in-scope', 'receipt_sha256': digest(acceptance)},
              'costs': {'complete_monetary_cost': None, 'source': 'Original campaign allocation; not earned-funded construction.'},
              'exposure': [artifact['task_sha256']], 'supersedes': []}
    memory = output / 'memory'
    ident = store(memory, record)
    fetched = retrieve(memory, {'schema_version': 1, 'conditions': CONDITIONS}, ROOT)
    write(output / 'RETRIEVAL.json', fetched)
    if len(fetched['records']) != 1:
        raise ValueError('VERIFIED_MEMORY_NOT_RETRIEVED')
    fresh = json.loads(Path(fresh_path).read_text())
    program = fetched['records'][0]['record']['generative_operator']['program']
    fresh['requires_absolute_calibration'] = program['requires_absolute_calibration']
    fresh['max_plans'] = program['max_plans']
    inherited = worker(fresh, program['mode'])
    ordinary = worker(fresh, 'construct')
    reset = worker(fresh, 'construct')
    without_calibration = copy.deepcopy(fresh)
    without_calibration['measurements'] = [x for x in fresh['measurements'] if not x['calibrated']]
    removed = worker(without_calibration, 'construct')
    for name, receipt in [('INHERITED', inherited), ('EQUAL_CONTENT_ORDINARY_REUSE', ordinary), ('RESET_WITH_STRONG_METHOD', reset), ('CALIBRATION_REMOVED', removed)]:
        write(output / (name + '.json'), receipt)
    write(output / 'REPORT.json', {'retained_capability_id': ident, 'fresh_task_sha256': hashlib.sha256(Path(fresh_path).read_bytes()).hexdigest(),
          'fresh_to_record': hashlib.sha256(Path(fresh_path).read_bytes()).hexdigest() not in record['exposure'],
          'freshness_scope': 'Different public input; development-exposed. Byte novelty is not independent sampling or protected confirmation.',
          'inherited_plan': inherited['worker']['result'], 'ordinary_reuse_plan': ordinary['worker']['result'],
          'inheritance_advantage': 'NOT_ESTABLISHED: same-content ordinary reuse and strong reset receive the same known basis method.',
          'earned_funding': 'DEFERRED: qualified unrestricted simulated earnings are zero; technical transfer uses original authorized resources.',
          'full_flywheel': 'NOT_DEMONSTRATED'})


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('construct')
    c.add_argument('--task', type=Path, default=ROOT / 'research/observability008/elowitz/model_constraints.json')
    c.add_argument('--output', type=Path, required=True)
    r = sub.add_parser('retain-use')
    for key in ['previous', 'acceptance', 'fresh', 'output']:
        r.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    if a.command == 'construct':
        print(json.dumps(construct(a.task, a.output)))
    else:
        retain_and_use(a.previous, a.acceptance, a.fresh, a.output)


if __name__ == '__main__':
    main()
