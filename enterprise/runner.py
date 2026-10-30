"""Freeze, execute and audit the current experiment without Git at runtime."""
import argparse
import copy
import gzip
import fcntl
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import zipfile

SCHEMA = 'agi-alpha/enterprise011-run/v1'
ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    from commercial.persistence import atomic_bytes
    atomic_bytes(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n')


class RunLock:
    def __init__(self, output):
        self.path = Path(output)/'RUN.lock'
    def __enter__(self):
        if self.path.is_symlink():
            raise ValueError('RUN_LOCK_SYMLINK_REFUSED')
        self.stream = self.path.open('a+')
        try:
            fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stream.close()
            raise ValueError('ANOTHER_CURRENT_RUN_OWNS_OUTPUT') from None
        return self
    def __exit__(self, *args):
        self.stream.close()


def source_paths(root):
    paths = []
    for directory in ['enterprise', 'commercial', 'vendor/alpha_claim', 'portfolio_scale', 'portfolio25']:
        paths += [p for p in (root / directory).glob('*') if p.is_file() and p.suffix in {'.py', '.json', '.md'}]
    paths += [root / p for p in ['vendor/__init__.py', 'experiments/__init__.py', 'experiments/commerce006.py', 'requirements-commercial010.txt']]
    paths += [root / ('flywheel/' + p) for p in ['__init__.py', 'strategy.py', 'evidence_executor.py', 'retention.py']]
    paths += list((root / 'campaign/enterprise-011').glob('*'))
    paths += list((root / 'tests').glob('test_enterprise*.py'))
    return sorted({p.relative_to(root).as_posix() for p in paths if p.is_file()})


def source_identity(root):
    files = {}
    for name in source_paths(root):
        path = root / name
        if path.is_symlink():
            raise ValueError('SOURCE_SYMLINK_REFUSED')
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'files': files, 'sha256': digest(files)}


def protocol(smoke=False):
    return {'schema': 'agi-alpha/enterprise011-confirmation/v1', 'scope': 'CONDITIONAL_SIMULATION',
            'edition': 'engineering-smoke' if smoke else 'fresh-confirmation-001',
            'seeds': [11011] if smoke else list(range(2610301101, 2610301109)),
            'development_seeds': [11011, 11012],
            'regimes': ['ordinary'] if smoke else ['ordinary', 'price_war', 'differentiation', 'correlated_shock'],
            'choice_models': ['utility'] if smoke else ['utility', 'logit'],
            'rival_models': ['responsive'] if smoke else ['responsive', 'lagged'],
            'central_region': ['ordinary', 'differentiation'], 'minimum_region_success_fraction': .75,
            'paired_control_seed_count': 1 if smoke else 2,
            'thresholds': {'cycles': 24, 'acquired_customers': 3, 'paid_jobs': 12, 'repeat_customers': 2,
                           'earned_funded_cycles': 2, 'positive_complete_cost_profit': True, 'cash_survival': True},
            'weights': 'Equal finite-design weights, not estimated real-world probabilities',
            'uncertainty': 'Wilson interval describes finite seeded simulation proportions; scenario worlds and paired arms are dependent, not an inferential sample of real buyers.',
            'selection': 'Policy and price-search procedure frozen before confirmation. No outcome-driven threshold or regime reclassification.',
            'sensitivity_cases': ['setup_upper', 'attempt_lower', 'attempt_upper', 'human_half', 'human_double', 'half_arrivals', 'latency_parity'],
            'recovery_granularity': 'Completed worlds are atomic checkpoints; interrupted worlds recompute from their unchanged seed/source. No completed-world job or payment is appended twice.',
            'scale_seeds': [11011] if smoke else list(range(2610302101, 2610302117))}


