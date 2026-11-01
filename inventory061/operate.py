"""Fund actual inventory engineering, accept its actual output, collect natively.

The $5,000 offer and buyer funding/consent are conditional simulated inputs.
This does not imply a real quote, buyer, purchase or achieved AI cost reduction.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

from commercial.ledger import canonical, digest, strict_json
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import source_identity
from connected_enterprise.scale import trailing_profit
from .native import BusinessAccount, audit_export
from .service import prepare_manifest

MICRO = 1_000_000


def money(value):
    return int((Decimal(str(value))*MICRO).to_integral_value(rounding=ROUND_CEILING))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def reopen(root, state_dir):
    root, state_dir = Path(root).resolve(), Path(state_dir).resolve()
    manifest = strict_json((state_dir/'manifest.json').read_bytes())
    previous = strict_json((state_dir/'public-native-export.json').read_bytes())
    result = strict_json((state_dir/'result.json').read_bytes())
    with BusinessAccount(root, manifest, state_dir/'owned-account.json',
                         contract='inventory061-'+result['arm']) as account:
        account.verify_checkpoint(result['checkpoint'])
        current = account.export()
        if current != previous:
            raise ValueError('INVENTORY061_REOPEN_CHANGED_FINANCIAL_HISTORY')
        verdict = account.audit()
        receipt = {'schema': 'inventory061/exact-reopen/v1', 'accepted': verdict['accepted'],
                   'same_export_sha256': digest(current), 'same_export_bytes': True,
                   'summary': account.snapshot()['summary'], 'native_audit': verdict,
                   'checkpoint_verified': True, 'reseeded': False, 'new_native_actions': 0}
    save(state_dir/'reopen.json', receipt)
    return receipt


def operate(root, state_dir, arm='conditional'):
    root, state_dir = Path(root).resolve(), Path(state_dir).resolve()
    if state_dir.exists():
        raise ValueError('INVENTORY061_NEW_EVIDENCE_DIRECTORY_REQUIRED_USE_REOPEN')
    state_dir.mkdir(parents=True)
    economics = strict_json((root/'inventory061/economics.json').read_bytes())
    manifest = prepare_manifest(root, delivery_path=f'inventory061/deliveries/{arm}/solution.json')
    save(state_dir/'manifest.json', manifest)
    source = source_identity(root)
    save(state_dir/'source-closure.json', source)
    report = {'schema': 'inventory061/native-first-engineering-example/v1', 'arm': arm,
              'scope': 'CONDITIONAL_NATIVE_SIMULATION_WITH_REAL_PUBLIC_INPUT_AND_ACTUAL_PRODUCTION',
              'primary_seed_usd': 100000, 'observed_buyers': 0,
              'price_status': economics['price_status'], 'economics': economics,
              'source_sha256': source['sha256'], 'manifest_sha256': digest(manifest),
              'production': None, 'acceptance': None, 'costs': [],
              'rights': {'retain_constructor': True, 'portable_accepted_output': True,
                         'exclusive_public_data_or_algorithm_rights': False,
                         'compelled_repeat_purchase': False, 'no_purchase_retains_cash': True},
              'limits': ['Historical2023 empirical service is not future inventory performance.',
                         'Modeled inventory cost is not AGI revenue, receivable, cash or profit.',
                         'One public client scenario does not establish a new industry or economic feasibility.',
                         'The included assistant constructed the instrument; this is not an unattended general inventor.',
                         'The all95-percent offer ties a competent ordinary empirical comparator.',
                         'No external API call, publication, contact, real sale or warehouse action.']}
    with BusinessAccount(root, manifest, state_dir/'owned-account.json', contract='inventory061-'+arm) as account:
        def cost(ident, amount, hour):
            native = account.cost(ident, money(amount), hour)
            report['costs'].append({'id': ident, 'microUSD': money(amount), 'hour': hour})
            return native
        if arm == 'no_purchase':
            cost('declined-before-construction-zero-incurred-cost', 0, 0)
            report['decision'] = 'DECLINE_NO_OBSERVED_PURCHASE_OR_EXCLUSIVE_RIGHTS_REQUIRED_RETAIN_CASH'
        else:
            for ident, amount in economics['fixed_costs_usd'].items():
                cost(ident, amount, 0)
            price = money(economics['fixed_price_usd'])
            terms = prospective_terms('inventory-first-job', price, 73, 25,
                residual=money(economics['native_residual_usd']), fee=money(economics['native_fee_usd']),
                counterparty_obligations='Conditional fixed-price engineering contract, not an observed buyer agreement. Producer delivers original-public-input inventory policies plus runnable instrument with every48 empirical joint services at least347/365. No future operational guarantee; all claims retained by producer. Buyer can decline or use portable artifact without forced future royalties.')
            account.begin_order('orlicense13-quality95', 'inventory-first-job',
                                'conditional-one-client-model', price, price, 24, 26, terms=terms)
            production_cost = sum(economics['production_prepaid_costs_usd'].values())
            payment = account.spend('fund-inventory-engineering', 'bespoke_inventory_engineering',
                money(production_cost), 24,
                {'request_sha256': digest(manifest['jobs'][0]['request']),
                 'quality_constructor_sha256': source['files']['inventory061/quality_constructor.py'],
                 'prepaid_cost_breakdown_usd': economics['production_prepaid_costs_usd'],
                 'action': 'Execute fresh quality_constructor process after this native commitment; independently accept actual output.'},
                expected_net=0, allow_seed=True)
            if payment is None:
                account.refund('inventory-first-job', 24)
                raise ValueError('INVENTORY061_NATIVE_PRODUCTION_FUNDING_REFUSED')
            before_export = account.export()
            funded = before_export['ledger']['orders'][0]['state'] == 'funded'
            destination = root/f'inventory061/deliveries/{arm}'
            if not funded or destination.exists():
                raise ValueError('INVENTORY061_FRESH_POST_FUNDING_PRODUCTION_REQUIRED')
            destination.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(root/'inventory061/quality_constructor.py'),
                       '--input', str(root/'inventory061/inputs/01.json'), '--output', str(destination)]
            env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
            started_wall, started_monotonic = time.time_ns(), time.monotonic()
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            save(state_dir/'production.started.json', {'command': command,
                'started_unix_ns': started_wall, 'funded_before_start': True,
                'native_action_count_before_start': len(before_export['ledger']['actions']),
                'native_actions_sha256_before_start': before_export['ledger']['actions_sha256'],
                'native_resource_receipt': payment, 'delivery_directory_absent_before_start': True,
                'source_sha256': source['sha256']})
            try:
                completed = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                           text=True, timeout=180, check=False)
                exitcode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
            except subprocess.TimeoutExpired as exc:
                exitcode, stdout, stderr = 124, str(exc.stdout or ''), str(exc.stderr or '')
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
            resource_receipt = {'exit_code': exitcode, 'actual_reaped_cpu_s': cpu,
                'actual_wall_s': time.monotonic()-started_monotonic,
                'max_rss_KiB': after.ru_maxrss, 'started_unix_ns': started_wall,
                'finished_unix_ns': time.time_ns(), 'external_model_calls': 0,
                'actual_total_AI_billing_usd': None,
                'python': platform.python_version(), 'executable_sha256': hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()}
            (state_dir/'production.stdout').write_text(stdout)
            (state_dir/'production.stderr').write_text(stderr)
            save(state_dir/'production-resource.json', resource_receipt)
            report['production'] = resource_receipt
            cost('actual-measured-production-compute', cpu/3600*economics['compute_usd_per_cpu_hour'], 25)
            if exitcode == 0:
                artifact = strict_json((destination/'solution.json').read_bytes())
                receipt = account.complete_order('inventory-first-job', 'orlicense13-quality95', artifact, 25)
                save(state_dir/'acceptance.json', receipt)
                report['acceptance'] = receipt
                if receipt['accepted']:
                    cost('payment-processing', economics['fixed_price_usd']*economics['payment_percent']+economics['payment_fixed_usd'], 25)
                    account.release('inventory-first-job', 25)
                else:
                    account.refund('inventory-first-job', 25)
            else:
                account.refund('inventory-first-job', 25)
            report['decision'] = 'LOSS_MAKING_CONDITIONAL_FIRST_CONSTRUCTION_DO_NOT_ASSERT_SUSTAINABILITY'
        account.advance(8758)
        summary = account.snapshot()['summary']
        tax = max(0, summary['profit']/MICRO)*economics['tax_rate_positive_income']
        if tax:
            cost('income-tax', tax, 8759)
        checkpoint = account.seal_checkpoint({'arm': arm, 'operating_end_hour': 8760,
            'funded_requests': int(arm == 'conditional'),
            'costs_complete_for_declared_model': True,
            'actual_total_AI_billing_known': False, 'no_additional_orders_assumed': True})
        account.verify_checkpoint(checkpoint)
        exported = account.export()
        verdict = account.audit()
        report.update(summary=account.snapshot()['summary'], native_audit=verdict,
            checkpoint=checkpoint, public_export_sha256=digest(exported),
            native_trailing_profit=trailing_profit(exported['ledger'], operating_end_hour=8760, operating_complete=True))
        save(state_dir/'public-native-export.json', exported)
        save(state_dir/'result.json', report)
    independent = audit_export(exported, root=root, manifest=manifest)
    save(state_dir/'public-native-audit.json', independent)
    reopen(root, state_dir)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'reopen'])
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--arm', choices=['conditional', 'no_purchase'], default='conditional')
    args = parser.parse_args()
    result = operate(args.root, args.state_dir, args.arm) if args.command == 'run' else reopen(args.root, args.state_dir)
    print(json.dumps({'summary': result['summary'], 'accepted_native_audit': result['native_audit']['accepted']}))
