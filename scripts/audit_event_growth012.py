"""Read-only audit of a completed, source-frozen event-growth012 publication.

No allocation deadline applies to this replay. The original operating controller
is never called. Existing files are read unchanged; native audit databases use
temporary directories. An optional receipt must use a new path.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def bound(root, relative, expected=None):
    name = Path(relative)
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('RELATIVE_PUBLICATION_PATH_REQUIRED')
    path = root / name
    if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('REGULAR_UNSYMLINKED_PUBLICATION_FILE_REQUIRED:' + str(relative))
    raw = path.read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('PUBLICATION_FILE_IDENTITY_MISMATCH:' + str(relative))
    return raw


def frontier(worlds, targets, horizon):
    rows, n = [], len(worlds)
    for target in targets:
        hits = [w['milestones'][str(target)] for w in worlds]
        reached = sorted(t for t in hits if t is not None)
        rows.append({'target_microUSD': target, 'target_USD': target / 1_000_000,
            'runs': n, 'attained': len(reached), 'attainment_fraction': len(reached) / n,
            'attainment_by_year': {str(y): sum(t is not None and t <= y * 8760 for t in hits) / n if y * 8760 <= horizon else None for y in [1, 3, 5, 10]},
            'observed_horizon_hours': horizon, 'longer_horizons_not_observed': [y for y in [1, 3, 5, 10] if y * 8760 > horizon],
            'unconditional_median_hours': reached[math.ceil(n / 2) - 1] if len(reached) >= math.ceil(n / 2) else None,
            'conditional_hitting_hours_quantiles': {str(q): reached[math.ceil(q * len(reached)) - 1] if reached else None for q in [.1, .5, .9]},
            'nonreaching_runs': n - len(reached), 'nonreaching_includes_insolvency': True,
            'empirical_restricted_time_hours': sum(t if t is not None else horizon for t in hits) / n})
    return rows


def aggregate(worlds, targets, horizon):
    n = len(worlds)
    result = {'worlds': n, 'cash_survival_fraction': sum(w['cash_survival'] for w in worlds) / n,
        'profitable_world_fraction': sum(w['metrics']['profit_microUSD'] > 0 for w in worlds) / n,
        'binding_constraints': dict(sum((Counter(w['binding_constraints']) for w in worlds), Counter())),
        'frontier': frontier(worlds, targets, horizon)}
    for key in ['collected_microUSD', 'profit_microUSD', 'costs_microUSD', 'paid_jobs', 'cash_microUSD', 'unrestricted_earned_microUSD', 'earned_funded_deliveries']:
        values = [w['metrics']['collections_microUSD' if key == 'collected_microUSD' else key] for w in worlds]
        result[key] = {'minimum': min(values), 'mean': sum(values) / n, 'maximum': max(values)}
    return result


def audit_publication(output):
    started = time.monotonic()
    output = Path(output).absolute()
    frozen = decode(bound(output, 'FROZEN.json'))
    if digest({k: v for k, v in frozen.items() if k != 'freeze_sha256'}) != frozen['freeze_sha256'] or digest(frozen['source']['files']) != frozen['source']['sha256']:
        raise ValueError('FROZEN_DOCUMENT_OR_SOURCE_IDENTITY')
    snapshot = output / 'source'
    for name, expected in frozen['source']['files'].items():
        bound(snapshot, name, expected)
    sys.path.insert(0, str(snapshot))
    from enterprise.tournament012 import scenario_config
    from verification.growth012 import audit_growth
    report_raw = bound(output, 'REPORT.json')
    report = decode(report_raw)
    if report['freeze_sha256'] != frozen['freeze_sha256'] or report['source_sha256'] != frozen['source']['sha256'] or not report['all_worlds_independently_audited'] or report['actual_revenue_microUSD'] != 0:
        raise ValueError('REPORT_FREEZE_SCOPE_MISMATCH')
    manifest = decode(bound(output, 'SERVICES.json'))
    protocol, tasks = frozen['protocol'], {}
    for family in protocol['families']:
        for arm in protocol['arms']:
            primary = arm in {'baseline', 'simple', 'joint'}
            if primary or family in protocol['intervention_families']:
                for seed in protocol['seeds'] if primary else protocol['intervention_seeds']:
                    tasks[family, arm, seed] = scenario_config(frozen['config'], family, arm)
    if len(tasks) != 128 or len(report['index']) != len(tasks):
        raise ValueError('COMPLETE_REGISTERED_128_WORLD_PRIMARY_REQUIRED')
    groups, seen, service_executions = {}, set(), 0
    for index in report['index']:
        key = index['family'], index['arm'], index['seed']
        if key not in tasks or key in seen:
            raise ValueError('UNREGISTERED_OR_DUPLICATE_WORLD')
        raw = bound(output, index['path'], index['sha256'])
        world = decode(gzip.decompress(raw))
        completed = decode(bound(output, index['completed_receipt'], index['completed_receipt_sha256']))
        config, controller = tasks[key]
        if world['seed'] != key[2] or world['controller'] != controller or world['config'] != config:
            raise ValueError('WORLD_DOES_NOT_MATCH_REGISTERED_TASK')
        required = {'source_sha256': frozen['source']['sha256'], 'config_sha256': digest(config),
            'manifest_sha256': digest(manifest), 'seed': key[2], 'controller': controller,
            'result_sha256': index['sha256'], 'actions_sha256': world['ledger']['actions_sha256']}
        if any(completed.get(k) != v for k, v in required.items()):
            raise ValueError('COMPLETED_WORLD_RECEIPT_BINDING')
        if index.get('runtime_archive_sha256') is not None:
            bound(output, index['runtime_archive'], index['runtime_archive_sha256'])
        for variant in index.get('preserved_storage_prefixes', []):
            bound(output, variant['path'], variant['sha256'])
        proof = audit_growth(world, root=snapshot, manifest=manifest)
        if not proof['accepted'] or not proof['native_replay_accepted'] or decode(bound(output, index['audit_path'])) != proof:
            raise ValueError('INDEPENDENT_REPLAY_OR_PUBLISHED_AUDIT_DISAGREES')
        ledger = world['ledger']
        released = {a['args']['id'] for a in ledger['actions'] if a['op'] == 'event' and a['args']['action'] == 'release'}
        earned = sum(any(i['state'] == 'complete' and int(i['actual']) > 0 and i['id'].endswith(':' + w['order_id'] + '-complete-delivery') for i in ledger['investments']) for w in world['work_executions'])
        metrics = {'collections_microUSD': proof['net_collected_microUSD'], 'profit_microUSD': proof['complete_cost_profit_microUSD'],
            'costs_microUSD': ledger['summary']['expenses'], 'paid_jobs': len(released),
            'cash_microUSD': proof['cash_microUSD'], 'unrestricted_earned_microUSD': proof['unrestricted_earned_microUSD'],
            'earned_funded_deliveries': earned}
        if any(world['metrics'].get(k) != v for k, v in metrics.items()) or world['milestones'] != proof['milestones']:
            raise ValueError('WORLD_METRICS_DISAGREE_WITH_INDEPENDENT_REBUILD')
        reasons = Counter(a['reason'] for d in world['decisions'] for a in d['feasible_actions'] if not a['feasible'] and a.get('reason'))
        groups.setdefault(key[:2], []).append({'seed': key[2], 'metrics': metrics, 'cash_survival': proof['cash_survival'], 'milestones': proof['milestones'], 'binding_constraints': dict(reasons)})
        seen.add(key)
        service_executions += proof['actual_service_executions']
    if seen != set(tasks) or set(report['summary']) != set(protocol['families']):
        raise ValueError('REGISTERED_WORLD_OR_CONDITION_MISSING')
    rebuilt = {}
    for (family, arm), worlds in groups.items():
        expected = aggregate(worlds, protocol['milestones_microUSD'], frozen['config']['horizon_hours'])
        actual = report['summary'][family][arm]
        for key, value in expected.items():
            if key == 'frontier':
                if len(actual[key]) != len(value) or any(any(a.get(k) != v for k, v in e.items()) for a, e in zip(actual[key], value)):
                    raise ValueError('REPORT_FRONTIER_REBUILD_MISMATCH')
            elif actual.get(key) != value:
                raise ValueError('REPORT_SUMMARY_REBUILD_MISMATCH:' + key)
        rebuilt.setdefault(family, {})[arm] = expected
    for family in report['summary']:
        if set(report['summary'][family]) != {arm for f, arm in groups if f == family}:
            raise ValueError('UNREGISTERED_REPORT_ARM')
    bound(output, report['historical_baseline']['path'], report['historical_baseline']['sha256'])
    if decode(bound(output, 'GROWTH_FRONTIER.json')) != report['summary'] or decode(bound(output, 'NEXT_ACTION.json')) != report['next_action'] or decode(bound(output, 'INVERSE_FRONTIER.json')) != report['inverse_frontier']:
        raise ValueError('PUBLISHED_REPORT_COMPANION_MISMATCH')
    return {'schema': 'agi-alpha/growth012-publication-audit/v1', 'accepted': True,
        'source_sha256': frozen['source']['sha256'], 'freeze_sha256': frozen['freeze_sha256'],
        'report_sha256': hashlib.sha256(report_raw).hexdigest(), 'source_files_checked': len(frozen['source']['files']),
        'worlds_independently_replayed': len(seen), 'synthetic_service_executions_rechecked_across_alternative_worlds': service_executions,
        'report_summary_and_frontier_rebuilt': True, 'rebuilt_summary_sha256': digest(rebuilt),
        'actual_revenue_microUSD': 0, 'wall_seconds': time.monotonic() - started,
        'scope': 'Read-only publication and native-financial replay, actual scoped synthetic service reexecution and independent numerical aggregation. No new operating trajectory, paid call, market calibration, global optimality or real revenue claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Existing complete primary experiment directory')
    parser.add_argument('--receipt', help='Optional new JSON receipt path; existing files are refused')
    args = parser.parse_args()
    proof = audit_publication(args.output)
    if args.receipt:
        path = Path(args.receipt).absolute()
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('UNSYMLINKED_NEW_RECEIPT_PATH_REQUIRED')
        with path.open('x', encoding='utf-8') as stream:
            json.dump(proof, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps({key: proof[key] for key in ['accepted', 'source_files_checked', 'worlds_independently_replayed', 'report_summary_and_frontier_rebuilt', 'report_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
