"""Run a source-bound, offline production060 comparison in isolated scratch."""

from argparse import ArgumentParser
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
from statistics import median
from subprocess import run
import sys
from time import monotonic, process_time
from unittest.mock import patch

from production060 import acceptance


ROOT = Path(__file__).resolve().parent
PRODUCTION = ROOT / 'runtime/production060'
REVISION = 'f0c8db6c7a1110dc614ab8a02c7a0bd5f79260de'
REGISTRATION = '940a3c2de587ebbf5d8f0c42f2fde6566e3f01df514ce3331cd530a7dc730a9c'
INPUTS = {
    'dispatch.py': 'f1c817938a7e7482937ac2db4030c4f33473980434ad0bd030e9808cab573664',
    'acceptance.py': 'c7bf65ea6aba50f9f0efb2567b32b9d86dab01103b666396798428031dfb041c',
    'data/resources.json': '3a5a6ab0db42199a8f75e6ea0847f18cf8d38104fc84e29999be5d7a3acd7d07',
}
CASES = {
    'cdp_o15_09d': 'e6d4d2bfa29d90ff572c7013ec4a5519876c6088e41d9271edc3560043cd4348',
    'cdp_o15_29d': 'f31f809d1cc562a6b167e9b8220839d20c34ad8d575ec3d19347c3fa1f92f76a',
    'cdp_o15_24d': '26bd5b2a8e974c261cae760dd7a2d575f33d073ddcbeb819bea966a3d3c0caa0',
    'cdp_o25_09d': 'f1b033663b20615fe48fd9fb45e8bcc88ceccb0b01261fa073721290546e32a3',
    'cdp_o25_27d': '7621f26ce403a18cf24d6e529227328accc31b25c76ab7a21733c231072ce635',
    'cdp_o30_13d': '250a19c814d158d79e4a9c18b68cc11c42695f9f015acedec82d316d8923af8d',
}
ARMS = ('ordinary', 'cold', 'lead-time', 'continuation')
BUDGET = 2.5


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n')


def case_inputs(case):
    path = PRODUCTION / 'data/days' / f'{case}.json'
    if digest(path) != CASES[case]:
        raise ValueError('Held instance bytes differ from registration')
    return read_json(path), read_json(PRODUCTION / 'data/resources.json')


def lead_time_order(loads):
    pending = list(loads)
    ordered = []
    while pending:
        ready = {load['order_id']: load for load in reversed(pending)}
        chosen = min(ready.values(), key=lambda load: (
            round(load['target_unload'] * 10) - min(load['travel'].values()),
            load['target_unload'], str(load['order_id']), load['load_index'],
        ))
        ordered.append(chosen)
        pending.remove(chosen)
    return ordered


def respects_split_order(order):
    seen = {}
    for load in order:
        order_id = load['order_id']
        if seen.get(order_id, -1) >= load['load_index']:
            return False
        seen[order_id] = load['load_index']
    return True


def produce(case, arm, folder):
    import numpy
    import ortools
    from ortools.sat.python import cp_model  # Load before starting matched operation.
    from production060 import dispatch

    if ortools.__version__ != '9.15.6755' or numpy.__version__ != '2.5.4' or not cp_model.CpModel:
        raise RuntimeError('Unexpected native solver environment')
    case_data, resources = case_inputs(case)
    cfg = dispatch.DispatchConfig(time_limit_s=BUDGET)
    mode = 'cold' if arm == 'cold' else 'ordinary'
    contract = acceptance.make_contract(case_data, resources, mode=mode, planning_scope='rolling', config=asdict(cfg))
    write_json(folder / 'contract.json', contract)
    original_greedy = dispatch._greedy
    original_window = dispatch._cp_window
    statuses = Counter()
    stats = Counter(windows_order_changed=0, window_orders_evaluated=0, windows=0)
    retained_order = []

    def greedy(loads, plants, trucks, matrix, state, bays, order_ready, config, now, nearest=False):
        stats['windows'] += 1
        def allocate(order):
            stats['window_orders_evaluated'] += 1
            return original_greedy(order, plants, trucks, matrix, state, bays, order_ready, config, now, nearest)

        if arm == 'lead-time':
            order = lead_time_order(loads)
            rows = allocate(order)
        elif arm == 'continuation':
            active = {tid for tid, entry in state.items() if entry['active']}
            options = ((sequence, allocate(sequence)) for sequence in permutations(loads)
                       if respects_split_order(sequence))
            order, rows = min(options, key=lambda item: round(dispatch._objective(item[1], active, config), 8))
        else:
            order = loads
            rows = allocate(order)
        stats['windows_order_changed'] += [load['load_id'] for load in order] != [load['load_id'] for load in loads]
        retained_order[:] = (loads, order)
        return rows

    def native_window(loads, *args):
        if not retained_order or retained_order[0] is not loads:
            raise RuntimeError('Order and producer window do not match')
        planned, receipt = original_window(retained_order[1], *args)
        statuses[(receipt['status'], receipt.get('selected', 'solver'))] += 1
        return planned, receipt

    began, cpu = monotonic(), process_time()
    with patch.object(dispatch, '_greedy', greedy), patch.object(dispatch, '_cp_window', native_window):
        artifact = dispatch.rolling_schedule(resources, case_data, mode=mode, config=cfg)
    duration = {'planner_wall_seconds': monotonic() - began, 'planner_cpu_seconds': process_time() - cpu}
    write_json(folder / 'plan.json', artifact)
    write_json(folder / 'execution.json', {
        **duration, 'window_stats': dict(stats), 'native_solver_calls': sum(statuses.values()),
        'native_solver_statuses': {f'{status}/{selected}': count for (status, selected), count in sorted(statuses.items())},
        'late_loads': artifact['objective']['late_loads'], 'frozen_contract_sha256': digest(folder / 'contract.json'),
        'artifacts_sha256': digest(folder / 'plan.json'),
    })


