"""Native financial aggregation and an explicit boundary on scale claims."""
from __future__ import annotations
import copy
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

MICRO = 1_000_000
HOURS_PER_DAY = 24
YEAR_HOURS = 365 * HOURS_PER_DAY
TARGETS_USD = (1_000_000, 10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000)
FLOW_FIELDS = ('collections', 'recoveryIncome', 'revenue', 'expenses', 'expensePaid')
STATE_FIELDS = ('cash', 'profit', 'payables', 'tailReserve', 'custodyReserve',
                'workingCapital', 'unrestrictedEarned', 'available', 'equityProtectionBacking')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _integer(value, label):
    if type(value) is not int:
        raise ValueError('INTEGER_MICROUSD_OR_TIME_REQUIRED:' + label)
    return value


def _covered(summary):
    protected = sum(summary[k] for k in ('tailReserve', 'custodyReserve', 'workingCapital'))
    return summary['payables'] == 0 and not summary['investmentStopped'] and summary['cash'] >= protected


def _calendar(epoch, hour):
    beginning = datetime.fromisoformat(epoch.replace('Z', '+00:00'))
    if beginning.tzinfo is None:
        raise ValueError('EXPLICIT_UTC_CALENDAR_REQUIRED')
    return (beginning + timedelta(hours=hour)).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _receivables(actions):
    orders = {}
    for action in actions:
        args = action['args']
        if action['op'] == 'offer':
            orders[args['id']] = {'price': args['price'], 'state': 'offered'}
        elif action['op'] == 'event':
            if args['id'] not in orders:
                raise ValueError('EVENT_WITHOUT_QUALIFIED_NATIVE_OFFER')
            orders[args['id']]['state'] = args['action']
    return sum(order['price'] for order in orders.values() if order['state'] == 'prepare')


def _point(summary, receivables):
    return {**{field: summary[field] for field in (*FLOW_FIELDS, *STATE_FIELDS)},
            'receivables': receivables, 'cash_generation': summary['collections'] + summary['recoveryIncome'] - summary['expensePaid'],
            'obligation_covered': _covered(summary),
            'profitable_and_obligation_covered': summary['profit'] > 0 and _covered(summary)}


