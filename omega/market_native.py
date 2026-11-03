"""Execute the registered causal market through the existing native account.

Reference counterfactuals are explicitly separate from the unavailable original
Omega account. No balance import, reseed, account pooling or new ledger exists.
Every selected cost/order passes JournalAccount; restart retains its sidecars.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import shutil
import subprocess
import time

from commercial.ledger import canonical, digest, read_bound, strict_json
from connected_enterprise.finance import JournalAccount, audit_journal, source_paths_for_manifest
from connected_enterprise.scale import trailing_profit
from experiments.commerce006 import PINS
from omega import market, product, process, process_verify

CENT = 10_000
EXTRA_SOURCE = ('omega/market.py', 'omega/market_native.py', 'omega/market_buyer.py',
                'omega/qualification_pool.py',
                'campaign/omega-strategy-20261103/PROTOCOL.md',
                'campaign/omega-strategy-20261103/PAPERS.md',
                'campaign/omega-strategy-20261103/PRIOR_ART.md',
                'campaign/omega-strategy-20261103/summarize.py')

PRIMARY_ACCOUNT_BOUNDARY = {'continued': False, 'historical_seed_USD': 100000,
    'historical_expense_USD': 24800, 'historical_cash_USD': 75200,
    'reason': 'Original authenticated recovery absent; these reference accounts neither replace it nor pool funds.'}


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value) + b'\n'
    temporary = path.with_name(path.name + '.pending')
    temporary.write_bytes(data); temporary.replace(path)


def hashes(root):
    names = set(source_paths_for_manifest({'schema': product.SCHEMA})) | set(PINS) | set(EXTRA_SOURCE)
    return {p: hashlib.sha256((Path(root) / p).read_bytes()).hexdigest() for p in sorted(names)}


def qualification():
    request = process.fixture(True)
    candidate = process.construct(request)
    ordinary = process_verify.conventional_policy(request)
    accepted = process_verify.verify_policy(request, candidate)
    if not accepted['accepted'] or candidate['status'] != 'QUALIFIED_POLICY':
        raise ValueError('ACTUAL_PROCESS_CAPABILITY_NOT_QUALIFIED')
    return {'request_sha256': digest(request), 'candidate_sha256': digest(candidate),
            'independent_check': accepted, 'candidate_worst_cost_cents': candidate['worst_cost_cents'],
            'ordinary_worst_cost_cents': ordinary['worst_cost_cents'],
            'superior_to_ordinary': candidate['worst_cost_cents'] < ordinary['worst_cost_cents']}


def lineitems(plan):
    return [(row, bundle, item) for row in plan['trace'] for bundle in row['bundles'] for item in bundle['items']]


def manifest_for(source, directory, plan):
    lines = lineitems(plan)
    costs = {p: {'unused_default': 0} for p in market.PRODUCTS}
    costs['group_session'] = {'prepaid_selected_action': 0}
    if not lines:
        return product.prepare_manifest(source, source / 'deliveries' / directory.name,
            jobs=1, hypothetical_rights=True, costs=costs,
            outcomes=[{'accepted': False, 'paid': False}])
    water = strict_json((source / 'omega/request.json').read_bytes())
    process_requests = []
    for row, bundle, item in lines:
        request = None
        if item['workflow'] == 'process' and item['product'] == 'self_hosted':
            request = process.fixture(True)
            request['name'] = 'Authored buyer process outcome ' + bundle['buyer_id']
        process_requests.append(request)
    return product.prepare_manifest(source, source / 'deliveries' / directory.name,
        jobs=[i['product'] for _, _, i in lines], hypothetical_rights=True,
        outcomes=[{'accepted': b['accepted'], 'paid': b['paid']} for _, b, _ in lines],
        costs=costs, prices=[i['price_cents'] * CENT for _, _, i in lines],
        choices=[i['choice'] for _, _, i in lines], water_requests=[water for _ in lines],
        process_requests=process_requests,
        job_costs=[{k: v * CENT for k, v in i['costs_cents'].items()} for _, _, i in lines],
        session_ids=[f'q{r["quarter"]}' if i['product'] == 'group_webinar' else None for r, _, i in lines])


def _contract(plan):
    return 'omega-market-reference:' + digest(plan)


def _marker(index):
    return 'market-step-complete-' + str(index)


def _native_args(source, manifest, directory, plan):
    return (source, manifest, directory / 'account.sqlite')


def _check_manifest(source, manifest, plan):
    lines = lineitems(plan)
    if len(manifest['jobs']) != max(1, len(lines)):
        raise ValueError('EXACT_REGISTERED_MARKET_JOBS_REQUIRED')
    if manifest['claim_window_hours'] != 720 or manifest['residual_bps'] != 100:
        raise ValueError('REGISTERED_OBLIGATION_TERMS_CHANGED')
    product.load_contracts(source, manifest)
    expected_water = strict_json((Path(source) / 'omega/request.json').read_bytes())
    for (row, bundle, item), job in zip(lines, manifest['jobs']):
        request = read_bound(source, job['input'], job['input_sha256'])
        expected_process = None
        if item['workflow'] == 'process':
            expected_process = process.fixture(True)
            expected_process['name'] = 'Authored buyer process outcome ' + bundle['buyer_id']
        if (request['choice'] != item['choice'] or request['price'] != item['price_cents'] * CENT
                or request['product'] != item['product']
                or request['job_costs'] != {k: v * CENT for k, v in item['costs_cents'].items()}
                or request['outcome'] != {'accepted': bundle['accepted'], 'paid': bundle['paid'], 'attended': True, 'completed': True}
                or request.get('workflow', 'water') != item['workflow']
                or request.get('process_request') != expected_process
                or request['water_request'] != expected_water
                or job['session_id'] != (f'q{row["quarter"]}' if item['product'] == 'group_webinar' else None)):
            raise ValueError('CAUSAL_PLAN_BUYER_CONTRACT_MISMATCH')
    return True


def execute_case(directory, source, plan, *, max_steps=None):
    """Resume the same native account at durable completed-step markers.

    A selected resource uses atomic native spend. The output directory never
    silently becomes a fresh account when recovery material has disappeared.
    """
    directory, source = Path(directory), Path(source)
    if hashes(source) != hashes(Path(__file__).resolve().parents[1]):
        raise ValueError('EXACT_EXECUTING_MARKET_SOURCE_REQUIRED')
    market.audit_policy(plan)
    qualification_receipt = qualification()
    manifest = strict_json((directory / 'manifest.json').read_bytes())
    _check_manifest(source, manifest, plan)
    path = directory / 'account.sqlite'
    started = directory / 'NATIVE_STARTED.json'
    if started.exists():
        files = list(directory.glob('account.sqlite*'))
        if not files or not any(p.name.endswith('.actions.jsonl') for p in files):
            raise ValueError('ORIGINAL_REFERENCE_RECOVERY_REQUIRED_NO_RESEED')
        if strict_json(started.read_bytes()) != {'contract': _contract(plan), 'opening_cents': plan['capital_cents']}:
            raise ValueError('REFERENCE_ACCOUNT_IDENTITY_CHANGED')
    else:
        if path.exists() or list(directory.glob('account.sqlite*')):
            raise ValueError('UNREGISTERED_EXISTING_ACCOUNT_REFUSED')
        write(started, {'contract': _contract(plan), 'opening_cents': plan['capital_cents']})
    completed_this_call = 0
    with JournalAccount(*_native_args(source, manifest, directory, plan),
                        opening=plan['capital_cents'] * CENT, working=0, contract=_contract(plan)) as account:
        item_offset = 0
        for index, row in enumerate(plan['trace']):
            count = sum(len(b['items']) for b in row['bundles'])
            record = account.export()
            markers = {a['args']['id']: a for a in record['ledger']['actions'] if a['op'] == 'cost'}
            if _marker(index) in markers:
                marker = markers[_marker(index)]
                if (marker['args']['amount'] != 0
                        or marker['after']['available'] != row['closing_available_cents'] * CENT):
                    raise ValueError('COMPLETED_NATIVE_STEP_CHANGED')
                item_offset += count
                continue
            if max_steps is not None and completed_this_call >= max_steps:
                write(directory / 'public.json', record)
                return {'complete': False, 'native_actions_sha256': record['ledger']['actions_sha256'],
                        'account_contract': _contract(plan), 'completed_steps_this_call': completed_this_call}
            # Native execution may be resuming within a step. Its signed journal
            # resumes identical commands; completion markers never mint authority.
            for kind, amount in row['fixed_costs_cents'].items():
                ident = f'market-s{index}-{kind}'
                expected_net = max(1, math_ceil(row['rationale']['best_one_round_expected_cents'])) * CENT
                work = {'plan_sha256': digest(plan), 'step': index, 'selected_action': row['action'],
                        'resource': kind, 'quantity': market.TASKS.get(kind),
                        'qualification': qualification_receipt if kind == 'package_process' else None}
                if amount:
                    receipt = account.spend(ident, kind, amount * CENT, row['hour'], work, expected_net, allow_seed=True)
                    if receipt is None:
                        raise ValueError('SELECTED_ACTION_HAS_NO_CURRENT_NATIVE_FUNDING')
            for bundle in row['bundles']:
                if not bundle['items']:
                    continue
                jobs = manifest['jobs'][item_offset:item_offset + len(bundle['items'])]
                outcome = product.fulfill_bundle(account, source, manifest, [j['id'] for j in jobs],
                    order_id_prefix=bundle['buyer_id'], buyer='synthetic-' + bundle['buyer_id'],
                    hour=row['delivery_hour'], consent=True)
                settled = outcome['complete'] if bundle['status'] == 'released' else outcome.get('settled')
                expected_collected = sum(i['price_cents'] for i in bundle['items']) * CENT if bundle['status'] == 'released' else 0
                if outcome['status'] != bundle['status'] or not settled or outcome['collected'] != expected_collected:
                    raise ValueError('NATIVE_BUNDLE_OUTCOME_DIVERGED:' + json.dumps(outcome, sort_keys=True))
                item_offset += len(jobs)
            if row['action']['kind'] == 'operate':
                account.advance_financial(row['maturity_hour'])
            snapshot = account.snapshot()['summary']
            if snapshot['available'] != row['closing_available_cents'] * CENT:
                raise ValueError('CAUSAL_PLAN_NATIVE_AVAILABLE_DIVERGED:' + str(index)
                                 + ':' + str(snapshot['available']) + ':' + str(row['closing_available_cents'] * CENT))
            mark_hour = row.get('maturity_hour', row['hour'])
            account.cost(_marker(index), 0, mark_hour)
            completed_this_call += 1
        # A tax liability is recognized even if liquid funding is insufficient;
        # the native account distinguishes incurred and paid expense/payables.
        account.cost('market-annual-tax', plan['tax_cents'] * CENT, 8758)
        account.cost('market-complete-365day-endpoint', 0, 8759)
        record = account.export()
    write(directory / 'public.json', record)
    result = derive_case(source, manifest, plan, record)
    write(directory / 'result.json', result)
    return result


def math_ceil(value):
    import math
    return math.ceil(value)


def derive_case(source, manifest, plan, record):
    if hashes(source) != hashes(Path(__file__).resolve().parents[1]):
        raise ValueError('EXACT_EXECUTING_MARKET_SOURCE_REQUIRED')
    policy_audit = market.audit_policy(plan)
    _check_manifest(source, manifest, plan)
    native = audit_journal(record, root=source, manifest=manifest)
    cfg = record['ledger']['config']
    if cfg['opening'] != plan['capital_cents'] * CENT or cfg['working'] != 0 or cfg['contract'] != _contract(plan):
        raise ValueError('ONE_REGISTERED_REFERENCE_IDENTITY_REQUIRED')
    summary = record['ledger']['summary']
    if (summary['revenue'] != plan['recognized_revenue_cents'] * CENT
            or summary['collections'] != plan['recognized_revenue_cents'] * CENT
            or summary['expenses'] != (plan['pretax_cash_expense_cents'] + plan['tax_cents']) * CENT
            or summary['profit'] != plan['accounting_profit_cents'] * CENT
            or summary['tailReserve'] != plan['residual_cents'] * CENT
            or summary['available'] != plan['closing_available_cents'] * CENT):
        raise ValueError('COMPLETE_NATIVE_MARKET_FINANCIAL_RECONCILIATION_FAILED')
    actions = record['ledger']['actions']
    fixed_expected = {f'market-s{i}-{kind}': (amount * CENT, row['hour'], kind)
                      for i, row in enumerate(plan['trace']) for kind, amount in row['fixed_costs_cents'].items() if amount}
    fixed_actual = {entry['request']['id']: (entry['request']['amount'], entry['request']['day'], entry['request']['kind'])
                    for entry in record['connected_journal']['entries'] if entry['request']['operation'] == 'spend'}
    if fixed_actual != fixed_expected:
        raise ValueError('ONLY_SELECTED_ACTION_COSTS_MAY_BE_SPENT')
    native_offers = [a for a in actions if a['op'] == 'offer']
    lines = lineitems(plan)
    if len(native_offers) != len(lines):
        raise ValueError('ONE_NATIVE_OFFER_PER_VOLUNTARY_LINE_REQUIRED')
    for offer, (row, bundle, item), job in zip(native_offers, lines, manifest['jobs']):
        if offer['args']['job_id'] != job['id'] or offer['args']['price'] != item['price_cents'] * CENT or offer['day'] != row['delivery_hour']:
            raise ValueError('EXACT_CAUSAL_OFFER_SEQUENCE_CHANGED')
    markers = {a['args']['id']: a for a in actions if a['op'] == 'cost'}
    for i, row in enumerate(plan['trace']):
        if _marker(i) not in markers or markers[_marker(i)]['after']['available'] != row['closing_available_cents'] * CENT:
            raise ValueError('EVERY_SELECTED_ACTION_NATIVE_COMPLETION_REQUIRED')
    if actions[-1]['args'] != {'id': 'market-complete-365day-endpoint', 'amount': 0} or actions[-1]['day'] != 8759:
        raise ValueError('EXACT_COMPLETE_365_DAY_ENDPOINT_REQUIRED')
    year = trailing_profit(record['ledger'], operating_end_hour=8760, operating_complete=True)
    funding = [{'resource': e['request']['kind'], 'amount_cents': e['request']['amount'] // CENT,
                'hour': e['request']['day'], 'funding': e['funding']}
               for e in record['connected_journal']['entries'] if e['request']['operation'] == 'spend']
    outcomes = {name: 0 for name in ('released', 'refunded', 'unpaid', 'liquidity_deferred')}
    before_fees = net = incremental = 0
    product_counts = {p: 0 for p in market.PRODUCTS}
    for row in plan['trace']:
        for bundle in row['bundles']:
            outcomes[bundle['status']] += 1
            if bundle['status'] == 'released':
                before_fees += bundle['expected_value_before_fees_microUSD']
                net += bundle['expected_buyer_net_microUSD']
                incremental += bundle['expected_increment_over_outside_microUSD']
                for item in bundle['items']:
                    product_counts[item['product']] += 1
    return {'schema': 'omega/native-market-case/v1', 'complete': True,
            'scenario': plan['scenario']['name'], 'seed': plan['scenario']['seed'], 'policy': plan['policy'],
            'account_contract': cfg['contract'], 'opening_capital_USD': plan['capital_cents'] / 100,
            'native_summary_microUSD': summary, 'trailing_365_native_accounting_profit': year,
            'noncash_founder_opportunity_cents': plan['noncash_founder_opportunity_cents'],
            'modeled_complete_economic_profit_cents': plan['economic_profit_cents'],
            'actual_complete_profit': None, 'founder_minutes': plan['founder_minutes'],
            'outcomes': outcomes, 'accepted_product_counts': product_counts,
            'buyer_expected_value_before_fees_microUSD': before_fees,
            'buyer_expected_net_microUSD': net, 'buyer_expected_increment_over_outside_microUSD': incremental,
            'buyer_realized_value': None, 'funding_receipts': funding,
            'decisions': [{'quarter': r['quarter'], 'action': r['action'], 'signal': r.get('signal'),
                           'available_before_cents': r['public_before']['available_cents'],
                           'available_after_cents': r['closing_available_cents']} for r in plan['trace']],
            'native_actions_sha256': record['ledger']['actions_sha256'],
            'public_record_sha256': digest(record), 'manifest_sha256': digest(manifest),
            'policy_audit': policy_audit, 'native_audit_accepted': native['accepted'],
            'claims': market.scientific_claims(),
            'identity_scope': 'INDEPENDENT_REGISTERED_COUNTERFACTUAL_NOT_ORIGINAL_OMEGA_ACCOUNT'}


def register(output, *, root=None, development=False, modes=market.POLICIES, cases=None, rates=market.Rates()):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'; identity = hashes(root)
    for name in identity:
        destination = source / name; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    cases = tuple(cases or market.registered_cases(development=development))
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True)
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=root, capture_output=True, text=True)
    registration = {'schema': 'omega/native-market-registration/v1', 'source_hashes': identity,
        'git_commit': git.stdout.strip() if git.returncode == 0 else None,
        'git_clean': status.returncode == 0 and not status.stdout,
        'evidence_role': 'development' if development else 'fresh_simulated_cases_after_source_freeze_not_market_validation',
        'cases': [asdict(s) for s in cases], 'policies': list(modes), 'rates': asdict(rates),
        'currency': 'USD', 'capital_cents': 10_000_000, 'endpoint_hour': 8760,
        'qualification': qualification(), 'cost_disclosure': market.cost_disclosure(rates),
        'primary_account': PRIMARY_ACCOUNT_BOUNDARY,
        'arms': []}
    write(output / 'registration.json', registration)
    for si, scenario in enumerate(cases):
        for mode in modes:
            name = f'case{si}-{mode}'; directory = output / 'accounts' / name; directory.mkdir(parents=True)
            plan = market.simulate(scenario, mode, rates=rates)
            write(directory / 'plan.json', plan)
            manifest = manifest_for(source, directory, plan)
            write(directory / 'manifest.json', manifest)
            registration['arms'].append({'id': name, 'plan_sha256': digest(plan), 'manifest_sha256': digest(manifest)})
    write(output / 'registration.json', registration)
    return registration


def validate_registration(registration):
    """Bind the denominator to its registered case × policy matrix.

    An audit is not original custody. Fresh evaluated claims additionally require
    the complete source-declared eight cases/six policies and a clean source tree.
    """
    if (registration.get('schema') != 'omega/native-market-registration/v1'
            or registration.get('currency') != 'USD' or registration.get('capital_cents') != 10_000_000
            or registration.get('endpoint_hour') != 8760
            or registration.get('primary_account') != PRIMARY_ACCOUNT_BOUNDARY):
        raise ValueError('EXACT_REGISTERED_MARKET_SCOPE_REQUIRED')
    cases, modes = registration.get('cases'), registration.get('policies')
    if not isinstance(cases, list) or not cases or not isinstance(modes, list) or not modes:
        raise ValueError('NONEMPTY_REGISTERED_CASE_POLICY_MATRIX_REQUIRED')
    if len({digest(c) for c in cases}) != len(cases) or len(set(modes)) != len(modes) or any(m not in market.POLICIES for m in modes):
        raise ValueError('UNIQUE_REGISTERED_CASES_AND_POLICIES_REQUIRED')
    expected_ids = [f'case{i}-{mode}' for i in range(len(cases)) for mode in modes]
    if [a.get('id') for a in registration.get('arms', [])] != expected_ids:
        raise ValueError('ALL_REGISTERED_CASE_POLICY_ARMS_REQUIRED')
    role = registration.get('evidence_role')
    if role != 'development':
        if (role != 'fresh_simulated_cases_after_source_freeze_not_market_validation'
                or canonical(cases) != canonical([asdict(s) for s in market.registered_cases()])
                or modes != list(market.POLICIES) or registration.get('git_clean') is not True):
            raise ValueError('SOURCE_FROZEN_COMPLETE_EVALUATION_MATRIX_REQUIRED')
    rates = market.Rates(**registration['rates'])
    if registration.get('cost_disclosure') != market.cost_disclosure(rates) or registration.get('qualification') != qualification():
        raise ValueError('REGISTERED_COST_OR_QUALIFICATION_CHANGED')
    return True


def _load(output):
    output = Path(output).resolve(); registration = strict_json((output / 'registration.json').read_bytes())
    validate_registration(registration)
    source = output / 'source'
    if hashes(source) != registration['source_hashes'] or hashes(Path(__file__).resolve().parents[1]) != registration['source_hashes']:
        raise ValueError('EXACT_REGISTERED_MARKET_SOURCE_REQUIRED')
    return output, registration, source


def operate(output, *, max_steps=None):
    output, registration, source = _load(output)
    start, cpu = time.perf_counter(), time.process_time()
    results = []
    for arm in registration['arms']:
        directory = output / 'accounts' / arm['id']
        plan = strict_json((directory / 'plan.json').read_bytes())
        manifest = strict_json((directory / 'manifest.json').read_bytes())
        if digest(plan) != arm['plan_sha256'] or digest(manifest) != arm['manifest_sha256']:
            raise ValueError('PRECOMMITTED_ARM_CHANGED')
        result = execute_case(directory, source, plan, max_steps=max_steps)
        results.append({'id': arm['id'], **result})
    result = {'schema': 'omega/native-market-result/v1', 'registration_sha256': digest(registration),
              'complete': all(r['complete'] for r in results), 'accounts': results,
              'account_count': len(results), 'pooled_profit': None,
              'primary_objective_established': False, 'actual_complete_profit': None,
              'telemetry': {'wall_seconds': time.perf_counter() - start, 'cpu_seconds': time.process_time() - cpu,
                            'maximum_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'not_business_billing_or_human_labor': True}}
    write(output / ('result.json' if result['complete'] else 'checkpoint.json'), result)
    return result


def audit(output):
    output, registration, source = _load(output)
    result = strict_json((output / 'result.json').read_bytes())
    if (set(result) != {'schema', 'registration_sha256', 'complete', 'accounts', 'account_count',
                       'pooled_profit', 'primary_objective_established', 'actual_complete_profit', 'telemetry'}
            or result['schema'] != 'omega/native-market-result/v1'
            or result['complete'] is not True or result['registration_sha256'] != digest(registration)
            or result['pooled_profit'] is not None or result['primary_objective_established'] is not False
            or result['actual_complete_profit'] is not None
            or type(result['account_count']) is not int or result['account_count'] != len(registration['arms'])
            or len(result['accounts']) != len(registration['arms'])):
        raise ValueError('COMPLETE_REGISTERED_RESULT_REQUIRED')
    expected = []
    for arm in registration['arms']:
        directory = output / 'accounts' / arm['id']
        plan = strict_json((directory / 'plan.json').read_bytes())
        manifest = strict_json((directory / 'manifest.json').read_bytes())
        record = strict_json((directory / 'public.json').read_bytes())
        if digest(plan) != arm['plan_sha256'] or digest(manifest) != arm['manifest_sha256']:
            raise ValueError('PRECOMMITTED_ARM_CHANGED')
        expected.append({'id': arm['id'], **derive_case(source, manifest, plan, record)})
    if canonical(expected) != canonical(result['accounts']):
        raise ValueError('NATIVE_MARKET_REPORT_CHANGED')
    return {'accepted': True, 'accounts_replayed': len(expected), 'result_sha256': digest(result),
            'all_registered_arms_preserved': len(expected) == len(registration['arms']),
            'original_primary_account_continued': False}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('register', 'operate', 'audit'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--development', action='store_true')
    parser.add_argument('--max-steps', type=int)
    args = parser.parse_args()
    if args.operation == 'register':
        result = register(args.output, development=args.development)
        print(json.dumps({'registered_arms': len(result['arms']), 'source_files': len(result['source_hashes'])}))
    elif args.operation == 'operate':
        result = operate(args.output, max_steps=args.max_steps)
        print(json.dumps({'complete': result['complete'], 'accounts': result['account_count'], 'telemetry': result['telemetry']}))
    else:
        print(json.dumps(audit(args.output)))


if __name__ == '__main__':
    main()
