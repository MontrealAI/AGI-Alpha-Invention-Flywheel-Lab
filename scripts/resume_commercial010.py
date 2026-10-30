"""Resume the unchanged frozen campaign from externally inventoried complete worlds.

This recovery instrument is outside the frozen candidate. It neither changes
policies nor refunds interrupted resource reservations. Every reused monetary
state is replayed through the existing pinned native exchange before copying.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regular(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('RELATIVE_RECOVERY_PATH_REQUIRED')
    path = Path(root) / p
    if not path.is_file() or path.is_symlink() or any(x.is_symlink() for x in path.parents):
        raise ValueError('REGULAR_RECOVERY_FILE_REQUIRED')
    return path


def load_inventory(path, expected, freeze_expected, previous_root=None):
    from commercial.ledger import strict_json
    path = Path(path)
    if path.is_symlink() or sha(path) != expected:
        raise ValueError('EXTERNAL_INTERRUPTION_INVENTORY_MISMATCH')
    inventory = strict_json(path.read_bytes())
    if inventory.get('schema') != 'agi-alpha/commercial010-interrupted-run/v1' or inventory.get('source_freeze_sha256') != freeze_expected or inventory.get('confirmation_completed') != 0:
        raise ValueError('INVENTORY_SCOPE_OR_FROZEN_SOURCE_MISMATCH')
    root = Path(previous_root or inventory['original_run_root']).absolute()
    directories = inventory['complete_world_directories']
    if not isinstance(directories, list) or len(set(directories)) != len(directories):
        raise ValueError('UNIQUE_COMPLETE_WORLD_INVENTORY_REQUIRED')
    for directory in directories:
        p = Path(directory)
        if p.parts[:2] != ('artifacts', 'exploration') or '..' in p.parts or p.is_absolute():
            raise ValueError('ONLY_COMPLETED_EXPLORATION_MAY_BE_REUSED')
        if str(p / 'RESULT.json') not in inventory['files'] or str(p / 'exchange.sqlite') not in inventory['files']:
            raise ValueError('COMPLETE_RESULT_AND_NATIVE_DATABASE_REQUIRED')
    for relative, metadata in inventory['files'].items():
        source = regular(root, relative)
        if set(metadata) != {'bytes', 'sha256'} or source.stat().st_size != metadata['bytes'] or sha(source) != metadata['sha256']:
            raise ValueError('INTERRUPTED_ARTIFACT_CHANGED ' + relative)
    return inventory, root


def validate_world(result, kwargs):
    from commercial.ledger import audit, digest
    from commercial.market import price_quote
    manifest, policy = kwargs['manifest'], kwargs['policy']
    expected = {'scope': 'SIMULATED', 'world': kwargs['world']['id'], 'seed': kwargs['seed'],
                'arm': kwargs['arm'], 'price_multiplier_bps': kwargs['multiplier'],
                'policy_sha256': digest(policy), 'cohort_sha256': digest(manifest),
                'actual_collections': 0, 'actual_profit': None,
                'first_price': price_quote(policy, kwargs['multiplier'], False),
                'repeat_price': price_quote(policy, kwargs['multiplier'], True),
                'cohort_jobs': len(manifest['jobs']),
                'failed_jobs': sum(not x['accepted'] for x in manifest['jobs']),
                'extra_failed_attempts': max(0, len(manifest['attempts']) - len(manifest['jobs'])),
                'charged_cost_units': len(manifest['jobs']) + max(0, len(manifest['attempts']) - len(manifest['jobs'])),
                'complete_cost_model': policy['cost_basis'], 'terminal_obligations': policy['terminal_obligations']}
    if any(result.get(k) != v for k, v in expected.items()):
        raise ValueError('RECOVERY_FROZEN_KWARGS_OR_COHORT_MISMATCH')
    native_contract = 'commercial010/' + digest({'policy': policy, 'world': kwargs['world'], 'seed': kwargs['seed'], 'multiplier': kwargs['multiplier'], 'manifest': digest(manifest), 'arm': kwargs['arm']})
    if result['ledger']['config']['contract'] != native_contract or result['ledger']['config']['opening'] != policy['opening'] or result['ledger']['config']['working'] != policy['working']:
        raise ValueError('RECOVERY_NATIVE_CONTRACT_OR_CAPITAL_MISMATCH')
    checked = audit(result['ledger'], root=kwargs['root'], manifest=manifest,
                    expected_actions_sha256=result['ledger']['actions_sha256'])
    states = {x['id']: x['state'] for x in checked['orders']}
    paid, earned, customers = 0, 0, {}
    eligible = sorted(x['id'] for x in manifest['jobs'] if x['accepted'])
    for i, cycle in enumerate(result['cycles']):
        selected = eligible[i * policy['jobs_per_cycle']:(i + 1) * policy['jobs_per_cycle']]
        if cycle['cycle'] != i or cycle['jobs'] != selected:
            raise ValueError('RECOVERY_COHORT_SEQUENCE_MISMATCH')
        collected = 0
        for decision in cycle['decisions']:
            ident = 'SIM-order-' + str(i) + '-' + decision['job_id']
            settled = states.get(ident) == 'released'
            if settled != (decision.get('outcome') == 'SIMULATED_COLLECTED'):
                raise ValueError('RECOVERY_COLLECTION_STATE_MISMATCH')
            if settled:
                collected += 1
                customers[decision['buyer']] = customers.get(decision['buyer'], 0) + 1
        if collected != cycle['collected']:
            raise ValueError('RECOVERY_CYCLE_COLLECTION_TOTAL_MISMATCH')
        paid += collected
        if cycle['funding'] == 'PRIOR_UNRESTRICTED_SIMULATED_EARNINGS':
            ident = 'delivery-capacity-' + str(i)
            matching = [x for x in checked['investments'] if x['id'] == ident and x['state'] == 'complete']
            if len(matching) != 1 or int(matching[0]['actual']) != cycle['charged_base_budget']:
                raise ValueError('RECOVERY_EARNED_FUNDING_PROVENANCE_MISMATCH')
            earned += int(collected > 0)
    s = checked['summary']
    repeat = sum(v > 1 for v in customers.values())
    go = (len(result['cycles']) == policy['cycles'] and paid >= policy['minimum_paid_jobs'] and
          earned >= policy['minimum_earned_cycles'] and repeat >= policy['minimum_repeat_buyers'] and
          s['profit'] > 0 and s['unrestrictedEarned'] > 0 and s['payables'] == 0 and
          s['custodyRestricted'] == 0 and not s['investmentStopped'])
    derived = {'paid_jobs': paid, 'earned_funded_cycles': earned, 'repeat_buyers': repeat,
               'conditional_simulated_go': go, 'available_earned_surplus': s['unrestrictedEarned'],
               'captured_simulated_surplus': s['profit'],
               'reinvested_earned': sum(int(x['actual']) for x in checked['investments'] if x['state'] == 'complete')}
    if any(result.get(k) != v for k, v in derived.items()):
        raise ValueError('RECOVERY_DERIVED_OUTCOME_MISMATCH')
    return {'accepted': True, 'scope': 'SIMULATED_ENGINEERING_RECOVERY',
            'actions_sha256': result['ledger']['actions_sha256'], 'native_summary': s, 'derived': derived}


def check_database(directory, result):
    database = Path(directory) / 'exchange.sqlite'
    db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        journal = [dict(x) for x in db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')]
        investments = [dict(x) for x in db.execute('SELECT * FROM investments ORDER BY id')]
        witnesses = [dict(x) for x in db.execute('SELECT * FROM investment_events ORDER BY seq')]
        orders = [{k: dict(x)[k] for k in ('id', 'buyer', 'price', 'state', 'refund_due', 'compensation_due', 'custody')}
                  for x in db.execute('SELECT * FROM trades ORDER BY id')]
        for key, actual in [('journal', journal), ('investments', investments), ('investment_witnesses', witnesses), ('orders', orders)]:
            if result['ledger'][key] != actual:
                raise ValueError('RECOVERY_NATIVE_DATABASE_' + key.upper() + '_MISMATCH')
    finally:
        db.close()


def allocation_proof(args):
    if args.cpu_seconds <= 1800 and args.allocation is None:
        return {'prior_charged_cpu_seconds': 3600, 'additional_cpu_seconds': args.cpu_seconds,
                'total_charged_cpu_seconds': 3600 + args.cpu_seconds,
                'scope': 'Original interrupted3600 plus existing bounded recovery; no refund.'}
    if args.allocation is None or args.allocation_sha256 is None or sha(args.allocation) != args.allocation_sha256:
        raise ValueError('EXTERNAL_ADDITIVE_ALLOCATION_REQUIRED')
    from commercial.ledger import strict_json
    document = strict_json(args.allocation.read_bytes())
    caps = document.get('caps', {})
    additional = caps.get('additional_cpu_seconds', caps.get('cpu_seconds', document.get('additional_cpu_seconds')))
    prior = caps.get('prior_charged_cpu_seconds', document.get('prior_charged_cpu_seconds'))
    total = caps.get('total_charged_cpu_seconds', document.get('total_charged_cpu_seconds'))
    if additional != args.cpu_seconds or prior != 5400 or total != prior + additional or args.cpu_seconds > 2400:
        raise ValueError('ADDITIVE_ALLOCATION_MUST_RETAIN_ALL_PRIOR_CHARGES')
    if not args.worker and args.resource_ledger is not None and args.resource_ledger.exists():
        existing = strict_json(args.resource_ledger.read_bytes())
        charged = sum(item['budget_cpu_seconds'] for item in existing['runs'].values())
        if charged + args.cpu_seconds > additional:
            raise ValueError('ADDITIVE_CYCLE_ALREADY_CHARGED; NO_REPLENISHMENT')
    return {'allocation_sha256': args.allocation_sha256, 'prior_charged_cpu_seconds': prior,
            'additional_cpu_seconds': additional, 'total_charged_cpu_seconds': total,
            'scope': 'Explicit additive bounded recovery cycle. Prior5400 remains charged; no replenishment or refund.'}


def worker(args):
    from run_commercial010 import checked_inputs
    from commercial.ledger import strict_json
    import commercial.market as market
    freeze, manifest_path, policy_path = checked_inputs(args.freeze_sha256)
    resources = allocation_proof(args)
    inventory_freeze = freeze.get('previous_source_freeze_sha256', args.freeze_sha256)
    if inventory_freeze != args.freeze_sha256:
        if freeze.get('repair_scope') != 'SQLITE_IO_AND_RECEIPT_REPORTING_ONLY':
            raise ValueError('EXPLICIT_IO_ONLY_FREEZE_TRANSITION_REQUIRED')
        archived = ROOT / 'historical/commercial-010/attempt-v2/campaign/commercial-010/SOURCE_FREEZE.json'
        if sha(archived) != inventory_freeze:
            raise ValueError('ORIGINAL_FROZEN_SOURCE_ARCHIVE_MISMATCH')
        prior = strict_json(archived.read_bytes())
        unchanged = ['commercial/market.py', 'commercial/verdicts.py', 'commercial/service.py', 'commercial/service_verifier.py',
                     'commercial/onboarding.py', 'experiments/commerce006.py', 'vendor/alpha_claim/protected_exchange.py',
                     'vendor/alpha_claim/contracts.py', prior['policy'], prior['manifest']]
        if any(freeze['sources'].get(name) != prior['sources'][name] for name in unchanged):
            raise ValueError('FINANCIAL_POLICY_OR_CORE_CHANGED_ACROSS_IO_RECOVERY')
    inventory, previous = load_inventory(args.inventory, args.inventory_sha256, inventory_freeze, args.previous_root)
    output = args.output.absolute()
    if output.exists() or output.is_symlink() or any(x.is_symlink() for x in output.parents):
        raise FileExistsError(output)
    completed = set(inventory['complete_world_directories'])
    progress = output.parent / 'RECOVERY_PROGRESS.jsonl'
    receipts = []
    original = market.run_world
    with progress.open('x') as log:
        def record(value):
            log.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
            log.flush()
            os.fsync(log.fileno())
            print(json.dumps({k: value[k] for k in ['sequence', 'mode', 'relative_directory']}), flush=True)

        def adapter(**kwargs):
            destination = Path(kwargs['directory']).absolute()
            relative = destination.relative_to(output)
            historical = Path('artifacts') / relative
            name = str(historical)
            if name not in completed:
                result = original(**kwargs)
                entry = {'sequence': len(receipts), 'mode': 'NEW_EXECUTION_UNCHANGED_FROZEN_CANDIDATE',
                         'relative_directory': str(relative), 'result_sha256': sha(destination / 'RESULT.json')}
                receipts.append(entry)
                record(entry)
                return result
            source = previous / historical
            # Require the exact inventory file set and hashes; never use a partial
            # directory or overwrite prior/new evidence.
            wanted = {p: meta for p, meta in inventory['files'].items() if Path(p).parent == historical}
            actual = {str(historical / p.name) for p in source.iterdir() if p.is_file()}
            if actual != set(wanted) or any(p.is_symlink() or not p.is_file() for p in source.iterdir()):
                raise ValueError('RECOVERY_DIRECTORY_INVENTORY_MISMATCH')
            for p, meta in wanted.items():
                path = regular(previous, p)
                if path.stat().st_size != meta['bytes'] or sha(path) != meta['sha256']:
                    raise ValueError('RECOVERY_SOURCE_CHANGED_AFTER_INVENTORY')
            result = strict_json((source / 'RESULT.json').read_bytes())
            receipt = validate_world(result, kwargs)
            check_database(source, result)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination, symlinks=False)
            for p, meta in wanted.items():
                copied = destination / Path(p).name
                if copied.stat().st_size != meta['bytes'] or sha(copied) != meta['sha256']:
                    raise ValueError('RECOVERY_COPY_IDENTITY_MISMATCH')
            entry = {'sequence': len(receipts), 'mode': 'REUSED_COMPLETE_EXTERNALLY_INVENTORIED_EXPLORATION',
                     'relative_directory': str(relative), 'result_sha256': sha(destination / 'RESULT.json'),
                     'audit': receipt}
            receipts.append(entry)
            record(entry)
            return result

        market.run_world = adapter
        try:
            result = market.run_campaign(root=ROOT, manifest_path=manifest_path, policy_path=policy_path, output=output,
                                         expected_manifest_sha256=freeze['sources'][freeze['manifest']],
                                         expected_policy_sha256=freeze['sources'][freeze['policy']])
        finally:
            market.run_world = original
    recovery = {'schema': 'agi-alpha/commercial010-recovery/v1', 'scope': 'SIMULATED_ENGINEERING_RECOVERY',
                'recovery_instrument_sha256': sha(__file__), 'source_freeze_sha256': args.freeze_sha256,
                'interruption_inventory_sha256': args.inventory_sha256,
                'reused_complete_worlds': sum(r['mode'].startswith('REUSED') for r in receipts),
                'new_executed_worlds': sum(r['mode'].startswith('NEW') for r in receipts),
                'resource_policy': resources,
                'candidate_changes': False, 'seed_substitutions': False, 'parameter_adaptations': False,
                'io_repair_only': inventory_freeze != args.freeze_sha256,
                'source_changed_since_previous_attempt': inventory_freeze != args.freeze_sha256,
                'previous_source_freeze_sha256': inventory_freeze,
                'reuse_scope': 'Existing complete engineering outputs, independently native-replayed and hash-copied; no fresh scientific result is invented.',
                'result_sha256': sha(output / 'RESULT.json'), 'progress_sha256': sha(progress)}
    with (output.parent / 'RECOVERY.json').open('x') as stream:
        json.dump(recovery, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'scope': 'SIMULATED', 'conditional_simulated_go': result['conditional_simulated_go'], 'recovery': recovery}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze-sha256', required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--previous-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resource-ledger', type=Path)
    parser.add_argument('--cpu-seconds', type=int, default=1800)
    parser.add_argument('--wall-seconds', type=int, default=1800)
    parser.add_argument('--storage-bytes', type=int, default=250000000)
    parser.add_argument('--allocation', type=Path)
    parser.add_argument('--allocation-sha256')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if args.resource_ledger is None:
        raise ValueError('EXISTING_RESOURCE_LEDGER_REQUIRED; NO_NEW_CAPACITY')
    allocation_proof(args)
    from experiments.resource006_v3 import run
    command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--freeze-sha256', args.freeze_sha256,
               '--inventory', str(args.inventory.absolute()), '--inventory-sha256', args.inventory_sha256,
               '--output', str(args.output.absolute() / 'artifacts'), '--cpu-seconds', str(args.cpu_seconds),
               '--wall-seconds', str(args.wall_seconds), '--storage-bytes', str(args.storage_bytes)]
    if args.allocation:
        command.extend(['--allocation', str(args.allocation.absolute()), '--allocation-sha256', args.allocation_sha256])
    if args.previous_root:
        command.extend(['--previous-root', str(args.previous_root.absolute())])
    limits = {'wall_seconds': args.wall_seconds, 'cpu_seconds': args.cpu_seconds, 'memory_bytes': 2147483648,
              'output_bytes': 64000000, 'storage_bytes': args.storage_bytes}
    wrapped = run(command, args.output, args.resource_ledger, 'commercial010-resume-' + str(time.time_ns()), limits, cwd=ROOT)
    print(json.dumps({'state': wrapped['receipt']['state'], 'receipt_path': str(args.output.absolute() / 'RECEIPT.json'), 'scope': 'SIMULATED'}), flush=True)
    if wrapped['receipt']['state'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