def aggregate_native(tape, checkpoints=(8, 16, 32)):
    """Aggregate exact monetary events; this does not simulate future activity."""
    if not isinstance(tape, dict) or not tape.get('actions'):
        raise ValueError('NONEMPTY_NATIVE_ACTION_TAPE_REQUIRED')
    if tape.get('actions_sha256') != _digest(tape['actions']):
        raise ValueError('NATIVE_ACTION_HASH_MISMATCH')
    actions = tape['actions']
    opening = _integer(tape['config']['opening'], 'opening')
    initial = actions[0]['before']
    accumulated = {field: initial[field] for field in FLOW_FIELDS}
    daily = {}
    collections = []
    overlapping = []
    released = 0
    previous = initial
    last_time = -1
    for index, action in enumerate(actions):
        moment = _integer(action['day'], 'native-hour')
        if moment < last_time or action['before'] != previous or action['seq'] != index:
            raise ValueError('NONCAUSAL_NATIVE_ACTION_SEQUENCE')
        after = action['after']
        flow = {field: _integer(after[field], field) - _integer(previous[field], field) for field in FLOW_FIELDS}
        for field in FLOW_FIELDS:
            accumulated[field] += flow[field]
        expected_cash = opening + accumulated['collections'] + accumulated['recoveryIncome'] - accumulated['expensePaid']
        expected_profit = accumulated['revenue'] + accumulated['recoveryIncome'] - accumulated['expenses']
        if expected_cash != after['cash'] or expected_profit != after['profit']:
            raise ValueError('AGGREGATE_TO_NATIVE_CASH_OR_PROFIT_MISMATCH')
        if after['cash'] < 0 or after['payables'] < 0 or after['unrestrictedEarned'] < 0:
            raise ValueError('NEGATIVE_NATIVE_FINANCIAL_STATE')
        if flow['collections']:
            collections.append({'hour': moment, 'amount': flow['collections'], 'action_index': index})
        day = moment // HOURS_PER_DAY
        if day not in daily:
            daily[day] = {'day': day, 'first_hour': moment, 'last_hour': moment,
                          'flow_microUSD': {field: 0 for field in FLOW_FIELDS}}
        row = daily[day]
        row['last_hour'] = moment
        for field in FLOW_FIELDS:
            row['flow_microUSD'][field] += flow[field]
        row['end_state_microUSD'] = _point(after, _receivables(actions[:index + 1]))
        row['trailing_365_day_collections_microUSD'] = sum(item['amount'] for item in collections if moment - YEAR_HOURS < item['hour'] <= moment)
        row['complete_365_day_history'] = moment >= YEAR_HOURS
        if action['op'] == 'event' and action['args']['action'] == 'release':
            released += 1
            if released in checkpoints:
                aggregate_values = {**accumulated, 'cash': expected_cash, 'profit': expected_profit}
                exact_values = {field: after[field] for field in aggregate_values}
                differences = {field: aggregate_values[field] - exact_values[field] for field in aggregate_values}
                overlapping.append({'collected_deliveries': released, 'native_action_index': index,
                                    'hour': moment, 'aggregate_minus_exact_microUSD': differences,
                                    'max_absolute_deviation_microUSD': max(abs(v) for v in differences.values()),
                                    'exact_state_microUSD': _point(after, _receivables(actions[:index + 1]))})
        previous, last_time = after, moment
    if previous != tape['summary']:
        raise ValueError('NATIVE_FINAL_SUMMARY_MISMATCH')
    if sum(row['flow_microUSD']['collections'] for row in daily.values()) != previous['collections'] - initial['collections']:
        raise ValueError('DAILY_COLLECTION_AGGREGATION_MISMATCH')
    return {'schema': 'agi-alpha/connected014-native-aggregation/v1',
            'scope': 'EXACT_RECORD_AGGREGATION_NOT_FORWARD_PROJECTION',
            'native_actions_sha256': tape['actions_sha256'],
            'clock_unit': 'integer_hours_using_native_day_field',
            'opening_seed_microUSD': opening,
            'collected_deliveries': released,
            'days': [daily[key] for key in sorted(daily)],
            'overlap_checks': overlapping,
            'requested_overlap_delivery_counts': list(checkpoints),
            'unreached_overlap_delivery_counts': [n for n in checkpoints if n > released],
            'max_overlap_deviation_microUSD': max((x['max_absolute_deviation_microUSD'] for x in overlapping), default=0),
            'end_state_microUSD': _point(previous, tape['receivables']),
            'collections': collections,
            'last_hour': last_time,
            'qualification_limit': 'Native event arithmetic is checked at each action. Overlap checks validate record aggregation only; they do not qualify future buyer behavior, unexecuted artifacts, larger-scale unit costs or a forecast model.'}


