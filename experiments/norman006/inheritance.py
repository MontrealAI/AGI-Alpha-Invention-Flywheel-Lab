import copy
import hashlib
import json
from pathlib import Path

from flywheel import retention
from mechanisms import mapping, policy006
from . import model


def digest(value):
    return hashlib.sha256(retention.canonical(value)).hexdigest()


def source_pins(root):
    paths = ['experiments/norman006/model.py', 'experiments/norman006/inheritance.py',
             'mechanisms/policy006.py', 'mechanisms/mapping.py', 'flywheel/retention.py', 'flywheel/sandbox.py',
             'verification/cycle006_symmetry_adjudication.py', 'historical/cycle-006/verifier-symmetry-original.py.txt']
    pins = {}
    for relative in paths:
        path = Path(root) / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError('SOURCE_SYMLINK')
        pins[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def exchange_mapping(target_id, simultaneous=True, unit='normalized-expression-coordinate'):
    donor = {'id': 'finite-group-averaging', 'nodes': [
        {'id': 'left', 'kind': 'exchangeable-input', 'unit': 'normalized-expression-coordinate'},
        {'id': 'right', 'kind': 'exchangeable-input', 'unit': 'normalized-expression-coordinate'},
        {'id': 'result', 'kind': 'joint-output', 'unit': 'normalized-expression-coordinate'}],
        'relations': [['left', 'contributes-to', 'result'], ['right', 'contributes-to', 'result']],
        'conditions': {'unordered_simultaneous_inputs': True},
        'provenance': 'Developer-supplied Reynolds/group-averaging construction from invariant estimation. This is established mathematics, not a newly discovered biological mechanism.'}
    target = {'id': target_id, 'nodes': [
        {'id': 'A', 'kind': 'exchangeable-input', 'unit': unit},
        {'id': 'B', 'kind': 'exchangeable-input', 'unit': unit},
        {'id': 'AB', 'kind': 'joint-output', 'unit': unit}],
        'relations': [['A', 'contributes-to', 'AB'], ['B', 'contributes-to', 'AB']],
        'conditions': {'unordered_simultaneous_inputs': simultaneous}}
    report = mapping.discover([donor], target, max_mappings=8)[0]
    if not report['applicable'] or not report['search_complete']:
        raise ValueError('NO_COMPLETE_EXCHANGE_MAPPING')
    permutations = []
    for correspondence in report['correspondences']:
        mapping.check_mapping(donor, target, correspondence)
        if correspondence['result'] != 'AB':
            raise ValueError('OUTPUT_ROLE_CHANGED')
        permutations.append([correspondence['left'], correspondence['right']])
    permutations = sorted(permutations)
    if permutations != [['A', 'B'], ['B', 'A']]:
        raise ValueError('UNQUALIFIED_GROUP_ACTION')
    return {'report': report, 'permutations': permutations,
            'transformation': {'symmetric': len(permutations) == 2, 'rule': 'average generated basis over every mapped input permutation'},
            'prediction': 'Swapping the simultaneous input roles preserves every predicted gene mean within numerical tolerance; this predicts no biological interaction or accuracy gain.'}


def constructive_constraint(adjudication_path, mapped):
    raw = Path(adjudication_path).read_bytes()
    adjudication = json.loads(raw)
    if adjudication.get('status') != 'established' or adjudication.get('schema') != 'agi-alpha-cycle006-exchange-symmetry-adjudication/v1':
        raise ValueError('ESTABLISHED_EXCHANGE_DEFECT_REQUIRED')
    if not mapped['transformation']['symmetric'] or mapped['permutations'] != [['A', 'B'], ['B', 'A']]:
        raise ValueError('MAPPING_DID_NOT_CONSTRUCT_GROUP_ACTION')
    return {'kind': 'exchange_symmetry', 'status': 'established', 'evidence_sha256': hashlib.sha256(raw).hexdigest()}


def acquire(before, after, search, adjudication_path, verification_path, root):
    adjudication_raw, verification_raw = Path(adjudication_path).read_bytes(), Path(verification_path).read_bytes()
    adjudication, verification = json.loads(adjudication_raw), json.loads(verification_raw)
    adjudication_identity, verification_identity = hashlib.sha256(adjudication_raw).hexdigest(), hashlib.sha256(verification_raw).hexdigest()
    for artifact in (before, after):
        if artifact.get('artifact_sha256') != model._digest({key: value for key, value in artifact.items() if key != 'artifact_sha256'}):
            raise ValueError('ACQUISITION_ARTIFACT_IDENTITY')
    if adjudication.get('status') != 'established' or adjudication.get('schema') != 'agi-alpha-cycle006-exchange-symmetry-adjudication/v1':
        raise ValueError('NO_ADJUDICATED_REPAIR')
    if verification.get('status') != 'repair_verified_in_functional_scope' or verification.get('schema') != 'agi-alpha-cycle006-exchange-symmetry-adjudication/v1':
        raise ValueError('NO_REPAIR_VERIFICATION')
    if adjudication.get('candidate_artifact_sha256') != before['artifact_sha256'] or verification.get('candidate_artifact_sha256') != after['artifact_sha256']:
        raise ValueError('REPAIR_RECEIPT_ARTIFACT_MISMATCH')
    verifier = Path(root) / 'verification/cycle006_symmetry_adjudication.py'
    verifier_identity = hashlib.sha256(verifier.read_bytes()).hexdigest()
    original_verifier_identity = hashlib.sha256((Path(root) / 'historical/cycle-006/verifier-symmetry-original.py.txt').read_bytes()).hexdigest()
    if adjudication.get('verifier_sha256') != original_verifier_identity or verification.get('verifier_sha256') != verifier_identity:
        raise ValueError('VERIFIER_SOURCE_IDENTITY')
    if any(receipt.get('candidate_source_sha256') != before['interpreter_source_sha256'] for receipt in (adjudication, verification)):
        raise ValueError('VERIFIER_CANDIDATE_SOURCE_IDENTITY')
    if not verification.get('checks') or any(check.get('passed') is not True for check in verification['checks'].values()):
        raise ValueError('REPAIR_CHECKS_REQUIRED')
    original, repaired = before['configuration'], after['configuration']
    if search.get('selected_configuration') != original or original['symmetric'] or not repaired['symmetric']:
        raise ValueError('ACQUIRED_REPAIR_MUST_FOLLOW_EXECUTED_SELECTION')
    if original['expressions'] != repaired['expressions'] or original['ridge'] != repaired['ridge']:
        raise ValueError('NOT_AN_EXCHANGE_REPAIR')
    if not repaired['constraints'] or any(c['evidence_sha256'] != adjudication_identity for c in repaired['constraints']):
        raise ValueError('REPAIR_DID_NOT_CONSUME_ADJUDICATION')
    import numpy as np
    data_path = Path(root) / 'experiments/interaction006_data/development.npz'
    data_identity = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if any(receipt.get('data_sha256') != data_identity for receipt in (adjudication, verification)):
        raise ValueError('RECEIPT_DATA_IDENTITY')
    with np.load(data_path, allow_pickle=False) as loaded:
        inputs = {key: loaded[key].copy() for key in ('A', 'B', 'ctrl', 'pairs', 'genes')}
    swapped = dict(inputs, A=inputs['B'], B=inputs['A'])
    differences = []
    for artifact in (before, after):
        first, second = model.predict(artifact, inputs), model.predict(artifact, swapped)
        differences.append(float(np.max(np.abs(first['prediction'] - second['prediction']))))
    if not differences[0] > 1e-10 or differences[1] > 1e-10:
        raise ValueError('RECOMPUTED_REPAIR_CONTRACT_FAILED')
    pins = source_pins(root)
    configuration = copy.deepcopy(repaired)
    return {'instrument': {'path': 'experiments/norman006/model.py', 'sha256': pins['experiments/norman006/model.py']},
            'applicability': {'schema_version': 1,
                'conditions': {'representation': 'single-intervention-panel-means', 'unordered_simultaneous_inputs': True, 'gene_axis_available': True},
                'assumptions': ['Observed single effects and controls share an axis and normalization.', 'New target training uses only its development outcomes.', 'Only unordered simultaneous labels justify the exchange action.'],
                'uncertainty': 'Functional permutation invariance is verified; predictive superiority and cross-dataset transfer are not implied.',
                'failures': [{'conditions': {'unordered_simultaneous_inputs': False}, 'reason': 'Order-dependent intervention effects do not admit this group action.'}]},
            'generative_operator': {'language': 'norman-residual-generator-v1',
                'program': {'configuration': configuration, 'construction_rule': 'generate_related_then_refit_target_development',
                            'learned_objects': ['executed selected arithmetic basis', 'adjudicated exchange constraint'],
                            'no_retained_fitted_weights': True}},
            'provenance': {'source_pins': pins, 'before_artifact_sha256': before['artifact_sha256'], 'after_artifact_sha256': after['artifact_sha256'],
                           'search_sha256': digest(search), 'adjudication_sha256': adjudication_identity,
                           'verifier_versions': {'original': original_verifier_identity, 'repair': verifier_identity},
                           'acquisition_recomputed_maximum_swap_errors': differences,
                           'authorship': 'Developer-authored grammar, source group-averaging theorem, PCA/ridge primitives; runtime-generated selected basis and trace-acquired repair. No unrestricted invention claim.'},
            'verification': {'status': 'verified-in-scope', 'receipt_sha256': verification_identity},
            'costs': {'acquisition_search': search.get('resources'), 'repair_construction': after.get('resources'), 'complete_lifecycle_cost': None},
            'exposure': ['Norman development pairs only; no protected AB outcomes used in acquisition'], 'supersedes': []}


def _check(record, root):
    retention.validate(record)
    if record['generative_operator']['language'] != 'norman-residual-generator-v1':
        raise ValueError('INCOMPATIBLE_GENERATIVE_LANGUAGE')
    expected = source_pins(root)
    if record['provenance'].get('source_pins') != expected:
        raise ValueError('CAPABILITY_DEPENDENCY_MISMATCH')
    if record['verification']['status'] != 'verified-in-scope':
        raise ValueError('UNVERIFIED_OPERATOR')
    program = record['generative_operator']['program']
    if set(program) != {'configuration', 'construction_rule', 'learned_objects', 'no_retained_fitted_weights'} or program['construction_rule'] != 'generate_related_then_refit_target_development' or program['no_retained_fitted_weights'] is not True:
        raise ValueError('GENERATOR_PROGRAM_SCHEMA')
    model.validate_configuration(program['configuration'])


def generate_related(record, root, seed=17, count=8, remove_operator=False):
    _check(record, root)
    if type(count) is not int or not 1 <= count <= 32:
        raise ValueError('SUCCESSOR_SEARCH_BOUND')
    acquired = copy.deepcopy(record['generative_operator']['program']['configuration'])
    if remove_operator:
        return {'configurations': [{'language': model.LANGUAGE, 'expressions': [], 'ridge': 1, 'symmetric': False, 'constraints': []}],
                'scope': 'Removed acquired generator; additive stopping remains eligible.', 'parent_sha256': digest(record)}
    inverse = dict(zip(model.TERMINALS, policy006.FEATURES))
    forward = dict(zip(policy006.FEATURES, model.TERMINALS))
    def translate(value, roles):
        if type(value) is str:
            return roles[value]
        if type(value) is list:
            return [value[0], translate(value[1], roles), translate(value[2], roles)]
        return value
    parents = [{'language': policy006.LANGUAGE, 'priority': translate(expression, inverse), 'stop_below': 0} for expression in acquired['expressions']]
    if not parents:
        parents = [{'language': policy006.LANGUAGE, 'priority': 'gain', 'stop_below': 0}]
    proposals = policy006.generate(seed=seed, count=max(1, count - 1), parents=parents)
    configurations = [acquired]
    for proposal in proposals['programs'][:count - 1]:
        changed = copy.deepcopy(acquired)
        changed['expressions'] = [translate(proposal['priority'], forward)]
        model.validate_configuration(changed)
        configurations.append(changed)
    return {'configurations': configurations, 'mutation_trace': proposals, 'parent_sha256': digest(record),
            'scope': 'Constructs related finite-language representations and refits on fresh target development; it does not replay retained fitted weights.'}


def retrieve_and_generate(store, target_conditions, root, seed=17, count=8):
    retrieved = retention.retrieve(store, {'schema_version': 1, 'conditions': target_conditions}, root)
    candidates = []
    for item in retrieved['records']:
        candidates.append({'id': item['id'], 'generated': generate_related(item['record'], root, seed, count)})
    return {'retrieval': retrieved, 'candidates': candidates}


def ordinary_generate(equivalent_records, root, seed=17, count=8):
    return [{'record_sha256': digest(record), 'generated': generate_related(record, root, seed, count)} for record in equivalent_records]
