"""Source-bound US$100k / 60-calendar-month native commerce challenge.

Preflight is a necessary-condition diagnostic, not a simulator or a profit proof.
The first-passage observer is read-only and requires separate native audit before
its figures qualify. Existing registered enterprise remains the sole operator.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path

from .engine import default_config
from .registration import SCHEMA as REGISTRATION_SCHEMA, validate as validate_registration
from .scale import MICRO, YEAR_HOURS, _digest

OPENING = 100_000 * MICRO
TARGET = 1_000_000_000 * MICRO
MONTHS = 60
SCHEMA = 'agi-alpha/billion036-challenge/v1'


def horizon_days(epoch):
    date = datetime.fromisoformat(epoch.replace('Z', '+00:00'))
    if date.utcoffset() is None or date.utcoffset().total_seconds() != 0 or any((date.hour, date.minute, date.second, date.microsecond)):
        raise ValueError('UTC_MIDNIGHT_EPOCH_REQUIRED')
    try:
        end = date.replace(year=date.year + MONTHS // 12)
    except ValueError as exc:
        raise ValueError('SAME_CALENDAR_DAY_60_MONTH_ENDPOINT_REQUIRED') from exc
    return (end - date).days


def registered_design():
    base = default_config()
    base.update(opening=OPENING, horizon_days=horizon_days(base['epoch_utc']))
    adverse = dict(base)
    adverse.update(arrival_bps=2000, price_pressure_bps=6000, production_cost=base['production_cost'] * 3,
                   onboarding_cost=base['onboarding_cost'] * 2)
    return validate_registration({
        'schema': REGISTRATION_SCHEMA, 'label': 'billion036-100k-60months',
        'evidence_role': 'finite_authored_comparison', 'seeds': [261031036],
        'configs': {'central': base, 'low_demand_high_cost': adverse},
        'arms': ['baseline', 'growth'], 'control_arm': 'baseline', 'candidate_arm': 'growth',
        'service_cohort_seed': 14013026, 'workers': 1,
    })


def preflight(registration):
    value = validate_registration(registration)
    for cfg in value['configs'].values():
        if cfg['opening'] != OPENING or cfg['horizon_days'] != horizon_days(cfg['epoch_utc']):
            raise ValueError('EXACT_100K_AND_60_CALENDAR_MONTHS_REQUIRED')
    cases = []
    for name, cfg in sorted(value['configs'].items()):
        if 'buyer_income_policy' in cfg or 'complete_offer_policy' in cfg:
            raise ValueError('FIXED_BUYER_BOUND_UNAVAILABLE_FOR_REPLENISHED_OR_COMPLETE_MARKET')
        # Current _buyers has fixed, non-replenishing lifetime budgets:
        # int((180 + 400*draw)*MICRO*multiplier/10000); draw in [0,1).
        # A deliberately generous upper bound ignores competition and costs.
        bound = cfg['customer_pool'] * (580 * MICRO * cfg['buyer_budget_multiplier_bps'] // 10000)
        cases.append({'case': name, 'opening_microUSD_per_independent_business': cfg['opening'],
                      'operating_horizon_days': cfg['horizon_days'],
                      'lifetime_buyer_spending_upper_bound_microUSD': bound,
                      'target_trailing_profit_microUSD': TARGET,
                      'finite_buyer_budget_barrier': bound < TARGET,
                      'qualification': ('STRUCTURAL_FIXED_BUYER_BUDGET_BARRIER' if bound < TARGET
                                        else 'NO_CONCLUSION_FROM_BUYER_BUDGET_BOUND'),
                      'gap_to_target_if_no_new_demand_microUSD': max(0, TARGET - bound)})
    return {'schema': SCHEMA, 'scope': 'NECESSARY_CONDITION_FOR_THIS_CANONICAL_FIXED_BUYER_MARKET_NOT_FORECAST',
            'registration_sha256': _digest(value), 'starting_capital_microUSD': OPENING,
            'trailing_profit_target_microUSD': TARGET, 'calendar_months': MONTHS,
            'cases': cases, 'matched_businesses': len(value['seeds'])*len(value['arms'])*len(value['configs']),
            'limits': ['Does not operate buyers, collect revenue, or grant new capital.',
                       'Conservation bound assumes current finite initial buyer budgets without replenishment or outside revenue.',
                       'Lifting this bound by inventing larger buyer budgets does not establish demand, willingness to pay or profit.',
                       'A blocked region remains evidence; neither extending the horizon nor enlarging opening cash resolves fixed demand.']}


def first_passage(tape, *, operating_end_hour, operating_complete, target_microUSD=TARGET):
    """Exact signed native profit first passage over full 365-day windows.

    Native financial and service-semantic audit is mandatory at the call site.
    This pure observer is not a self-certifying audit or a forward model.
    """
    if type(operating_end_hour) is not int or operating_end_hour <= 0 or type(operating_complete) is not bool:
        raise ValueError('OPERATING_HORIZON_AND_BOOL_COMPLETION_REQUIRED')
    if type(target_microUSD) is not int or target_microUSD <= 0:
        raise ValueError('POSITIVE_INTEGER_TARGET_REQUIRED')
    if tape['config']['opening'] != OPENING:
        raise ValueError('CHALLENGE_OPENING_MUST_BE_EXACTLY_100K')
    actions = tape.get('actions')
    if not isinstance(actions, list) or not actions or tape.get('actions_sha256') != _digest(actions):
        raise ValueError('VALID_NATIVE_ACTIONS_HASH_REQUIRED')
    if actions[0]['before']['profit'] != 0:
        raise ValueError('ZERO_ORIGIN_PROFIT_HISTORY_REQUIRED')
    previous = actions[0]['before']
    deltas = defaultdict(int)
    last_time = -1
    for i, action in enumerate(actions):
        hour = action['day']
        if type(hour) is not int or hour < last_time or hour < 0 or action['seq'] != i or action['before'] != previous:
            raise ValueError('NONCAUSAL_NATIVE_PROFIT_SEQUENCE')
        before, after = action['before'], action['after']
        delta = sum(after[k]-before[k] for k in ('revenue', 'recoveryIncome')) - (after['expenses']-before['expenses'])
        if delta != after['profit']-before['profit']:
            raise ValueError('PROFIT_NOT_RECONCILED_TO_SIGNED_NATIVE_FLOWS')
        if hour < operating_end_hour:
            deltas[hour] += delta
        previous, last_time = after, hour
    if tape.get('summary') != previous:
        raise ValueError('TERMINAL_NATIVE_SUMMARY_MISMATCH')
    if not operating_complete or operating_end_hour < YEAR_HOURS:
        return {'schema': SCHEMA, 'scope': 'READ_ONLY_NATIVE_WINDOW_NOT_SELF_CERTIFYING',
                'source_actions_sha256': tape['actions_sha256'], 'status': 'INCOMPLETE_NO_ATTAINMENT_VERDICT',
                'first_attainment': None, 'trailing_365_day_profit_microUSD': None,
                'full_year_history': False, 'independent_audit_required': True}
    # Crossings can occur after same-hour activity OR when an old expense ages out.
    hours = sorted(deltas)
    ticks = {YEAR_HOURS, operating_end_hour}
    for h in hours:
        for t in (max(YEAR_HOURS, h+1), h+YEAR_HOURS+1):
            if YEAR_HOURS <= t <= operating_end_hour:
                ticks.add(t)
    end_i = start_i = total_end = total_before = 0
    first = terminal = None
    for t in sorted(ticks):
        while end_i < len(hours) and hours[end_i] < t:
            total_end += deltas[hours[end_i]]
            end_i += 1
        while start_i < len(hours) and hours[start_i] < t-YEAR_HOURS:
            total_before += deltas[hours[start_i]]
            start_i += 1
        profit = total_end-total_before
        if first is None and profit >= target_microUSD:
            first = {'operating_hour_exclusive': t, 'window_start_hour_inclusive': t-YEAR_HOURS,
                     'trailing_365_day_profit_microUSD': profit}
        if t == operating_end_hour:
            terminal = profit
    return {'schema': SCHEMA, 'scope': 'READ_ONLY_NATIVE_WINDOW_NOT_SELF_CERTIFYING',
            'source_actions_sha256': tape['actions_sha256'],
            'status': 'ATTAINED_WITH_AUDIT_PREREQUISITE' if first else 'NOT_REACHED_WITHIN_EXECUTED_HORIZON',
            'first_attainment': first, 'trailing_365_day_profit_microUSD': terminal,
            'terminal_above_target': terminal >= target_microUSD,
            'full_year_history': True, 'independent_audit_required': True,
            'accounting_basis': 'Signed accrued native revenue plus recovery income minus native incurred expenses; no annualization, seed income or reserve transfer.'}


def inspect_output(output):
    """Continue the canonical source-frozen run; qualify only completed audit results."""
    from .runner import read_freeze, tasks, audit_output
    output = Path(output).resolve()
    frozen = read_freeze(output)
    registration_path = frozen.get('registration_path')
    if registration_path is None:
        raise ValueError('REGISTERED_100K_CHALLENGE_REQUIRED')
    design = json.loads((output/'source'/registration_path).read_text())
    diagnosis = preflight(design)
    if not (output/'COMPLETE.json').exists():
        return {'preflight': diagnosis, 'status': 'CHECKPOINT_NOT_AUDITED_OR_COMPLETE',
                'next_action': 'Continue the canonical registered operation under existing permissions and actual platform limits, or redesign the fixed-demand market.'}
    audit = audit_output(output)
    if audit.get('accepted') is not True:
        raise ValueError('INDEPENDENT_CANONICAL_AUDIT_REQUIRED')
    worlds = []
    for task in tasks(frozen['protocol']):
        result = json.loads((output/'worlds'/task['id']/'RESULT.json').read_text())
        cfg = result['config']
        worlds.append({'task': task, 'native_actions_sha256': result['owned_account']['ledger']['actions_sha256'],
                       'profit_observer': first_passage(result['owned_account']['ledger'],
                            operating_end_hour=cfg['horizon_days']*24,
                            operating_complete=result['complete']),
                       'simulated_only': True})
    return {'preflight': diagnosis, 'audit': {'accepted': True, 'source_sha256': audit['source_sha256']},
            'status': 'QUALIFIED_NATIVE_COMPARISON', 'worlds': worlds,
            'limits': ['No account pooling or inferred forward market demand.', 'Host/model billing remains unmeasured.']}


def main():
    p = argparse.ArgumentParser(description='Native registered $100k / 60-month scale challenge')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('registration')
    sub.add_parser('preflight')
    s = sub.add_parser('inspect');s.add_argument('--output', required=True)
    args = p.parse_args()
    result = (registered_design() if args.command == 'registration' else
              preflight(registered_design()) if args.command == 'preflight' else
              inspect_output(args.output))
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