def trailing_profit(tape, *, operating_end_hour, operating_complete, aggregation=None):
    """Exact one-account observed profit, never a projection or funding authority.

    A completed operating horizon closes at its exclusive configured endpoint.
    Settlement-drain actions at/after that endpoint remain on the native account
    but do not silently lengthen the operating horizon or enter this window.
    Native validity/financial audit is a caller prerequisite; arithmetic/hash
    checks here are an additional reconciliation, not a substitute audit.
    """
    end = _integer(operating_end_hour, 'operating_end_hour')
    if end <= 0 or type(operating_complete) is not bool:
        raise ValueError('POSITIVE_OPERATING_HORIZON_AND_COMPLETION_REQUIRED')
    if tape.get('actions_sha256') != _digest(tape.get('actions')):
        raise ValueError('NATIVE_ACTION_HASH_MISMATCH')
    aggregation = aggregate_native(tape) if aggregation is None else aggregation
    if aggregation['native_actions_sha256'] != tape['actions_sha256']:
        raise ValueError('AGGREGATION_ACCOUNT_BINDING_MISMATCH')
    if not operating_complete:
        end = min(end, aggregation['last_hour'] + 1)
    start = max(0, end - YEAR_HOURS)
    fields = ('revenue', 'recoveryIncome', 'expenses')
    flows = {k: 0 for k in fields}
    initial = tape['actions'][0]['before']
    before_start = {k: initial[k] for k in fields}
    before_end = dict(before_start)
    endpoint_summary = dict(initial)
    if any(initial[k] != 0 for k in fields) or any(a['day'] < 0 for a in tape['actions']):
        raise ValueError('OPENING_ORIGIN_HISTORY_REQUIRED')
    included = 0
    for action in tape['actions']:
        moment = action['day']
        if moment < start:
            before_start = {k: action['after'][k] for k in fields}
        if moment < end:
            before_end = {k: action['after'][k] for k in fields}
            endpoint_summary = dict(action['after'])
        if start <= moment < end:
            included += 1
            for k in fields:
                flows[k] += action['after'][k] - action['before'][k]
    prefix = {k: before_end[k] - before_start[k] for k in fields}
    if flows != prefix:
        raise ValueError('ROLLING_PROFIT_EVENT_PREFIX_MISMATCH')
    profit = flows['revenue'] + flows['recoveryIncome'] - flows['expenses']
    prefix_profit = ((before_end['revenue'] + before_end['recoveryIncome'] - before_end['expenses'])
                    - (before_start['revenue'] + before_start['recoveryIncome'] - before_start['expenses']))
    if profit != prefix_profit:
        raise ValueError('ROLLING_PROFIT_PREFIX_IDENTITY_MISMATCH')
    qualified = operating_complete and end >= YEAR_HOURS
    return {
        'schema': 'agi-alpha/native-trailing-profit/v1',
        'scope': 'ONE_ACCOUNT_EXACT_MODELED_ACCRUAL_PROFIT_NOT_FORWARD_PROJECTION',
        'native_actions_sha256': tape['actions_sha256'],
        'interval': {'start_hour_inclusive': start, 'end_hour_exclusive': end,
                     'clock': 'native integer hours from opening',
                     'boundary': '[start,end); all same-hour actions included or excluded together'},
        'operating_complete': operating_complete,
        'complete_365_day_operating_history': qualified,
        'qualification': 'FULL_OPERATING_YEAR' if qualified else 'INSUFFICIENT_OPERATING_HORIZON',
        'trailing_365_day_profit_microUSD': profit if qualified else None,
        'observed_window_profit_microUSD': profit,
        'observed_window_flows_microUSD': flows,
        'prefix_difference_microUSD': prefix,
        'prefix_before_start_microUSD': before_start,
        'prefix_before_end_microUSD': before_end,
        'native_endpoint_summary': endpoint_summary,
        'obligation_scope': 'Endpoint native summary preserved, not a new reserve-coverage or complete-cost qualification.',
        'event_prefix_max_deviation_microUSD': max(abs(flows[k] - prefix[k]) for k in fields),
        'included_native_actions': included,
        'settlement_drain_actions_excluded': sum(a['day'] >= end for a in tape['actions']),
        'accounting_basis': 'Recognized revenue plus recovery income minus incurred expenses; signed revisions retained. Seed and principal reserve releases are not profit. Payables remain incurred expenses even when unpaid. Taxes enter only when recorded as native expense; no added hypothetical tax/depreciation.',
        'limits': ['Requires independent native and operating audits of the source result.',
                   'Existing modeled cost coverage and unknown host/model billing are unchanged.',
                   'No annualization, pooled enterprises, forward inference, or spending authority.',
                   'Post-operating settlement drain remains on the account but is excluded from this operating-window measure.']}


def _milestones(tape, aggregation, epoch):
    records = []
    for dollars in TARGETS_USD:
        threshold = dollars * MICRO
        revenue_crossing = qualified_crossing = None
        for item in aggregation['collections']:
            hour = item['hour']
            amount = sum(row['amount'] for row in aggregation['collections'] if hour - YEAR_HOURS < row['hour'] <= hour and row['action_index'] <= item['action_index'])
            if amount < threshold:
                continue
            index = item['action_index']
            summary = tape['actions'][index]['after']
            record = {'hour': hour, 'calendar_utc': _calendar(epoch, hour),
                      'trailing_365_day_collections_microUSD': amount,
                      'complete_365_day_history': hour >= YEAR_HOURS,
                      'state_microUSD': _point(summary, _receivables(tape['actions'][:index + 1]))}
            if revenue_crossing is None:
                revenue_crossing = record
            if qualified_crossing is None and summary['profit'] > 0 and _covered(summary):
                qualified_crossing = record
        records.append({'target_usd': dollars, 'target_microUSD': threshold,
                        'revenue_attainment': revenue_crossing,
                        'profitable_obligation_covered_attainment': qualified_crossing,
                        'status': 'REACHED' if revenue_crossing else 'NOT_REACHED_WITHIN_EXECUTED_HORIZON',
                        'subsequent_terminal_obligation_covered': _covered(tape['summary']),
                        'subsequent_terminal_profit_microUSD': tape['summary']['profit']})
    return records


