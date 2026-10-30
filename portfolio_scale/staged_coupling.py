"""Opt-in finite public-signal investment game; no execution or cash authority."""
from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

from .transformational import digest, fields, read_json

SCHEMA = 'alpha-staged-coupling/v1'
MONEY_LIMIT = 10**24


def number(value, low=0, high=MONEY_LIMIT):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('BOUNDED_INTEGER_REQUIRED')
    return value


def name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        raise ValueError('BOUNDED_IDENTIFIER_REQUIRED')
    return value


def validate(request):
    fields(request, {'schema', 'scope', 'currency', 'funding', 'state_weights',
                     'portfolios', 'probes', 'max_loss', 'max_evaluations'})
    if (request['schema'], request['scope'], request['currency']) != (
            SCHEMA, 'SIMULATED_PLANNING_ONLY', 'simulated-microUSD'):
        raise ValueError('EXPLICIT_SIMULATED_PLANNING_SCOPE_REQUIRED')
    fields(request['funding'], {'source', 'available', 'unrestrictedEarned', 'authorized_allocation'})
    name(request['funding']['source'])
    for key in ('available', 'unrestrictedEarned', 'authorized_allocation'):
        if request['funding'][key] is not None:
            number(request['funding'][key])
    weights = request['state_weights']
    if not isinstance(weights, dict) or not 1 <= len(weights) <= 64:
        raise ValueError('FINITE_STATE_MODEL_REQUIRED')
    for key, weight in weights.items():
        name(key); number(weight, 0, 10000)
    if sum(weights.values()) != 10000:
        raise ValueError('PRIOR_MUST_SUM_TO_10000')
    number(request['max_loss'])
    number(request['max_evaluations'], 1, 1_000_000)
    portfolios, probes = request['portfolios'], request['probes']
    if not isinstance(portfolios, list) or not 1 <= len(portfolios) <= 128:
        raise ValueError('FINITE_PORTFOLIOS_REQUIRED')
    if not isinstance(probes, list) or len(probes) > 32:
        raise ValueError('FINITE_PROBES_REQUIRED')
    ids, keep, response_terms = set(), 0, 0
    for action in portfolios:
        fields(action, {'id', 'lane', 'cost', 'authorized', 'evidence', 'responses'})
        ident = name(action['id'])
        if ident in ids:
            raise ValueError('DUPLICATE_PORTFOLIO')
        ids.add(ident)
        if action['lane'] not in {'retain', 'commerce', 'capability', 'combined'}:
            raise ValueError('UNKNOWN_PORTFOLIO_LANE')
        number(action['cost']); name(action['evidence'])
        if type(action['authorized']) is not bool:
            raise ValueError('EXPLICIT_AUTHORIZATION_REQUIRED')
        if action['responses'] is None:
            if action['lane'] == 'retain':
                raise ValueError('EXPLICIT_ZERO_CASH_OPTION_REQUIRED')
            continue
        if not isinstance(action['responses'], dict) or not 1 <= len(action['responses']) <= 32:
            raise ValueError('FINITE_RESPONSE_SET_REQUIRED')
        for response, outcomes in action['responses'].items():
            name(response); fields(outcomes, set(weights)); response_terms += len(weights)
            for outcome in outcomes.values():
                fields(outcome, {'net_receipts', 'rival_value', 'future_cash_required'})
                number(outcome['net_receipts'], -MONEY_LIMIT)
                number(outcome['rival_value'], -MONEY_LIMIT)
                number(outcome['future_cash_required'])
                if outcome['future_cash_required'] < max(0, -outcome['net_receipts']):
                    raise ValueError('LATER_NET_LIABILITY_MUST_BE_COVERED')
        if action['lane'] == 'retain':
            keep += 1
            if action['cost'] or not action['authorized'] or any(
                    o['net_receipts'] or o['future_cash_required']
                    for values in action['responses'].values() for o in values.values()):
                raise ValueError('EXPLICIT_ZERO_CASH_OPTION_REQUIRED')
    if keep != 1:
        raise ValueError('EXACTLY_ONE_RETAIN_CASH_OPTION_REQUIRED')
    probe_ids, signals = set(), 1
    for probe in probes:
        fields(probe, {'id', 'cost', 'authorized', 'evidence', 'discount_bps', 'likelihoods'})
        ident = name(probe['id'])
        if ident in probe_ids:
            raise ValueError('DUPLICATE_PROBE')
        probe_ids.add(ident)
        number(probe['cost']); number(probe['discount_bps'], 0, 10000); name(probe['evidence'])
        if type(probe['authorized']) is not bool:
            raise ValueError('EXPLICIT_AUTHORIZATION_REQUIRED')
        if not isinstance(probe['likelihoods'], dict) or not 1 <= len(probe['likelihoods']) <= 32:
            raise ValueError('FINITE_PUBLIC_SIGNAL_MODEL_REQUIRED')
        for signal, row in probe['likelihoods'].items():
            name(signal); fields(row, set(weights)); signals += 1
            for weight in row.values():
                number(weight, 0, 10000)
        for state in weights:
            if sum(row[state] for row in probe['likelihoods'].values()) != 10000:
                raise ValueError('LIKELIHOODS_MUST_SUM_TO_10000_PER_STATE')
    if response_terms * signals > request['max_evaluations']:
        raise ValueError('DECLARED_EVALUATION_BUDGET_EXCEEDED')
    return response_terms * signals