def freeze_run(output, smoke=False):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError('NEW_UNSYMLINKED_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    identity = source_identity(ROOT)
    snapshot = output / 'source'
    for name in identity['files']:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (snapshot / 'tests/__init__.py').touch()
    if source_identity(snapshot) != identity:
        raise ValueError('SNAPSHOT_IDENTITY_MISMATCH')
    from .model import default_policy
    frozen = {'schema': SCHEMA, 'source': identity, 'protocol': protocol(smoke), 'policy': default_policy(),
              'registered_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'git_commit': None, 'model_usage': 'Code-authored deterministic service tools; no paid model calls. Host assistant billing unavailable; conditional conservative costs, never CPU-as-human-time.'}
    try:
        frozen['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    frozen['freeze_sha256'] = digest(frozen)
    write_json(output / 'FROZEN.json', frozen)
    return output


def wilson(successes, n):
    if not n:
        return None
    p, z = successes / n, 1.959963984540054
    d = 1 + z*z/n
    mid = (p + z*z/(2*n))/d
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [max(0, mid-half), min(1, mid+half)]


def compact(result):
    brief = {k: v for k, v in result.items() if k not in {'ledger', 'cycles', 'decisions', 'events', 'pricing_receipts', 'price_searches', 'cost_receipts'}}
    prices = [d['price'] for c in result.get('cycles', []) for d in c['decisions'] if d.get('outcome') == 'SIMULATED_SETTLED']
    brief['settled_prices_microUSD'] = {'minimum': min(prices, default=0), 'maximum': max(prices, default=0), 'mean': sum(prices)/len(prices) if prices else 0}
    return brief


def result_paid(result):
    return result.get('paid_jobs', result.get('settled_jobs', 0))


def result_go(result):
    return result.get('conditional_simulated_go', result.get('conditional_flywheel_succeeded', False))


def aggregate(results):
    successes = sum(result_go(r) for r in results)
    summaries = [r['ledger']['summary'] for r in results]
    return {'runs': len(results), 'successful_runs': successes, 'success_fraction': successes / len(results) if results else 0,
            'wilson_simulation_interval': wilson(successes, len(results)),
            'paid_jobs_total': sum(result_paid(r) for r in results),
            'profit_microUSD': {'minimum': min((s['profit'] for s in summaries), default=0),
                                'mean': sum(s['profit'] for s in summaries) / len(summaries) if summaries else 0,
                                'maximum': max((s['profit'] for s in summaries), default=0)},
            'cash_survival_fraction': sum(s['cash'] >= s['payables'] + s['custodyReserve'] + s['tailReserve'] + s['workingCapital'] and not s['investmentStopped'] for s in summaries) / len(summaries) if summaries else 0,
            'scope': 'Finite conditional simulation; sums across alternative worlds are not enterprise revenue.'}


def _save_result(path, result):
    raw = canonical(result)
    from commercial.persistence import atomic_bytes
    if path.exists():
        raise FileExistsError(path)
    atomic_bytes(path, gzip.compress(raw, mtime=0))
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'uncompressed_sha256': hashlib.sha256(raw).hexdigest()}


def tasks_for(frozen):
    p, tasks = frozen['protocol'], []
    arms = ['strategic_autonomous', 'fixed_autonomous', 'strategic_original', 'fixed_original']
    for seed, regime, choice, rival in itertools.product(p['seeds'], p['regimes'], p['choice_models'], p['rival_models']):
        tasks.append((seed, regime, choice, rival, arms[0], False))
    for seed, regime, choice in itertools.product(p['seeds'][:p['paired_control_seed_count']], [r for r in p['regimes'] if r in p['central_region']], p['choice_models']):
        tasks += [(seed, regime, choice, 'responsive', arm, True) for arm in arms[1:]]
    for seed, regime in itertools.product(p['seeds'][:p['paired_control_seed_count']], [r for r in p['regimes'] if r in p['central_region']]):
        tasks += [(seed, regime, p['choice_models'][0], 'responsive', arm, True) for arm in ['strategic_no_bundle', 'strategic_fixed_allocation']]
    for seed, choice, case in itertools.product(p['seeds'][:p['paired_control_seed_count']], p['choice_models'], p['sensitivity_cases']):
        tasks.append((seed, 'ordinary', choice, 'responsive', 'sensitivity_' + case, True))
    return tasks


def task_policy(frozen, arm):
    policy = copy.deepcopy(frozen['policy'])
    if arm == 'strategic_no_bundle':
        policy['bundle_enabled'] = False
    elif arm == 'strategic_fixed_allocation':
        policy['dynamic_allocation'] = False
    elif arm.startswith('sensitivity_'):
        case = arm.removeprefix('sensitivity_')
        if case == 'setup_upper':
            policy['setup_cost'] = 1500_000_000
        elif case in {'attempt_lower', 'attempt_upper'}:
            base = sum(policy['costs_usd'][k] for k in ['inference_tools_production', 'independent_verification_corrections', 'compute_storage_infrastructure', 'delivery_support_obligation', 'maintenance_failure_retry'])
            factor = (policy['cost_ranges_usd']['per_attempt'][0] if case == 'attempt_lower' else policy['cost_ranges_usd']['per_attempt'][1]) / base
            for key in ['inference_tools_production', 'independent_verification_corrections', 'compute_storage_infrastructure', 'delivery_support_obligation', 'maintenance_failure_retry']:
                policy['costs_usd'][key] *= factor
        elif case in {'human_half', 'human_double'}:
            for service in policy['human_services'].values():
                service['stages_hours'] = {k: v * (.5 if case == 'human_half' else 2) for k, v in service['stages_hours'].items()}
        elif case == 'half_arrivals':
            policy['regimes']['ordinary']['arrival_probability'] *= .5
        elif case == 'latency_parity':
            policy['regimes']['ordinary']['rival_hours'] = policy['regimes']['ordinary']['our_hours']
        else:
            raise ValueError('UNREGISTERED_SENSITIVITY')
    actual_arm = arm if arm in {a['id'] for a in policy['arms']} else 'strategic_autonomous'
    return policy, next(a for a in policy['arms'] if a['id'] == actual_arm)


def stable_world(result):
    if isinstance(result, dict):
        return {k: stable_world(v) for k, v in result.items() if k not in {'process_cpu_seconds', 'production_cpu_seconds', 'production_wall_seconds'}}
    if isinstance(result, list):
        return [stable_world(v) for v in result]
    return result


def validate_world(result, frozen, manifest, task, root, *, deterministic=False):
    from commercial.ledger import audit
    seed, regime, choice, rival, arm, _ = task
    policy, declared_arm = task_policy(frozen, arm)
    expected = {'policy_sha256': digest(policy), 'manifest_sha256': digest(manifest), 'seed': seed, 'regime': regime, 'choice_model': choice, 'competitor_model': rival, 'arm': declared_arm}
    if any(result.get(k) != v for k, v in expected.items()):
        raise ValueError('WORLD_TASK_OR_MANIFEST_IDENTITY_MISMATCH')
    checked = audit(result['ledger'], root=root, manifest=manifest)
    if result['summary'] != checked['summary'] or result['paid_jobs'] != sum(o['state'] == 'released' for o in checked['orders']):
        raise ValueError('WORLD_DERIVED_FINANCIAL_SUMMARY_MISMATCH')
    if deterministic:
        from .model import run_world
        replay = run_world(root, manifest, policy, seed, regime, choice, declared_arm, competitor_model=rival)
        if stable_world(replay) != stable_world(result):
            raise ValueError('WORLD_OPERATIONAL_REPLAY_MISMATCH')
    return checked


def execute_frozen(output):
    output = Path(output).absolute()
    frozen = json.loads((output / 'FROZEN.json').read_text())
    freeze_sha = frozen.pop('freeze_sha256')
    if digest(frozen) != freeze_sha or source_identity(ROOT) != frozen['source']:
        raise ValueError('FROZEN_SOURCE_OR_PROTOCOL_CHANGED')
    frozen['freeze_sha256'] = freeze_sha
    from .services import prepare_services
    from .model import run_world
    from .scale import default_config, evaluate_scale
    start, cpu = time.monotonic(), time.process_time()
    manifest_path = ROOT / 'runtime-services/MANIFEST.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        partial = ROOT / 'runtime-services'
        if partial.exists():
            shutil.move(str(partial), str(ROOT / ('interrupted-services-' + str(time.time_ns()))))
        manifest = prepare_services(ROOT, 'runtime-services')
    write_json(output / 'SERVICES.json', manifest)
    p = frozen['protocol']
    results, index, compact_results = [], [], []
    results_dir = output / 'worlds'
    results_dir.mkdir(exist_ok=True)
    controls = []
    tasks = tasks_for(frozen)
    for n, (seed, regime, choice, rival, arm, control) in enumerate(tasks):
        ident = f'{seed}-{regime}-{choice}-{rival}-{arm}'
        path = results_dir / (ident + '.json.gz')
        world_policy, declared_arm = task_policy(frozen, arm)
        if path.exists():
            try:
                result = json.loads(gzip.decompress(path.read_bytes()))
            except (ValueError, OSError, EOFError):
                shutil.move(str(path), str(path) + '.interrupted-' + str(time.time_ns()))
                result = None
            if result is not None:
                validate_world(result, frozen, manifest, tasks[n], ROOT, deterministic=True)
        else:
            result = None
        if result is None:
            result = run_world(ROOT, manifest, world_policy, seed, regime, choice, declared_arm, competitor_model=rival)
            _save_result(path, result)
        record = {'id': ident, 'control': control, **_file_record(path, output)}
        index.append(record)
        brief = {'id': ident, 'control': control, **compact(result)}
        compact_results.append(brief)
        (controls if control else results).append(result)
        write_json(output / 'PROGRESS.json', {'completed': n+1, 'planned': len(tasks), 'last': ident, 'freeze_sha256': freeze_sha})
        if time.monotonic() - start > 1500 or time.process_time() - cpu > 6000:
            raise TimeoutError('REGISTERED_EVALUATION_RESOURCE_BOUNDARY; CHECKPOINT_PRESERVED')
    central = [r for r in results if r.get('regime', r.get('world')) in p['central_region']]
    grouped = {}
    for regime in p['regimes']:
        grouped[regime] = aggregate([r for r in results if r.get('regime', r.get('world')) == regime])
    central_summary = aggregate(central)
    go = central_summary['runs'] > 0 and central_summary['success_fraction'] >= p['minimum_region_success_fraction'] and central_summary['cash_survival_fraction'] == 1
    scale = evaluate_scale(default_config(), p['scale_seeds'])
    write_json(output / 'SCALE.json', scale)
    representative = next((r for r in results if result_go(r)), results[0])
    from .portfolio import admitted_portfolio
    write_json(output / 'PORTFOLIO.json', admitted_portfolio(ROOT, manifest))
    from .frontier import run_frontier
    frontier = run_frontier(ROOT, manifest, representative)
    write_json(output / 'FRONTIER.json', frontier)
    report = {'schema': SCHEMA, 'scope': 'CONDITIONAL_SIMULATION', 'source_sha256': frozen['source']['sha256'], 'freeze_sha256': freeze_sha,
              'protocol': p, 'service_count': len({j['service_id'] for j in manifest['jobs'] if j['accepted']}),
              'actual_artifacts': len(manifest['jobs']), 'central_region': central_summary, 'regimes': grouped,
              'representative': compact(representative), 'representative_ledger_summary': representative['ledger']['summary'],
              'controls': compact_results[len(results):], 'all_world_summaries': compact_results,
              'frontier': {k: v for k, v in frontier.items() if k not in {'ledger', 'supplemental_ledger'}},
              'verdicts': {'executed_service_capability': 'PASS_BOUNDED_SYNTHETIC_INPUTS',
                           'conditional_simulated_commercial_flywheel': 'SUCCEEDED' if go else 'NOT_ESTABLISHED',
                           'actual_commercial_operation': 'NOT_EXECUTED', 'capability_compounding_invention': 'NOT_ESTABLISHED', 'blue_sky_enablement': 'NOT_ESTABLISHED'},
              'conclusion': 'A conditional simulated commercial flywheel succeeded under the tested central conditions.' if go else 'Current conditional criteria were not met; all trajectories retained.',
              'resource_receipt': {'worker_cpu_seconds': time.process_time()-cpu, 'worker_wall_seconds': time.monotonic()-start, 'billing': 'UNAVAILABLE', 'model_calls': 0},
              'evidence_limits': ['Demand, willingness to pay, human task hours, service latency and autonomous costs are disclosed assumptions, not observed market receipts.', 'Actual execution uses deterministic tools constructed by the assistant; no frontier provider API was called.', 'Procedurally separate checkers share authors and host; no external certification.', 'Initial seed may continue backing reserves. Earned delivery financing is separately witnessed.', 'Scale trajectories are conditional planning simulations, separate from the native audited small-cohort ledger.']}
    write_json(output / 'INDEX.json', {'freeze_sha256': freeze_sha, 'worlds': index})
    write_json(output / 'REPORT.json', report)
    write_json(output / 'COMPLETE.json', {'report_sha256': hashlib.sha256((output/'REPORT.json').read_bytes()).hexdigest(), 'source_sha256': frozen['source']['sha256'], 'completed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    print(json.dumps({'conclusion': report['conclusion'], 'worlds': len(tasks), 'report': str(output/'REPORT.json')}), flush=True)


def _file_record(path, root):
    return {'path': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def audit_run(output):
    output = Path(output).absolute()
    if ROOT != output / 'source':
        completed = subprocess.run([sys.executable, '-m', 'enterprise', '_audit', '--output', str(output)], cwd=output/'source', capture_output=True, text=True)
        if completed.returncode:
            raise ValueError('SNAPSHOT_AUDIT_FAILED: ' + completed.stderr.strip().splitlines()[-1])
        return json.loads(completed.stdout)
    frozen = json.loads((output/'FROZEN.json').read_text())
    expected = frozen.pop('freeze_sha256')
    if digest(frozen) != expected or source_identity(output/'source') != frozen['source']:
        raise ValueError('FREEZE_OR_SOURCE_TAMPERED')
    manifest = json.loads((output/'SERVICES.json').read_text())
    index = json.loads((output/'INDEX.json').read_text())
    if index.get('freeze_sha256') != expected:
        raise ValueError('INDEX_FREEZE_IDENTITY_MISMATCH')
    records = index['worlds']
    tasks = tasks_for(frozen)
    expected_ids = [f'{s}-{r}-{c}-{v}-{a}' for s, r, c, v, a, _ in tasks]
    if [r.get('id') for r in records] != expected_ids:
        raise ValueError('COMPLETE_UNIQUE_PREREGISTERED_COVERAGE_REQUIRED')
    results, briefs = [], []
    for item, task in zip(records, tasks):
        if item.get('control') is not task[-1] or item['path'] != 'worlds/' + item['id'] + '.json.gz':
            raise ValueError('EXACT_RESULT_PATH_AND_ARM_REQUIRED')
        path = output/item['path']
        if _file_record(path, output) != {k: item[k] for k in ['path', 'sha256', 'bytes']}:
            raise ValueError('RESULT_BYTES_CHANGED')
        result = json.loads(gzip.decompress(path.read_bytes()))
        validate_world(result, frozen, manifest, task, output/'source', deterministic=True)
        briefs.append({'id': item['id'], 'control': item['control'], **compact(result)})
        if not item['control']:
            results.append(result)
    report_raw = (output/'REPORT.json').read_bytes()
    completion = json.loads((output/'COMPLETE.json').read_text())
    if hashlib.sha256(report_raw).hexdigest() != completion['report_sha256']:
        raise ValueError('REPORT_SUMMARY_TAMPERED')
    report = json.loads(report_raw)
    central = aggregate([r for r in results if r['regime'] in frozen['protocol']['central_region']])
    go = central['runs'] > 0 and central['success_fraction'] >= frozen['protocol']['minimum_region_success_fraction'] and central['cash_survival_fraction'] == 1
    if report['central_region'] != central or report['all_world_summaries'] != briefs or report['verdicts']['conditional_simulated_commercial_flywheel'] != ('SUCCEEDED' if go else 'NOT_ESTABLISHED'):
        raise ValueError('INDEPENDENT_REPORT_DERIVATION_MISMATCH')
    for regime in frozen['protocol']['regimes']:
        if report['regimes'][regime] != aggregate([r for r in results if r['regime'] == regime]):
            raise ValueError('REGIME_SUMMARY_TAMPERED')
    representative = next((r for r in results if result_go(r)), results[0])
    contracts = len({j['service_id'] for j in manifest['jobs'] if j['accepted']})
    if report['representative'] != compact(representative) or report['representative_ledger_summary'] != representative['ledger']['summary'] or report['controls'] != [b for b in briefs if b['control']] or report['service_count'] != contracts or report['actual_artifacts'] != len(manifest['jobs']) or report['protocol'] != frozen['protocol'] or report['source_sha256'] != frozen['source']['sha256'] or report['freeze_sha256'] != expected:
        raise ValueError('REPORT_REPRESENTATIVE_OR_SCOPE_TAMPERED')
    fixed_verdicts = {'executed_service_capability': 'PASS_BOUNDED_SYNTHETIC_INPUTS', 'actual_commercial_operation': 'NOT_EXECUTED', 'capability_compounding_invention': 'NOT_ESTABLISHED', 'blue_sky_enablement': 'NOT_ESTABLISHED'}
    if any(report['verdicts'].get(k) != v for k, v in fixed_verdicts.items()):
        raise ValueError('INDEPENDENT_VERDICT_SCOPE_TAMPERED')
    from .portfolio import admitted_portfolio
    if json.loads((output/'PORTFOLIO.json').read_text()) != admitted_portfolio(output/'source', manifest):
        raise ValueError('ADMISSION_REPORT_TAMPERED')
    from .scale import default_config, evaluate_scale
    if json.loads((output/'SCALE.json').read_text()) != evaluate_scale(default_config(), frozen['protocol']['scale_seeds']):
        raise ValueError('SCALE_PROJECTION_TAMPERED')
    frontier = json.loads((output/'FRONTIER.json').read_text())
    if report['frontier'] != {k: v for k, v in frontier.items() if k not in {'ledger', 'supplemental_ledger'}}:
        raise ValueError('FRONTIER_REPORT_TAMPERED')
    if frontier['commercial_trajectory_actions_sha256'] != representative['ledger']['actions_sha256'] or frontier['before'] != representative['ledger']['summary']:
        raise ValueError('FRONTIER_BASE_TRAJECTORY_CHANGED')
    if frontier.get('supplemental_ledger'):
        from commercial.ledger import audit
        extension = audit(frontier['supplemental_ledger'], root=output/'source', manifest=manifest)
        base_actions = representative['ledger']['actions']
        if frontier['supplemental_ledger']['actions'][:len(base_actions)] != base_actions or extension['summary'] != frontier['after'] or extension['summary']['collections'] != frontier['before']['collections'] or extension['summary']['expenses'] - frontier['before']['expenses'] != frontier['budget_microUSD']:
            raise ValueError('FRONTIER_EARNED_FUNDING_RECONCILIATION')
    return {'accepted': True, 'source_sha256': frozen['source']['sha256'], 'world_ledgers_independently_replayed': len(records)}


def package_run(output, archive):
    output, archive = Path(output).absolute(), Path(archive).absolute()
    if archive.exists() or output in archive.parents:
        raise FileExistsError('NEW_ARCHIVE_OUTSIDE_RUN_REQUIRED')
    audit_run(output)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(output.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and not path.is_symlink():
                z.write(path, path.relative_to(output))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('ARCHIVE_CRC_FAILURE')
    return {'path': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run'); run.add_argument('--output', required=True); run.add_argument('--smoke', action='store_true')
    for name in ['audit', '_audit', 'resume', '_worker']:
        sub.add_parser(name).add_argument('--output', required=True)
    package = sub.add_parser('package'); package.add_argument('--output', required=True); package.add_argument('--archive', required=True)
    args = parser.parse_args()
    if args.command == 'run':
        output = freeze_run(args.output, args.smoke)
        subprocess.run([sys.executable, '-m', 'enterprise', '_worker', '--output', str(output)], cwd=output/'source', check=True)
    elif args.command in {'resume', '_worker'}:
        if args.command == 'resume' and ROOT != Path(args.output).absolute()/'source':
            subprocess.run([sys.executable, '-m', 'enterprise', '_worker', '--output', str(Path(args.output).absolute())], cwd=Path(args.output).absolute()/'source', check=True)
        else:
            with RunLock(args.output):
                execute_frozen(args.output)
    elif args.command in {'audit', '_audit'}:
        print(json.dumps(audit_run(args.output)))
    else:
        print(json.dumps(package_run(args.output, args.archive)))