def _cohorts(result):
    orders = result.get('orders', [])
    released = {row['id'] for row in result['owned_account']['ledger']['orders'] if row['state'] == 'released'}
    collected = sorted((row for row in orders if row.get('collection_time') is not None and row['id'] in released),
                       key=lambda row: (row['collection_time'], row['id']))
    customers = defaultdict(list)
    for row in collected:
        customers[row['customer_id']].append(row)
    first = [rows[0] for rows in customers.values()]
    repeat = [row for rows in customers.values() for row in rows[1:]]
    investments = result.get('investments', [])
    channel_invoices = {row['id']: row['cost'] for row in investments if row.get('kind') in {'acquisition', 'channel', 'channel_renewal'}}
    for row in result.get('costs', []):
        if row.get('category') != 'acquisition_contract':
            continue
        if row['id'] in channel_invoices and channel_invoices[row['id']] != row['amount']:
            raise ValueError('ACQUISITION_INVOICE_ALLOCATION_MISMATCH')
        channel_invoices[row['id']] = row['amount']
    paid_channel_cost = sum(channel_invoices.values())
    exposure_categories = {'exposure', 'qualification', 'acquisition', 'outreach',
                           'outreach_including_failed_and_unused_slots', 'qualification_including_lost_offers'}
    exposure_cost = sum(row['amount'] for row in result.get('costs', []) if row.get('category') in exposure_categories and row['id'] not in channel_invoices)
    channel_buyers = {row['customer_id'] for row in collected if row.get('acquisition_source_plan_id')}
    attribution = []
    for investment in investments:
        source = investment.get('plan_id') or (investment.get('funding_receipt') or {}).get('plan_id')
        field = 'capacity_source_plan_id' if investment.get('kind') == 'capacity' else 'acquisition_source_plan_id'
        linked = [row for row in orders if source and row.get(field) == source]
        used = [row for row in collected if source and row.get(field) == source]
        receipts = sum(row['price'] for row in used)
        cost = sum(row['complete_cost'] for row in linked)
        flows = [(investment.get('purchased_time', 0), 0, investment['id'], -investment['cost'])]
        flows += [(row.get('qualified_time', 0), 0, row['id'], -row['complete_cost']) for row in linked]
        flows += [(row['collection_time'], 1, row['id'], row['price']) for row in used]
        cumulative = 0
        payback = None
        for moment, kind, ident, amount in sorted(flows):
            cumulative += amount
            if kind == 1 and payback is None and cumulative >= 0:
                payback = moment
        attribution.append({'investment_id': investment['id'], 'kind': investment['kind'], 'plan_id': source,
                            'cost_microUSD': investment['cost'], 'subsequent_collected_order_ids': [row['id'] for row in used],
                            'all_linked_attempt_order_ids': [row['id'] for row in linked],
                            'attributed_collections_microUSD': receipts, 'attributed_direct_complete_cost_microUSD': cost,
                            'attributed_scoped_contribution_microUSD': receipts - cost - investment['cost'],
                            'attributed_payback_hour': payback,
                            'attributed_terminal_contribution_nonnegative': receipts - cost - investment['cost'] >= 0,
                            'scope': 'Source-linked utilization and direct cash contribution, including failed/refunded/pending attempts. Payback charges prepaid resources at qualification, not collection. Shared outreach, qualification, setup, maintenance and taxes remain in the complete enterprise allocation, so this is not full enterprise payback. Non-additive across capacity/channel investments serving the same order; causal increment requires matched control.'})
    contribution = lambda rows: sum(row['price'] - row['complete_cost'] for row in rows)
    native = result['owned_account']['ledger']['summary']
    resources = sum(row['complete_cost'] for row in orders)
    shared = native['expenses'] - resources
    if shared < 0:
        raise ValueError('ORDER_RESOURCES_EXCEED_COMPLETE_NATIVE_ENTERPRISE_COST')
    first_ids = {row['id'] for row in first}
    repeat_ids = {row['id'] for row in repeat}
    allocation = {name: {'orders': 0, 'collections_microUSD': 0, 'direct_resources_microUSD': 0, 'shared_enterprise_cost_microUSD': 0}
                  for name in ('first_collected', 'repeat_collected', 'noncollected', 'no_order')}
    quotient, remainder = divmod(shared, len(orders)) if orders else (0, 0)
    for index, row in enumerate(sorted(orders, key=lambda item: item['id'])):
        cohort = 'first_collected' if row['id'] in first_ids else 'repeat_collected' if row['id'] in repeat_ids else 'noncollected'
        target = allocation[cohort]
        target['orders'] += 1
        target['collections_microUSD'] += row['price'] if row['id'] in first_ids | repeat_ids else 0
        target['direct_resources_microUSD'] += row['complete_cost']
        target['shared_enterprise_cost_microUSD'] += quotient + (index < remainder)
    if not orders:
        allocation['no_order']['shared_enterprise_cost_microUSD'] = shared
    for row in allocation.values():
        row['allocated_complete_cost_microUSD'] = row['direct_resources_microUSD'] + row['shared_enterprise_cost_microUSD']
        row['allocated_collected_contribution_microUSD'] = row['collections_microUSD'] - row['allocated_complete_cost_microUSD']
    return {'paying_customers': len(customers), 'repeat_paying_customers': sum(len(rows) > 1 for rows in customers.values()),
            'first_sale_direct_contribution_microUSD': contribution(first),
            'repeat_direct_contribution_microUSD': contribution(repeat),
            'all_paid_channel_and_exposure_cost_microUSD': paid_channel_cost + exposure_cost,
            'source_linked_paying_channel_customers': len(channel_buyers),
            'acquisition_cost_per_source_linked_paying_customer_microUSD': None if not channel_buyers else (paid_channel_cost + exposure_cost) / len(channel_buyers),
            'acquisition_denominator_scope': 'Distinct collected customers linked to a paid channel. Includes all registered channel and exposure costs; this is a whole-run ratio, not a causal counterfactual.',
            'whole_enterprise_cost_allocation': {
                'cohorts': allocation,
                'native_complete_cost_microUSD': native['expenses'],
                'allocated_complete_cost_microUSD': sum(row['allocated_complete_cost_microUSD'] for row in allocation.values()),
                'shared_enterprise_cost_microUSD': shared,
                'reported_resource_cost_rows_microUSD': sum(row['amount'] for row in result.get('costs', [])),
                'allocation_scope': 'All order resources, including failed/refunded/pending work, assigned once. Remaining native costs, including one shared development/setup invoice, acquisition, capacity, maintenance and taxes, are allocated equally per admitted order with deterministic integer remainder. Attribution/payback tables are separate non-additive direct diagnostics; they do not add expenses or grant revenue.'},
            'investment_attribution': attribution}


