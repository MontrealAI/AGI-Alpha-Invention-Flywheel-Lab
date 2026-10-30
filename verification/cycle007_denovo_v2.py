import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import shutil
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_tree(labels, edges):
    if len(labels) != 8 or labels.count('N') != 1 or labels.count('C') != 7 or len(edges) != 7:
        raise ValueError('C7H17N_TREE_SCOPE')
    adjacent = [[] for _ in labels]
    for a, b in edges:
        if a == b or not 0 <= a < 8 or not 0 <= b < 8 or b in adjacent[a]:
            raise ValueError('INVALID_TREE_EDGE')
        adjacent[a].append(b); adjacent[b].append(a)
    if any(len(neighbors) > (3 if labels[index] == 'N' else 4) for index, neighbors in enumerate(adjacent)):
        raise ValueError('NEUTRAL_VALENCE_SCOPE')
    seen = set()
    def rooted(node, parent):
        if node in seen:
            raise ValueError('TREE_CYCLE')
        seen.add(node)
        return labels[node] + '(' + ''.join(sorted(rooted(other, node) for other in adjacent[node] if other != parent)) + ')'
    value = rooted(labels.index('N'), -1)
    if len(seen) != 8:
        raise ValueError('DISCONNECTED_TREE')
    return value


def smiles_tree(smiles):
    if type(smiles) is not str or len(smiles) > 200:
        raise ValueError('SMILES_SCOPE')
    labels, edges, stack = [], [], []
    current = None
    index = 0
    while index < len(smiles):
        char = smiles[index]
        if char == '(':
            if current is None:
                raise ValueError('SMILES_BRANCH')
            stack.append(current); index += 1; continue
        if char == ')':
            if not stack:
                raise ValueError('SMILES_BRANCH')
            current = stack.pop(); index += 1; continue
        if char == '[':
            end = smiles.find(']', index)
            if end < 0:
                raise ValueError('SMILES_ATOM')
            token = smiles[index+1:end]
            if not re.fullmatch(r'(?:[CN](?:@{1,2})?(?:H[0-4]?)?|H)', token):
                raise ValueError('SMILES_UNSUPPORTED_ATOM')
            label = token[0]; index = end + 1
        elif char in ('C', 'N'):
            label = char; index += 1
        else:
            raise ValueError('SMILES_UNSUPPORTED_GRAMMAR')
        node = len(labels); labels.append(label)
        if current is not None:
            edges.append((current, node))
        current = node
    if stack:
        raise ValueError('SMILES_BRANCH')
    if 'H' in labels:
        adjacent = [[] for _ in labels]
        for left, right in edges:
            adjacent[left].append(right); adjacent[right].append(left)
        for index, label in enumerate(labels):
            if label == 'H' and (len(adjacent[index]) != 1 or labels[adjacent[index][0]] not in ('C', 'N')):
                raise ValueError('EXPLICIT_HYDROGEN_VALENCE')
            if label in ('C', 'N') and len(adjacent[index]) > (4 if label == 'C' else 3):
                raise ValueError('EXPLICIT_HEAVY_ATOM_VALENCE')
        retained = [index for index, label in enumerate(labels) if label != 'H']
        remap = {index: number for number, index in enumerate(retained)}
        edges = [(remap[left], remap[right]) for left, right in edges if left in remap and right in remap]
        labels = [labels[index] for index in retained]
    return canonical_tree(labels, edges)


def sdf_trees(path):
    result = []
    for record in Path(path).read_text().split('$$$$'):
        if not record.strip():
            continue
        lines = record.splitlines()
        counts = next((index for index, line in enumerate(lines) if 'V2000' in line), None)
        if counts is None:
            raise ValueError('SDF_V2000_REQUIRED')
        atoms, bonds = int(lines[counts][:3]), int(lines[counts][3:6])
        atom_lines = lines[counts+1:counts+1+atoms]
        labels = [line.split()[3] for line in atom_lines]
        if any(int(line.split()[5]) != 0 for line in atom_lines) or any(line.startswith('M  CHG') for line in lines):
            raise ValueError('SDF_CHARGED_ATOM')
        edges = []
        for line in lines[counts+1+atoms:counts+1+atoms+bonds]:
            if int(line[6:9]) != 1:
                raise ValueError('SDF_NON_SINGLE_BOND')
            edges.append((int(line[:3])-1, int(line[3:6])-1))
        result.append(canonical_tree(labels, edges))
    if len(result) != len(set(result)):
        raise ValueError('DUPLICATE_ENUMERATED_GRAPH')
    return set(result)


def independent_universe():
    result = set()
    labels = ['N'] + ['C']*7
    for sequence in itertools.product(range(8), repeat=6):
        degree = [1]*8
        for node in sequence:
            degree[node] += 1
        if degree[0] > 3 or any(value > 4 for value in degree[1:]):
            continue
        edges = []
        for node in sequence:
            leaf = next(index for index, value in enumerate(degree) if value == 1)
            edges.append((leaf, node)); degree[leaf] -= 1; degree[node] -= 1
        remaining = [index for index, value in enumerate(degree) if value == 1]
        edges.append(tuple(remaining))
        result.add(canonical_tree(labels, edges))
    return result


