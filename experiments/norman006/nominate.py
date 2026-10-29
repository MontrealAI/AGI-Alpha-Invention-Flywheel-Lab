import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.norman006 import controls, model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, separators=(',', ':'), allow_nan=False)
        stream.write('\n')


def load(path):
    with np.load(path, allow_pickle=False) as source:
        return {key: source[key].copy() for key in source.files}


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def family(name, development_path, features_path, split_path, output, producer_receipt, cross=None):
    output.mkdir(parents=True, exist_ok=False)
    data, features = load(development_path), load(features_path)
    if set(features) != {'A', 'B', 'ctrl', 'pairs', 'genes'}:
        raise ValueError('HELDOUT_FEATURES_ONLY')
    qualified = controls.qualify(data)
    qualified_path = output / 'QUALIFIED_CONTROLS.json'
    write(qualified_path, qualified)
    versions = {path: sha(ROOT / path) for path in ('experiments/norman006/model.py', 'experiments/norman006/controls.py',
                'experiments/norman006/nominate.py', 'experiments/norman006/inheritance.py', 'experiments/norman006/policy_comparison.py',
                'mechanisms/policy006.py')}
    arms = {}

    def register(arm_name, kind, prediction, artifact_path=None, hyperparameters=None, receipt=producer_receipt, details=None):
        destination = output / (arm_name + '-predictions.npz')
        np.savez_compressed(destination, prediction=np.asarray(prediction), pairs=np.asarray(features['pairs']), genes=np.asarray(features['genes']))
        value = {'status': 'complete', 'kind': kind, 'prediction_path': relative(destination), 'prediction_sha256': sha(destination),
                 'hyperparameters': hyperparameters or {}, 'resource_receipt_path': relative(receipt), 'source_versions': versions,
                 'development_only_selection': True, 'protected_outcomes_used': False}
        if artifact_path is not None:
            value.update(artifact_path=relative(artifact_path), artifact_file_sha256=sha(artifact_path))
        if details:
            value.update(details)
        arms[arm_name] = value

    predictions = controls.predict_all(qualified, features)
    for control_name, prediction in predictions.items():
        kind = 'ridge' if 'kernel_ridge' in control_name else control_name
        configuration = {'qualification_path': relative(qualified_path), 'qualification_sha256': sha(qualified_path)}
        if kind == 'ridge':
            key = {'full_kernel_ridge': 'ridge', 'direct_kernel_ridge': 'direct_ridge', 'residual_kernel_ridge': 'residual_ridge'}[control_name]
            configuration.update(alpha=qualified[key]['alpha'], residual=qualified[key]['residual'], kernel_scale=1000,
                                 feature='A+B-2ctrl', scale_floor=1e-8, target='AB-additive' if qualified[key]['residual'] else 'AB-ctrl')
        register(control_name, kind, prediction, hyperparameters=configuration)
    if name == 'norman':
        paths = {'candidate': ROOT / 'evidence/cycle-006/norman-repair-constructor-002b-mapped-run/artifacts/ARTIFACT.json',
                 'original_unrepaired': ROOT / 'evidence/cycle-006/norman-development-constructor-001c-run/artifacts/ARTIFACT.json'}
        for arm_name, artifact_path in paths.items():
            artifact = json.loads(artifact_path.read_text())
            predicted = model.predict(artifact, features)
            register(arm_name, 'model', predicted['prediction'], artifact_path, artifact['configuration'],
                     details={'source_trial': 'Actual selected development program and mapped repair; original remains an explicit functional-defect control.'})
        primary = 'candidate'
    else:
        if cross is None:
            raise ValueError('FRESH_ACTUAL_POLICY_CROSS_REQUIRED')
        final = json.loads((cross / 'FINAL_ARTIFACTS.json').read_text())
        for arm_name, value in final.items():
            artifact_path = cross / value['artifact_file']
            artifact = json.loads(artifact_path.read_text())
            predicted = model.predict(artifact, features)
            old = load(cross / value['prediction_file'])
            if not np.array_equal(predicted['prediction'], old['prediction']) or not np.array_equal(features['pairs'], old['pairs']) or not np.array_equal(features['genes'], old['genes']):
                raise ValueError('CROSS_PREDICTION_REPLAY_MISMATCH')
            register(arm_name, 'model', predicted['prediction'], artifact_path, artifact['configuration'],
                     receipt=cross.parent / 'RECEIPT.json', details={'fallback': value['fallback'], 'cross_report_path': relative(cross / 'REPORT.json')})
        primary = 'new_policy_new_tools'
    manifest = {'schema': 'agi-alpha-cycle006-arm-manifest/v1', 'family': name, 'primary_candidate': primary,
                'development_path': relative(development_path), 'features_path': relative(features_path), 'split_path': relative(split_path),
                'development_sha256': sha(development_path), 'features_sha256': sha(features_path), 'split_sha256': sha(split_path),
                'arms': arms, 'primary_controls': ['additive', 'matching_mean', 'full_kernel_ridge', 'residual_mean'],
                'additional_qualified_controls': ['direct_kernel_ridge', 'residual_kernel_ridge', 'training_mean'],
                'qualification_path': relative(qualified_path), 'qualification_sha256': sha(qualified_path),
                'scope': 'Predictions and all configuration/source/data identities fixed before the verifier opens protected outcomes. No acceptance is asserted here.'}
    write(output / 'ARM_MANIFEST.json', manifest)
    return manifest


def run(output, cross, producer_receipt, wessels_public):
    started, cpu = time.monotonic(), time.process_time()
    output.mkdir(parents=True, exist_ok=False)
    first = ROOT / 'experiments/interaction006_data'
    registry = {}
    for name, source in (('norman', first), ('wessels', wessels_public)):
        result = family(name, source / 'development.npz', source / 'heldout_features.npz', source / 'SPLIT.json',
                        output / name, producer_receipt, cross if name == 'wessels' else None)
        registry[name] = {'manifest_path': relative(output / name / 'ARM_MANIFEST.json'),
                          'manifest_sha256': sha(output / name / 'ARM_MANIFEST.json'), 'arms': list(result['arms']),
                          'primary_candidate': result['primary_candidate']}
    result = {'schema': 'agi-alpha-cycle006-prediction-registry/v1', 'families': registry,
              'resources': {'wall_seconds': time.monotonic()-started, 'host_cpu_seconds': time.process_time()-cpu, 'complete_monetary_cost': None},
              'all_protected_outcomes_unread': True, 'scientific_acceptance': 'UNRUN_PENDING_FROZEN_INDEPENDENT_CONFIRMATION'}
    write(output / 'REGISTRY.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    for key in ('output', 'cross', 'producer-receipt', 'wessels-public'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve(), args.cross.resolve(), args.producer_receipt.resolve(), args.wessels_public.resolve()), indent=2))


if __name__ == '__main__':
    main()