def analyze(result):
    record = result['owned_account']
    tape = record['ledger']
    aggregation = aggregate_native(tape)
    config = result.get('config', {})
    epoch = config.get('epoch_utc', '2026-11-01T00:00:00Z')
    last = aggregation['last_hour']
    trailing = sum(row['amount'] for row in aggregation['collections'] if last - YEAR_HOURS < row['hour'] <= last)
    totals = tape['summary']
    max_outstanding = max(action['after']['custodyReserve'] + action['after']['tailReserve'] + action['after']['workingCapital'] for action in tape['actions'])
    max_precollection_cost = 0
    for action in tape['actions']:
        if action['after']['collections']:
            break
        max_precollection_cost = max(max_precollection_cost, action['after']['expensePaid'])
    return {'schema': 'agi-alpha/connected014-growth-bridge/v1', 'scope': 'SIMULATED_EXACT_NATIVE_RECORDS',
            'seed': result.get('seed'), 'arm': result.get('arm'),
            'config_sha256': _digest(config), 'native_actions_sha256': tape['actions_sha256'],
            'calendar_epoch_utc': epoch, 'terminal_calendar_utc': _calendar(epoch, last),
            'executed_hours': last,
            'trailing_profit': trailing_profit(tape, operating_end_hour=config['horizon_days'] * HOURS_PER_DAY, operating_complete=result.get('complete', False), aggregation=aggregation),
            'trailing_365_day_collections_microUSD': trailing,
            'complete_365_day_history': last >= YEAR_HOURS,
            'annualized_collections_run_rate_microUSD': None if last == 0 else round(totals['collections'] * YEAR_HOURS / last),
            'annualization_scope': 'Whole-executed-horizon average annualized only; not a trailing-year milestone or prediction.',
            'milestones': _milestones(tape, aggregation, epoch),
            'aggregation': aggregation,
            'cohorts': _cohorts(result),
            'seed_capital_microUSD': tape['config']['opening'],
            'cash_paid_before_first_collection_microUSD': max_precollection_cost,
            'peak_known_protected_balances_microUSD': max_outstanding,
            'terminal_state_microUSD': _point(totals, tape['receivables']),
            'historical_billion_models_bridge_status': 'UNBRIDGED_NATIVE_SCALE',
            'growth_projection_status': 'NO_UNEXECUTED_LARGE_SCALE_DELIVERIES_OR_CUSTOMERS_ADDED',
            'limits': ['Exact aggregation is not a forward market-model qualification.',
                       'Finite source inventory, audience, budget and channel contracts remain binding.',
                       'No native earned balance is copied into the historical scale studies.',
                       'Native permanent tail obligations are not replaced with historical expiring percentage reserves.',
                       'Host inference billing unavailable; costs remain disclosed modeled envelopes, not measured provider receipts.']}