def evaluate(protocol_path, freeze_path, groundtruth, sdf, output):
    protocol_path, freeze_path, groundtruth, sdf, output = [Path(p).resolve() for p in (protocol_path, freeze_path, groundtruth, sdf, output)]
    if output.exists():
        raise FileExistsError(output)
    protocol, freeze = json.loads(protocol_path.read_text()), json.loads(freeze_path.read_text())
    if freeze['protocol_sha256'] != sha(protocol_path) or freeze['verifier_sha256'] != sha(__file__) or freeze['groundtruth_sha256'] != sha(groundtruth) or protocol['private_groundtruth_sha256'] != sha(groundtruth) or freeze['sdf_sha256'] != sha(sdf):
        raise ValueError('FROZEN_PROTOCOL_VERIFIER_TRUTH_OR_UNIVERSE')
    for row in freeze['score_files'].values():
        if sha(row['path']) != row['sha256']:
            raise ValueError('FROZEN_SCORE_IDENTITY')
    output.mkdir(parents=True)
    shutil.copyfile(freeze_path, output/'FREEZE.json')
    started = time.monotonic()
    universe, sdf_universe = independent_universe(), sdf_trees(sdf)
    universe_equal = universe == sdf_universe and len(universe) == 89
    truth_rows = json.loads(groundtruth.read_text())
    truth = {}
    source_hashes = {}
    for row in truth_rows:
        query = row['query_id']
        value = smiles_tree(row['ground_truth_smiles'][0])
        if query in truth and truth[query] != value:
            raise ValueError('INCONSISTENT_GROUNDTRUTH_GRAPH')
        truth[query] = value
        source_hashes.setdefault(query, []).append(row['source_row']['sha256'])
    results = []
    tolerance = 1e-12
    for query in protocol['query_ids']:
        with Path(freeze['score_files'][query]['path']).open(newline='') as stream:
            scored_rows = list(csv.DictReader(stream))
        scores = {}
        for row in scored_rows:
            graph = smiles_tree(row['SMILES'])
            score = float(row['Score'])
            if not math.isfinite(score) or graph in scores or graph not in universe:
                raise ValueError('INVALID_OR_DUPLICATE_SCORED_GRAPH')
            scores[graph] = score
        complete = set(scores) == universe
        true_score = scores.get(truth[query])
        rank = None if true_score is None else [1+sum(score > true_score+tolerance for score in scores.values()), sum(score >= true_score-tolerance for score in scores.values())]
        ordered = sorted(scores.values(), reverse=True)
        descriptions = []
        for k in (1, 5, 10, 20):
            cutoff = ordered[min(k, len(ordered))-1] if ordered else math.inf
            chosen = {graph for graph, score in scores.items() if score >= cutoff-tolerance}
            descriptions.append({'rank_positions': k, 'tie_inclusive_size': len(chosen), 'retains_truth': truth[query] in chosen,
                                 'candidate_reduction_fraction': 1-len(chosen)/len(universe)})
        primary = next(row for row in descriptions if row['rank_positions'] == 10)
        passes = (complete and primary['retains_truth'] and primary['tie_inclusive_size'] <= 10 and primary['candidate_reduction_fraction'] >= 0.9)
        results.append({'query_id': query, 'enumerated_candidates': len(universe), 'scored_candidates': len(scores), 'all_enumerated_graphs_scored': complete,
                        'true_graph_in_complete_enumeration': truth[query] in universe, 'true_graph_in_scores': true_score is not None,
                        'true_score': true_score, 'true_rank_interval': rank, 'top_score_tie_set_size': sum(score >= ordered[0]-tolerance for score in ordered) if ordered else 0,
                        'shortlists': descriptions, 'primary_pilot_threshold_passed': passes, 'groundtruth_source_record_sha256': source_hashes[query]})
    report = {'schema': 'agi-alpha/denovo-baseline-verification007/v1', 'stage': freeze['stage'], 'protocol_sha256': sha(protocol_path),
              'verifier_sha256': sha(__file__), 'freeze_sha256': sha(freeze_path), 'private_groundtruth_sha256': sha(groundtruth),
              'independent_prufer_enumeration_count': len(universe), 'MAYGEN_enumeration_count': len(sdf_universe), 'complete_graph_universes_equal': universe_equal,
              'results': results, 'all_primary_pilot_thresholds_passed': universe_equal and all(row['primary_pilot_threshold_passed'] for row in results),
              'engineering_tool_qualification': universe_equal and all(row['all_enumerated_graphs_scored'] and row['true_graph_in_complete_enumeration'] for row in results),
              'wall_seconds': time.monotonic()-started, 'scope': 'Two masked-identity descriptive standard-record hypothesis-ranking checks. Not calibrated ambiguity coverage, unique chemical identification, fresh physical acquisition, external authentication, population accuracy, unrestricted library-retrieval superiority or a commercially admitted service.',
              'independence': 'Separate verifier used held-back source structures and a Python Prüfer/tree implementation independent of MAYGEN/CDK. Shared host/model family; procedural blindness only.',
              'statistical_alpha_spent': 0, 'source_feedback_rule': 'Any outcome used for adaptation consumes these cases as development; later evaluation is not fresh confirmation.'}
    with (output/'REPORT.json').open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False);stream.write('\n')
    shutil.copyfile(groundtruth, output/'EXPOSED_GROUNDTRUTH.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('protocol', 'freeze', 'groundtruth', 'sdf', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = evaluate(args.protocol, args.freeze, args.groundtruth, args.sdf, args.output)
    print(json.dumps({key: result[key] for key in ('engineering_tool_qualification', 'all_primary_pilot_thresholds_passed', 'independent_prufer_enumeration_count')}))
