"""Source-frozen paired operating comparisons; scenario assumptions are not sales."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
import copy
from datetime import datetime, timezone
import gzip
import gc
import hashlib
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import shutil
import resource
import subprocess
import time
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'agi-alpha/growth012-tournament/v1'
TARGETS = [500, 1000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000]
ARMS = ['baseline', 'simple', 'joint', 'joint_fast_settlement', 'joint_finite_liability', 'joint_finite_fast', 'joint_channel', 'joint_retention', 'joint_combination', 'simple_combination']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    from commercial.persistence import atomic_bytes
    atomic_bytes(Path(path), json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n')


def source_paths(root):
    names = set()
    for directory in ['enterprise', 'commercial', 'vendor/alpha_claim', 'portfolio_scale', 'portfolio25']:
        names.update(p.relative_to(root).as_posix() for p in (root / directory).glob('*') if p.is_file() and p.suffix in {'.py', '.json', '.md'})
    names.update(p.relative_to(root).as_posix() for p in (root / 'tests').glob('*growth012*.py'))
    names.update(p.relative_to(root).as_posix() for p in (root / 'campaign/growth-012').glob('*') if p.is_file() and p.suffix in {'.json', '.md'})
    names.update(p.relative_to(root).as_posix() for p in (root / 'verification').glob('*growth012*.py'))
    for name in ['run_growth012.py', '.github/workflows/event-growth012.yml', 'requirements-commercial010.txt', 'vendor/__init__.py', 'experiments/__init__.py', 'experiments/commerce006.py']:
        if (root / name).is_file():
            names.add(name)
    return sorted(names)


def source_identity(root=ROOT):
    root = Path(root)
    files = {}
    for name in source_paths(root):
        path = root / name
        if path.is_symlink():
            raise ValueError('SOURCE_SYMLINK_REFUSED')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'files': files, 'sha256': digest(files)}


def quantiles(values):
    ordered = sorted(values)
    return {str(q): ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))] if ordered else None for q in [.1, .5, .9]}


def milestone_frontier(worlds, targets, horizon_hours):
    """Nonreaching and insolvent trajectories stay in the denominator."""
    n = len(worlds)
    rows = []
    for target in targets:
        hits = [w['milestones'].get(str(target)) for w in worlds]
        reached = [x for x in hits if x is not None]
        median = sorted(reached)[math.ceil(n / 2) - 1] if n and len(reached) >= math.ceil(n / 2) else None
        rows.append({'target_microUSD': target, 'target_USD': target / 1_000_000,
                     'runs': n, 'attained': len(reached), 'attainment_fraction': len(reached) / n if n else None,
                     'attainment_by_year': {str(year): sum(x is not None and x <= year * 365 * 24 for x in hits) / n if n and year * 365 * 24 <= horizon_hours else None for year in [1, 3, 5, 10]},
                     'observed_horizon_hours': horizon_hours,
                     'longer_horizons_not_observed': [year for year in [1, 3, 5, 10] if year * 365 * 24 > horizon_hours],
                     'unconditional_median_hours': median,
                     'conditional_hitting_hours_quantiles': quantiles(reached),
                     'nonreaching_runs': n - len(reached),
                     'nonreaching_includes_insolvency': True,
                     'empirical_restricted_time_hours': sum(x if x is not None else horizon_hours for x in hits) / n if n else None,
                     'time_basis': 'First passage of actual-in-simulation trailing365-day collected revenue. Quantiles explicitly condition on reaching; empirical restricted time assigns the horizon to every nonreaching world, including insolvency, and is not a survival estimator.'})
    return rows


def _number(world, key, default=0):
    return world.get('metrics', {}).get(key, default)


def summarize(worlds, targets, horizon_hours):
    n = len(worlds)
    def stat(key):
        values = [_number(w, key) for w in worlds]
        return {'minimum': min(values, default=0), 'mean': sum(values) / n if n else None, 'maximum': max(values, default=0)}
    return {'worlds': n, 'cash_survival_fraction': sum(w.get('cash_survival') is True for w in worlds) / n if n else None,
            'profitable_world_fraction': sum(_number(w, 'profit_microUSD') > 0 for w in worlds) / n if n else None,
            'collected_microUSD': stat('collections_microUSD'), 'profit_microUSD': stat('profit_microUSD'),
            'costs_microUSD': stat('costs_microUSD'), 'paid_jobs': stat('paid_jobs'),
            'cash_microUSD': stat('cash_microUSD'), 'unrestricted_earned_microUSD': stat('unrestricted_earned_microUSD'),
            'earned_funded_deliveries': stat('earned_funded_deliveries'),
            'binding_constraints': {reason: sum(world.get('binding_constraints', {}).get(reason, 0) for world in worlds) for reason in sorted({reason for world in worlds for reason in world.get('binding_constraints', {})})},
            'frontier': milestone_frontier(worlds, targets, horizon_hours),
            'scope': 'Finite paired authored simulation design, not an estimate of real-market probabilities. Alternative worlds are not additive enterprise revenue.'}


def paired_difference(base, candidate):
    if len(base) != len(candidate):
        raise ValueError('MATCHED_WORLD_COUNT_REQUIRED')
    pairs = []
    for first, second in zip(base, candidate):
        if first['seed'] != second['seed']:
            raise ValueError('MATCHED_SEED_REQUIRED')
        pairs.append({'seed': first['seed'], 'delta_collections_microUSD': _number(second, 'collections_microUSD') - _number(first, 'collections_microUSD'),
                      'delta_profit_microUSD': _number(second, 'profit_microUSD') - _number(first, 'profit_microUSD'),
                      'delta_paid_jobs': _number(second, 'paid_jobs') - _number(first, 'paid_jobs'),
                      'candidate_cash_survival': second.get('cash_survival'), 'baseline_cash_survival': first.get('cash_survival'),
                      'milestone_times': {target: {'baseline_hour': first.get('milestones', {}).get(target), 'candidate_hour': second.get('milestones', {}).get(target),
                                                   'candidate_minus_baseline_hours_when_both_reach': second['milestones'][target] - first['milestones'][target] if first.get('milestones', {}).get(target) is not None and second.get('milestones', {}).get(target) is not None else None}
                                          for target in sorted(set(first.get('milestones', {})) | set(second.get('milestones', {})), key=int)}})
    n = len(pairs)
    return {'pairs': pairs, 'mean_delta_collections_microUSD': sum(p['delta_collections_microUSD'] for p in pairs) / n if n else None,
            'mean_delta_profit_microUSD': sum(p['delta_profit_microUSD'] for p in pairs) / n if n else None,
            'mean_delta_paid_jobs': sum(p['delta_paid_jobs'] for p in pairs) / n if n else None,
            'positive_collection_difference_fraction': sum(p['delta_collections_microUSD'] > 0 for p in pairs) / n if n else None,
            'precision_scope': 'Six paired seeds per primary condition and four per business intervention resolve material finite-design differences only; no claim of one-percent tail-risk precision or external market calibration.'}


def freeze_run(output, *, smoke=False, config=None):
    from .growth012 import default_config
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError('NEW_UNSYMLINKED_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    supplied_config = config is not None
    config = copy.deepcopy(default_config() if config is None else config)
    if smoke:
        config['horizon_hours'] = min(14 * 24, config['horizon_hours'])
    elif not supplied_config:
        config['horizon_hours'] = 60 * 24
    config['targets_collected_microUSD'] = [value * 1_000_000 for value in TARGETS]
    protocol = default_protocol(config, smoke=smoke)
    identity = source_identity()
    for name in identity['files']:
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    if source_identity(output / 'source') != identity:
        raise ValueError('SOURCE_SNAPSHOT_MISMATCH')
    frozen = {'schema': SCHEMA, 'source': identity, 'config': config, 'protocol': protocol,
              'registered_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'git_parent': None, 'actual_revenue_microUSD': 0,
              'resource_boundary': 'Existing local execution and public branch/PR grants only; no spending, outreach, real finance or deployment. Allocation file controls actual budget.',
              'assumptions': 'Authored conditional demand, autonomous resource costs and buyer behavior; exact synthetic service production and separate semantic checking. Host assistant bill unavailable; no human staffing is charged.'}
    try:
        frozen['git_parent'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    frozen['freeze_sha256'] = digest(frozen)
    write_json(output / 'FROZEN.json', frozen)
    return frozen


def default_protocol(config, smoke=False):
    return {'edition': 'development-smoke' if smoke else 'protected-growth012-001',
            'seeds': [12001] if smoke else list(range(2610301201, 2610301207)),
            'intervention_seeds': [12001] if smoke else list(range(2610301201, 2610301205)),
            'intervention_families': ['ordinary'] if smoke else ['ordinary', 'low_demand'],
            'workers': 2,
            'development_seeds': [12001, 12002],
            'families': ['ordinary'] if smoke else ['ordinary', 'low_demand', 'price_war', 'shock'],
            'arms': ['baseline', 'simple', 'joint', 'joint_finite_liability'] if smoke else ARMS,
            'milestones_microUSD': [value * 1_000_000 for value in TARGETS],
            'equal_capital': True,
            'obligations_unchanged_first_comparison': True,
            'historical_scale_reference': {'source': 'enterprise/scale.py', 'config': 'exact default_config', 'seed': 12001 if smoke else 2610301201, 'separate_from_matched_comparison': True},
            'risk_limit': 'No unfunded commitments, borrowing or topups. Preserve native funded obligations and declared liquidity floor before every investment; report all unprofitable and nonreaching paths.',
            'next_action_selection_condition': 'ordinary',
            'sample_rationale': 'Development timing12.04seconds for4 integrated14-dayworlds motivated a fixed128-world60-daydesign:6pairedseeds×4conditions×3controllers plus4seeds×2conditions×7businessinterventions. Unused previously registered seeds stay unexposed. Two independent owned-account worker processes reduce wall time, with shared output-run ownership. Precision is limited to material finite-design differences, not rare risk or empirical demand calibration.',
            'learning_rule': 'Frozen controller update rules may use own legitimate observations inside each trajectory; no changes after protected results.',
            'recovery': 'Completed worlds are source-bound checkpoints. An interrupted incomplete world is preserved then recomputed from identical source, config and seed in a new account; no completed world is appended twice.',
            'aggregation': 'Only exact executably qualified cohorts; large milestones remain unreached when no validated large-scale aggregation exists. Historical scale projections remain explicitly separate.'}


def scenario_config(base, family, arm):
    if arm not in ARMS:
        raise ValueError('UNREGISTERED_ARM')
    config = copy.deepcopy(base)
    if family == 'low_demand':
        config['contacts_per_day'] = max(1, config['contacts_per_day'] // 2)
    elif family == 'price_war':
        config['market_regime'] = 'price_war'
    elif family == 'shock':
        config['market_regime'] = 'correlated_shock'
    elif family != 'ordinary':
        raise ValueError('UNREGISTERED_FAMILY')
    if arm in {'joint_fast_settlement', 'joint_finite_fast', 'joint_combination', 'simple_combination'}:
        config['settlement_hours'] = 0
        config['policy']['payment_bps'] += 50
        config['intervention_setup_cost'] += 5_000_000
    if arm in {'joint_finite_liability', 'joint_finite_fast', 'joint_combination', 'simple_combination'}:
        config['finite_liability_hours'] = 7 * 24
    if arm in {'joint_channel', 'joint_combination', 'simple_combination'}:
        config['contacts_per_day'] *= 2
        config['intervention_setup_cost'] += 10_000_000
        config['intervention_daily_cost'] += 1_000_000
    if arm in {'joint_retention', 'joint_combination', 'simple_combination'}:
        config['retention_probability'] = min(.99, config['retention_probability'] + .05)
        config['intervention_setup_cost'] += 10_000_000
        config['intervention_daily_cost'] += 1_000_000
    controller = 'simple' if arm.startswith('simple') else 'baseline' if arm == 'baseline' else 'joint'
    return config, controller


def _load_world(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def _save_world(path, result):
    from commercial.persistence import atomic_bytes
    atomic_bytes(Path(path), gzip.compress(canonical(result), mtime=0))


def tasks_for(frozen):
    p, tasks = frozen['protocol'], []
    for family in p['families']:
        for arm in p['arms']:
            primary = arm in {'baseline', 'simple', 'joint'}
            if not primary and family not in p['intervention_families']:
                continue
            for seed in p['seeds'] if primary else p['intervention_seeds']:
                config, controller = scenario_config(frozen['config'], family, arm)
                tasks.append({'family': family, 'arm': arm, 'seed': seed, 'config': config, 'controller': controller})
    return tasks


def _archive_runtime(work, target, *, remove=True):
    if not work.exists():
        return hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    if target.exists():
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(target.read_bytes())), mode='r:') as archive:
            previous_bytes = {member.name: archive.extractfile(member).read() for member in archive.getmembers() if member.isfile()}
        current_bytes = {path.relative_to(work).as_posix(): path.read_bytes() for path in work.rglob('*') if path.is_file() and not path.is_symlink()}
        changes = [name for name, raw in current_bytes.items() if previous_bytes.get(name) != raw]
        if any(name not in previous_bytes or not name.endswith('.actions.jsonl') or not current_bytes[name].endswith(b'\n') or not previous_bytes[name].startswith(current_bytes[name]) for name in changes):
            raise ValueError('CLOSED_RUNTIME_CHANGED_AFTER_ARCHIVAL; original and later files preserved')
        if changes:
            identities = {name: hashlib.sha256(raw).hexdigest() for name, raw in current_bytes.items()}
            variant = target.with_name(target.name.removesuffix('.tar.gz') + '-stale-prefix-' + digest(identities)[:16] + '.tar.gz')
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode='w') as archive:
                for path in sorted(work.rglob('*')):
                    if path.is_file():
                        archive.add(path, arcname=path.relative_to(work).as_posix(), recursive=False)
            from commercial.persistence import atomic_bytes
            atomic_bytes(variant, gzip.compress(raw.getvalue(), mtime=0))
            write_json(variant.with_suffix('.json'), {'scope': 'OBSERVED_STORAGE_PREFIX_ANOMALY', 'canonical_final_runtime_archive': target.name,
                       'canonical_final_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'preserved_stale_prefix_archive': variant.name,
                       'changed_paths': changes, 'description': 'After parallel account execution/close, earlier action-tape prefixes reappeared at redundant loose paths. Complete audited result and the previously verified final runtime archive remain authoritative. Earlier prefixes are preserved, never used to resume completed money state. No additional native financial actions are inferred.'})
        if remove:
            shutil.rmtree(work)
        if remove and work.exists():
            raise ValueError('CLOSED_RUNTIME_DIRECTORY_REMOVAL_FAILED')
        return hashlib.sha256(target.read_bytes()).hexdigest()
    raw = io.BytesIO()
    entries = {}
    with tarfile.open(fileobj=raw, mode='w') as archive:
        for path in sorted(work.rglob('*')):
            if path.is_symlink():
                raise ValueError('RUNTIME_ARCHIVE_SYMLINK_REFUSED')
            if path.is_file():
                relative = path.relative_to(work).as_posix()
                entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                archive.add(path, arcname=relative, recursive=False)
    encoded = gzip.compress(raw.getvalue(), mtime=0)
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(encoded)), mode='r:') as archive:
        recovered = {member.name: hashlib.sha256(archive.extractfile(member).read()).hexdigest() for member in archive.getmembers() if member.isfile()}
    if recovered != entries:
        raise ValueError('LOSSLESS_RUNTIME_ARCHIVE_FAILED')
    from commercial.persistence import atomic_bytes
    atomic_bytes(target, encoded)
    if target.read_bytes() != encoded:
        raise ValueError('RUNTIME_ARCHIVE_WRITE_FAILED')
    if remove:
        shutil.rmtree(work)
    if remove and work.exists():
        raise ValueError('CLOSED_RUNTIME_DIRECTORY_REMOVAL_FAILED')
    return hashlib.sha256(encoded).hexdigest()


def _world_task(task):
    from .growth012 import run_growth
    from verification.growth012 import audit_growth
    cpu = time.process_time()
    output, root = Path(task['output']), Path(task['root'])
    allocation = task['allocation']
    deadline = allocation.get('deadline_utc')
    if deadline and datetime.now(timezone.utc) >= datetime.fromisoformat(deadline):
        raise RuntimeError('REGISTERED_WALL_ALLOCATION_EXHAUSTED; checkpoints preserved')
    if time.process_time() > allocation.get('local_cpu_core_seconds_limit', 7200) / task['workers']:
        raise RuntimeError('REGISTERED_WORKER_CPU_ALLOCATION_EXHAUSTED; checkpoints preserved')
    output_bytes = sum(path.stat().st_size for path in output.rglob('*') if path.is_file() and not path.is_symlink())
    if output_bytes > allocation.get('new_output_bytes_limit', 536870912):
        raise RuntimeError('REGISTERED_OUTPUT_ALLOCATION_EXHAUSTED; checkpoints preserved')
    if source_identity() != task['source']:
        raise ValueError('OPERATING_SOURCE_CHANGED_AFTER_FREEZE')
    family, arm, seed, config, controller = [task[key] for key in ['family', 'arm', 'seed', 'config', 'controller']]
    key = f'{family}-{seed}-{arm}'
    directory = output / 'worlds'
    path, work, runtime = directory / (key + '.json.gz'), directory / key, directory / (key + '.runtime.tar.gz')
    completed_path = directory / (key + '.completed.json')
    if path.exists():
        if not completed_path.exists():
            raise ValueError('UNAUTHENTICATED_COMPLETED_CHECKPOINT; original preserved, no raw account reopened')
        completed = json.loads(completed_path.read_text())
        if completed.get('result_sha256') != hashlib.sha256(path.read_bytes()).hexdigest() or completed.get('config_sha256') != digest(config) or completed.get('source_sha256') != task['source']['sha256']:
            raise ValueError('COMPLETED_CHECKPOINT_IDENTITY_MISMATCH; no raw account reopened')
        result = _load_world(path)
    else:
        if work.exists():
            work.rename(directory / (key + '-interrupted-' + str(time.time_ns())))
        result = run_growth(root, task['manifest'], config, seed, controller=controller, output=work, persist=True)
        _save_world(path, result)
    if result.get('seed') != seed or result.get('controller') != controller or result.get('config') != config:
        raise ValueError('WORLD_CONFIG_SEED_OR_CONTROLLER_IDENTITY')
    audit = audit_growth(result, root=root, manifest=task['manifest'])
    if not audit.get('accepted') or not audit.get('native_replay_accepted'):
        raise ValueError('INDEPENDENT_FINANCIAL_AUDIT_REFUSED')
    if audit['complete_cost_profit_microUSD'] != _number(result, 'profit_microUSD') or audit['net_collected_microUSD'] != _number(result, 'collections_microUSD'):
        raise ValueError('OPERATING_METRIC_DISAGREES_WITH_NATIVE_AUDIT')
    write_json(directory / (key + '.audit.json'), audit)
    completed = {'schema': 'agi-alpha/growth012-completed-world/v1', 'source_sha256': task['source']['sha256'],
                 'config_sha256': digest(config), 'manifest_sha256': digest(task['manifest']), 'seed': seed, 'controller': controller,
                 'result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'actions_sha256': result['ledger']['actions_sha256'],
                 'recovery_authority': 'Authenticated completed gzip result with full independently replayed native actions. Retired raw paths are preserved diagnostic copies and are never reopened by this runner.'}
    write_json(completed_path, completed)
    if work.exists():
        write_json(work / 'RETIRED.json', completed)
    gc.collect()
    constraints = {}
    for rejected in result.get('rejected_growth_actions', []):
        if rejected.get('reason'):
            constraints[rejected['reason']] = constraints.get(rejected['reason'], 0) + 1
    brief = {'seed': seed, 'metrics': copy.deepcopy(result['metrics']), 'milestones': audit['milestones'],
             'cash_survival': audit['cash_survival'], 'binding_constraints': constraints}
    brief['metrics']['cash_microUSD'] = audit['cash_microUSD']
    brief['metrics']['unrestricted_earned_microUSD'] = audit['unrestricted_earned_microUSD']
    receipt = {'family': family, 'arm': arm, 'seed': seed, 'path': 'worlds/' + path.name,
               'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'audit_path': 'worlds/' + key + '.audit.json',
               'completed_receipt': 'worlds/' + completed_path.name, 'completed_receipt_sha256': hashlib.sha256(completed_path.read_bytes()).hexdigest(),
               'runtime_archive': 'worlds/' + runtime.name, 'runtime_archive_sha256': hashlib.sha256(runtime.read_bytes()).hexdigest() if runtime.exists() else None,
               'worker_cpu_seconds': time.process_time() - cpu}
    return brief, receipt


def execute_frozen(output):
    from .growth012 import run_growth
    from .workload012 import prepare_workload
    from .scale import default_config as scale_config, simulate_scale
    from .runner import RunLock
    from verification.growth012 import audit_growth
    output = Path(output).absolute()
    frozen = json.loads((output / 'FROZEN.json').read_text())
    check = {k: v for k, v in frozen.items() if k != 'freeze_sha256'}
    if digest(check) != frozen['freeze_sha256'] or source_identity() != frozen['source'] or source_identity(output / 'source') != frozen['source']:
        raise ValueError('FROZEN_SOURCE_CONFIG_OR_PROTOCOL_CHANGED')
    with RunLock(output):
        started, cpu = time.monotonic(), time.process_time()
        service_root = output / 'source'
        service_path = service_root / 'runtime-services012' / 'MANIFEST.json'
        if service_path.exists():
            manifest = json.loads(service_path.read_text())
        else:
            partial = service_root / 'runtime-services012'
            if partial.exists():
                partial.rename(service_root / ('interrupted-services012-' + str(time.time_ns())))
            manifest = prepare_workload(service_root, 'runtime-services012', per_service=96)
        write_json(output / 'SERVICES.json', manifest)
        parent_audit = service_root / 'campaign/growth-012/PARENT_FUNDING_AUDIT.json'
        if parent_audit.exists():
            shutil.copyfile(parent_audit, output / 'PARENT_FUNDING_AUDIT.json')
        historical = simulate_scale(scale_config(), frozen['protocol']['historical_scale_reference']['seed'])
        write_json(output / 'HISTORICAL_PR19_SCALE.json', historical)
        p = frozen['protocol']
        allocation_path = service_root / 'campaign/growth-012/ALLOCATION.json'
        allocation = json.loads(allocation_path.read_text()) if allocation_path.exists() else {}
        worlds, index, comparisons = {}, [], {}
        world_dir = output / 'worlds'
        world_dir.mkdir(exist_ok=True)
        tasks = tasks_for(frozen)
        for task in tasks:
            worlds.setdefault(task['family'], {}).setdefault(task['arm'], [])
            task.update(output=str(output), root=str(service_root), allocation=allocation,
                        workers=p['workers'], manifest=manifest, source=frozen['source'])
        child_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        with ProcessPoolExecutor(max_workers=p['workers'], mp_context=multiprocessing.get_context('spawn')) as pool:
            for brief, receipt in pool.map(_world_task, tasks):
                work = output / receipt['path'].removesuffix('.json.gz')
                receipt['runtime_archive_sha256'] = _archive_runtime(work, output / receipt['runtime_archive'], remove=False)
                worlds[receipt['family']][receipt['arm']].append(brief)
                index.append(receipt)
                write_json(output / 'CHECKPOINT.json', {'freeze_sha256': frozen['freeze_sha256'],
                           'completed': len(index), 'total': len(tasks), 'last_world': receipt['path'],
                           'completed_world_receipts': index,
                           'completed_worker_cpu_seconds': sum(row['worker_cpu_seconds'] for row in index)})
        child_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        child_cpu = child_after.ru_utime + child_after.ru_stime - child_before.ru_utime - child_before.ru_stime
        for receipt in index:
            work = output / receipt['path'].removesuffix('.json.gz')
            receipt['runtime_archive_sha256'] = _archive_runtime(work, output / receipt['runtime_archive'], remove=False)
            prefix = Path(receipt['runtime_archive']).name.removesuffix('.tar.gz') + '-stale-prefix-*.tar.gz'
            receipt['preserved_storage_prefixes'] = [{'path': 'worlds/' + path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(world_dir.glob(prefix))]
        for family, arms in worlds.items():
            comparisons[family] = {}
            for arm, results in arms.items():
                if arm == 'baseline':
                    continue
                comparator = 'baseline' if arm in {'joint', 'simple'} else 'joint_combination' if arm.startswith('simple') else 'joint'
                reference = {world['seed']: world for world in arms[comparator]}
                comparisons[family][arm] = paired_difference([reference[world['seed']] for world in results], results)
        horizon = frozen['config']['horizon_hours']
        summary = {family: {arm: summarize(results, p['milestones_microUSD'], horizon) for arm, results in arms.items()} for family, arms in worlds.items()}
        report = {'schema': SCHEMA, 'freeze_sha256': frozen['freeze_sha256'], 'source_sha256': frozen['source']['sha256'],
                  'summary': summary, 'paired_comparisons': comparisons, 'index': index,
                  'historical_baseline': {'path': 'HISTORICAL_PR19_SCALE.json', 'sha256': hashlib.sha256((output / 'HISTORICAL_PR19_SCALE.json').read_bytes()).hexdigest(), 'scope': 'Exact preserved PR19 monthly default implementation; separate conditional projection, not matched causal event-clock evidence.'},
                  'all_worlds_independently_audited': True, 'actual_revenue_microUSD': 0,
                  'large_scale_aggregation_validated': False,
                  'resource_receipt': {'process_cpu_seconds': time.process_time() - cpu + child_cpu, 'parent_cpu_seconds': time.process_time() - cpu, 'child_cpu_seconds': child_cpu, 'worker_processes': p['workers'], 'wall_seconds': time.monotonic() - started, 'actual_paid_api_calls': 0}}
        report['next_action'] = next_action(report)
        report['inverse_frontier'] = inverse_frontier(report)
        write_json(output / 'REPORT.json', report)
        write_json(output / 'GROWTH_FRONTIER.json', summary)
        write_json(output / 'NEXT_ACTION.json', report['next_action'])
        write_json(output / 'INVERSE_FRONTIER.json', report['inverse_frontier'])
        (output / 'REPORT.md').write_text(render_report(report))
        return report


def next_action(report):
    by_arm = {}
    for family, arms in report['paired_comparisons'].items():
        for arm, comparison in arms.items():
            if arm in {'joint', 'simple', 'simple_combination'}:
                continue
            by_arm.setdefault(arm, []).append({'family': family, 'mean_delta_collections_microUSD': comparison['mean_delta_collections_microUSD'],
                                              'mean_delta_profit_microUSD': comparison['mean_delta_profit_microUSD'],
                                              'survival_fraction': report['summary'][family][arm]['cash_survival_fraction']})
    rows = [{'intervention': arm, 'mean_delta_collections_microUSD': sum(x['mean_delta_collections_microUSD'] for x in cases) / len(cases),
             'mean_delta_profit_microUSD': sum(x['mean_delta_profit_microUSD'] for x in cases) / len(cases),
             'minimum_condition_survival_fraction': min(x['survival_fraction'] for x in cases), 'conditions': cases,
             'resource_and_contract_changes': intervention_changes(arm)} for arm, cases in by_arm.items()]
    rows.sort(key=lambda x: (x['minimum_condition_survival_fraction'], x['mean_delta_collections_microUSD'], x['mean_delta_profit_microUSD']), reverse=True)
    condition_rankings = {}
    for row in rows:
        for case in row['conditions']:
            condition_rankings.setdefault(case['family'], []).append({**case, 'intervention': row['intervention'], 'resource_and_contract_changes': row['resource_and_contract_changes']})
    for cases in condition_rankings.values():
        cases.sort(key=lambda x: (x['survival_fraction'], x['mean_delta_collections_microUSD'], x['mean_delta_profit_microUSD']), reverse=True)
    eligible = [x for x in condition_rankings.get('ordinary', []) if x['mean_delta_profit_microUSD'] > 0 and x['mean_delta_collections_microUSD'] > 0 and x['survival_fraction'] == 1]
    chosen = eligible[0] if eligible else None
    return {'ranked_executed_interventions': rows, 'selected': chosen,
            'per_condition_rankings': condition_rankings, 'selection_condition_registered_before_confirmation': 'ordinary',
            'decision': 'Retain the demonstrated favorable conditional intervention and test its measurement/cost sensitivity next.' if chosen else 'Retain cash and diagnose the recorded binding constraint; no tested business intervention established positive incremental complete-cost profit.',
            'inverse_planning_scope': 'Smallest supported change can only be selected from executed discrete interventions, not inferred from an optimistic extrapolation. Large milestone feasibility is unresolved when all exact-cohort worlds remain below target.',
            'required_authority': 'Synthetic/local operation only. New real contracts, spending, customers or deployment require their own authorization.',
            'ranking_rule': 'In the preregistered ordinary condition, among interventions with positive incremental complete-cost profit, positive extra collections and no tested cash failure, prefer greatest incremental collections; report setup cost, daily cost, fees, liability timing and other-condition failures alongside. Cross-condition rankings are separate diagnostics, not a universal commercial-success gate. This is a declared finite-set choice, not a universal scalar optimum.',
            'cheapest_discriminating_next_experiment': 'Repeat the selected change at its break-even incremental cost and customer-friction envelope on fresh observations. A loss of extra collections or complete-cost profit overturns retention of that intervention. If none is selected, reproduce the dominant recorded rejection under a one-variable counterfactual before purchasing anything.',
            'uncertainty': 'Finite authored conditions; ranking is conditional and does not certify global economic optimality.'}


def intervention_changes(arm):
    finite = arm in {'joint_finite_liability', 'joint_finite_fast', 'joint_combination', 'simple_combination'}
    fast = arm in {'joint_fast_settlement', 'joint_finite_fast', 'joint_combination', 'simple_combination'}
    channel = arm in {'joint_channel', 'joint_combination', 'simple_combination'}
    retention = arm in {'joint_retention', 'joint_combination', 'simple_combination'}
    return {'setup_microUSD': int(finite) * 5_000_000 + int(fast) * 5_000_000 + int(channel) * 10_000_000 + int(retention) * 10_000_000,
            'extra_daily_microUSD': int(channel) * 1_000_000 + int(retention) * 1_000_000,
            'extra_collection_fee_bps': int(finite) * 50 + int(fast) * 50,
            'liability_hours': 168 if finite else 'preserved permanent native tail',
            'settlement_hours': 0 if fast else 'unchanged',
            'contacts_per_day_multiplier': 2 if channel else 1,
            'retention_probability_increment': .05 if retention else 0,
            'finite_contract_extra_customer_friction_USD': 2 if finite else 0,
            'basis': 'Costed authored contract/channel/retention hypotheses, not observed supplier quotes or empirically achieved demand improvements.'}


def inverse_frontier(report):
    arms = {'joint': [], 'joint_fast_settlement': ['settlement'], 'joint_finite_liability': ['liability_contract'],
            'joint_finite_fast': ['liability_contract', 'settlement'], 'joint_channel': ['channel'], 'joint_retention': ['retention'],
            'joint_combination': ['liability_contract', 'settlement', 'channel', 'retention']}
    rows = []
    targets = sorted({x['target_microUSD'] for family in report['summary'].values() for values in family.values() for x in values['frontier']})
    for target in targets:
        by_condition = {}
        for family, family_arms in report['summary'].items():
            candidates, observed = [], []
            for arm, changes in arms.items():
                if arm not in family_arms:
                    continue
                summary = family_arms[arm]
                milestone = next(x for x in summary['frontier'] if x['target_microUSD'] == target)
                case = {'arm': arm, 'changed_dimensions': changes, 'attainment_fraction': milestone['attainment_fraction'],
                        'attained_worlds': milestone['attained'], 'worlds': milestone['runs'],
                        'mean_profit_microUSD': summary['profit_microUSD']['mean'], 'survival_fraction': summary['cash_survival_fraction'],
                        'resource_and_contract_changes': intervention_changes(arm)}
                observed.append(case)
                if case['attained_worlds'] > 0 and case['mean_profit_microUSD'] > 0 and case['survival_fraction'] == 1:
                    candidates.append(case)
            minimum = min((len(c['changed_dimensions']) for c in candidates), default=None)
            by_condition[family] = {'all_executed_candidates': observed,
                                    'minimal_changed_dimension_candidates': [c for c in candidates if len(c['changed_dimensions']) == minimum],
                                    'unresolved_is_not_impossible': not candidates}
        rows.append({'target_microUSD': target, 'per_condition': by_condition,
                     'criterion': 'Within each condition, at least one audited profitable funded first passage, positive ending mean complete-cost profit and full observed cash survival. Every attainment fraction and nonreaching path is shown. Minimum means fewest changed dimensions among executed choices; incomparable cash, fee and time changes remain parallel candidates.',
                     'global_robustness_is_not_a_commercial_GO_requirement': True})
    return {'rows': rows, 'scope': 'Inverse comparison of a finite executed intervention set. No continuous minimum, forecast achievement or terminal enterprise value is invented.'}


def render_report(report):
    lines = ['# Event-driven growth comparison 012', '', 'Conditional simulated operation with actual synthetic service production and separate acceptance. Real collected revenue is USD 0.', '', '| Condition | Controller / intervention | Mean collected USD | Mean complete-cost profit USD | Mean paid jobs | Cash survival |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for family, arms in report['summary'].items():
        for arm, values in arms.items():
            lines.append(f"| {family} | {arm} | {values['collected_microUSD']['mean'] / 1_000_000:.2f} | {values['profit_microUSD']['mean'] / 1_000_000:.2f} | {values['paid_jobs']['mean']:.2f} | {values['cash_survival_fraction']:.1%} |")
    lines += ['', 'All paired worlds, unsuccessful paths and unreached targets remain in REPORT.json and GROWTH_FRONTIER.json. Conditional hitting-time quantiles accompany unconditional attainment and nonreaching counts. No unvalidated aggregation is used to claim large-scale growth.', '', report['next_action']['decision'], '', 'The preserved PR19 monthly default is reproduced separately in HISTORICAL_PR19_SCALE.json; it is not substituted for a matched event-controller counterfactual.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--freeze-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--config')
    args = parser.parse_args(argv)
    if args.resume and (args.config or args.freeze_only):
        parser.error('--resume cannot change a frozen configuration')
    if not args.resume:
        config = json.loads(Path(args.config).read_text()) if args.config else None
        frozen = freeze_run(args.output, smoke=args.smoke, config=config)
        print(json.dumps({'freeze_sha256': frozen['freeze_sha256'], 'source_sha256': frozen['source']['sha256'], 'output': str(Path(args.output).absolute())}, sort_keys=True))
    if not args.freeze_only:
        result = execute_frozen(args.output)
        print(json.dumps({'completed_worlds': len(result['index']), 'all_worlds_independently_audited': result['all_worlds_independently_audited'], 'output': str(Path(args.output).absolute())}, sort_keys=True))


if __name__ == '__main__':
    main()