def compare(results, baseline='baseline', candidate='growth'):
    """Compare equal-capital exact businesses without pooling their cash."""
    indexed = {}
    for result in results:
        key = (result.get('seed'), result.get('world', result.get('case', 'central')), result.get('config', {}).get('customer_pool'))
        arm = result['arm']
        if arm in indexed.setdefault(key, {}):
            raise ValueError('DUPLICATE_MATCHED_BUSINESS_IDENTITY')
        indexed[key][arm] = result
    pairs = []
    for key, arms in sorted(indexed.items(), key=lambda item: str(item[0])):
        if baseline not in arms or candidate not in arms:
            continue
        old, new = arms[baseline], arms[candidate]
        old_tape, new_tape = old['owned_account']['ledger'], new['owned_account']['ledger']
        if old_tape['config']['opening'] != new_tape['config']['opening']:
            raise ValueError('EQUAL_STARTING_CAPITAL_REQUIRED')
        before, after = old_tape['summary'], new_tape['summary']
        pairs.append({'identity': list(key), 'baseline_arm': baseline, 'candidate_arm': candidate,
                      'opening_microUSD': old_tape['config']['opening'],
                      'collected_delivery_delta': sum(row['state'] == 'released' for row in new_tape['orders']) - sum(row['state'] == 'released' for row in old_tape['orders']),
                      'collections_delta_microUSD': after['collections'] - before['collections'],
                      'profit_delta_microUSD': after['profit'] - before['profit'],
                      'unrestricted_earned_delta_microUSD': after['unrestrictedEarned'] - before['unrestrictedEarned'],
                      'baseline_obligation_covered': _covered(before), 'candidate_obligation_covered': _covered(after)})
    return {'schema': 'agi-alpha/connected014-matched-growth/v1', 'pairs': pairs,
            'scope': 'Exact separate-business paired outcomes; no accounts pooled and no universal market probability inferred.'}


def frontier(results):
    """Retain every executed economic region, including losses and nonreach."""
    groups = defaultdict(list)
    for result in results:
        config = result.get('config', {})
        case = result.get('world', result.get('case', 'central'))
        if not isinstance(case, str):
            case = _digest(case)
        key = (case, result.get('arm'), config.get('customer_pool'), result['owned_account']['ledger']['config']['opening'])
        groups[key].append(result)
    rows = []
    for key, worlds in sorted(groups.items(), key=lambda item: str(item[0])):
        summaries = [world['owned_account']['ledger']['summary'] for world in worlds]
        paired_go = [summary['profit'] > 0 and summary['unrestrictedEarned'] > 0 and _covered(summary) for summary in summaries]
        profit = [summary['profit'] for summary in summaries]
        jobs = [sum(row['state'] == 'released' for row in world['owned_account']['ledger']['orders']) for world in worlds]
        rows.append({'case': key[0], 'arm': key[1], 'customer_pool': key[2], 'opening_microUSD': key[3],
                     'businesses': len(worlds), 'positive_profit_available_earnings_and_covered': sum(paired_go),
                     'covered_businesses': sum(_covered(summary) for summary in summaries),
                     'loss_businesses': sum(summary['profit'] <= 0 for summary in summaries),
                     'profit_range_microUSD': [min(profit), max(profit)],
                     'collected_delivery_range': [min(jobs), max(jobs)],
                     'collections_range_microUSD': [min(summary['collections'] for summary in summaries), max(summary['collections'] for summary in summaries)],
                     'seeds': [world.get('seed') for world in worlds],
                     'terminal_stops': [world.get('stop') for world in worlds]})
    return {'schema': 'agi-alpha/connected014-executed-frontier/v1', 'regions': rows,
            'scope': 'Finite executed design regions, not calibrated market probabilities or a universal viability boundary.',
            'commercial_completion_limit': 'Positive profit/available earnings and covered obligations are necessary financial conditions. Useful acceptance, customer breadth, repeat delivery and earned-funded investment require the independent operating completion verdict.'}
