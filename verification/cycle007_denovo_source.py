import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from verification.cycle007_massbank_source import PIN, parse
from verification.cycle007_denovo import smiles_tree


def verify(protocol_path, anonymous_path, truth_path, source_repo, output):
    protocol_path, anonymous_path, truth_path, source_repo, output = [Path(p).resolve() for p in (protocol_path, anonymous_path, truth_path, source_repo, output)]
    if output.exists():
        raise FileExistsError(output)
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    protocol = json.loads(protocol_path.read_text())
    if sha(anonymous_path) != protocol['tool_input_files']['anonymous-input.json'] or sha(truth_path) != protocol['private_groundtruth_sha256']:
        raise ValueError('FROZEN_ANONYMOUS_SOURCE_IDENTITY')
    if subprocess.check_output(['git', '-C', str(source_repo), 'rev-parse', 'HEAD'], text=True).strip() != PIN:
        raise ValueError('SOURCE_COMMIT_IDENTITY')
    inputs = {row['query_id']: row for row in json.loads(anonymous_path.read_text())['queries']}
    private = json.loads(truth_path.read_text())
    counts, graphs = {}, {}
    for row in private:
        query, original = row['query_id'], row['source_row']
        relative = Path(original['path']).relative_to(source_repo).as_posix()
        raw = subprocess.check_output(['git', '-C', str(source_repo), 'show', PIN+':'+relative])
        if hashlib.sha256(raw).hexdigest() != original['sha256']:
            raise ValueError('GROUNDTRUTH_SOURCE_IDENTITY')
        fields, peaks = parse(raw)
        if fields.get('CH$SMILES') != row['ground_truth_smiles'] or fields.get('CH$IUPAC') != row['ground_truth_inchi']:
            raise ValueError('GROUNDTRUTH_GRAPH_EXTRACTION')
        def one(prefix, values):
            found = [item[len(prefix):] for item in values if item.startswith(prefix)]
            if len(found) != 1:
                raise ValueError('SOURCE_METADATA_MULTIPLICITY')
            return found[0]
        ms, focused = fields['AC$MASS_SPECTROMETRY'], fields['MS$FOCUSED_ION']
        energy = one('COLLISION_ENERGY ', ms)
        input_row = inputs[query]
        matches = [obs for obs in input_row['observations'] if obs['energy'] == energy]
        valid = (len(matches) == 1 and matches[0]['peaks'] == peaks and matches[0]['precursor_mz'] == float(one('PRECURSOR_M/Z ', focused)) and
                 input_row['formula'] == fields['CH$FORMULA'][0] == 'C7H17N' and input_row['adduct'] == one('PRECURSOR_TYPE ', focused) and
                 input_row['mode'] == one('ION_MODE ', ms) and input_row['instrument'] == fields['AC$INSTRUMENT'][0] and input_row['fragmentation_mode'] == one('FRAGMENTATION_MODE ', ms) and
                 fields.get('LICENSE') == original['license'] and fields.get('AUTHORS') == original['authors'] and
                 any(value in ('CONFIDENCE 1', 'CONFIDENCE standard compound') for value in fields.get('COMMENT', [])))
        if not valid:
            raise ValueError('ANONYMOUS_QUERY_OR_METADATA_MISMATCH')
        graph = smiles_tree(row['ground_truth_smiles'][0])
        if query in graphs and graphs[query] != graph:
            raise ValueError('SOURCE_STRUCTURE_INCONSISTENT')
        graphs[query] = graph; counts[query] = counts.get(query, 0)+1
    if counts != {'q01': 9, 'q02': 9} or len(set(graphs.values())) != 2:
        raise ValueError('FIXED_QUERY_COHORT_COVERAGE')
    result = {'schema': 'agi-alpha/denovo-source-verification007/v1', 'accepted_source_identity': True, 'records_verified': len(private), 'queries': counts,
              'source_commit': PIN, 'anonymous_input_sha256': sha(anonymous_path), 'private_groundtruth_sha256': sha(truth_path), 'verifier_sha256': sha(__file__),
              'scope': 'Confirms anonymous peak data and held-back full constitutional structures derive from the same eighteen exact published standard-compound records. Source labels are not new chemical authentication; no fresh acquisition or statistical population inference.',
              'groundtruth_disclosed_to_builder_by_this_report': False, 'statistical_alpha_spent': 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2);stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('protocol', 'anonymous', 'truth', 'source-repo', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = verify(args.protocol, args.anonymous, args.truth, args.source_repo, args.output)
    print(json.dumps({'accepted_source_identity': result['accepted_source_identity'], 'records_verified': result['records_verified']}))