def _options(request, belief, budget, probe_cost):
    """Opponent acts on the same posterior, never on the true hidden state."""
    support = [state for state, prob in belief.items() if prob]
    result = []
    for action in request['portfolios']:
        if not action['authorized'] or action['responses'] is None:
            continue
        responses = action['responses']
        reserve = max(o[s]['future_cash_required'] for o in responses.values() for s in support)
        required = action['cost'] + reserve
        if required > budget:
            continue
        if min(o[s]['net_receipts'] - action['cost'] - probe_cost
               for o in responses.values() for s in support) < -request['max_loss']:
            continue
        rival_values = {r: sum(belief[s] * values[s]['rival_value'] for s in support)
                        for r, values in responses.items()}
        best = max(rival_values.values())
        best_responses = sorted(r for r in responses if rival_values[r] == best)
        seller_values = {r: sum(belief[s] * responses[r][s]['net_receipts'] for s in support)
                            - action['cost'] for r in best_responses}
        selected = min(best_responses, key=lambda r: (seller_values[r], r))
        result.append({'portfolio': action['id'], 'lane': action['lane'], 'cost': action['cost'],
                       'required_funds': required, 'expected_net': seller_values[selected],
                       'rival_response': selected, 'rival_best_responses': best_responses,
                       'rival_expected_value': best,
                       'worst_net_cash': min(o[s]['net_receipts'] - action['cost'] - probe_cost
                                             for o in responses.values() for s in support)})
    return sorted(result, key=lambda row: (-row['expected_net'], row['required_funds'], row['portfolio']))


def _serialize(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, list):
        return [_serialize(x) for x in value]
    if isinstance(value, dict):
        return {key: _serialize(x) for key, x in value.items()}
    return value


def choose(request):
    """Exact backward induction for one optional public probe, then pure commitment.

    Finite menus, common prior/public signal, rival observing the chosen portfolio,
    risk-neutral expected cash objective, conservative best-response tie breaking.
    This is not a general Nash solver or a real-market/long-horizon guarantee.
    """
    work_bound = validate(request)
    funding = request['funding']
    output = {'schema': SCHEMA, 'request_sha256': digest(request),
              'scope': 'EXACT_FINITE_PUBLIC_SIGNAL_STACKELBERG_DECISION',
              'execution_authorized': False, 'funding_authenticated': False,
              'commercial_success': 'NOT_EVALUATED', 'capability_compounding': 'NOT_EVALUATED',
              'unresolved_portfolios': [a['id'] for a in request['portfolios'] if a['responses'] is None],
              'evaluation_term_upper_bound': work_bound,
              'information_rule': 'Prior or public signal only; no hidden-state-conditioned decision',
              'tie_rule': 'Worst seller outcome among rival best responses',
              'safety_rule': 'Peak later cash requirements and max loss covered across all modeled responses'}
    keys = ('available', 'unrestrictedEarned', 'authorized_allocation')
    if any(funding[key] is None for key in keys):
        return {**output, 'decision': 'UNKNOWN_FUNDING', 'selected': None}
    budget = min(funding[key] for key in keys)
    prior = {s: Fraction(w, 10000) for s, w in request['state_weights'].items()}
    now_options = _options(request, prior, budget, 0)
    best_now = now_options[0]
    direct = {'route': 'commit_now', 'probe': None, 'expected_net': best_now['expected_net'],
              'upfront_cost': best_now['cost'], 'peak_required_funds': best_now['required_funds'],
              'continuations': {'prior': {'probability': Fraction(1), 'posterior': prior, **best_now}}}
    routes = [direct]
    fixed_controls = [dict(route='commit_now', probe=None, portfolio=best_now['portfolio'],
                           expected_net=best_now['expected_net'])]
    for probe in request['probes']:
        cost = probe['cost']
        if not probe['authorized'] or cost > budget or cost > request['max_loss']:
            continue
        continuations, option_rows = {}, {}
        expected = Fraction(-cost)
        discount = Fraction(probe['discount_bps'], 10000)
        for signal, likelihood in probe['likelihoods'].items():
            joint = {s: prior[s] * Fraction(likelihood[s], 10000) for s in prior}
            probability = sum(joint.values())
            if not probability:
                continue
            posterior = {s: joint[s] / probability for s in joint}
            opts = _options(request, posterior, budget - cost, cost)
            best = opts[0]
            option_rows[signal] = {row['portfolio']: row for row in opts}
            continuations[signal] = {'probability': probability, 'posterior': posterior, **best}
            expected += probability * discount * best['expected_net']
        for ident in set.intersection(*(set(rows) for rows in option_rows.values())):
            val = Fraction(-cost) + discount * sum(
                continuations[signal]['probability'] * rows[ident]['expected_net']
                for signal, rows in option_rows.items())
            fixed_controls.append({'route': 'probe_with_fixed_followup', 'probe': probe['id'],
                                   'portfolio': ident, 'expected_net': val})
        routes.append({'route': 'probe_then_choose', 'probe': probe['id'], 'expected_net': expected,
                       'upfront_cost': cost,
                       'peak_required_funds': cost + max(row['required_funds'] for row in continuations.values()),
                       'continuations': continuations})
    selected = min(routes, key=lambda r: (-r['expected_net'], r['peak_required_funds'], r['probe'] or ''))
    fixed = min(fixed_controls, key=lambda r: (-r['expected_net'], r['probe'] or '', r['portfolio']))
    output.update(decision=selected['route'], budget=budget, selected=selected, alternatives=routes,
                  best_nonadaptive_control=fixed,
                  advantage_over_nonadaptive=selected['expected_net']-fixed['expected_net'],
                  modeled_policy_optimization_gap='0',
                  limitation='Zero gap only within this enumerated model and pure observed-action timing; payoff and likelihood evidence is supplied, not validated.')
    return _serialize(output)


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = choose(read_json(args.input))
        if args.output.is_symlink():
            raise ValueError('OUTPUT_SYMLINK_REFUSED')
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')
    print('Computed a conditional strategy; no investment executed or authorized.')


if __name__ == '__main__':
    main()
