"""Replay the registered public-release comparison with independent structural checks."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from frontier_member_value import review_digest

PROJECTIONS = (
    ('45282872456', '341980419241e5c5f19e2614a19a0f6fb2fa1026294cad4297fec818228067e8'),
    ('45287921702', '4e88bb5313eb5d7068c97289e1f8b2042d9c103fc1430032071fa232be91c7a6'),
)
LEDGER = '83335886ce2a420d124e0d203f2ee826dea009471a5007cc14a073308999766a'


def read_pinned(path, expected):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f'Public bytes differ from the registered input: {path.name}')
    return json.loads(raw), len(raw)


def index(manifest):
    records = {record['id']: record for record in manifest['briefs']}
    if len(records) != len(manifest['briefs']):
        raise ValueError('Duplicate decision identity')
    return records


def cases(earlier, later, ledger):
    old, current = index(earlier), index(later)
    for key, brief in old.items():
        yield 'release-forward', key, brief, current.get(key), earlier['capabilities'], later['capabilities']
    for key in sorted(current.keys() - old.keys()):
        yield 'release-withheld', key, current[key], None, later['capabilities'], earlier['capabilities']

    tools = later['capabilities']
    for row in ledger['records']:
        history = row['editorial']
        if history and history[0]['reviewed_commit'] != history[-1]['reviewed_commit']:
            brief = current[row['id']]
            assert brief['source_version'] == history[-1]['reviewed_commit']
            # Hold conclusions fixed to isolate the effect of a documented source revision.
            previous = {**brief, 'source_version': history[0]['reviewed_commit']}
            yield 'historical-editorial-pin', row['id'], previous, brief, tools, tools

    sample = current['shift-archive-point']
    for name, path, value in (
            ('verdict', ('verdict',), 'ABSTAIN'),
            ('alternative', ('fr', 'alternative'), 'Solution de rechange modifiée pour le contrôle.'),
            ('limit', ('en', 'uncertainty'), 'Scope reduced for the control.'),
            ('next', ('en', 'next'), 'Use the new validation procedure for the control.'),
            ('observation-time-only', ('updated_at',), '2026-11-24T00:00:00Z'),
            ('different-id', ('id',), 'shift-other'),
    ):
        updated = deepcopy(sample)
        target = updated if len(path) == 1 else updated[path[0]]
        target[path[-1]] = value
        yield 'control', name, sample, updated, tools, tools
    altered_tools = deepcopy(tools)
    altered_tools['archive']['sha256'] = '0' * 64
    yield 'control', 'tool-digest', sample, sample, tools, altered_tools


def same_decision(old, current, old_tools, current_tools):
    # Conventional comparator. Compare the published structure directly
    # instead of importing the candidate's fingerprint or review policy.
    if current is None or old['id'] != current['id']:
        return 'missing'
    if any(old[key] != current[key] for key in ('source_version', 'verdict', 'evidence', 'atlas_state', 'tool')):
        return 'revised'
    tool = old['tool']
    if tool and any(old_tools[tool][key] != current_tools[tool][key] for key in ('sha256', 'version')):
        return 'revised'
    if {source['url'] for source in old['evidence_links']} != {source['url'] for source in current['evidence_links']}:
        return 'revised'
    for language in ('en', 'fr'):
        for field in ('alternative', 'uncertainty', 'next', 'why', 'possibility',
                      'rights', 'economics', 'missing_move', 'protocol'):
            if old[language][field] != current[language][field]:
                return 'revised'
    return 'current'


def seal(record, tools):
    if record is None:
        return None
    return {'id': record['id'], 'version': record['source_version'], 'review': review_digest(record, tools)}


def evaluate(prior, newer):
    acquisition = perf_counter_ns()
    earlier, before_bytes = read_pinned(prior / 'member-value.json', PROJECTIONS[0][1])
    later, after_bytes = read_pinned(newer / 'member-value.json', PROJECTIONS[1][1])
    ledger, history_bytes = read_pinned(newer / 'atlas-ledger.json', LEDGER)
    read_ns = perf_counter_ns() - acquisition
    cohort = list(cases(earlier, later, ledger))
    conventional_start = perf_counter_ns()
    conventional = [same_decision(*row[2:]) for row in cohort]
    conventional_ns = perf_counter_ns() - conventional_start

    candidate_start = perf_counter_ns()
    pins = [[seal(left, tl), seal(right, tr)] for _, _, left, right, tl, tr in cohort]
    seal_ns = perf_counter_ns() - candidate_start
    request = json.dumps(pins, separators=(',', ':')).encode()
    candidate = subprocess.run(
        ['node', '--input-type=module', '-e', '''
import {readFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
import {reviewSaved} from './docs/research/frontier-omega-alpha/frontier-goals.mjs';
const cases = JSON.parse(readFileSync(0, 'utf8'));
const stamp = performance.now();
const ordered = cases.map(([saved, current]) => reviewSaved(saved, current));
console.log(JSON.stringify({ordered, ns: Math.round((performance.now() - stamp) * 1e6)}));
'''], input=request, capture_output=True, check=True, cwd=ROOT)
    candidate_wall_ns = perf_counter_ns() - candidate_start
    measured = json.loads(candidate.stdout)
    outcomes = []
    for (group, key, *_), reference, result in zip(cohort, conventional, measured['ordered'], strict=True):
        outcomes.append({'group': group, 'id': key, 'conventional': reference, 'candidate': result})
    disagreements = sum(row['conventional'] != row['candidate'] for row in outcomes)
    planned = {'release-forward': len(earlier['briefs']), 'release-withheld': len(later['briefs']) - len(earlier['briefs']),
               'historical-editorial-pin': 8, 'control': 7}
    assert dict(Counter(row['group'] for row in outcomes)) == planned
    for row in outcomes:
        if row['group'] == 'control':
            expected = {'observation-time-only': 'current', 'different-id': 'missing'}.get(row['id'], 'revised')
            assert row['conventional'] == expected
    assert not disagreements
    return {
        'schema': 'frontier/saved-decision-public-comparison-v1',
        'workflow_runs': [run for run, _ in PROJECTIONS],
        'member_input_sha256': [digest for _, digest in PROJECTIONS],
        'ledger_sha256': LEDGER,
        'outcomes': outcomes,
        'quality': dict(Counter(conventional)),
        'disagreements': disagreements,
        'bytes': {'shared_evidence': before_bytes + after_bytes + history_bytes,
                  'candidate_comparison_input': len(request)},
        'wall_ns': {'shared_read_and_check': read_ns, 'conventional_structural_compare': conventional_ns,
                    'prepare_candidate_pins': seal_ns, 'candidate_comparison_only': measured['ns'],
                    'candidate_with_startup_and_pins': candidate_wall_ns},
        'real_member_trials': None, 'human_rework': None, 'complete_cost': None,
        'verdict': 'equal_decisions_flagship_unqualified',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prior', type=Path)
    parser.add_argument('newer', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.prior, args.newer), indent=2, sort_keys=True))
