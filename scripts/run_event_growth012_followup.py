"""Execute the preregistered costed buyer-pool followup without policy edits."""
import argparse, copy, hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enterprise.tournament012 import _world_task, digest, source_identity, write_json


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def size(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file() and not p.is_symlink())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--plan', default=str(ROOT / 'evidence/event-growth012/FOLLOWUP_PLAN.json'))
    parser.add_argument('--cpu-reserve-seconds', type=int, default=1200)
    args = parser.parse_args()
    primary, output, plan_path = Path(args.primary).absolute(), Path(args.output).absolute(), Path(args.plan).absolute()
    frozen = json.loads((primary / 'FROZEN.json').read_text())
    plan = json.loads(plan_path.read_text())
    allocation = json.loads((primary / 'source/campaign/growth-012/ALLOCATION.json').read_text())
    deadline = datetime.fromisoformat(allocation['deadline_utc'])
    while not (primary / 'REPORT.json').exists():
        if datetime.now(timezone.utc) >= deadline:
            raise RuntimeError('PRIMARY_NOT_COMPLETE_WITHIN_REGISTERED_ALLOCATION')
        time.sleep(5)
    report = json.loads((primary / 'REPORT.json').read_text())
    if len(report['index']) != 128 or not report['all_worlds_independently_audited'] or report['source_sha256'] != frozen['source']['sha256']:
        raise ValueError('COMPLETE_SOURCE_BOUND_PRIMARY_REQUIRED')
    if source_identity() != frozen['source'] or source_identity(primary / 'source') != frozen['source']:
        raise ValueError('FROZEN_OPERATING_SOURCE_CHANGED')
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError('NEW_UNSYMLINKED_FOLLOWUP_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    ordinary = report['summary']['ordinary']
    eligible = [a for a in ['simple', 'joint'] if ordinary[a]['profit_microUSD']['mean'] > 0 and ordinary[a]['cash_survival_fraction'] == 1]
    if not eligible:
        write_json(output / 'SKIPPED.json', {'reason': 'NO_ELIGIBLE_PROFITABLE_FUNDED_EVENT_POLICY', 'primary_sha256': file_sha(primary / 'REPORT.json')})
        return
    selected = max(eligible, key=lambda a: (ordinary[a]['collected_microUSD']['mean'], ordinary[a]['profit_microUSD']['mean'], a == 'simple'))
    remaining = allocation['local_cpu_core_seconds_limit'] - report['resource_receipt']['process_cpu_seconds'] - args.cpu_reserve_seconds
    if remaining < 120 or datetime.now(timezone.utc).timestamp() + 300 >= deadline.timestamp():
        raise RuntimeError('FOLLOWUP_WOULD_ENDANGER_REGISTERED_RESOURCE_OR_PUBLICATION_BOUNDARY')
    allocation['local_cpu_core_seconds_limit'] = int(remaining)
    manifest = json.loads((primary / 'SERVICES.json').read_text())
    tasks = []
    for arm in plan['arms']:
        for seed in plan['seeds']:
            config = copy.deepcopy(frozen['config'])
            config.update(customer_pool=arm['customer_pool'], horizon_hours=plan['horizon_hours'])
            config['intervention_setup_cost'] += arm['extra_setup_microUSD']
            config['intervention_daily_cost'] += arm['extra_daily_microUSD']
            tasks.append(dict(family='ordinary', arm=arm['id'], seed=seed, config=config, controller=selected, output=str(output), root=str(primary / 'source'), allocation=allocation, workers=1, manifest=manifest, source=frozen['source']))
    registration = {'schema': plan['schema'], 'plan': plan, 'plan_sha256': file_sha(plan_path), 'helper_sha256': file_sha(__file__), 'primary_freeze_sha256': frozen['freeze_sha256'], 'primary_report_sha256': file_sha(primary / 'REPORT.json'), 'source': frozen['source'], 'selected_controller': selected, 'selection_metrics': {a: ordinary[a] for a in ['simple', 'joint']}, 'configs': [{k: t[k] for k in ['family', 'arm', 'seed', 'config', 'controller']} for t in tasks], 'cpu_reserve_for_prior_work_and_publication_seconds': args.cpu_reserve_seconds, 'registered_utc': datetime.now(timezone.utc).isoformat()}
    registration['freeze_sha256'] = digest(registration)
    write_json(output / 'FROZEN.json', registration)
    (output / 'worlds').mkdir()
    started, cpu, worlds, index = time.monotonic(), time.process_time(), {}, []
    for task in tasks:
        if size(primary) + size(output) + 20_000_000 > allocation['new_output_bytes_limit']:
            raise RuntimeError('COMBINED_OUTPUT_ALLOCATION_HEADROOM_EXHAUSTED; CHECKPOINTS_PRESERVED')
        brief, receipt = _world_task(task)
        receipt.pop('runtime_archive', None)
        receipt.pop('runtime_archive_sha256', None)
        worlds.setdefault(task['arm'], {})[str(task['seed'])] = brief
        index.append(receipt)
        write_json(output / 'CHECKPOINT.json', {'freeze_sha256': registration['freeze_sha256'], 'completed_worlds': index, 'results': worlds})
    baseline, comparisons, choices = worlds[plan['arms'][0]['id']], {}, []
    for arm in plan['arms'][1:]:
        changes = {seed: {'collections_microUSD': w['metrics']['collections_microUSD'] - baseline[seed]['metrics']['collections_microUSD'], 'profit_microUSD': w['metrics']['profit_microUSD'] - baseline[seed]['metrics']['profit_microUSD'], 'cash_survival': w['cash_survival']} for seed, w in worlds[arm['id']].items()}
        comparisons[arm['id']] = changes
        if all(c['collections_microUSD'] > 0 and c['profit_microUSD'] > 0 and c['cash_survival'] for c in changes.values()):
            choices.append(arm)
    result = {'freeze_sha256': registration['freeze_sha256'], 'index': index, 'worlds': worlds, 'paired_changes': comparisons, 'smallest_tested_improving_change': min(choices, key=lambda a: a['customer_pool']) if choices else None, 'all_worlds_independently_audited': True, 'actual_revenue_microUSD': 0, 'scope': plan['scope'], 'demand_assumption': plan['demand_assumption'], 'resource_receipt': {'process_cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started}, 'decision_scope': 'Two unused seeds, four costed reachable-buyer assumptions, unchanged frozen algorithm and original native obligations. No continuous minimum or empirically achieved demand claim.'}
    write_json(output / 'REPORT.json', result)
    print(json.dumps({'worlds': len(index), 'controller': selected, 'selected_change': result['smallest_tested_improving_change']}, sort_keys=True))


if __name__ == '__main__':
    main()
