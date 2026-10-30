import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.norman006 import model, policy_comparison


def main():
    parser = argparse.ArgumentParser()
    for key in ('data', 'heldout-features', 'store', 'capability', 'search', 'repair-report', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--cell-line', required=True)
    parser.add_argument('--perturbation', required=True)
    parser.add_argument('--seed', type=int, default=41)
    parser.add_argument('--fits', type=int, default=4)
    args = parser.parse_args()
    data = dict(np.load(args.data, allow_pickle=False))
    heldout = dict(np.load(args.heldout_features, allow_pickle=False))
    if 'AB' in heldout or 'error' in heldout or 'rank' in heldout:
        raise ValueError('PROTECTED_OUTCOMES_SUPPLIED_TO_BUILDER')
    capability = json.loads(args.capability.read_text())
    history = json.loads(args.search.read_text())
    repair_report = json.loads(args.repair_report.read_text())
    conditions = {'representation': 'single-intervention-panel-means', 'unordered_simultaneous_inputs': True,
                  'gene_axis_available': True, 'cell_line': args.cell_line, 'perturbation': args.perturbation}
    report = policy_comparison.run(data, args.store, conditions, capability, history, repair_report, args.output, ROOT, args.seed, args.fits)
    source_sha = hashlib.sha256((ROOT / 'experiments/norman006/model.py').read_bytes()).hexdigest()
    artifacts = args.output / 'refitted-all-development'
    artifacts.mkdir(exist_ok=False)
    final = {}
    for name, arm in report['arms'].items():
        selected = arm['best_functionally_admitted']
        configuration = selected['configuration'] if selected is not None else policy_comparison.stopping_configuration()
        artifact = model.fit(data, configuration, source_sha)
        prediction = model.predict(artifact, heldout)
        policy_comparison.write(artifacts / (name + '.json'), artifact)
        np.savez_compressed(artifacts / (name + '-predictions.npz'), prediction=prediction['prediction'],
                            pairs=np.asarray(prediction['pairs']), genes=np.asarray(prediction['genes']))
        final[name] = {'configuration': configuration, 'artifact_sha256': artifact['artifact_sha256'],
                       'artifact_file': str((artifacts / (name + '.json')).relative_to(args.output)),
                       'prediction_file': str((artifacts / (name + '-predictions.npz')).relative_to(args.output)),
                       'fallback': None if selected is not None else 'No functionally admissible selected experiment; explicit conventional additive stopping',
                       'development_only_selection': True, 'protected_outcomes_used': False,
                       'extra_refit_scope': 'One common all-development refit per arm after its matched search allowance; this cost is outside search and is explicitly charged by the enclosing resource receipt'}
    policy_comparison.write(args.output / 'FINAL_ARTIFACTS.json', final)
    policy_comparison.write(args.output / 'INPUT_IDENTITY.json', {'data_sha256': hashlib.sha256(args.data.read_bytes()).hexdigest(),
                  'heldout_features_sha256': hashlib.sha256(args.heldout_features.read_bytes()).hexdigest(),
                  'capability_sha256': hashlib.sha256(args.capability.read_bytes()).hexdigest(),
                  'conditions': conditions, 'protected_outcomes_used': False})
    print(json.dumps({'output': str(args.output), 'arms': {name: {'experiments': len(arm['experiments']),
                    'best_median_pair_rmse': arm['best_functionally_admitted']['median_pair_rmse'] if arm['best_functionally_admitted'] else None,
                    'execution': arm['execution']['state']} for name, arm in report['arms'].items()},
                    'selected_policy': json.loads((args.output / 'POLICY_NOMINATION.json').read_text())['selected_policy']}))


if __name__ == '__main__':
    main()
