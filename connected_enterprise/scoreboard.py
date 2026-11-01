"""Read-only display of bound operating records; never a funding authority."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from commercial.ledger import digest, strict_json
from .scale import analyze


def _path(root, name):
    if not isinstance(name, str) or not name:
        raise ValueError('SCOREBOARD_NORMALIZED_RELATIVE_PATH_REQUIRED')
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name:
        raise ValueError('SCOREBOARD_NORMALIZED_RELATIVE_PATH_REQUIRED')
    path = root / relative
    if any(part.is_symlink() for part in [path, *path.parents]):
        raise ValueError('SCOREBOARD_SYMLINK_REFUSED')
    return path


def _read(root, name):
    try:
        return strict_json(_path(root, name).read_bytes())
    except FileNotFoundError as exc:
        raise ValueError('SCOREBOARD_REQUIRED_FILE_MISSING:' + name) from exc


def _unique(rows, key, label):
    if not isinstance(rows, list) or any(not isinstance(row, dict) or key not in row for row in rows):
        raise ValueError('SCOREBOARD_' + label + '_RECORDS_REQUIRED')
    ids = [row[key] for row in rows]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('SCOREBOARD_' + label + '_DUPLICATE_OR_MISSING_ID')


def _daily(result, aggregation):
    daily = {row['day']: copy.deepcopy(row) for row in aggregation['days']}
    fields = ('contacts', 'opportunities_with_recorded_choice', 'offers', 'qualified_orders',
              'completed_work', 'accepted_orders', 'settled_orders')

    def increment(moment, name):
        if type(moment) is not int or moment < 0:
            raise ValueError('SCOREBOARD_NONNEGATIVE_EVENT_CLOCK_REQUIRED')
        day = moment // 24
        if day not in daily:
            daily[day] = {'day': day, 'first_hour': moment, 'last_hour': moment,
                          'flow_microUSD': None, 'end_state_microUSD': None}
        daily[day]['first_hour'] = min(daily[day]['first_hour'], moment)
        daily[day]['last_hour'] = max(daily[day]['last_hour'], moment)
        counts = daily[day].setdefault('recorded_counts', {field: 0 for field in fields})
        counts[name] += 1

    for row in result['events']:
        if row['kind'] == 'EXPOSURE':
            increment(row['time'], 'contacts')
    for row in result['decisions']:
        if row['kind'] in {'offer', 'outside_choice'}:
            increment(row['time'], 'opportunities_with_recorded_choice')
        if row['kind'] == 'offer':
            increment(row['time'], 'offers')
    for row in result['orders']:
        increment(row['qualified_time'], 'qualified_orders')
        if row.get('service_receipt') is not None:
            increment(row['production_time'], 'completed_work')
        if row.get('acceptance_time') is not None:
            increment(row['acceptance_time'], 'accepted_orders')
        if row.get('collection_time') is not None and row.get('outcome') == 'SETTLED':
            increment(row['collection_time'], 'settled_orders')
    for row in daily.values():
        row.setdefault('recorded_counts', {field: 0 for field in fields})
        row['retention_fraction'] = None
        row['measured_host_billing_microUSD'] = None
        row['measured_frontier_inference_billing_microUSD'] = None
    return [daily[day] for day in sorted(daily)]


def _world(task, result, directory):
    record = result['owned_account']
    if record.get('schema') != 'agi-alpha/adaptive012-owned-account/v1' or record.get('scope') != 'SIMULATED':
        raise ValueError('SCOREBOARD_NATIVE_OWNED_SIMULATED_ACCOUNT_REQUIRED')
    ledger = record['ledger']
    if result['summary'] != ledger['summary']:
        raise ValueError('SCOREBOARD_NATIVE_SUMMARY_MISMATCH')
    for key, label in [('orders', 'ORDER'), ('events', 'EVENT'), ('investments', 'INVESTMENT'), ('costs', 'COST')]:
        _unique(result[key], 'id', label)
    growth = analyze(result)
    summary = result['summary']
    stored_audit = _read(directory, 'AUDIT.json')
    decisions = result['decisions']
    offers = sum(row['kind'] == 'offer' for row in decisions)
    orders = result['orders']
    settled = [row for row in orders if row.get('outcome') == 'SETTLED' and row.get('collection_time') is not None]
    accepted = sum(row.get('acceptance_time') is not None for row in orders)
    completed = sum(row.get('service_receipt') is not None for row in orders)
    choices = sum(row['kind'] in {'offer', 'outside_choice'} for row in decisions)
    known_services = sorted({row['offer']['service_id'] for row in orders})
    cost_categories = {}
    for row in result['costs']:
        cost_categories[row['category']] = cost_categories.get(row['category'], 0) + row['amount']
    return {'business_reference': task['id'], 'seed': task['seed'], 'case': task['case'], 'arm': task['arm'],
            'account_identity': record.get('account_identity'),
            'account_identity_scope': 'No account identity is inferred from a seed, world label or absence of a published private key.',
            'scope': result['scope'], 'complete': result['complete'], 'executed_hours': growth['executed_hours'],
            'native_actions_sha256': ledger['actions_sha256'],
            'verification': {'record_binding': 'HASH_BOUND_TO_COMPLETED_PACKAGE',
                             'financial_display': 'NATIVE_EVENT_ARITHMETIC_RECONCILED_NOT_ACCOUNT_AUTHORITY_AUDIT',
                             'stored_audit_accepted': stored_audit.get('accepted'),
                             'stored_audit_sha256': digest(stored_audit),
                             'stored_audit_scope': 'Recorded receipt only. Run the canonical audit command to reconstruct financial and operating authority.'},
            'recorded_counts': {'contacts': sum(row['kind'] == 'EXPOSURE' for row in result['events']),
                                'opportunities_with_recorded_choice': choices, 'offers': offers,
                                'qualified_orders': len(orders), 'completed_work': completed,
                                'accepted_orders': accepted, 'settled_orders': len(settled),
                                'paying_customers': growth['cohorts']['paying_customers'],
                                'repeat_paying_customers': growth['cohorts']['repeat_paying_customers']},
            'ratios': {'qualified_per_offer': None if not offers else len(orders) / offers,
                       'settled_per_offer': None if not offers else len(settled) / offers,
                       'retention_fraction': None},
            'financial_state_microUSD': copy.deepcopy(summary),
            'cash_generation_microUSD': summary['collections'] + summary['recoveryIncome'] - summary['expensePaid'],
            'recorded_cost_categories_microUSD': cost_categories,
            'native_expense_minus_reported_cost_rows_microUSD': summary['expenses'] - sum(cost_categories.values()),
            'cohorts_and_nonadditive_investment_attribution': growth['cohorts'],
            'growth_ledger': _daily(result, growth['aggregation']),
            'service_ids_with_qualified_orders': known_services,
            'forecast_investment_net_microUSD': [{'investment_id': row['id'], 'predicted_net_microUSD': row.get('predicted_net'),
                                                  'realized_complete_enterprise_increment_microUSD': None} for row in result['investments']],
            'trailing_twelve_month_profit_microUSD': growth['trailing_profit']['trailing_365_day_profit_microUSD'],
            'trailing_365_profit_observer': copy.deepcopy(growth['trailing_profit']),
            'annual_profit_status': ('RECONCILED_DECLARED_365_DAY_MODELED_WINDOW'
                                    if growth['trailing_profit']['complete_365_day_operating_history']
                                    else 'NOT_COMPUTED_NO_SHORT_COHORT_ANNUALIZATION'),
            'measured_host_billing_microUSD': None, 'measured_frontier_inference_billing_microUSD': None,
            'resource_receipt': copy.deepcopy(result.get('resource_receipt')),
            'resource_receipt_scope': 'Final run_world invocation only; prior paused invocations are not accumulated here. Retain durable command receipts for complete lifecycle resource accounting.',
            'cost_scope': result['config'].get('cost_evidence'),
            'actual_external_commerce': {'customers': result.get('actual_customers'),
                                         'collections_microUSD': result.get('actual_collections'),
                                         'profit_microUSD': result.get('actual_profit')},
            'limits': copy.deepcopy(result['config'].get('limits', []))}


def scoreboard(output):
    """Display one completed package without writing files or opening live accounts."""
    output = Path(output).expanduser()
    if any(part.is_symlink() for part in [output, *output.parents]):
        raise ValueError('SCOREBOARD_SYMLINK_REFUSED')
    output = output.resolve()
    frozen = _read(output, 'FROZEN.json')
    if not isinstance(frozen, dict) or frozen.get('schema') != 'agi-alpha/connected014-freeze/v1':
        raise ValueError('SCOREBOARD_CONNECTED_FREEZE_REQUIRED')
    frozen_body = {key: value for key, value in frozen.items() if key != 'sha256'}
    if frozen.get('sha256') != digest(frozen_body):
        raise ValueError('SCOREBOARD_FREEZE_HASH_MISMATCH')
    source = frozen['source']
    if not isinstance(source.get('files'), dict) or not source['files'] or source.get('sha256') != digest(source['files']):
        raise ValueError('SCOREBOARD_SOURCE_IDENTITY_MISMATCH')
    for name, expected in source['files'].items():
        if hashlib.sha256(_path(output / 'source', name).read_bytes()).hexdigest() != expected:
            raise ValueError('SCOREBOARD_FROZEN_SOURCE_BYTES_CHANGED:' + name)
    report = _read(output, 'REPORT.json')
    complete = _read(output, 'COMPLETE.json')
    if not isinstance(report, dict) or report.get('schema') != 'agi-alpha/connected014-report/v1' or report.get('scope') != 'CONDITIONAL_SIMULATION':
        raise ValueError('SCOREBOARD_CONNECTED_SIMULATED_REPORT_REQUIRED')
    indices = report.get('worlds_index')
    if not isinstance(indices, list) or not indices or any(not isinstance(row, dict) for row in indices):
        raise ValueError('SCOREBOARD_NONEMPTY_WORLD_INDEX_REQUIRED')
    if (report.get('source_sha256') != source['sha256'] or report.get('frozen_sha256') != frozen['sha256']
            or report.get('worlds') != len(indices)
            or complete != {'source_sha256': source['sha256'], 'report_sha256': digest(report), 'worlds': len(indices)}):
        raise ValueError('SCOREBOARD_COMPLETION_OR_REPORT_BINDING_MISMATCH')
    tasks = [row.get('task') for row in indices]
    _unique(tasks, 'id', 'BUSINESS')
    from .runner import tasks as registered_tasks, task_config
    if tasks != registered_tasks(frozen['protocol']):
        raise ValueError('SCOREBOARD_REGISTERED_BUSINESS_SET_MISMATCH')
    identities = []
    worlds = []
    for task, index in zip(tasks, indices):
        if (set(task) != {'id', 'seed', 'case', 'arm'} or type(task['seed']) is not int
                or any(not isinstance(task[key], str) or not task[key] for key in ['case', 'arm'])
                or task['id'] != str(task['seed']) + '-' + task['case'] + '-' + task['arm']):
            raise ValueError('SCOREBOARD_EXACT_WORLD_IDENTITY_REQUIRED')
        _path(output / 'worlds', task['id'])
        ident = (task['seed'], task['case'], task['arm'])
        if ident in identities:
            raise ValueError('SCOREBOARD_DUPLICATE_WORLD_IDENTITY')
        identities.append(ident)
        directory = output / 'worlds' / task['id']
        result = _read(directory, 'RESULT.json')
        if (not isinstance(result, dict) or result.get('schema') != 'agi-alpha/connected014-result/v1'
                or result.get('scope') != 'CONDITIONAL_SIMULATION'
                or index.get('result_sha256') != digest(result) or result.get('source') != source
                or any(result.get(key) != task[key] for key in ['seed', 'case', 'arm'])
                or result.get('config') != task_config(frozen, task)
                or result.get('complete') is not True):
            raise ValueError('SCOREBOARD_WORLD_RESULT_BINDING_MISMATCH:' + task['id'])
        worlds.append(_world(task, result, directory))
    return {'schema': 'agi-alpha/connected-scoreboard/v1', 'scope': 'RECORDED_CONDITIONAL_SIMULATION',
            'source_sha256': source['sha256'], 'frozen_sha256': frozen['sha256'], 'report_sha256': digest(report),
            'world_count': len(worlds), 'businesses': worlds,
            'pooling': 'Each world is a separately seeded simulated business. Cash, profit, obligations and earned funding are not pooled.',
            'authority': 'Read-only record display. This command cannot authorize funding, certify a release or replace audit_account.',
            'scale_bridge': 'EXACT_NATIVE_RECORD_DISPLAY_ONLY_NOT_VALIDATED_FORWARD_AGGREGATION',
            'target_trailing_twelve_month_profit_microUSD': 3_000_000_000 * 1_000_000,
            'target_status': 'NOT_ESTABLISHED_BY_THIS_SCOREBOARD'}
