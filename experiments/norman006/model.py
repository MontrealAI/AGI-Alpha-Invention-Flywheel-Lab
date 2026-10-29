LANGUAGE = 'norman-residual-construction/v1'
TERMINALS = ('a0', 'b0', 'a1', 'b1', 'a2', 'b2')
OPERATIONS = ('add', 'sub', 'mul', 'div', 'min', 'max')


def _finite(value, bound=1000000000):
    return type(value) in (int, float) and value == value and abs(value) <= bound


def _expression(value, depth=0):
    if depth > 6:
        raise ValueError('EXPRESSION_DEPTH')
    if _finite(value, 8) or type(value) is str and value in TERMINALS:
        return 1
    if type(value) is not list or len(value) != 3 or value[0] not in OPERATIONS:
        raise ValueError('EXPRESSION_GRAMMAR')
    count = 1 + _expression(value[1], depth + 1) + _expression(value[2], depth + 1)
    if count > 47:
        raise ValueError('EXPRESSION_NODES')
    return count


def _value(expression, row):
    if type(expression) in (float, int):
        return float(expression)
    if type(expression) is str:
        return row[TERMINALS.index(expression)]
    left, right = _value(expression[1], row), _value(expression[2], row)
    operation = expression[0]
    if operation == 'add':
        result = left + right
    elif operation == 'sub':
        result = left - right
    elif operation == 'mul':
        result = left * right
    elif operation == 'div':
        result = left / (right if abs(right) >= .000001 else (.000001 if right >= 0 else -.000001))
    elif operation == 'min':
        result = min(left, right)
    else:
        result = max(left, right)
    return max(-1000000000, min(1000000000, result))


def validate_configuration(configuration):
    if type(configuration) is not dict or set(configuration) != {'language', 'expressions', 'ridge', 'symmetric', 'constraints'} or configuration['language'] != LANGUAGE:
        raise ValueError('CONFIGURATION_SCHEMA')
    if type(configuration['expressions']) is not list or len(configuration['expressions']) > 8:
        raise ValueError('BASIS_BOUND')
    for expression in configuration['expressions']:
        _expression(expression)
    if not _finite(configuration['ridge'], 1000000) or configuration['ridge'] <= 0 or type(configuration['symmetric']) is not bool:
        raise ValueError('RIDGE_OR_SYMMETRY')
    if type(configuration['constraints']) is not list or len(configuration['constraints']) > 4:
        raise ValueError('CONSTRAINT_BOUND')
    for constraint in configuration['constraints']:
        if type(constraint) is not dict or set(constraint) != {'kind', 'status', 'evidence_sha256'} or constraint['kind'] != 'exchange_symmetry' or constraint['status'] != 'established':
            raise ValueError('CONSTRAINT_SCHEMA')
        identity = constraint['evidence_sha256']
        if type(identity) is not str or len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
            raise ValueError('CONSTRAINT_EVIDENCE_IDENTITY')
    if configuration['constraints'] and not configuration['symmetric']:
        raise ValueError('CONSTRAINT_NOT_CONSUMED')
    return True


def interpret_basis(payload):
    if type(payload) is not dict or set(payload) != {'configuration', 'rows'}:
        raise ValueError('BASIS_PAYLOAD')
    configuration, rows = payload['configuration'], payload['rows']
    validate_configuration(configuration)
    if type(rows) is not list or len(rows) > 512:
        raise ValueError('ROW_BOUND')
    output = []
    for row in rows:
        if type(row) is not list or len(row) != 6 or any(not _finite(item, 1) for item in row):
            raise ValueError('NORMALIZED_SINGLE_EFFECT_COORDINATES')
        swapped = [row[1], row[0], row[3], row[2], row[5], row[4]]
        values = [_value(expression, row) for expression in configuration['expressions']]
        if configuration['symmetric']:
            values = [(left + _value(expression, swapped)) / 2 for left, expression in zip(values, configuration['expressions'])]
        output.append(values)
    return {'features': output, 'symmetric': configuration['symmetric'], 'scope': 'Generated bounded arithmetic representations of observed single-perturbation coordinates only; no double outcomes or acceptance access'}


