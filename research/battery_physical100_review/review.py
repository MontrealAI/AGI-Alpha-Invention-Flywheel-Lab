"""Post-hoc arithmetic review of PhysicalBattery100's already exposed cohort.

No fitting, new measurements, acquisition, prediction or equipment operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).parent
METHODS = ('adjusted_peer', 'peer', 'persistence', 'recent_linear', 'sqrt_linear', 'curve_ridge')
SOURCE_SHA = '67644b8519d510188ab7f64e1679f78e3266371c'
ARTIFACT_SHA = 'e347f626c423a620e937e49405d5483d15413f33a2c1f65c9af989a518a89095'
SEAL = '814d8d4863d5efd19f4135f2c7101ac7ffaf71a4dfa52ec16c72b19b630a1f29'
THRESHOLD = 0.8


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Expected finite number')
    return value


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: number(value))


def analyze(data):
    source = data['source']
    require(source == {'repository': 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab',
                      'pull_request': 238, 'run_id': 41931850452, 'artifact_id': 13370954244,
                      'source_commit': SOURCE_SHA, 'sha256': ARTIFACT_SHA}, 'Unexpected source')
    predictions = data['sealed']['predictions']
    digest = hashlib.sha256(json.dumps(predictions, sort_keys=True, separators=(',', ':'),
                                      allow_nan=False).encode()).hexdigest()
    require(digest == data['sealed']['prediction_sha256'] == SEAL, 'Prediction seal mismatch')
    require(len(predictions) == 54, 'Expected six methods on nine cells')
    cells, groups, targets = set(), set(), {}
    for row in data['target_capacities']:
        cell = row['cell']
        require(cell not in cells and row['group'] not in groups, 'Duplicate cell or represented group')
        cells.add(cell)
        groups.add(row['group'])
        capacities = row['reference_first10_capacities_ah']
        require(len(capacities) == 10, 'Missing reference cycle')
        require(all(number(value) > 0 for value in capacities), 'Nonpositive reference capacity')
        reference = statistics.median(capacities)
        require(set(row['endpoint_capacities_ah']) == {'500', '1000'}, 'Missing endpoint')
        for endpoint, value in row['endpoint_capacities_ah'].items():
            require(number(value) > 0, 'Nonpositive endpoint capacity')
            targets[cell, endpoint] = value / reference
    require(len(cells) == 9 and len(targets) == 18, 'Incomplete test denominator')
    seen, grouped, misses, decisions = set(), {method: [] for method in METHODS}, [], {}
    for row in predictions:
        method, cell = row['method'], row['cell']
        require(method in METHODS and cell in cells, 'Unexpected method or cell')
        require((method, cell) not in seen, 'Duplicate prediction row')
        seen.add((method, cell))
        require(set(row['endpoints']) == {'500', '1000'}, 'Missing prediction endpoint')
        for endpoint, forecast in row['endpoints'].items():
            y = targets[cell, endpoint]
            lower, prediction, upper = (number(forecast[key]) for key in ('lower', 'prediction', 'upper'))
            require(lower <= upper, 'Reversed interval')
            decision = 'SCREEN_PASS' if lower >= THRESHOLD else ('SCREEN_FAIL' if upper < THRESHOLD else 'CONTINUE_TESTING')
            require(decision == forecast['decision'], 'Decision disagrees with registered threshold')
            covered = lower <= y <= upper
            grouped[method].append((100 * abs(y - prediction), covered, 100 * (upper - lower)))
            if endpoint == '1000':
                decisions[method, cell] = (decision, y >= THRESHOLD)
            if method == 'adjusted_peer' and not covered:
                misses.append(dict(cell=cell, endpoint=endpoint, observed=y, lower=lower, upper=upper))
    require(seen == {(m, c) for m in METHODS for c in cells}, 'Incomplete method-cell grid')
    metrics = []
    for method, rows in grouped.items():
        metrics.append(dict(method=method, n_endpoints=len(rows),
                            mean_absolute_error_pp=statistics.mean(r[0] for r in rows),
                            maximum_absolute_error_pp=max(r[0] for r in rows),
                            intervals_covering_observation=sum(r[1] for r in rows),
                            mean_interval_width_pp=statistics.mean(r[2] for r in rows),
                            cycle1000_screen_passes=sum(decisions[method, c][0] == 'SCREEN_PASS' for c in cells),
                            cycle1000_abstentions=sum(decisions[method, c][0] == 'CONTINUE_TESTING' for c in cells)))
    primary = metrics[0]
    decisive = [(d, y) for (m, _), (d, y) in decisions.items()
                if m == 'adjusted_peer' and d != 'CONTINUE_TESTING']
    gates = dict(all_nine_cells_and_two_endpoints=primary['n_endpoints'] == 18,
                 maximum_error_at_most_five_percentage_points=primary['maximum_absolute_error_pp'] <= 5,
                 all_18_endpoint_intervals_cover=primary['intervals_covering_observation'] == 18,
                 at_least_three_decisive_cycle1000=len(decisive) >= 3,
                 no_wrong_decisive_cycle1000=bool(decisive) and all((d == 'SCREEN_PASS') == y for d, y in decisive))
    require(data['original_primary'] == 'adjusted_peer', 'Unexpected primary')
    require(data['original_acceptance_conditions'] == gates, 'Original gate mismatch')
    require(type(data['original_acceptance']) is bool and data['original_acceptance'] == all(gates.values()), 'Original verdict mismatch')
    observations = [targets[cell, '1000'] for cell in sorted(cells)]
    return dict(kind='POST_HOC_REANALYSIS_NOT_FRESH_CONFIRMATION', source=source,
                original_primary='adjusted_peer', original_acceptance=all(gates.values()),
                original_acceptance_conditions=gates, unique_test_cells=9, represented_groups=9,
                endpoint_count_per_method=18, prediction_rows=54, registered_threshold=THRESHOLD,
                comparison=metrics, primary_interval_misses=misses,
                cycle1000_observed_range=[min(observations), max(observations)],
                cycle1000_below_threshold=sum(y < THRESHOLD for y in observations),
                always_pass_correct_on_exposed_test_cells=sum(y >= THRESHOLD for y in observations))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT / 'evidence.json')
    parser.add_argument('--check', type=Path, help='Compare computed result with this JSON')
    args = parser.parse_args()
    result = analyze(read(args.evidence))
    if args.check:
        require(result == read(args.check), 'Committed result mismatch')
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
