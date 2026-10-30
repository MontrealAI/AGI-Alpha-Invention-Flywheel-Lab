import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from flywheel import retention
from inventions.lifetime007.compiler import construct, construct_from_operator, remap_operator, validate
from inventions.lifetime007.execute import execute

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_file_spec():
    operations = ['file_close', 'file_stream', 'file_fsync', 'file_write', 'file_open']
    names = ['publish', 'close', 'prepare', 'acquire', 'commit']
    return {'schema': 'agi-alpha/lifetime-spec007/v1', 'task_id': 'fresh-framed-file-export', 'domain': 'file',
            'effects': [{'id': name, 'operation': operation, 'resource': 'framed-export-fd'} for name, operation in zip(names, operations)],
            'blocks': [{'effects': ['prepare', 'publish'], 'separable': True},
                       {'effects': ['commit'], 'separable': False}, {'effects': ['close'], 'separable': False},
                       {'effects': ['acquire'], 'separable': False}],
            'obligations': {'durable_before_visible': True, 'live_during_consumption': True, 'close_on_exit': True}}


def ordinary_explicit(spec):
    roles = validate(spec)
    order = [roles[k] for k in ['acquire', 'prepare', 'durable', 'consume', 'release']]
    split = [i for i, block in enumerate(spec['blocks']) if len(block['effects']) > 1]
    return {'schema': 'agi-alpha/lifetime-plan007/v1', 'task_id': spec['task_id'],
            'spec_sha256': retention_hash(spec), 'mapping': construct(spec)['mapping'], 'status': 'CONSTRUCTED',
            'order': order, 'split_blocks': split, 'search_attempts': 0, 'failed_attempts': [],
            'origin': 'Competent ordinary explicit commit-before-publication and finally-close combination, supplied the same operation semantics and contract.'}


def retention_hash(value):
    return hashlib.sha256(retention.canonical(value)).hexdigest()


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.monotonic(), time.process_time()
    source = json.loads((ROOT/'campaign/cycle-007/LIFETIME_SPEC.json').read_text())
    target = fresh_file_spec()
    intact = construct(source, allow_factorization=False)
    acquired = construct(source)
    source_runs = {str(fault): execute(source, acquired, ['first', 'second', 'third'], fault)
                   for fault in [None, 'commit', 'mid_consume', 'mid_interrupt']}
    acquisition = {'plan': acquired, 'executions': source_runs}
    write(output/'ACQUISITION.json', acquisition)
    record = {
        'instrument': {'path': 'inventions/lifetime007/compiler.py', 'sha256': sha(ROOT/'inventions/lifetime007/compiler.py')},
        'applicability': {'schema_version': 1, 'conditions': {'effect_family': 'durable-live-reader', 'separable': True},
                          'assumptions': ['Five reviewed typed effects', 'Commit and release can be separated without changing authorized writes', 'At most 64 bounded records'],
                          'uncertainty': 'No unknown APIs, arbitrary generated code, storage power-loss guarantee or novel algorithm claim.',
                          'failures': [{'conditions': {'separable': False}, 'reason': 'No authority to factor inseparable finalizer.'}]},
        'generative_operator': {'language': 'typed-effect-factor-v1', 'program': acquired['generated_operator']},
        'provenance': {'developer_supplied': ['Effect semantics', 'Donor contract', 'Search algorithm', 'Runtime adapters'],
                       'constructed': ['Block factoring choice', 'Target execution order', 'Remapped file operator'],
                       'source_task': source, 'executor_sha256': sha(ROOT/'inventions/lifetime007/execute.py')},
        'verification': {'status': 'verified-in-scope', 'receipt_sha256': sha(output/'ACQUISITION.json')},
        'costs': {'acquisition_cpu_seconds_so_far': time.process_time()-cpu, 'model_inference_usd': None, 'complete_lifecycle_usd': None,
                  'receipt_scope': 'Development execution checked within runner; independent final verifier is separate and not implied by this field.'},
        'exposure': ['Source development tasks exposed; successor here is an authored fresh domain transfer, not population confirmation'],
        'supersedes': []}
    identity = retention.store(output/'memory', record)
    retrieval = retention.retrieve(output/'memory', {'schema_version': 1, 'conditions': {'effect_family': 'durable-live-reader', 'separable': True}}, ROOT)
    if len(retrieval['records']) != 1:
        raise RuntimeError('RETRIEVAL_FAILED')
    inherited_record = retrieval['records'][0]['record']
    mapped = remap_operator(inherited_record['generative_operator']['program'], inherited_record['provenance']['source_task'], target)
    ordinary_mapped = remap_operator(copy.deepcopy(acquired['generated_operator']), copy.deepcopy(source), target)
    arm_builders = {
        'frozen_old_capability': lambda: construct(target, allow_factorization=False),
        'reset_equal_tools': lambda: construct(target),
        'inherited_retrieved_remapped': lambda: construct_from_operator(target, mapped),
        'ordinary_equivalent_content_reuse': lambda: construct_from_operator(target, ordinary_mapped),
        'strongest_conventional_explicit_split': lambda: ordinary_explicit(target)}
    arms = {}
    for name, builder in arm_builders.items():
        wall0, cpu0 = time.monotonic(), time.process_time()
        plan = builder()
        result = execute(target, plan, ['report:42', 'Unicode:α', 'line\nbreak']) if plan['status'] == 'CONSTRUCTED' else None
        arms[name] = {'plan': plan, 'execution': result, 'wall_seconds': time.monotonic()-wall0,
                      'cpu_seconds': time.process_time()-cpu0, 'accepted': result is not None and result['error'] is None and result['output'] == ['report:42', 'Unicode:α', 'line\nbreak'] and result['closed']}
    report = {'schema': 'agi-alpha/lifetime-construction-transfer007/v1', 'source_spec': source, 'fresh_target_spec': target,
              'intact_finalizer': intact, 'acquisition': acquisition, 'retained_identity': identity, 'retrieval': retrieval,
              'remapped_operator': mapped, 'successor_arms': arms,
              'decisions': {'bounded_operator_construction': 'DEMONSTRATED_IN_GRAMMAR',
                            'newly_feasible_against_strongest_complete_route': 'FAILED: ordinary explicit split already meets the contract',
                            'combination_advantage': 'FAILED: strongest ordinary combination ties accepted outcome',
                            'experience_advantage': 'FAILED: equivalent-content ordinary reuse ties; lifecycle acquisition costs remain unknown',
                            'generated_discovery_policy_improvement': 'UNRUN: no independently useful generated policy change proposed',
                            'earned_funded_successor': 'UNRUN: no commercially qualified unrestricted earnings; this technical transfer uses campaign allocation'},
              'source_sha256': {p: sha(ROOT/p) for p in ['experiments/lifetime007.py', 'inventions/lifetime007/compiler.py', 'inventions/lifetime007/execute.py', 'flywheel/retention.py']},
              'wall_seconds': time.monotonic()-started, 'self_cpu_seconds': time.process_time()-cpu,
              'full_cost_unknowns': ['Development model inference', 'historical acquisition', 'deployment integration', 'support', 'buyer participation'],
              'statistical_alpha_spent': 0, 'scope': 'Finite development engineering comparison, all authored cases exposed; no population or commercial confirmation.'}
    write(output/'REPORT.json', report)
    write(output/'COMPLETE.json', {'report_sha256': sha(output/'REPORT.json')})
    if arms['inherited_retrieved_remapped']['accepted'] is not True or arms['ordinary_equivalent_content_reuse']['accepted'] is not True:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
