import hashlib
import json
import time

import numpy as np

ALPHAS = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0)
MATCHING_MEAN_SOURCE = 'https://doi.org/10.1038/s41587-025-02777-8'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def checked(data, training=False):
    keys = ('A', 'B', 'ctrl') + (('AB',) if training else ())
    arrays = {key: np.asarray(data[key], dtype=float) for key in keys}
    shape = arrays['A'].shape
    if len(shape) != 2 or shape[1] != 1000 or not 1 <= shape[0] <= 256 or any(x.shape != shape or not np.isfinite(x).all() for x in arrays.values()):
        raise ValueError('CONTROL_INPUT_SHAPE_OR_FINITE')
    if len(data['pairs']) != shape[0] or len(data['genes']) != shape[1]:
        raise ValueError('CONTROL_AXES')
    if len(set(map(str, data['pairs']))) != shape[0] or len(set(map(str, data['genes']))) != shape[1]:
        raise ValueError('CONTROL_DUPLICATE_AXES')
    if not training and 'AB' in data:
        raise ValueError('PROTECTED_OUTCOME_IN_PREDICTION')
    return arrays


def subset(data, indices, outcomes=True):
    keys = ('A', 'B', 'ctrl', 'pairs') + (('AB',) if outcomes else ())
    return {**{key: np.asarray(data[key])[indices] for key in keys}, 'genes': np.asarray(data['genes'])}


def fit_ridge(data, alpha, residual=False):
    arrays = checked(data, True)
    if alpha not in ALPHAS:
        raise ValueError('UNREGISTERED_RIDGE_ALPHA')
    features = arrays['A'] + arrays['B'] - 2 * arrays['ctrl']
    center = features.mean(axis=0)
    scale = np.maximum(features.std(axis=0), 1e-8)
    x = (features - center) / scale
    base = arrays['A'] + arrays['B'] - arrays['ctrl'] if residual else arrays['ctrl']
    y = arrays['AB'] - base
    y_center = y.mean(axis=0)
    kernel = x @ x.T / features.shape[1]
    dual = np.linalg.solve(kernel + alpha * np.eye(len(x)), y - y_center)
    return {'language': 'full-multioutput-kernel-ridge/v1', 'alpha': alpha, 'residual': residual, 'feature_center': center.tolist(), 'feature_scale': scale.tolist(),
            'training_x': x.tolist(), 'target_center': y_center.tolist(), 'dual': dual.tolist(),
            'genes': list(map(str, data['genes'])), 'training_pairs': list(map(str, data['pairs'])),
            'definition': 'All1000 symmetric single-effect features; fitted standardization and intercept; regularized dual linear solve; no target double outcomes at prediction.'}


def predict_ridge(artifact, inputs):
    arrays = checked(inputs)
    if list(map(str, inputs['genes'])) != artifact['genes']:
        raise ValueError('RIDGE_GENE_AXIS')
    x = (arrays['A'] + arrays['B'] - 2 * arrays['ctrl'] - np.asarray(artifact['feature_center'])) / np.asarray(artifact['feature_scale'])
    kernel = x @ np.asarray(artifact['training_x']).T / x.shape[1]
    base = arrays['A'] + arrays['B'] - arrays['ctrl'] if artifact['residual'] else arrays['ctrl']
    prediction = base + np.asarray(artifact['target_center']) + kernel @ np.asarray(artifact['dual'])
    if not np.isfinite(prediction).all():
        raise ValueError('NONFINITE_RIDGE_PREDICTION')
    return prediction


def qualify(data):
    started, cpu = time.monotonic(), time.process_time()
    checked(data, True)
    fit_indices = np.asarray(data['fit_indices'], dtype=int)
    calibration_indices = np.asarray(data['calibration_indices'], dtype=int)
    if set(fit_indices) & set(calibration_indices) or set(fit_indices) | set(calibration_indices) != set(range(len(data['pairs']))):
        raise ValueError('CONTROL_DEVELOPMENT_SPLIT')
    training = subset(data, fit_indices)
    calibration = subset(data, calibration_indices, False)
    truth = np.asarray(data['AB'])[calibration_indices]
    trials = []
    for residual in (False, True):
        for alpha in ALPHAS:
            artifact = fit_ridge(training, alpha, residual)
            prediction = predict_ridge(artifact, calibration)
            trials.append({'alpha': alpha, 'residual': residual, 'median_pair_rmse': float(np.median(np.sqrt(np.mean((prediction-truth)**2, axis=1)))),
                           'pooled_rmse': float(np.sqrt(np.mean((prediction-truth)**2)))})
    def best(rows):
        return min(rows, key=lambda x: (x['median_pair_rmse'], x['pooled_rmse'], -x['alpha'], not x['residual']))
    winner = best(trials)
    artifact = fit_ridge(data, winner['alpha'], winner['residual'])
    artifact['artifact_sha256'] = digest(artifact)
    mean = np.mean(np.asarray(data['AB']) - np.asarray(data['ctrl']), axis=0)
    direct_choice, residual_choice = best([x for x in trials if not x['residual']]), best([x for x in trials if x['residual']])
    return {'ridge': artifact, 'direct_ridge': fit_ridge(data, direct_choice['alpha'], False), 'residual_ridge': fit_ridge(data, residual_choice['alpha'], True),
            'training_mean_effect': mean.tolist(), 'residual_mean_effect': np.mean(np.asarray(data['AB'])-(np.asarray(data['A'])+np.asarray(data['B'])-np.asarray(data['ctrl'])), axis=0).tolist(),
            'training_genes': list(map(str, data['genes'])),
            'qualification': {'source': MATCHING_MEAN_SOURCE, 'matching_mean_equation': '(A+B)/2 for both-seen-single interventions; no unseen-single fallback admitted.',
                              'ridge_trials': trials, 'selected_alpha': winner['alpha'], 'selected_residual_target': winner['residual'],
                              'selection': 'Select both direct-effect and additive-residual ridge families by median pair calibration RMSE; pooled RMSE then larger alpha and residual prior tie breaks; refit all development.',
                              'no_protected_outcomes_used': True},
            'resources': {'wall_seconds': time.monotonic()-started, 'host_cpu_seconds': time.process_time()-cpu, 'complete_monetary_cost': None}}


def predict_all(qualified, inputs):
    arrays = checked(inputs)
    if list(map(str, inputs['genes'])) != qualified['training_genes']:
        raise ValueError('CONTROL_GENE_AXIS')
    return {'additive': arrays['A'] + arrays['B'] - arrays['ctrl'],
            'matching_mean': (arrays['A'] + arrays['B']) / 2,
            'full_kernel_ridge': predict_ridge(qualified['ridge'], inputs),
            'direct_kernel_ridge': predict_ridge(qualified['direct_ridge'], inputs),
            'residual_kernel_ridge': predict_ridge(qualified['residual_ridge'], inputs),
            'residual_mean': arrays['A'] + arrays['B'] - arrays['ctrl'] + np.asarray(qualified['residual_mean_effect']),
            'training_mean': arrays['ctrl'] + np.asarray(qualified['training_mean_effect'])}
