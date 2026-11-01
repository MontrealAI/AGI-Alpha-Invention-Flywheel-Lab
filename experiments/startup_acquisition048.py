"""Fixed source-bound startup buy/hold comparison on the canonical native ledger."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
from adaptive_enterprise.instruments import audit_admission, prepare_complete_offer_services
from commercial.ledger import digest
from connected_enterprise.engine import run_world
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit

ROOT = Path(__file__).resolve().parents[1]
CASES = ('positive', 'no_demand', 'overpriced', 'default', 'support', 'timing', 'failed_channel', 'unexpected_default')
SEED = 2611010483
COHORT = 2611010481


def fixture(manifest, enabled, case):
    spec = importlib.util.spec_from_file_location('startup048_public_fixture', ROOT / 'tests/test_connected_startup048.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg = module.fixture(manifest, enabled, case)
    if case == 'unexpected_default':
        cfg['nonpayment_bps'] = 10000
    return cfg


def source():
    value = identity(ROOT)
    for name in ('experiments/startup_acquisition048.py', 'scripts/run_commoncost026.py'):
        value['files'][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    value['sha256'] = digest(value['files'])
    return value


def write(path, value):
    with Path(path).open('w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def protocol():
    return {'schema': 'startup048-fixed-comparison/v1', 'cases': list(CASES), 'arms': ['off', 'on'],
                'seed': SEED, 'cohort_seed': COHORT, 'horizon_days': 8, 'opening_microUSD_per_separate_account': 100000000000,
                'primary_metric': 'Actual paid newly reached customers and complete modeled enterprise profit, with canonical independent audit',
                'comparison': 'Identical public offers, outside choices, inventory, channel and payment environment within each pair; candidate pays extra USD5 development plus USD0.05 startup evaluation and actual native acquisition/support/fulfillment costs.',
                'adverse': 'Unexpected-default world leaves public collection priors unchanged while environment refunds every accepted order. Expected-default, no-demand, overpriced, support, timing and failed-channel worlds test hold.',
                'stopping_rule': 'Complete these exact16 eight-day worlds and drain; preserve negative/refunded outcomes. No seed replacement, horizon extension or optional favorable retry.',
                'exposure': 'Builder-visible finite authored engineering cases, not untouched holdouts or empirical demand',
                'actual_host_model_engineering_billing_usd': None, 'authority': []}


def _validate_registration(frozen):
    if frozen['protocol'] != protocol():
        raise ValueError('FIXED_STARTUP_REGISTRATION_CHANGED')
    manifest = frozen['manifest']
    admission = manifest.get('cohort_provenance', {}).get('finite_admission', {})
    geometry = {'primitive_jobs_per_service': 32, 'packet_jobs': 1, 'packet_rows_per_kind': 40, 'chunk_size': 64}
    if manifest.get('native_engine') != 'exact-permanent-v2' or any(type(admission.get(k)) is not int or admission[k] != v for k,v in geometry.items()):
        raise ValueError('FIXED_STARTUP_INVENTORY_CHANGED')
    expected = {case: {arm: fixture(manifest, arm == 'on', case) for arm in ('off', 'on')} for case in CASES}
    if frozen['configs'] != expected:
        raise ValueError('FIXED_STARTUP_CONFIGS_CHANGED')
    # A generation label is insufficient: reconstruct the admitted raw origins.
    audit_admission(ROOT, manifest, cohort_seed=COHORT)


def _require_world_identity(frozen, case, arm, result):
    if (type(result.get('seed')) is not int or result['seed'] != SEED or result['seed'] != frozen['protocol']['seed']
            or result.get('arm') != 'competitive_growth' or result.get('complete') is not True
            or result.get('config') != frozen['configs'][case][arm] or result.get('source') != frozen['source']):
        raise ValueError('SAVED_NATIVE_WORLD_IDENTITY_CHANGED')


def _saved_result(output, frozen, row):
    result = json.loads((output / 'private' / (row['case'] + '-' + row['arm']) / 'RESULT.json').read_text())
    if digest(result) != row['result_sha256']:
        raise ValueError('SAVED_NATIVE_RESULT_REAUDIT_FAILED')
    _require_world_identity(frozen, row['case'], row['arm'], result)
    if not audit(ROOT, frozen['manifest'], result)['accepted']:
        raise ValueError('SAVED_NATIVE_RESULT_REAUDIT_FAILED')
    return result


def _require_summary(summary):
    required = {'protocol_sha256', 'rows', 'status', 'actual_profit_usd', 'authority'}
    if (not required <= set(summary) or set(summary) - required - {'process_cpu_seconds', 'wall_seconds'}
            or summary['actual_profit_usd'] is not None or summary['authority'] != []
            or summary['status'] not in {'RUNNING', 'COMPLETED'}):
        raise ValueError('FIXED_STARTUP_SUMMARY_CLAIMS_CHANGED')


def register(output):
    output.mkdir(parents=True, exist_ok=False)
    relative = '.startup048-inputs/' + digest(str(output))[:16]
    manifest = prepare_complete_offer_services(ROOT, relative, cohort_seed=COHORT, jobs_per_service=32, packet_jobs=1)
    manifest['native_engine'] = 'exact-permanent-v2'
    frozen = {'protocol': protocol(), 'source': source(), 'manifest': manifest,
              'configs': {case: {arm: fixture(manifest, arm == 'on', case) for arm in ('off', 'on')} for case in CASES}}
    write(output / 'PREREGISTRATION.json', frozen)
    return frozen


def run(output):
    frozen = json.loads((output / 'PREREGISTRATION.json').read_text())
    if frozen['source'] != source():
        raise ValueError('FROZEN_SOURCE_CHANGED')
    result_path = output / 'SUMMARY.json'
    summary = json.loads(result_path.read_text()) if result_path.exists() else {
        'protocol_sha256': digest(frozen), 'rows': [], 'status': 'RUNNING', 'actual_profit_usd': None, 'authority': []}
    _require_summary(summary)
    _validate_registration(frozen)
    if summary['protocol_sha256'] != digest(frozen) or summary['status'] == 'COMPLETED':
        raise ValueError('PREREGISTRATION_CHANGED_OR_FIXED_COMPARISON_COMPLETE')
    completed = {(row['case'], row['arm']) for row in summary['rows']}
    if len(completed) != len(summary['rows']) or not completed <= {(case, arm) for case in CASES for arm in ('off', 'on')}:
        raise ValueError('MATCHED_COVERAGE_REQUIRED')
    for row in summary['rows']:
        _saved_result(output, frozen, row)
    start, cpu = time.monotonic(), time.process_time()
    for case in CASES:
        for arm in ('off', 'on'):
            if (case, arm) in completed:
                continue
            cfg = frozen['configs'][case][arm]
            folder = output / 'private' / (case + '-' + arm)
            result = run_world(ROOT, frozen['manifest'], cfg, SEED, 'competitive_growth', folder, source=frozen['source'])
            _require_world_identity(frozen, case, arm, result)
            checked = audit(ROOT, frozen['manifest'], result)
            new = [o for o in result['orders'] if o['customer_id'] not in {f'SIM-customer-{i:03d}' for i in range(4)}]
            row = {'case': case, 'arm': arm, 'complete': result['complete'], 'audit_accepted': checked['accepted'],
                   'result_sha256': digest(result), 'summary': result['summary'], 'paid_jobs': result['paid_jobs'],
                   'new_paid_customers': len({o['customer_id'] for o in new if o['outcome'] == 'SETTLED'}),
                   'refunded_jobs': sum(o['outcome'] == 'REFUNDED' for o in result['orders']),
                   'actual_exposures': sum(record['realized_exposures'] for record in result['channels']['exposures_by_day'].values()),
                   'investments': [{k: i[k] for k in ('id', 'plan_id', 'kind', 'cost', 'purchased_time', 'activation_time', 'expiry_time')} |
                                   {'funding': i['funding_receipt']['funding'], 'native_plan_id': i['funding_receipt']['plan_id']} for i in result['investments']],
                   'orders': [{k:o.get(k) for k in ('id','job_id','customer_id','price','complete_cost','outcome','qualified_time','collection_time','acquisition_source_plan_id')} for o in result['orders']],
                   'commercial_gate': result['conditional_simulated_commercial_success']}
            if not result['complete'] or not checked['accepted']:
                raise ValueError('COMPLETE_NATIVE_AUDIT_REQUIRED')
            summary['rows'].append(row)
            summary['process_cpu_seconds'] = time.process_time() - cpu
            summary['wall_seconds'] = time.monotonic() - start
            write(result_path, summary)
    summary['status'] = 'COMPLETED'
    write(result_path, summary)
    return summary


def verify(output):
    frozen = json.loads((output / 'PREREGISTRATION.json').read_text())
    summary = json.loads((output / 'SUMMARY.json').read_text())
    if frozen['source'] != source() or summary['protocol_sha256'] != digest(frozen) or summary['status'] != 'COMPLETED':
        raise ValueError('SOURCE_PROTOCOL_OR_COMPLETION_CHANGED')
    _require_summary(summary)
    _validate_registration(frozen)
    expected = {(case, arm) for case in CASES for arm in ('off', 'on')}
    if {(row['case'], row['arm']) for row in summary['rows']} != expected or len(summary['rows']) != len(expected):
        raise ValueError('MATCHED_COVERAGE_REQUIRED')
    for row in summary['rows']:
        result = _saved_result(output, frozen, row)
        new=[o for o in result['orders'] if o['customer_id'] not in {f'SIM-customer-{i:03d}' for i in range(4)}]
        expected_row={'case':row['case'],'arm':row['arm'],'complete':result['complete'],'audit_accepted':True,'result_sha256':digest(result),'summary':result['summary'],'paid_jobs':result['paid_jobs'],
            'new_paid_customers':len({o['customer_id'] for o in new if o['outcome']=='SETTLED'}),'refunded_jobs':sum(o['outcome']=='REFUNDED' for o in result['orders']),
            'actual_exposures':sum(record['realized_exposures'] for record in result['channels']['exposures_by_day'].values()),
            'investments':[{k:i[k] for k in ('id','plan_id','kind','cost','purchased_time','activation_time','expiry_time')}|{'funding':i['funding_receipt']['funding'],'native_plan_id':i['funding_receipt']['plan_id']} for i in result['investments']],
            'orders':[{k:o.get(k) for k in ('id','job_id','customer_id','price','complete_cost','outcome','qualified_time','collection_time','acquisition_source_plan_id')} for o in result['orders']],
            'commercial_gate':result['conditional_simulated_commercial_success']}
        if row!=expected_row:raise ValueError('PUBLIC_SUMMARY_DOES_NOT_RECONCILE')
    value = {'accepted': True, 'worlds': len(expected), 'summary_sha256': digest(summary), 'source_sha256': frozen['source']['sha256'], 'authority': []}
    write(output / 'VERIFY.json', value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('register', 'run', 'verify'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'register': register, 'run': run, 'verify': verify}[args.command](args.output.resolve())
    print(json.dumps({'command': args.command, 'status': result.get('status'), 'accepted': result.get('accepted'), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