def _digest(value):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _data(data, training):
    import numpy as np
    required = {'A', 'B', 'ctrl', 'pairs', 'genes'} | ({'AB'} if training else set())
    allowed = required | ({'fit_indices', 'calibration_indices'} if training else set())
    if not isinstance(data, dict) or not required <= set(data) or set(data) - allowed:
        raise ValueError('TRAINING_OR_PREDICTION_SCHEMA')
    arrays = {key: np.asarray(data[key], dtype=float) for key in ('A', 'B', 'ctrl') + (('AB',) if training else ())}
    shape = arrays['A'].shape
    if len(shape) != 2 or not 1 <= shape[0] <= 256 or not 1 <= shape[1] <= 2000 or any(value.shape != shape or not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError('DATA_SHAPE_OR_FINITE_BOUND')
    pairs, genes = [str(x) for x in data['pairs']], [str(x) for x in data['genes']]
    if len(pairs) != shape[0] or len(genes) != shape[1] or len(set(pairs)) != len(pairs) or len(set(genes)) != len(genes):
        raise ValueError('PAIR_OR_GENE_IDENTITY')
    return arrays, pairs, genes


def _coordinates(arrays, transformation=None):
    import numpy as np
    a, b = arrays['A'] - arrays['ctrl'], arrays['B'] - arrays['ctrl']
    if transformation is None:
        joined = np.concatenate((a, b))
        mean = joined.mean(axis=0)
        scale = np.sqrt(np.mean((joined - mean) ** 2, axis=0))
        scale = np.maximum(scale, 1e-8)
        centered = (joined - mean) / scale
        unused, singular, vectors = np.linalg.svd(centered, full_matrices=False)
        components = vectors[:min(3, len(vectors))].copy()
        for component in components:
            if component[np.argmax(np.abs(component))] < 0:
                component *= -1
        components = np.pad(components, ((0, 3 - len(components)), (0, 0)))
        coordinate_scale = np.maximum(np.std(centered @ components.T, axis=0), 1e-8)
        transformation = {'mean': mean.tolist(), 'scale': scale.tolist(), 'components': components.tolist(), 'coordinate_scale': coordinate_scale.tolist()}
    mean, scale = np.asarray(transformation['mean']), np.asarray(transformation['scale'])
    components, coordinate_scale = np.asarray(transformation['components']), np.asarray(transformation['coordinate_scale'])
    first = np.tanh(((a - mean) / scale) @ components.T / coordinate_scale)
    second = np.tanh(((b - mean) / scale) @ components.T / coordinate_scale)
    rows = np.stack((first, second), axis=2).reshape(len(a), 6)
    return rows, transformation


def _basis(configuration, coordinates, expected_source_sha256):
    import numpy as np
    from pathlib import Path
    from flywheel import sandbox
    receipt = sandbox.run(Path(__file__), 'interpret_basis', {'configuration': configuration, 'rows': coordinates.tolist()}, expected_source_sha256)
    if receipt['state'] != 'COMPLETE':
        raise ValueError('CONFINED_BASIS_FAILED:' + receipt['state'])
    features = np.asarray(receipt['worker']['result']['features'], dtype=float)
    return features.reshape(len(coordinates), len(configuration['expressions'])), receipt


def fit(data, configuration, expected_source_sha256):
    import numpy as np
    import time
    validate_configuration(configuration)
    started, cpu = time.monotonic(), time.process_time()
    arrays, pairs, genes = _data(data, True)
    rows, transformation = _coordinates(arrays)
    features, receipt = _basis(configuration, rows, expected_source_sha256)
    baseline = arrays['A'] + arrays['B'] - arrays['ctrl']
    if configuration['expressions']:
        feature_mean = features.mean(axis=0)
        feature_scale = np.maximum(features.std(axis=0), 1e-8)
        centered = (features - feature_mean) / feature_scale
        design = np.column_stack((np.ones(len(features)), centered))
        target = arrays['AB'] - baseline
        penalty = np.eye(design.shape[1]) * configuration['ridge']
        penalty[0, 0] = 0
        coefficient = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    else:
        feature_mean, feature_scale = np.zeros(0), np.ones(0)
        coefficient = np.zeros((1, len(genes)))
    artifact = {'language': LANGUAGE, 'configuration': configuration, 'transformation': transformation,
                'feature_mean': feature_mean.tolist(), 'feature_scale': feature_scale.tolist(), 'coefficient': coefficient.tolist(),
                'genes': genes, 'training_pairs': pairs, 'interpreter_source_sha256': expected_source_sha256,
                'training_input_sha256': _digest({key: value.tolist() if hasattr(value, 'tolist') else value for key, value in data.items()}),
                'construction': {'source': 'Developer-authored PCA/ridge primitives composed with runtime-generated arithmetic basis; no target double outcomes at prediction',
                                 'basis_receipt': receipt, 'constraints_consumed': configuration['constraints']},
                'resources': {'wall_seconds': time.monotonic() - started, 'host_cpu_seconds': time.process_time() - cpu, 'complete_monetary_cost': None}}
    artifact['artifact_sha256'] = _digest(artifact)
    return artifact


def predict(artifact, inputs):
    import numpy as np
    if artifact.get('artifact_sha256') != _digest({key: value for key, value in artifact.items() if key != 'artifact_sha256'}):
        raise ValueError('ARTIFACT_IDENTITY')
    arrays, pairs, genes = _data(inputs, False)
    if genes != artifact['genes']:
        raise ValueError('GENE_AXIS_IDENTITY')
    rows, unused = _coordinates(arrays, artifact['transformation'])
    features, receipt = _basis(artifact['configuration'], rows, artifact['interpreter_source_sha256'])
    baseline = arrays['A'] + arrays['B'] - arrays['ctrl']
    if artifact['configuration']['expressions']:
        normalized = (features - np.asarray(artifact['feature_mean'])) / np.asarray(artifact['feature_scale'])
        output = baseline + np.column_stack((np.ones(len(features)), normalized)) @ np.asarray(artifact['coefficient'])
    else:
        output = baseline
    if output.shape != arrays['A'].shape or not np.isfinite(output).all():
        raise ValueError('PREDICTION_SHAPE_OR_NUMERIC')
    return {'prediction': output, 'pairs': pairs, 'genes': genes, 'basis_receipt': receipt, 'artifact_sha256': artifact['artifact_sha256']}


def generate_configurations(seed=0, count=24, omega_source_path=None):
    import random
    from mechanisms import policy006
    if type(count) is not int or not 2 <= count <= 64:
        raise ValueError('CONFIGURATION_SEARCH_BOUND')
    proposals = policy006.generate(seed, min(256, count * 4), omega_source_path=omega_source_path)
    roles = dict(zip(policy006.FEATURES, TERMINALS))
    def convert(value):
        if type(value) is str:
            return roles[value]
        if type(value) is list:
            return [value[0], convert(value[1]), convert(value[2])]
        return value
    rng = random.Random(seed)
    configurations = [{'language': LANGUAGE, 'expressions': [], 'ridge': 1, 'symmetric': False, 'constraints': []}]
    for index in range(count - 1):
        expressions = [convert(item['priority']) for item in proposals['programs'][index * 4:index * 4 + rng.randint(1, 4)]]
        configurations.append({'language': LANGUAGE, 'expressions': expressions, 'ridge': rng.choice((.01, .1, 1, 10, 100)), 'symmetric': False, 'constraints': []})
    return {'configurations': configurations, 'generator_trace': proposals, 'terminal_correspondence': roles,
            'scope': 'Developer-supplied mapping of generic arithmetic terminals to learned single-effect coordinates; not autonomous biological mechanism discovery'}


def repair(configuration, constraints):
    import copy
    validate_configuration(configuration)
    candidate = copy.deepcopy(configuration)
    candidate['constraints'] = copy.deepcopy(constraints)
    candidate['symmetric'] = bool(constraints) or candidate['symmetric']
    validate_configuration(candidate)
    return {'configuration': candidate, 'before_sha256': _digest(configuration), 'after_sha256': _digest(candidate),
            'transformation': 'Average every generated basis under exchange of the two intervention roles; objective, measurements and fit data unchanged'}


def subset(data, indices, outcomes=True):
    import numpy as np
    index = np.asarray(indices, dtype=int)
    values = {key: np.asarray(data[key])[index] for key in ('A', 'B', 'ctrl', 'pairs') + (('AB',) if outcomes else ())}
    values['genes'] = np.asarray(data['genes'])
    return values


def search(data, configurations, expected_source_sha256):
    import numpy as np
    import time
    arrays, pairs, genes = _data(data, True)
    first, second = np.asarray(data['fit_indices']), np.asarray(data['calibration_indices'])
    if first.ndim != 1 or second.ndim != 1 or not len(first) or not len(second) or set(first) & set(second) or set(first) | set(second) != set(range(len(pairs))):
        raise ValueError('DEVELOPMENT_SPLIT')
    if type(configurations) is not list or not 1 <= len(configurations) <= 64:
        raise ValueError('SEARCH_BOUND')
    started, cpu, records = time.monotonic(), time.process_time(), []
    training, validation = subset(data, first), subset(data, second, False)
    truth = arrays['AB'][second]
    for index, configuration in enumerate(configurations):
        try:
            artifact = fit(training, configuration, expected_source_sha256)
            prediction = predict(artifact, validation)
            error = np.sqrt(np.mean((prediction['prediction'] - truth) ** 2, axis=1))
            records.append({'index': index, 'status': 'executed', 'configuration': configuration,
                            'median_pair_rmse': float(np.median(error)), 'pooled_rmse': float(np.sqrt(np.mean((prediction['prediction'] - truth) ** 2))),
                            'fit_artifact_sha256': artifact['artifact_sha256'], 'pair_rmse': error.tolist(),
                            'resources': artifact['resources'], 'prediction_basis_receipt': prediction['basis_receipt']})
        except Exception as error:
            records.append({'index': index, 'status': 'failed', 'configuration': configuration, 'error_type': type(error).__name__, 'message': str(error)[:300]})
    successful = [item for item in records if item['status'] == 'executed']
    if not successful:
        return {'status': 'failed', 'records': records, 'selected_configuration': None}
    winner = min(successful, key=lambda item: (item['median_pair_rmse'], item['pooled_rmse'], len(item['configuration']['expressions']), item['index']))
    return {'status': 'nominated-development-only', 'selected_configuration': winner['configuration'], 'selected_index': winner['index'], 'records': records,
            'selection_rule': 'Lowest development-calibration median pair RMSE, pooled RMSE tie-break, then smallest basis, then earlier index. Additive stopping eligible.',
            'resources': {'wall_seconds': time.monotonic() - started, 'host_cpu_seconds': time.process_time() - cpu, 'complete_monetary_cost': None},
            'scope': 'Sixty fit/twenty development calibration pairs only; no protected outcomes or scientific acceptance'}
