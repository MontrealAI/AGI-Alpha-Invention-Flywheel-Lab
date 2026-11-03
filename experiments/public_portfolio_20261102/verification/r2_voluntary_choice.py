"""Additional public-only reconciliation of buyer budgets and current alternatives."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import time

import verify_finance as frozen
import verify_science as base
import r2_finance_supplement as profile_helper
import r2_stream_audit as public_helper
from r2_finance_supplement import independent_profile, micro
from r2_stream_audit import case_inputs, immutable_save
from connected_enterprise.finance import source_identity

SOURCE = 'bb74d40f7a84ca155189f908c091db32b27093e203e0d63696f327a9a2492901'
PROTOCOL = Path(__file__).with_name('r2_voluntary_choice_protocol.json')


def check_case(state, record, operating):
    route = state['route']; scenario = next(s for s in operating['registered_scenarios'] if s['id'] == state['scenario']['id'])
    p = independent_profile(operating, route, scenario)
    budget = 3 * p['buyer_base_value']; actors = {route + '-p' + str(i).zfill(2) for i in range(operating['finite_market']['prospects_per_route'])}
    actions = record['ledger']['actions']; failures = []; quotes = 0
    wallets = [a for a in actions if a['op'] == 'wallet']
    if any(a['args']['buyer'] not in actors or a['args']['amount'] != budget for a in wallets) or len(wallets) != len({a['args']['buyer'] for a in wallets}):
        failures.append('original_wallet_actor_budget_or_uniqueness')
    contacts = [(d['hour'], d['buyer']) for d in state['decisions']]
    if len(contacts) != len(set(contacts)):
        failures.append('same_buyer_contact_hour_not_unique')
    offers = {a['args']['id']: a for a in actions if a['op'] == 'offer'}
    for d in state['decisions']:
        if 'choice' not in d:
            continue
        quotes += 1; buyer = d['buyer']; hour = d['hour']; q = d['choice']
        if buyer not in actors:
            failures.append('quoted_unregistered_buyer'); continue
        index = int(buyer.rsplit('p', 1)[1]); prior = []
        for a in actions:
            if a['day'] >= hour or a['op'] != 'event':
                continue
            offer = offers.get(a['args']['id'])
            if offer is None or offer['args']['buyer'] != buyer:
                continue
            if a['args']['action'] == 'fund':
                prior.append(offer)
            elif a['args']['action'] in {'refund', 'late_reversal'}:
                failures.append('failed_refunded_buyer_requoted')
        paid = sum(o['args']['price'] for o in prior)
        remaining = max(0, budget - paid - len(prior) * p['adoption'])
        if d['buyer_remaining_budget_microUSD'] != remaining:
            failures.append('remaining_budget_disagrees_with_prior_native_funding_and_adoption')
        expected = {'free_source_self_service': p['free_source_integration'],
                    'competent_human_conventional': p['conventional'],
                    'hybrid': p['hybrid'], 'autonomous_rival': p['rival']}
        if hour >= scenario.get('compression_month', 18) * operating['month_hours']:
            for name in ('autonomous_rival', 'free_source_self_service'):
                expected[name] = min(expected[name], p['compressed_outside_floor'])
        if q['outside_costs_microUSD'] != expected:
            failures.append('current_outside_costs_disagree_with_registered_timing')
        from decimal import Decimal
        value = int(Decimal(p['buyer_base_value']) * (80 + 5 * index) * Decimal(str(scenario.get('demand_multiplier', 1))) / 100)
        utilities = {name: max(0, value - cost) for name, cost in expected.items()}
        if q['outside_utilities_microUSD'] != utilities or q['best_outside_utility_microUSD'] != max([0, *utilities.values()]):
            failures.append('current_outside_utilities_disagree_with_registered_world')
    return {'case_id': state['case_id'], 'passed': not failures, 'quoted_decisions_checked': quotes,
            'wallets_checked': len(wallets), 'failures': failures}


def run(public_root, summary_path):
    public_root = Path(public_root).resolve(); summary_path = Path(summary_path).resolve()
    dependencies = {profile_helper.__file__: '8abf79014a12561aba9aa7429412fb200c42f5e09019f66a550def22af73e8fd',
                    public_helper.__file__: '3c4ed4acc6202ea3318c527c8bbf48c7265fd444f7cc81ced5352dbe6baa3ca4'}
    if any(base.digest(path) != expected for path, expected in dependencies.items()):
        raise ValueError('EXACT_AUDITOR_HELPER_DEPENDENCIES_REQUIRED')
    operating = frozen.read(public_root / 'protocol.json')
    if operating != frozen.read(base.BASE / 'ECONOMICS_PROTOCOL.json'):
        raise ValueError('ORIGINAL_REGISTERED_ECONOMIC_PROTOCOL_REQUIRED')
    summary = frozen.read(summary_path)
    plan = {r + '-' + s['id'] for r in ('purpose', 'interface', 'complementarity', 'arrangement', 'foundry') for s in operating['registered_scenarios']}
    rows = []; candidate = None; ids = []
    for compact in summary['cases']:
        ident = compact['case_id']
        if ident not in plan or ident in ids:
            raise ValueError('ORIGINAL_UNIQUE_REGISTERED_CASE_REQUIRED')
        ids.append(ident); loaded = case_inputs(public_root, ident)
        if loaded is None:
            raise ValueError('COMPLETED_PUBLIC_CASE_REQUIRED:' + ident)
        parsed, hashes = loaded
        actual = source_identity(base.ROOT, parsed['manifest.json'])
        if actual['sha256'] != SOURCE or parsed['account.public.json']['connected_journal']['source'] != actual:
            raise ValueError('UNCHANGED_FINANCIAL_SOURCE_REQUIRED')
        row = check_case(parsed['RESULT.json'], parsed['account.public.json'], operating)
        if candidate is None and row['quoted_decisions_checked']:
            candidate = (parsed['RESULT.json'], parsed['account.public.json'])
        if case_inputs(public_root, ident)[1] != hashes:
            raise ValueError('PUBLIC_INPUT_CHANGED_DURING_AUDIT:' + ident)
        row['input_hashes'] = hashes; rows.append(row)
    controls = []
    if candidate is not None:
        state, record = candidate
        for field in ('budget', 'current_outside_cost'):
            altered = copy.deepcopy(state)
            d = next(d for d in altered['decisions'] if 'choice' in d)
            if field == 'budget':
                d['buyer_remaining_budget_microUSD'] += 1
            else:
                d['choice']['outside_costs_microUSD']['autonomous_rival'] += 1
            checked = check_case(altered, record, operating)
            controls.append({'mutation': field, 'detected': not checked['passed'], 'original_files_changed': False})
    complete = set(ids) == plan and len(ids) == 110 and summary.get('completed_businesses') == 110 and summary.get('failed_businesses') == 0
    passed = all(row['passed'] for row in rows) and len(controls) == 2 and all(c['detected'] for c in controls)
    return {'schema': 'public-portfolio/independent-voluntary-choice-reconciliation/v1',
            'checker_sha256': base.digest(__file__), 'protocol_sha256': base.digest(PROTOCOL),
            'auditor_helper_sha256': {Path(path).name: value for path, value in dependencies.items()},
            'financial_source_sha256': SOURCE, 'summary_sha256': base.digest(summary_path),
            'cases_checked': len(rows), 'original110_denominator_complete': complete,
            'status': 'COMPLETE_110_CHECKS' if complete and passed else 'PARTIAL_OR_FAILED_DIAGNOSTIC',
            'passed': passed, 'cases': rows, 'in_memory_negative_controls': controls,
            'scope': 'Additional posthoc known-world audit of registered budget/adoption and current outside-price arithmetic. Does not measure actual willingness to pay, human productivity or integration costs, and adds no original native-replay denominator.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--public-root', required=True); p.add_argument('--summary'); p.add_argument('--output', required=True)
    args = p.parse_args(); output = Path(args.output)
    if output.exists():
        raise ValueError('REFUSE_EXISTING_VOLUNTARY_AUDIT_OVERWRITE')
    started = time.time(); result = run(args.public_root, args.summary or str(Path(args.public_root) / 'RESULTS.json'))
    result['wall_seconds'] = time.time() - started; immutable_save(output, result)
    print(json.dumps({k: result[k] for k in ('status', 'cases_checked', 'passed', 'original110_denominator_complete')}))
    raise SystemExit(0 if result['passed'] else 1)
