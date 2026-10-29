"""The executing mapping, criticism, acquisition and fresh-reuse chain."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

from flywheel import sandbox
from flywheel.retention import retrieve
from . import construct, criticism, executor, mapping, memory

ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = {'invariants': [{'id': 'interruption-record', 'kind': 'mark_after_reservation'},
                               {'id': 'no-false-completion', 'kind': 'no_commit_on_failure'}],
                 'effect_scope': 'exclusive_local_output'}


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def supported_specification(task, specification):
    """Refuse any obligation the fixed file verifier cannot actually assess."""
    if type(specification) is not dict or set(specification) - {'invariants', 'effect_scope'}:
        raise ValueError('UNSUPPORTED_SPECIFICATION_FIELDS')
    if specification.get('effect_scope', 'exclusive_local_output') != 'exclusive_local_output':
        raise ValueError('UNSUPPORTED_EFFECT_SCOPE')
    invariants = specification.get('invariants')
    if type(invariants) is not list or not invariants or len(invariants) > 48:
        raise ValueError('INVALID_INVARIANT_LIST')
    phases = {phase['id'] for phase in task['phases']}
    identities = set()
    for invariant in invariants:
        if type(invariant) is not dict or set(invariant) - {'id', 'kind', 'phase_ids'}:
            raise ValueError('UNSUPPORTED_INVARIANT_FIELDS')
        if type(invariant.get('id')) is not str or not invariant['id'] or invariant['id'] in identities:
            raise ValueError('INVALID_OR_DUPLICATE_INVARIANT_ID')
        identities.add(invariant['id'])
        if type(invariant.get('kind')) is not str or invariant['kind'] not in {'mark_after_reservation', 'no_commit_on_failure'}:
            raise ValueError('UNSUPPORTED_ACTUAL_EFFECT_INVARIANT')
        selection = invariant.get('phase_ids', list(phases))
        if type(selection) is not list or not selection or any(type(phase) is not str or phase not in phases for phase in selection) or len(set(selection)) != len(selection):
            raise ValueError('INVALID_INVARIANT_SCOPE')
    return invariants


def example(prefix='acquisition', reverse=False):
    names = [prefix + '-' + x for x in ('allocate', 'capture', 'derive', 'publish')]
    phases = [{'id': name, 'kind': kind, 'deps': [] if i == 0 else [names[i-1]], 'unit': 'event'}
              for i, (name, kind) in enumerate(zip(names, ('reserve', 'capture', 'compute', 'commit')))]
    task = {'id': prefix, 'phases': list(reversed(phases)) if reverse else phases,
            'conditions': {'failure': 'catchable_exception', 'effects': 'exclusive_local_output'}}
    donor = {'id': 'transaction-role-fragment', 'nodes': [
        {'id': r, 'kind': k, 'unit': 'event'} for r, k in zip(('allocate', 'prepare', 'apply', 'commit'), ('reserve', 'capture', 'compute', 'commit'))],
        'relations': [['allocate', 'precedes', 'prepare'], ['prepare', 'precedes', 'apply'], ['apply', 'precedes', 'commit']],
        'conditions': task['conditions'], 'obligations': [{'kind': 'protect', 'role_ids': ['prepare']}],
        'provenance': 'Developer-authored partial transaction-role mechanism, not a discovered scientific principle'}
    return task, [donor], mapping.target_from_task(task)


def verify(task, program, output, specification=None):
    """Final unchanged objective is outside candidate and acquisition control."""
    output = Path(output)
    specification = SPECIFICATION if specification is None else specification
    output.mkdir(parents=True, exist_ok=False)
    try:
        invariants = supported_specification(task, specification)
    except ValueError as error:
        refused = {'passed': False, 'state': 'refused', 'checks': [], 'reason': str(error),
                   'specification_sha256': memory.digest(specification), 'candidate_sha256': memory.digest(program),
                   'scope': 'No verification receipt is issued for unsupported or malformed obligations'}
        write(output / 'VERIFICATION.json', refused)
        return refused
    if program is None:
        result = {'passed': False, 'checks': [], 'reason': 'NO_EXECUTABLE_PROGRAM'}
        write(output / 'VERIFICATION.json', result)
        return result
    construct.validate(task, program)
    nodes = {p['id']: p for p in task['phases']}
    normal = executor.execute(task, program, output / 'normal')
    checks = []
    for index, phase in enumerate(program['order']):
        confined = sandbox.run(ROOT / 'mechanisms/construct.py', 'interpret',
                    {'task': task, 'program': program, 'interrupt_at': phase, 'interrupt_stage': 'during'}, file_sha(ROOT / 'mechanisms/construct.py'))
        actual_output = output / ('failure-%03d' % index)
        actual = executor.execute(task, program, actual_output, phase)
        if nodes[phase]['kind'] == 'reserve':
            passed = not actual['directory_created'] and not actual['complete_exists']
        else:
            observed = confined.get('worker', {}).get('result', {})
            passed = confined['state'] == 'COMPLETE'
            for invariant in invariants:
                if phase not in invariant.get('phase_ids', program['order']):
                    continue
                if invariant['kind'] == 'mark_after_reservation':
                    passed = passed and observed.get('interrupted_marker') is True and actual['interrupted_marker'] is True
                if invariant['kind'] == 'no_commit_on_failure':
                    passed = passed and observed.get('complete_exists') is False and actual['complete_exists'] is False
        checks.append({'phase': phase, 'passed': passed, 'confined': confined, 'actual': actual})
    result = {'passed': normal['completed'] and normal['complete_exists'] and all(x['passed'] for x in checks),
              'normal': normal, 'checks': checks, 'specification_sha256': memory.digest(specification),
              'candidate_sha256': memory.digest(program), 'scope': 'Catchable phase interruptions and normal dependency-ordered local-file effects'}
    write(output / 'VERIFICATION.json', result)
    return result


def develop(task, donors, target_graph, output, memory_root, use_mapping=True, use_critic=True, specification=None):
    started, cpu = time.monotonic(), time.process_time()
    output, memory_root = Path(output), Path(memory_root)
    specification = SPECIFICATION if specification is None else specification
    output.mkdir(parents=True, exist_ok=False)
    reports = mapping.discover(donors, target_graph)
    choices = [(donor, report) for donor in donors for report in reports if report['source'] == donor['id'] and report['status'] == 'unique']
    if use_mapping and not choices:
        result = {'status': 'refused', 'reason': 'NO_UNIQUE_APPLICABLE_MAPPING', 'discovery': reports, 'retained': None}
        write(output / 'RESULT.json', result)
        return result
    mapped = mapping.compile_mapping(choices[0][0], target_graph, choices[0][1]['correspondences'][0]) if use_mapping else None
    if not use_mapping:
        result = {'status': 'refused', 'reason': 'MAPPING_REMOVED; separately labeled conventional fallback remains available', 'retained': None, 'discovery': reports}
        write(output / 'RESULT.json', result)
        return result
    before = construct.construct(task, mapped['obligations'], max_candidates=64)
    write(output / 'DISCOVERY.json', {'reports': reports, 'compiled_mapping': mapped, 'input_sha256': memory.digest({'task': task, 'donors': donors, 'target': target_graph})})
    write(output / 'BEFORE.json', before)
    before_verification = verify(task, before['program'], output / 'before-check', specification)
    objections, adjudications, obligations = [], [], []
    if use_critic:
        for item in before_verification['checks']:
            actual = copy.deepcopy(item['actual'])
            actual['interrupt_stage'] = 'during'
            generated = criticism.critique(task, before['program'], actual, specification,
                                         {'constructor': file_sha(ROOT / 'mechanisms/construct.py'), 'executor': file_sha(ROOT / 'mechanisms/executor.py')})
            for objection in generated:
                number = len(adjudications)
                def reproduce(frozen_task, frozen_program, phase, number=number):
                    result = executor.execute(frozen_task, frozen_program, output / ('adjudication-%03d' % number), phase)
                    result['interrupt_stage'] = 'during'
                    return result
                decision = criticism.adjudicate(objection, reproduce)
                objections.append(objection)
                adjudications.append(decision)
                obligations.extend(criticism.derive(decision, task))
    write(output / 'CRITICISM.json', {'objections': objections, 'adjudications': adjudications, 'derived_obligations': obligations})
    after = construct.construct(task, mapped['obligations'] + obligations, max_candidates=64)
    write(output / 'AFTER.json', after)
    after_verification = verify(task, after['program'], output / 'after-check', specification)
    retained, refused = None, None
    receipt = {'before_sha256': memory.digest(before['program']), 'after_sha256': memory.digest(after['program']),
               'before_passed': before_verification['passed'], 'after_passed': after_verification['passed'],
               'before_verification_sha256': memory.digest(before_verification), 'after_verification_sha256': memory.digest(after_verification),
               'objective_scope': copy.deepcopy(specification),
               'verifier_source': {'path': 'mechanisms/pipeline.py', 'sha256': file_sha(ROOT / 'mechanisms/pipeline.py')},
               'costs': {'wall_seconds': time.monotonic()-started, 'cpu_seconds': time.process_time()-cpu, 'full_cost': None}}
    try:
        retained = memory.retain(memory_root, task, mapped, before['program'], after['program'], obligations, receipt, ROOT)
    except ValueError as error:
        refused = str(error)
    result = {'status': 'verified-in-scope' if after_verification['passed'] else 'failed',
              'mapping': mapped, 'before': before, 'after': after, 'before_passed': before_verification['passed'],
              'after_passed': after_verification['passed'], 'obligations': obligations, 'retained': retained,
              'retention_refusal': refused, 'verification_receipt': receipt,
              'mechanism_path': ['discovery', 'mapped obligations', 'strategy', 'actual counterexamples', 'adjudication', 'derived obligations', 'generated repair', 'verification', 'acquired role rewrite', 'immutable store'],
              'resources': receipt['costs'], 'exposure': 'Development engineering case; not scientific confirmation'}
    write(output / 'RESULT.json', result)
    return result


def combinations(task, donors, target_graph, output, memory_root, successor_task=None):
    """Acquire two complementary instruments, then check all fresh bundles externally."""
    output, memory_root = Path(output), Path(memory_root)
    output.mkdir(parents=True, exist_ok=False)
    acquired = []
    for index, invariant in enumerate(SPECIFICATION['invariants']):
        scope = {'invariants': [copy.deepcopy(invariant)], 'effect_scope': SPECIFICATION['effect_scope']}
        learned = develop(task, donors, target_graph, output / ('acquire-%d' % index), memory_root, specification=scope)
        acquired.append({'scope': scope, 'result': learned})
    if successor_task is None:
        fresh, _, fresh_graph = example(task['id'] + '-complementary-successor', True)
    else:
        fresh, fresh_graph = successor_task, mapping.target_from_task(successor_task)
    loaded = retrieve(memory_root, {'schema_version': 1, 'conditions': fresh['conditions']}, ROOT)
    records = loaded['records']
    arms = {}
    for name in ('inheritance', 'ordinary'):
        budget = {'max_candidates': 64, 'max_combinations': 4, 'max_bundle_size': 2}
        generated = (memory.generate_bundle(memory_root, fresh, donors, ROOT, budget) if name == 'inheritance'
                     else memory.ordinary_bundle(records, fresh, donors, ROOT, budget))
        checked = []
        for index, candidate in enumerate(generated['candidates']):
            result = verify(fresh, candidate.get('program'), output / (name + '-bundle-%d' % index))
            checked.append({'construction': candidate, 'verification': result, 'passed': result['passed']})
        arms[name] = {'generated': generated, 'checks': checked,
                      'selection_rule': 'Smallest number of records satisfying the unchanged full objective; all checks and costs retained',
                      'passed': any(item['passed'] for item in checked)}
    result = {'acquisition': acquired, 'fresh_task': fresh, 'fresh_graph': fresh_graph, 'retrieval': loaded,
              'arms': arms, 'scope': 'Two prospectively separated invariant-scoped engineering instruments; neither alone implies full service acceptance',
              'complete_lifecycle_cost': None, 'no_structured_memory_superiority_claim': True}
    write(output / 'COMBINATIONS.json', result)
    return result


def policy_comparison(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    exposed = json.loads((ROOT / 'evidence/cycle-004/verifier-fresh-final/REPORT.json').read_text())['cases']
    cases = []
    for index, item in enumerate(exposed):
        original = item['task']
        predecessors = {phase: [a for a, b in original['dependencies'] if b == phase] for phase in original['phases']}
        task = {'id': 'exposed-policy-%d' % index, 'phases': [
            {'id': p, 'kind': 'reserve' if p == 'reserve' else 'commit' if p == 'complete' else 'action',
             'deps': predecessors[p], 'unit': 'event'} for p in original['phases']]}
        obligations = [{'kind': 'protect', 'phase_ids': [p for p in original['phases'] if p != 'reserve']},
                       {'kind': 'atomic_publish', 'phase_ids': ['complete']}]
        cells = {}
        for policy in ('old', 'new'):
            for tools, capabilities in [('old', ['protect']), ('new', ['protect', 'atomic_publish'])]:
                built = construct.evaluate_policy(task, policy, capabilities, obligations, max_candidates=64)
                checked = verify(task, built.get('program'), output / ('case-%d-%s-%s' % (index, policy, tools)))
                cells[policy + '_policy_' + tools + '_tools'] = {'construction': built, 'verification': checked, 'passed': checked['passed']}
        cases.append({'task': task, 'cells': cells})
    scores = {key: sum(case['cells'][key]['passed'] for case in cases) for key in cases[0]['cells']}
    result = {'cases': cases, 'scores': scores, 'cases_count': len(cases),
              'exposure': 'All eight are the historical exposed engineering cases, never new confirmation',
              'objective_unchanged': copy.deepcopy(SPECIFICATION), 'candidate_allowance_each': 64,
              'interpretation': 'Separately crosses developer-authored search policy and starting primitive availability. This is not learned discovery-policy improvement or scientific superiority.',
              'full_lifecycle_cost': None}
    write(output / 'POLICIES.json', result)
    return result


def archive_enabling(output):
    """A real reproduced missing dependency becomes a built, checked instrument."""
    from flywheel.archive_v2 import build, extract, materialize_cycle004
    from flywheel.legacy import materialize
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    original_zip = ROOT / 'evidence/cycle-005/archive-original/release.zip'
    original_sha = '551932fadd6d65903c7bb4e5feef071cd9c72588787252548e4cc9bf5faf0634'
    if file_sha(original_zip) != original_sha:
        raise ValueError('ORIGINAL_PUBLIC_ARCHIVE_MISMATCH')
    task = {'id': 'portable-exact-historical-materialization', 'phases': [
        {'id': 'claim-output', 'kind': 'reserve', 'deps': [], 'unit': 'event'},
        {'id': 'resolve-frozen-input', 'kind': 'materialize', 'deps': ['claim-output'], 'unit': 'event'},
        {'id': 'publish-evidence', 'kind': 'commit', 'deps': ['resolve-frozen-input'], 'unit': 'event'}]}
    candidate = construct.conventional(task)
    specification = {'invariants': [{'id': 'exact-dependencies-available', 'kind': 'required_effect_available',
                                    'effect': 'historical_source_materialization'}]}
    with tempfile.TemporaryDirectory(prefix='alpha-actual-public-archive-') as directory:
        temporary = Path(directory)
        original = temporary / 'old'
        original.mkdir()
        with zipfile.ZipFile(original_zip) as archive:
            for name in archive.namelist():
                prefix = 'AGI_ALPHA_Connected_Pilot/'
                if not name.startswith(prefix):
                    raise ValueError('ORIGINAL_ARCHIVE_PATH')
                relative = Path(name[len(prefix):])
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('ORIGINAL_ARCHIVE_PATH')
                leaf = original / relative
                if name.endswith('/'):
                    leaf.mkdir(parents=True, exist_ok=True)
                else:
                    leaf.parent.mkdir(parents=True, exist_ok=True)
                    leaf.write_bytes(archive.read(name))
        def missing_effect(frozen_task, frozen_candidate, phase):
            number = len(list(output.glob('original-failure-*.log')))
            destination = temporary / ('old-materialization-%d' % number)
            result = subprocess.run([sys.executable, '-m', 'flywheel.legacy', '--root', str(original), '--output', str(destination)],
                         cwd=original, capture_output=True, text=True, timeout=30,
                         env={'PATH': os.defpath, 'LANG': 'C.UTF-8'})
            with (output / ('original-failure-%d.log' % number)).open('x') as stream:
                stream.write(result.stdout + result.stderr)
            if result.returncode == 0 or 'LEGACY_IDENTITY_MISMATCH' not in result.stderr:
                raise ValueError('ORIGINAL_FAILURE_DID_NOT_REPRODUCE')
            return {'state': 'INCOMPLETE', 'completed': False, 'trace': ['claim-output'], 'reserved': ['claim-output'],
                    'failure_at': phase, 'interrupted_marker': True, 'directory_created': True, 'complete_exists': False,
                    'effect_observations': [{'phase_id': phase, 'effect': 'historical_source_materialization', 'available': False,
                        'input_sha256': original_sha, 'error': {'type': 'LEGACY_IDENTITY_MISMATCH', 'message': result.stderr}}]}
        witness = missing_effect(task, candidate, 'resolve-frozen-input')
        objection = criticism.critique(task, candidate, witness, specification,
                                      {'original_legacy_source': file_sha(original / 'flywheel/legacy.py')})[0]
        adjudicated = criticism.adjudicate(objection, missing_effect)
        instrument = criticism.instrument_spec(adjudicated, task, ['protect', 'atomic_publish'])
        write(output / 'MISSING_INSTRUMENT.json', {'objection': objection, 'adjudication': adjudicated, 'specification': instrument})
        packed, clean = temporary / 'repaired.zip', temporary / 'clean'
        archive_receipt = build(ROOT, packed)
        extract(packed, clean)
        def check(name, command, cwd):
            with (output / (name + '.log')).open('xb') as stream:
                result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=120,
                      env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
            return result.returncode == 0
        checks = {}
        checks['unit_suite'] = check('clean-unit', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], clean)
        checks['verifier_suite'] = check('clean-verifier', [sys.executable, '-m', 'unittest', 'discover', '-s', 'verification', '-v'], clean)
        old1 = temporary / 'edition001'
        materialize(clean, old1)
        checks['original_edition'] = check('original-edition', [sys.executable, str(old1 / 'verification/check_edition.py')], old1)
        old4 = temporary / 'edition004'
        materialize_cycle004(clean, old4)
        checks['unchanged_connected_replay'] = check('unchanged-connected', [sys.executable, str(old4 / 'run_cycle.py'), '--output', str(temporary / 'old-replay')], old4)
        freeze = json.loads((old4 / 'campaign/cycle-004/FREEZE.json').read_text())
        checks['source_identities'] = all(file_sha(old4 / name) == expected for name, expected in freeze['sources'].items())
        objective = {'source_identities': freeze['sources'], 'full_checks': sorted(checks),
                     'service_obligations': ['No .git or parent repository history', 'No hidden developer source cache', 'Exclusive output refusal'],
                     'safety_obligations': ['No relaxed source hashes', 'No overwritten original release or evidence']}
        receipt = {'verified': all(checks.values()), 'objective_sha256': memory.digest(objective),
                   'source_identities': objective['source_identities'], 'checks': checks}
        reframed = construct.reframe(objective, {'inherited_method_assumption': 'Git history must supply frozen workflow'},
                                     ['verified_snapshot'], receipt)
        result = {'original_failure': witness, 'missing_instrument_specification': instrument,
                  'constructed_instrument': {'built': True, 'source': 'flywheel/archive_v2.py + flywheel/legacy.py',
                                             'origin': 'Developer engineering driven by reproduced missing dependency; no generated new primitive claim',
                                             'source_sha256': {'archive_v2': file_sha(ROOT / 'flywheel/archive_v2.py'), 'legacy': file_sha(ROOT / 'flywheel/legacy.py')}},
                  'newly_possible_in_scope': 'Execute the original exact-source unit/verifier/edition/replay obligations in a clean no-Git archive',
                  'checks': checks, 'reframing': reframed, 'archive': {k: v for k, v in archive_receipt.items() if k != 'manifest'},
                  'passed': all(checks.values()), 'complete_cost': None,
                  'limitations': 'Portable engineering capability and reproducibility repair, not a new scientific production frontier or proven business'}
        write(output / 'ENABLING.json', result)
        return result


def reuse(task, donors, target_graph, output, memory_root, mode='inheritance'):
    started = time.monotonic()
    output, memory_root = Path(output), Path(memory_root)
    output.mkdir(parents=True, exist_ok=False)
    if mode == 'inheritance':
        built = memory.generate(memory_root, task, donors, ROOT, {'max_candidates': 64})
    elif mode in ('ordinary', 'removed'):
        loaded = retrieve(memory_root, {'schema_version': 1, 'conditions': task['conditions']}, ROOT)
        if not loaded['records']:
            built = {'program': None, 'status': 'refused', 'retrieval': loaded}
        else:
            content = copy.deepcopy(loaded['records'][0]['record'])
            if mode == 'removed':
                content['generative_operator']['program']['role_deltas'] = []
            try:
                built = memory.ordinary_generate(content, task, donors, ROOT, {'max_candidates': 64})
            except ValueError as error:
                built = {'program': None, 'status': 'refused', 'reason': str(error)}
            built['retrieval'] = loaded
    elif mode == 'conventional':
        built = {'status': 'constructed', 'program': construct.conventional(task), 'source': 'competent topological complete control'}
    elif mode == 'reset':
        built = construct.construct(task, [])
    else:
        raise ValueError('UNKNOWN_CONTROL')
    checked = verify(task, built.get('program'), output / 'checks')
    result = {'mode': mode, 'construction': built, 'passed': checked['passed'],
              'verification': checked, 'target_sha256': memory.digest({'task': task, 'target': target_graph}),
              'wall_seconds': time.monotonic()-started, 'complete_cost': None,
              'acquisition_charged_separately': True, 'scope': 'Fresh engineering task; a competent ordinary reuse/conventional tie remains a tie'}
    write(output / 'RESULT.json', result)
    return result
