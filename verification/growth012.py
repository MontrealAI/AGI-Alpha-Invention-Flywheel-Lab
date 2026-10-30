"""Independent evidence and native-money checks for the event-growth edition.

This checker does not call the operating controller or infer market validity.
Native action replay supplies financial authority. Service production is rerun
and independently checked; milestones are rebuilt from net collected events.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from commercial.ledger import audit as audit_tape, digest, load_jobs
from enterprise.services import execute_job, check_job

YEAR_HOURS = 365 * 24


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('GROWTH_AUDIT_NONNEGATIVE_INTEGER_REQUIRED')
    return value


def collected_frontier(actions, targets, horizon):
    """Rebuild first passage including nonreaching targets and late reversals."""
    if not isinstance(targets, list) or not targets or len(targets) != len(set(targets)):
        raise ValueError('GROWTH_AUDIT_UNIQUE_TARGETS_REQUIRED')
    for target in targets:
        _integer(target, 1)
    _integer(horizon)
    receipts, milestones = [], {str(target): None for target in targets}
    maximum_trailing = 0
    for action in actions:
        tick = _integer(action['day'])
        delta = action['after']['collections'] - action['before']['collections']
        if delta:
            receipts.append({'hour': tick, 'net_collected_microUSD': delta})
        trailing = sum(row['net_collected_microUSD'] for row in receipts if tick - YEAR_HOURS < row['hour'] <= tick)
        maximum_trailing = max(maximum_trailing, trailing)
        state = action['after']
        obligations_funded = state['payables'] == 0 and not state['investmentStopped']
        if state['profit'] > 0 and obligations_funded:
            for target in targets:
                if milestones[str(target)] is None and trailing >= target:
                    milestones[str(target)] = tick
    trailing_terminal = sum(row['net_collected_microUSD'] for row in receipts if horizon - YEAR_HOURS < row['hour'] <= horizon)
    return {'milestones': milestones, 'collected_events': receipts,
            'terminal_trailing365_collected_microUSD': trailing_terminal,
            'maximum_trailing365_collected_microUSD': maximum_trailing,
            'milestone_basis': 'Net collected money in the preceding 365 days; positive complete-cost native profit and no unpaid obligations or stopped investment at first passage. Unreached targets remain null.'}


def _forbidden_observation(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {'private', 'private_values', 'reservation_value', 'future_draw', 'future_shocks', 'hidden_scenario_label'}:
                raise ValueError('GROWTH_AUDIT_PRIVATE_INFORMATION_IN_OBSERVATION')
            _forbidden_observation(child)
    elif isinstance(value, list):
        for child in value:
            _forbidden_observation(child)


def audit_growth(result, *, root, manifest):
    if not isinstance(result, dict) or not isinstance(result.get('config'), dict):
        raise ValueError('GROWTH_AUDIT_RESULT_CONFIG_REQUIRED')
    config = result['config']
    ledger = result.get('ledger')
    finite_terms = None
    if isinstance(ledger, dict) and ledger.get('config', {}).get('schema') == 'agi-alpha/growth012-finite-contract/v1':
        from enterprise.contract012 import audit_contract012
        native = audit_contract012(ledger, root=root, manifest=manifest)
        finite_terms = ledger['config']['terms']
        if finite_terms['time_unit'] != 'hours' or config.get('finite_liability_hours') != finite_terms['liability_ticks']:
            raise ValueError('GROWTH_AUDIT_FINITE_TERMS_TIME_BINDING')
    else:
        native = audit_tape(ledger, root=root, manifest=manifest)
        if config.get('finite_liability_hours') is not None:
            raise ValueError('GROWTH_AUDIT_UNIMPLEMENTED_FINITE_LIABILITY_CLAIM')
    actions = ledger['actions']
    production = _integer(config['production_hours'], 1)
    settlement = _integer(config['settlement_hours'])
    horizon = _integer(config['horizon_hours'], 1)
    if actions and actions[-1]['day'] > horizon:
        raise ValueError('GROWTH_AUDIT_ACTION_AFTER_HORIZON')
    jobs = load_jobs(root, manifest)
    offers, funded, prepared, settled, matured = {}, {}, {}, {}, set()
    for action in actions:
        args, tick = action['args'], action['day']
        if action['op'] == 'offer':
            offers[args['id']] = {'job_id': args['job_id'], 'hour': tick, 'price': args['price']}
        elif action['op'] == 'mature':
            ident = args['id']
            if finite_terms is None or ident not in settled or tick < settled[ident] + finite_terms['liability_ticks']:
                raise ValueError('GROWTH_AUDIT_PREMATURE_LIABILITY_RELEASE')
            if ident in matured:
                if action['before'] != action['after']:
                    raise ValueError('GROWTH_AUDIT_DUPLICATE_MATURITY_EFFECT')
                continue
            if action['before']['tailReserve'] - action['after']['tailReserve'] != offers[ident]['price'] + 200_000:
                raise ValueError('GROWTH_AUDIT_RESERVE_RELEASE_AMOUNT')
            unchanged = ['cash', 'revenue', 'collections', 'profit', 'expenses', 'expensePaid', 'recoveryIncome', 'payables']
            if any(action['before'][key] != action['after'][key] for key in unchanged):
                raise ValueError('GROWTH_AUDIT_FINALITY_MINTED_MONEY_OR_COST')
            matured.add(ident)
        elif action['op'] == 'event':
            ident, kind = args['id'], args['action']
            if kind == 'fund':
                funded.setdefault(ident, tick)
            elif kind == 'prepare':
                if ident not in funded or tick < funded[ident] + production:
                    raise ValueError('GROWTH_AUDIT_PRODUCTION_CAUSALITY')
                prepared.setdefault(ident, {'hour': tick, 'seq': action['seq']})
            elif kind in {'release', 'late_reversal'}:
                if ident not in prepared or tick < prepared[ident]['hour'] + settlement:
                    raise ValueError('GROWTH_AUDIT_SETTLEMENT_CAUSALITY')
                if kind == 'release':
                    settled.setdefault(ident, tick)
    works = result.get('work_executions')
    if not isinstance(works, list):
        raise ValueError('GROWTH_AUDIT_ACTUAL_EXECUTION_RECORDS_REQUIRED')
    seen_jobs, seen_orders = set(), set()
    for work in works:
        if not isinstance(work, dict):
            raise ValueError('GROWTH_AUDIT_EXECUTION_RECORD_REQUIRED')
        ident, job_id, tick = work['order_id'], work['job_id'], work['time']
        if ident in seen_orders or job_id in seen_jobs or ident not in prepared or job_id not in jobs:
            raise ValueError('GROWTH_AUDIT_DUPLICATE_OR_UNPREPARED_WORK')
        if ident not in offers or offers[ident]['job_id'] != job_id or tick != prepared[ident]['hour']:
            raise ValueError('GROWTH_AUDIT_WORK_BINDING_OR_TIME')
        commitment = _integer(work['commitment_action_seq'])
        if commitment >= prepared[ident]['seq']:
            raise ValueError('GROWTH_AUDIT_COMMITMENT_AFTER_WORK')
        commitment_event = actions[commitment]
        if commitment_event['op'] != 'event' or commitment_event['args']['action'] != 'fund' or commitment_event['args']['id'] != ident:
            raise ValueError('GROWTH_AUDIT_WORK_COMMITMENT_BINDING')
        job = jobs[job_id]['job']
        receipt = work['receipt']
        if not isinstance(receipt, dict) or receipt.get('accepted') is not True or receipt.get('reexecuted') is not True or receipt.get('artifact_sha256') != job['artifact_sha256']:
            raise ValueError('GROWTH_AUDIT_EXECUTED_ACCEPTANCE_REQUIRED')
        check_job(root, manifest, job)
        repeated = execute_job(root, job)
        if repeated['accepted'] is not True or repeated['artifact_sha256'] != receipt['artifact_sha256']:
            raise ValueError('GROWTH_AUDIT_SERVICE_REEXECUTION_FAILED')
        seen_orders.add(ident)
        seen_jobs.add(job_id)
    if seen_orders != set(prepared):
        raise ValueError('GROWTH_AUDIT_NATIVE_PREPARE_WITHOUT_ACTUAL_WORK')
    decisions = result.get('decisions')
    if not isinstance(decisions, list):
        raise ValueError('GROWTH_AUDIT_DECISIONS_REQUIRED')
    prior, decision_ids = -1, set()
    for decision in decisions:
        ident, tick = decision['id'], _integer(decision['time'])
        if ident in decision_ids or tick < prior or tick > horizon:
            raise ValueError('GROWTH_AUDIT_DECISION_ID_OR_TIME')
        observation = decision['observation']
        _forbidden_observation(observation)
        if 'observation_sha256' in decision and decision['observation_sha256'] != digest(observation):
            raise ValueError('GROWTH_AUDIT_OBSERVATION_IDENTITY')
        prefix = observation.get('native_actions_through')
        if prefix is not None:
            _integer(prefix)
            if prefix > len(actions) or prefix and actions[prefix - 1]['day'] > tick or prefix < len(actions) and actions[prefix]['day'] < tick:
                raise ValueError('GROWTH_AUDIT_OBSERVATION_FUTURE_OR_STALE_PREFIX')
            state = actions[prefix - 1]['after'] if prefix else actions[0]['before'] if actions else ledger['summary']
            if observation.get('snapshot') != state:
                raise ValueError('GROWTH_AUDIT_OBSERVATION_STATE_BINDING')
        options = decision.get('feasible_actions')
        if not isinstance(options, list) or not options:
            raise ValueError('GROWTH_AUDIT_ENUMERATED_ACTIONS_REQUIRED')
        ids = [item['id'] for item in options]
        if len(ids) != len(set(ids)):
            raise ValueError('GROWTH_AUDIT_DUPLICATE_ACTION_OPTION')
        selected = decision['selected_action']
        if isinstance(selected, dict):
            selected = selected['id']
        matching = [item for item in options if item['id'] == selected]
        if len(matching) != 1 or matching[0].get('feasible') is not True:
            raise ValueError('GROWTH_AUDIT_SELECTED_ACTION_NOT_FEASIBLE')
        for option in options:
            _integer(option['cash_required'])
            _integer(option['payback_hours'])
            _integer(option['downside'])
            if option.get('feasible') is not True and (not option.get('reason') or not option.get('constraint_class')):
                raise ValueError('GROWTH_AUDIT_REJECTION_WITHOUT_EVIDENCE')
        prior = tick
        decision_ids.add(ident)
    targets = config.get('targets_collected_microUSD')
    if targets is None:
        targets = [target * 1_000_000 for target in [500, 1000, 1_000_000, 10_000_000, 100_000_000, 1_000_000_000, 10_000_000_000]]
    frontier = collected_frontier(actions, targets, horizon)
    summary = native['summary']
    return {'accepted': True, 'scope': 'CONDITIONAL_SIMULATED_EVENT_GROWTH_AUDIT',
            'native_replay_accepted': native['accepted'], 'actions_sha256': ledger['actions_sha256'],
            'manifest_sha256': digest(manifest), 'config_sha256': digest(config),
            'actual_service_executions': len(works), 'prepared_orders': len(prepared),
            'settled_orders': len(settled), 'decisions_checked': len(decisions),
            'complete_cost_profit_microUSD': summary['profit'],
            'net_collected_microUSD': summary['collections'], 'cash_microUSD': summary['cash'],
            'unrestricted_earned_microUSD': summary['unrestrictedEarned'],
            'payables_microUSD': summary['payables'], 'tail_reserve_microUSD': summary['tailReserve'],
            'finite_liability_terms': finite_terms,
            'cash_survival': all(a['after']['payables'] == 0 and not a['after']['investmentStopped'] for a in actions),
            **frontier,
            'limits': 'Independent checker implementation on shared host and native dependency. Audits finance, actual scoped synthetic delivery and recorded causality; does not certify demand calibration, global optimality, hidden implementation isolation or real revenue.'}


def reproduce_baseline_bottlenecks():
    from enterprise.scale import default_config, simulate_scale
    config = default_config()
    config.update(months=3, initial_customers=1, reachable_market_customers=1,
        initial_capacity_jobs=20, opening_cash_cents=10000000,
        setup_cost_cents=0, liquidity_floor_cents=0, fixed_monthly_cost_cents=0,
        support_per_customer_cents=0, onboarding_per_customer_cents=0,
        monthly_churn_probability=0., technical_acceptance_probability=1.,
        collection_probability=1., refund_probability=0., supplier_outage_probability=0.,
        shock_month=0, base_products_per_customer=1, extra_products_per_customer=0,
        utilization_probability=1., annual_price_compression=0., reserve_bps=0,
        payment_fee_bps=0, payment_fixed_cents=0, base_monthly_contacts=0,
        referral_contacts_per_customer=0., settlement_months=0)
    zero = simulate_scale(config, 123)
    one_config = copy.deepcopy(config)
    one_config['settlement_months'] = 1
    one = simulate_scale(one_config, 123)
    cash_config = copy.deepcopy(config)
    cash_config.update(months=1, initial_capacity_jobs=0, opening_cash_cents=20000,
        capacity_block_jobs=1, capacity_block_cost_cents=10000, attempt_cost_cents=1000)
    default_share = simulate_scale(cash_config, 123)
    full_config = copy.deepcopy(cash_config)
    full_config['capacity_budget_fraction'] = 1.
    full_share = simulate_scale(full_config, 123)
    return {'source': 'enterprise/scale.py unchanged PR19 baseline',
        'settlement': {'zero_and_one_month_financial_rows_identical': zero['monthly'] == one['monthly'],
                       'zero_month_receipts': [[m['month'], m['collected_revenue_cents']] for m in zero['monthly']],
                       'one_month_receipts': [[m['month'], m['collected_revenue_cents']] for m in one['monthly']]},
        'capacity': {'available_cash_cents': 20000, 'complete_action_cash_cents': 11000,
                     'default_fraction': default_share['monthly'][0],
                     'full_fraction': full_share['monthly'][0],
                     'default_binding_constraints': default_share['binding_constraints']},
        'scope': 'Directed deterministic policy counterexamples, not observed commercial or original protected outcomes.'}