def evaluate(case, folder):
    data, resources = case_inputs(case)
    exec_record = read_json(folder / 'execution.json')
    if digest(folder / 'contract.json') != exec_record['frozen_contract_sha256']:
        raise ValueError('Frozen contract changed during production')
    if digest(folder / 'plan.json') != exec_record['artifacts_sha256']:
        raise ValueError('Stored plan changed before independent checking')
    began, cpu = monotonic(), process_time()
    verdict = acceptance.verify(data, resources, read_json(folder / 'plan.json'), read_json(folder / 'contract.json'))
    write_json(folder / 'verified.json', {**exec_record, **verdict,
               'checker_wall_seconds': monotonic() - began, 'checker_cpu_seconds': process_time() - cpu})


def execute_cohort():
    if digest(ROOT / 'REGISTRATION.md') != REGISTRATION:
        raise ValueError('Registration changed')
    for path, expected in INPUTS.items():
        if digest(PRODUCTION / path) != expected:
            raise ValueError('Pinned source changed')
    prior = read_json(ROOT / 'preflight-verified.json')
    if set(prior) != {'cold', 'ordinary'} or any(not row['accepted'] or not row['native_window_statuses']
                                               for row in prior.values()):
        raise RuntimeError('Availability preflight did not qualify')
    results = []
    for repeat in range(2):
        for index, case in enumerate(CASES):
            offset = (index + repeat) % 4
            for arm in ARMS[offset:] + ARMS[:offset]:
                folder = ROOT / 'held' / f'{repeat}-{case}-{arm}'
                folder.mkdir(parents=True, exist_ok=False)
                command = [sys.executable, '-B', str(Path(__file__)), '--case', case, '--arm', arm, '--folder', str(folder)]
                for phase in ('plan', 'verify'):
                    began = monotonic()
                    run([*command, phase], timeout=30, check=True)
                    (folder / f'{phase}-process-wall-s.txt').write_text(f'{monotonic() - began:.8f}\n')
                result = read_json(folder / 'verified.json')
                results.append({'case': case, 'repeat': repeat, 'arm': arm, **result,
                                'plan_process_wall_s': float((folder / 'plan-process-wall-s.txt').read_text()),
                                'verify_process_wall_s': float((folder / 'verify-process-wall-s.txt').read_text())})
                print(repeat, case, arm, result['accepted'], result['kpis'].get('value'),
                      result['native_solver_calls'], flush=True)
    summarize(results)


def summarize(results):
    verified = all(row['accepted'] and row['native_solver_calls'] > 0 for row in results)
    repeats = []
    for number in range(2):
        paired = []
        for case in CASES:
            rows = {row['arm']: row for row in results if row['repeat'] == number and row['case'] == case}
            if not all(row['accepted'] for row in rows.values()):
                continue
            best = min((arm for arm in ARMS if arm != 'continuation'),
                       key=lambda arm: (round(rows[arm]['kpis']['value'], 8),
                                        len(rows[arm]['kpis']['driver_review_flags'])))
            candidate, control = (rows[arm]['kpis'] for arm in ('continuation', best))
            paired.append({'case': case, 'best_control': best,
                           'improvement': round(control['value'] - candidate['value'], 8),
                           'review_flag_change': len(candidate['driver_review_flags']) - len(control['driver_review_flags']),
                           'missing_mix_change': len(candidate['missing_mix_order_ids']) - len(control['missing_mix_order_ids'])})
        repeats.append({'repeat': number, 'paired': paired,
                        'improved_days': sum(row['improvement'] > 0 for row in paired),
                        'aggregate_improvement': round(sum(row['improvement'] for row in paired), 8)})
    advance = verified and len(results) == 48 and all(
        row['improved_days'] >= 4 and row['aggregate_improvement'] > 0
        and all(pair['review_flag_change'] <= 0 and pair['missing_mix_change'] <= 0 for pair in row['paired'])
        for row in repeats
    )
    metrics = {}
    for arm in ARMS:
        rows = [row for row in results if row['arm'] == arm]
        metrics[arm] = {'accepted': sum(row['accepted'] for row in rows), 'cases': len(rows),
                        'native_solver_calls': sum(row['native_solver_calls'] for row in rows),
                        'changed_windows': sum(row['window_stats']['windows_order_changed'] for row in rows),
                        'wall_s_median': median(row['planner_wall_seconds'] + row['checker_wall_seconds'] for row in rows),
                        'cpu_s_median': median(row['planner_cpu_seconds'] + row['checker_cpu_seconds'] for row in rows),
                        'whole_process_wall_s_median': median(row['plan_process_wall_s'] + row['verify_process_wall_s'] for row in rows)}
    summary = {'schema': 'frontier/rolling-feasibility-ordering-v1', 'source_revision': REVISION,
               'registration_sha256': REGISTRATION, 'source_sha256': INPUTS, 'held_days_sha256': CASES,
               'trial_code_sha256': digest(Path(__file__)), 'preflight_sha256': digest(ROOT / 'preflight-verified.json'),
               'scope': 'offline retrospective replay of public historical operational requests',
               'registered_advance': advance, 'repeats': repeats, 'metrics': metrics, 'execution_results': results}
    write_json(ROOT / 'HELD-RESULT.json', summary)
    print(json.dumps({key: summary[key] for key in ('registered_advance', 'repeats', 'metrics')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('phase', choices=('batch', 'plan', 'verify'))
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--folder', type=Path)
    args = parser.parse_args()
    if args.phase == 'batch':
        execute_cohort()
    elif args.phase == 'plan':
        produce(args.case, args.arm, args.folder)
    else:
        evaluate(args.case, args.folder)
