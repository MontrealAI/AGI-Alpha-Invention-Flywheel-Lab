"""Native engineering fixture for a downloaded demo, never the Omega mission account."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount, audit_journal
from omega.native_lifecycle.acceptance import EDITION, FILES, SCOPE, accept
from omega.native_lifecycle.service import manifest_for, load_jobs
from omega.native_lifecycle.stage import stage

MICRO = 1_000_000
OPENING = 1_000 * MICRO
PUBLIC_POLICY_PATH = 'campaign/omega-continuation-bdd6/SELLER_FIXTURE.json'
PUBLIC_POLICY_SHA256 = '836e8218ba505316b358739cedd6cd2ca853ed7dd6cfda0bd2b92f9a39f41e68'
ORIGINAL = {'actions_sha256': 'abd9b0b7fe7339684b9099f4e8c56c99a09bf24503059767bc62bdf8d24688ef',
            'registration_sha256': '5ae4763d90a97e2c920b39bcec6312433599cefb4a871ea2d4890c23b05ba5b8',
            'scope': 'UNCHANGED_PUBLIC_REFERENCE_NOT_RECOVERED_OR_IMPORTED'}


def package():
    return {'schema': 'omega/download-package/v1', 'edition': EDITION, 'scope': SCOPE,
            'files': dict(FILES), 'sha256': {n: hashlib.sha256(v.encode()).hexdigest() for n, v in FILES.items()}}


def checkout_choice(choice, consent):
    if type(consent) is not bool or not isinstance(choice, str) or choice not in {'no_purchase', 'self_hosted_demo', 'webinar', 'founder_private'}:
        raise ValueError('ONE_EXPLICIT_OFFER_AND_CONSENT_DECISION_REQUIRED')
    if choice == 'no_purchase' or not consent:
        return 'NO_ORDER'
    if choice in {'webinar', 'founder_private'}:
        return 'MANUAL_DELIVERY_NOT_EXECUTED'
    return 'SYNTHETIC_ORDER_ELIGIBLE'


def steps():
    result = []
    def native(ident, op, args, hour):
        result.append({'id': ident, 'kind': 'native', 'op': op, 'args': args, 'hour': hour})
    def cost(ident, dollars, hour):
        native(ident, 'cost', {'id': ident, 'amount': dollars * MICRO}, hour)
    def event(order, action, hour):
        native(order + '-' + action, 'event', {'id': order, 'action': action, 'event_id': order + '-' + action}, hour)
    def local(ident, kind, hour, order=None):
        result.append({'id': ident, 'kind': kind, 'hour': hour, **({'order': order} if order else {})})
    cost('setup-docs-security', 120, 0)
    local('decline', 'decline', 1)
    local('ambiguous-choice', 'ambiguous', 1)
    local('tampered-package', 'tamper', 1)
    for name, hour in [('A', 2), ('B', 9)]:
        if name == 'B':
            local('liquidity', 'liquidity', 7)
            local('unavailable-model-help', 'help', 8)
        cost(name + '-acquisition', 5, hour)
        native(name + '-wallet', 'wallet', {'buyer': 'synthetic-buyer-' + name, 'amount': 299 * MICRO}, hour)
        native(name + '-offer', 'offer', {'id': name, 'buyer': 'synthetic-buyer-' + name,
                                       'price': 299 * MICRO, 'job_id': 'demo-download', 'deadline': 20}, hour)
        event(name, 'consent', hour)
        event(name, 'fund', hour + 1)
        cost(name + '-processing', 9, hour + 1)
        cost(name + '-hosting-onboarding', 1, hour + 1)
        local(name + '-entitlement', 'entitlement', hour + 2, name)
        if name == 'A':
            local('A-download', 'download', 4, 'A')
            local('A-onboarding', 'onboarding', 4, 'A')
            event('A', 'prepare', 5)
            event('A', 'release', 6)
        else:
            local('B-failed-download', 'failed_delivery', 11, 'B')
            cost('B-refund-admin', 2, 12)
            event('B', 'refund', 12)
    cost('A-dispute-admin', 3, 13)
    native('A-dispute-processing', 'cost', {'id': 'A-dispute-processing', 'amount': 200_000}, 13)
    event('A', 'late_reversal', 13)
    local('revocation', 'revocation', 14, 'A')
    cost('closed-fixture-observation', 0, 14)
    return result


def registration():
    raw = (Path(__file__).resolve().parents[1] / PUBLIC_POLICY_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PUBLIC_POLICY_SHA256:
        raise ValueError('PUBLIC_REGISTERED_FIXTURE_POLICY_CHANGED')
    return {'schema': 'omega/lifecycle-registration/v1', 'scope': 'FRESH_ENGINEERING_FIXTURE_NOT_MISSION_ACCOUNT',
            'public_protocol_commit': 'de303edf37550caef668a9d926dbe79292ece567',
            'public_protocol_sha256': PUBLIC_POLICY_SHA256,
            'currency': 'USD', 'opening_microUSD': OPENING, 'original_account': ORIGINAL,
            'financing': 'one separately labeled fixture seed, no transfers or topups',
            'price_microUSD': 299 * MICRO, 'edition': EDITION, 'steps': steps(),
            'cost_basis': 'AUTHORED_COST_ENVELOPES_NOT_INVOICES_OR_MEASURED_LABOR',
            'capital_expenditure_microUSD': 0, 'depreciation_microUSD': 0,
            'taxes_microUSD': None, 'actual_model_host_development_cost_microUSD': None,
            'human_minutes': {'unresolved_help': 5, 'dispute_review': 10,
                              'webinar_preparation': 60, 'webinar_presentation': 60, 'webinar_admin': 30,
                              'private_preparation': 30, 'private_session': 30, 'private_admin': 15},
            'founder_opportunity_usd_per_hour': [0, 200, 2000],
            'manual_offers': {'webinar': {'price_usd': 99, 'max_seats': 500, 'delivery': 'NOT_EXECUTED_MANUAL'},
                              'founder_private': {'price_usd': 20000, 'session_minutes': 30, 'delivery': 'NOT_EXECUTED_MANUAL'}},
            'claim_limits': ['No real buyers, payment provider, customers, webinar or founder session.',
                             'Synthetic consent is an authored control, not inferred from utility.',
                             'Download acceptance proves only this working onboarding demo.',
                             'This fixture cannot count toward the original US$100000 mission account.',
                             'No full operating year or complete-cost profit qualification.']}


def _read(path):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('REGULAR_LIFECYCLE_FILE_REQUIRED')
    raw = path.read_bytes()
    if len(raw) > 8_000_000:
        raise ValueError('BOUNDED_LIFECYCLE_FILE_REQUIRED')
    return strict_json(raw)


def _write(path, value):
    atomic_bytes(path, canonical(value) + b'\n')


def _order(account, ident):
    rows = account.export()['ledger']['orders']
    return next(row for row in rows if row['id'] == ident)


def entitled(account, ident):
    return _order(account, ident)['state'] in {'funded', 'verified', 'released'}


def _local(account, step, output, manifest):
    kind = step['kind']
    if kind == 'decline':
        if checkout_choice('no_purchase', False) != 'NO_ORDER':
            raise ValueError('VOLUNTARY_DECLINE_MUST_NOT_CREATE_ORDER')
        return {'decision': 'NO_PURCHASE', 'native_order_created': False, 'reason': 'Authored voluntary decline control'}
    if kind == 'ambiguous':
        try:
            checkout_choice(['self_hosted_demo', 'webinar'], True)
        except ValueError:
            return {'ambiguous_choice': 'REJECTED', 'native_order_created': False}
        raise ValueError('AMBIGUOUS_CHECKOUT_NOT_REJECTED')
    if kind == 'tamper':
        invalid = package()
        invalid['files']['demo.py'] = 'print("forged")'
        try:
            accept(invalid)
        except ValueError:
            return {'tampered_package': 'REJECTED', 'native_preparation_authorized': False}
        raise ValueError('TAMPERED_DOWNLOAD_NOT_REJECTED')
    if kind == 'help':
        docs = package()['files']['README.txt']
        return {'model_available': False, 'external_calls': 0, 'documentation_sha256': hashlib.sha256(docs.encode()).hexdigest(),
                'known_action': 'Run the included local Python diagnostic.',
                'unresolved': True, 'next_action': 'DEFER_AND_KEEP_DATA_LOCAL', 'human_exception_minutes_assumed': 5}
    if kind == 'liquidity':
        before = account.snapshot()
        receipt = account.spend('unfunded-expansion', 'capacity', 1001 * MICRO, step['hour'],
                                {'scope': 'Engineering insufficient-cash control'}, 2000 * MICRO, allow_seed=True)
        after = account.snapshot()
        if receipt is not None or before != after or before['summary']['profit'] <= 0 or before['summary']['available'] >= 1001 * MICRO:
            raise ValueError('POSITIVE_PROFIT_ILLIQUIDITY_CONTROL_FAILED')
        return {'investment': 'DEFERRED', 'requested_microUSD': 1001 * MICRO,
                'profit_microUSD': before['summary']['profit'], 'available_microUSD': before['summary']['available'],
                'native_state_unchanged': True}
    if kind == 'revocation':
        if entitled(account, step['order']):
            raise ValueError('REVERSED_ENTITLEMENT_NOT_REVOKED')
        return {'download_access': 'REVOKED', 'previously_downloaded_copy': 'Cannot be remotely erased'}
    if not entitled(account, step['order']):
        raise ValueError('FUNDED_NATIVE_ENTITLEMENT_REQUIRED')
    if kind == 'entitlement':
        return {'entitlement': 'ACTIVE', 'order': step['order'], 'edition': EDITION,
                'native_state': _order(account, step['order'])['state']}
    if kind == 'failed_delivery':
        return {'status': 'AUTHORED_NETWORK_FAILURE', 'entitlement': 'Refund required', 'attempts': 1}
    if kind == 'download':
        bound = load_jobs(output / 'source', manifest)['demo-download']['artifact']
        accepted = accept(bound)
        destination = output / 'buyer-A' / 'package.json'
        _write(destination, bound)
        if canonical(_read(destination)) != canonical(bound):
            raise ValueError('DOWNLOADED_PACKAGE_CHANGED')
        return {'status': 'DOWNLOADED_AND_HASH_VERIFIED', 'package_sha256': accepted['package_sha256']}
    if kind == 'onboarding':
        bound = _read(output / 'buyer-A' / 'package.json')
        accept(bound)
        directory = output / 'buyer-A' / 'installed-demo'
        directory.mkdir(exist_ok=True)
        for name, text in bound['files'].items():
            atomic_bytes(directory / name, text.encode())
        process = subprocess.run([sys.executable, 'demo.py'], cwd=directory, capture_output=True, text=True, check=True)
        actual = strict_json(process.stdout)
        if actual != {'diagnostic': 'local_python_ready', 'external_calls': 0} or process.stderr:
            raise ValueError('ONBOARDING_DIAGNOSTIC_FAILED')
        return {'status': 'LOCAL_DEMO_EXECUTED', 'diagnostic': actual}
    raise ValueError('REGISTERED_LIFECYCLE_STEP_REQUIRED')


def _operate(output, *, interrupt_after=None):
    output = Path(output).resolve()
    policy = _read(output / 'registration.json')
    if canonical(policy) != canonical(registration()):
        raise ValueError('LIFECYCLE_REGISTRATION_CHANGED')
    manifest = _read(output / 'manifest.json')
    source = output / 'source'
    if source != Path(__file__).resolve().parents[1]:
        raise ValueError('EXECUTE_FROM_EXACT_STAGED_RUNTIME')
    state_path = output / 'STATE.json'
    account_path = output / 'account.sqlite'
    if state_path.exists() and not account_path.with_name('account.sqlite.adaptive-simulation-key').is_file():
        raise ValueError('ORIGINAL_FIXTURE_RECOVERY_AUTHORITY_REQUIRED')
    with JournalAccount(source, manifest, account_path, opening=OPENING, working=0,
                        contract='omega-lifecycle:' + digest(policy)) as account:
        if state_path.exists():
            state = account.verify_checkpoint(_read(state_path))
        else:
            if account.export()['ledger']['actions']:
                raise ValueError('OPERATING_CHECKPOINT_MISSING_DO_NOT_RESTART')
            state = {'next_step': 0, 'local_results': {}}
            _write(state_path, account.seal_checkpoint(state))
        sequence = steps()
        for index in range(state['next_step'], len(sequence)):
            step = sequence[index]
            if step['kind'] == 'native':
                account.execute(step['op'], step['args'], step['hour'])
            else:
                state['local_results'][step['id']] = _local(account, step, output, manifest)
            if interrupt_after == step['id']:
                os._exit(75)
            state['next_step'] = index + 1
            _write(state_path, account.seal_checkpoint(state))
        record = account.export()
        report = derive_report(output, policy, manifest, record, state['local_results'])
        _write(output / 'native-public-export.json', record)
        _write(output / 'result.json', report)
        return report


def derive_report(output, policy, manifest, record, local_results):
    output = Path(output)
    if canonical(policy) != canonical(registration()):
        raise ValueError('LIFECYCLE_REGISTRATION_CHANGED')
    config = record['ledger']['config']
    if config['contract'] != 'omega-lifecycle:' + digest(policy) or config['opening'] != OPENING or config['working'] != 0:
        raise ValueError('LIFECYCLE_ACCOUNT_BINDING_CHANGED')
    expected = [{'op': s['op'], 'args': s['args'], 'day': s['hour']} for s in steps() if s['kind'] == 'native']
    actual = [{k: a[k] for k in ['op', 'args', 'day']} for a in record['ledger']['actions']]
    if canonical(expected) != canonical(actual):
        raise ValueError('LIFECYCLE_REGISTERED_NATIVE_ACTIONS_CHANGED')
    audit = audit_journal(record, root=output / 'source', manifest=manifest)
    local_ids = {s['id'] for s in steps() if s['kind'] != 'native'}
    if set(local_results) != local_ids:
        raise ValueError('COMPLETE_REGISTERED_LOCAL_JOURNEY_REQUIRED')
    release = next(a for a in record['ledger']['actions'] if a['op'] == 'event' and a['args']['event_id'] == 'A-release')
    required = {'investment': 'DEFERRED', 'requested_microUSD': 1001 * MICRO,
                'profit_microUSD': release['after']['profit'], 'available_microUSD': release['after']['available'],
                'native_state_unchanged': True}
    if canonical(local_results['liquidity']) != canonical(required) or required['profit_microUSD'] <= 0:
        raise ValueError('LIQUIDITY_REPORT_CHANGED')
    downloaded = _read(output / 'buyer-A' / 'package.json')
    checked = accept(downloaded)
    if local_results['A-download'] != {'status': 'DOWNLOADED_AND_HASH_VERIFIED', 'package_sha256': checked['package_sha256']}:
        raise ValueError('DOWNLOAD_RECEIPT_CHANGED')
    for name, text in downloaded['files'].items():
        if (output / 'buyer-A' / 'installed-demo' / name).read_bytes() != text.encode():
            raise ValueError('INSTALLED_DEMO_CHANGED')
    expected_locals = {
        'decline': {'decision': 'NO_PURCHASE', 'native_order_created': False, 'reason': 'Authored voluntary decline control'},
        'ambiguous-choice': {'ambiguous_choice': 'REJECTED', 'native_order_created': False},
        'tampered-package': {'tampered_package': 'REJECTED', 'native_preparation_authorized': False},
        'unavailable-model-help': {'model_available': False, 'external_calls': 0,
            'documentation_sha256': hashlib.sha256(FILES['README.txt'].encode()).hexdigest(),
            'known_action': 'Run the included local Python diagnostic.', 'unresolved': True,
            'next_action': 'DEFER_AND_KEEP_DATA_LOCAL', 'human_exception_minutes_assumed': 5},
        'A-onboarding': {'status': 'LOCAL_DEMO_EXECUTED', 'diagnostic': {'diagnostic': 'local_python_ready', 'external_calls': 0}},
        'B-failed-download': {'status': 'AUTHORED_NETWORK_FAILURE', 'entitlement': 'Refund required', 'attempts': 1},
        'revocation': {'download_access': 'REVOKED', 'previously_downloaded_copy': 'Cannot be remotely erased'},
    }
    for ident in ['A', 'B']:
        expected_locals[ident + '-entitlement'] = {'entitlement': 'ACTIVE', 'order': ident, 'edition': EDITION, 'native_state': 'funded'}
    for name, value in expected_locals.items():
        if canonical(local_results[name]) != canonical(value):
            raise ValueError('LOCAL_JOURNEY_RECEIPT_CHANGED:' + name)
    summary = record['ledger']['summary']
    return {'schema': 'omega/lifecycle-result/v1', 'scope': policy['scope'],
            'registration_sha256': digest(policy), 'native_audit': audit,
            'native_summary_microUSD': summary, 'native_actions_sha256': record['ledger']['actions_sha256'],
            'local_results': copy.deepcopy(local_results), 'original_account': ORIGINAL,
            'accepted_downloads': 1, 'failed_deliveries_refunded': 1, 'released_orders_later_reversed': 1,
            'authored_buyer_cases': 3, 'buyer_choices_declined': 1,
            'human_exception_cases': 2, 'human_exception_minutes_assumed': 15,
            'human_exception_rate_of_three_buyer_cases': {'numerator': 2, 'denominator': 3},
            'founder_opportunity_cost_microUSD': [0, 50 * MICRO, 500 * MICRO],
            'profit_after_founder_opportunity_before_unknown_tax_microUSD': [summary['profit'] - c for c in [0, 50 * MICRO, 500 * MICRO]],
            'manual_offers': policy['manual_offers'], 'modeled_session_minutes': {'webinar': 150, 'founder_private': 75},
            'actual_complete_cost_profit_microUSD': None, 'trailing_365_day_profit_microUSD': None,
            'period': {'first_hour': 0, 'last_hour': 14, 'full_year': False},
            'next_action': 'NO_EXPANSION; retain cash, require supported buyer value and product rights',
            'claim_limits': policy['claim_limits']}


def replay(output):
    output = Path(output).resolve()
    policy, manifest = _read(output / 'registration.json'), _read(output / 'manifest.json')
    record, saved = _read(output / 'native-public-export.json'), _read(output / 'result.json')
    expected = derive_report(output, policy, manifest, record, saved.get('local_results', {}))
    if canonical(expected) != canonical(saved):
        raise ValueError('LIFECYCLE_REPORTED_RESULT_CHANGED')
    return {'accepted': expected['native_audit']['accepted'], 'native_actions_sha256': expected['native_actions_sha256'],
            'scope': expected['scope'], 'registration_sha256': digest(policy)}


def run_fixture(output, *, resume=False, interrupt_after=None, root=None):
    output = Path(output).absolute()
    if not resume:
        if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
            raise ValueError('FRESH_FIXTURE_DESTINATION_REQUIRED')
        output.mkdir(parents=True)
        stage(root or Path(__file__).resolve().parents[1], output / 'source')
        _write(output / 'registration.json', registration())
        _write(output / 'source' / 'download-fixture' / 'package.json', package())
        build = subprocess.run([sys.executable, '-m', 'omega.seller_lifecycle', '--output', str(output), '--staged', '--initialize'],
                               cwd=output / 'source', capture_output=True, text=True)
        if build.returncode:
            raise ValueError('STAGED_FIXTURE_INITIALIZATION_FAILED:' + build.stderr[-2000:])
    elif not (output / 'STATE.json').is_file():
        raise ValueError('EXISTING_SAME_FIXTURE_CHECKPOINT_REQUIRED')
    command = [sys.executable, '-m', 'omega.seller_lifecycle', '--output', str(output), '--staged']
    if interrupt_after:
        if interrupt_after not in {s['id'] for s in steps()}:
            raise ValueError('REGISTERED_INTERRUPT_STEP_REQUIRED')
        command += ['--interrupt-after', interrupt_after]
    process = subprocess.run(command, cwd=output / 'source', capture_output=True, text=True)
    if process.returncode == 75:
        return {'complete': False, 'interrupted_after': interrupt_after, 'scope': registration()['scope']}
    if process.returncode:
        raise ValueError('STAGED_FIXTURE_EXECUTION_FAILED:' + process.stderr[-3000:])
    return _read(output / 'result.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--staged', action='store_true')
    parser.add_argument('--initialize', action='store_true')
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--interrupt-after')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    try:
        if args.staged and args.initialize:
            if (output / 'manifest.json').exists():
                raise ValueError('EXISTING_MANIFEST_NEVER_REINITIALIZED')
            _write(output / 'manifest.json', manifest_for(output / 'source', 'download-fixture/package.json'))
            result = {'initialized': True}
        elif args.staged:
            result = replay(output) if args.audit else _operate(output, interrupt_after=args.interrupt_after)
        elif args.audit:
            process = subprocess.run([sys.executable, '-m', 'omega.seller_lifecycle', '--output', str(output), '--staged', '--audit'],
                                     cwd=output / 'source', check=True, capture_output=True, text=True)
            print(process.stdout, end='')
            return
        else:
            result = run_fixture(output, resume=args.resume, interrupt_after=args.interrupt_after)
        print(json.dumps(result, indent=2, sort_keys=True))
    except InterruptedError:
        sys.exit(75)


if __name__ == '__main__':
    main()
