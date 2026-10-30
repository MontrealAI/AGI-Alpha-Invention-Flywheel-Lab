import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.norman006 import model


def run(data_path, output, count, seed, omega_source=None, proposals_path=None):
    output.mkdir(parents=True, exist_ok=False)
    source_sha = hashlib.sha256((ROOT / 'experiments/norman006/model.py').read_bytes()).hexdigest()
    data = dict(np.load(data_path, allow_pickle=False))
    if proposals_path is None:
        proposals = model.generate_configurations(seed, count, omega_source)
        proposal_mode = 'new-runtime-generation'
    else:
        proposals = json.loads(proposals_path.read_text())
        if len(proposals.get('configurations', [])) != count:
            raise ValueError('RETAINED_PROPOSAL_COUNT')
        proposal_mode = 'replay-retained-runtime-proposals; no native generation claimed'
    (output / 'PROPOSALS.json').write_text(json.dumps(proposals, indent=2) + '\n')
    result = model.search(data, proposals['configurations'], source_sha)
    (output / 'SEARCH.json').write_text(json.dumps(result, indent=2) + '\n')
    if result['selected_configuration'] is None:
        raise RuntimeError('NO_DEVELOPMENT_CANDIDATE')
    artifact = model.fit(data, result['selected_configuration'], source_sha)
    (output / 'ARTIFACT.json').write_text(json.dumps(artifact, indent=2) + '\n')
    inputs = model.subset(data, range(len(data['pairs'])), False)
    first = model.predict(artifact, inputs)['prediction']
    swapped = dict(inputs)
    swapped['A'], swapped['B'] = inputs['B'], inputs['A']
    second = model.predict(artifact, swapped)['prediction']
    maximum_difference = float(np.max(np.abs(first - second)))
    finding = {'candidate_artifact_sha256': artifact['artifact_sha256'], 'source_sha256': source_sha,
               'claim': 'Unordered intervention pair prediction is exchange-invariant',
               'max_absolute_difference': maximum_difference, 'defect_proposed': maximum_difference > 1e-6,
               'scope': 'Development pairs only; independent reproduction/adjudication required; no established constraint inserted'}
    (output / 'SWAP_CRITIC_OBSERVATION.json').write_text(json.dumps(finding, indent=2) + '\n')
    return {'source_sha256': source_sha, 'proposal_mode': proposal_mode, 'proposal_file_sha256': hashlib.sha256(proposals_path.read_bytes()).hexdigest() if proposals_path is not None else None, 'status': result['status'], 'selected_index': result['selected_index'],
            'selected_configuration': result['selected_configuration'], 'swap_max_absolute_difference': maximum_difference,
            'records': len(result['records']), 'failed_records': sum(row['status'] == 'failed' for row in result['records']),
            'resources': result['resources'], 'exposure': 'Development only, not protected confirmation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=24)
    parser.add_argument('--seed', type=int, default=20261029)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--omega-source', type=Path)
    source.add_argument('--proposals', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.output, args.count, args.seed, args.omega_source, args.proposals)))
