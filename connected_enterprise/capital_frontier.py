"""Read-only native capital diagnostics; never a ledger or release authority."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

NUMBERS = ('cash', 'collections', 'recoveryIncome', 'revenue', 'expenses', 'expensePaid',
           'profit', 'payables', 'custodyReserve', 'tailReserve', 'workingCapital',
           'reservedInvestment', 'available', 'unrestrictedEarned',
           'equityProtectionBacking', 'earnedProtectionBacking',
           'netEarnedAfterIncurredObligations')


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('INTEGER_REQUIRED:' + name)
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _balances(opening, state, investment_paid, tail):
    protection = state['custodyReserve'] + tail + state['workingCapital']
    raw = state['cash'] - state['payables'] - protection
    net = state['collections'] - state['expensePaid'] - state['payables'] - investment_paid
    equity = min(protection, max(0, opening + state['recoveryIncome'] + min(0, net)))
    earned_backing = protection - equity
    reserved = state['reservedInvestment']
    available = max(0, max(0, raw) - reserved)
    earned = max(0, min(max(0, raw), max(0, net) - earned_backing) - reserved)
    return {'available': available,
            'unrestrictedEarned': 0 if state['investmentStopped'] else earned,
            'equityProtectionBacking': equity, 'earnedProtectionBacking': earned_backing,
            'netEarnedAfterIncurredObligations': net}


def diagnose(opening, state, *, investment_paid=0):
    """Check the cash bridge against a supplied native snapshot, without authenticating it."""
    _integer(opening, 'opening'); _integer(investment_paid, 'investment_paid')
    if not isinstance(state, dict) or type(state.get('investmentStopped')) is not bool:
        raise ValueError('NATIVE_STATE_REQUIRED')
    for key in NUMBERS:
        if key not in state or type(state[key]) is not int:
            raise ValueError('INTEGER_NATIVE_FIELD_REQUIRED:' + key)
        if key not in ('profit', 'collections', 'revenue', 'netEarnedAfterIncurredObligations') and state[key] < 0:
            raise ValueError('NEGATIVE_NATIVE_FIELD:' + key)
    if state['cash'] != opening + state['collections'] + state['recoveryIncome'] - state['expensePaid'] - investment_paid:
        raise ValueError('CASH_IDENTITY_MISMATCH')
    if state['profit'] != state['revenue'] + state['recoveryIncome'] - state['expenses']:
        raise ValueError('PROFIT_IDENTITY_MISMATCH')
    computed = _balances(opening, state, investment_paid, state['tailReserve'])
    if any(state[k] != value for k, value in computed.items()):
        raise ValueError('NATIVE_FUNDING_IDENTITY_MISMATCH')
    tail_less_collections = state['tailReserve'] - state['collections']
    raw = (opening + state['recoveryIncome'] - state['expensePaid'] - investment_paid
           - state['payables'] - state['custodyReserve'] - state['workingCapital']
           - tail_less_collections - state['reservedInvestment'])
    if max(0, raw) != computed['available']:
        raise ValueError('CAPITAL_BRIDGE_MISMATCH')
    return {'schema': 'agi-alpha/capital-frontier/v1', 'scope': 'READ_ONLY_NATIVE_ARITHMETIC',
            'currency': 'simulated-microUSD', 'state_sha256': _digest(state), 'opening_microUSD': opening,
            'profit_microUSD': state['profit'], **computed,
            'unclamped_liquidity_headroom_microUSD': raw,
            'tail_minus_collections_microUSD': tail_less_collections,
            'native_authentication_performed': False, 'execution_authorized': False,
            'claim': 'Snapshot identities only; native replay, source binding and action-time reservation remain required.'}


def required_tail_release(opening, state, commitment, *, added_cost=0, investment_paid=0):
    """Smallest hypothetical tail reduction for one earned commitment, with a paid cost.

    This is an inverse constraint, not permission to change a contract or reserves.
    Custody, working capital, existing reservations and breach stops are preserved.
    """
    diagnosis = diagnose(opening, state, investment_paid=investment_paid)
    _integer(commitment, 'commitment', 1); _integer(added_cost, 'added_cost')
    base = {'schema': 'agi-alpha/tail-release-requirement/v1',
            'scope': 'HYPOTHETICAL_CONTRACT_REQUIREMENT_NOT_AUTHORITY',
            'state_sha256': diagnosis['state_sha256'], 'commitment_microUSD': commitment,
            'added_cost_microUSD': added_cost, 'execution_authorized': False,
            'release_microUSD': None}
    if state['investmentStopped']:
        return {**base, 'status': 'BREACH_STOP_REQUIRES_SEPARATE_REQUALIFICATION'}
    if added_cost > state['available']:
        return {**base, 'status': 'ARRANGEMENT_NOT_UPFRONT_FUNDED'}
    candidate = copy.deepcopy(state)
    candidate['cash'] -= added_cost
    candidate['expensePaid'] += added_cost
    candidate['expenses'] += added_cost
    candidate['profit'] -= added_cost
    def can_fund(release):
        balances = _balances(opening, candidate, investment_paid, candidate['tailReserve'] - release)
        return balances['unrestrictedEarned'] >= commitment
    if not can_fund(candidate['tailReserve']):
        return {**base, 'status': 'TAIL_RELEASE_ALONE_INSUFFICIENT'}
    lo, hi = 0, candidate['tailReserve']
    while lo < hi:
        middle = (lo + hi) // 2
        if can_fund(middle): hi = middle
        else: lo = middle + 1
    return {**base, 'status': 'ALREADY_FINANCEABLE' if lo == 0 else 'CONTRACT_CHANGE_REQUIRED',
            'release_microUSD': lo,
            'hypothetical_funding': _balances(opening, candidate, investment_paid, candidate['tailReserve'] - lo),
            'condition': 'An independently valid, priced contract must legally and operationally extinguish this exposure. No reserve or cash was changed.'}


def settled_cost_bound(opening, working, setup, minimum_cost_per_paid_job, *, tail_fee=200_000):
    """Necessary terminal upper bound, NOT an achievable order count or growth forecast.

    Assumes all collected principal remains reserved, no recovery/new capital/tail
    expiry, costs >= the given lower bound, no outstanding custody or reservations.
    Admission collateral and timing can make the achievable count smaller.
    """
    for key, value in [('opening', opening), ('working', working), ('setup', setup), ('tail_fee', tail_fee)]:
        _integer(value, key)
    base = {'scope': 'CONDITIONAL_NECESSARY_CAPITAL_BOUND_NOT_DEMAND',
            'execution_authorized': False, 'maximum_paid_jobs_upper_bound': None,
            'hypotheses': 'Permanent full-principal reserve; no new capital, recovery or expiry; supplied positive complete-cost lower bound.'}
    if minimum_cost_per_paid_job is None:
        return {**base, 'status': 'UNKNOWN_COST_LOWER_BOUND'}
    _integer(minimum_cost_per_paid_job, 'minimum_cost_per_paid_job', 1)
    if opening < working + setup:
        return {**base, 'status': 'INITIAL_OBLIGATIONS_UNFUNDED', 'maximum_paid_jobs_upper_bound': 0}
    count = (opening - working - setup) // (minimum_cost_per_paid_job + tail_fee)
    return {**base, 'status': 'FINITE_UNDER_DECLARED_HYPOTHESES',
            'maximum_paid_jobs_upper_bound': count,
            'growth_constraint': 'Positive margins alone cannot remove this bound; sale price cancels the retained principal.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commitment-microUSD', type=int)
    parser.add_argument('--arrangement-cost-microUSD', type=int, default=0)
    args = parser.parse_args()
    try:
        from commercial.ledger import strict_json
        if not args.input.is_file() or args.input.is_symlink():
            raise ValueError('REGULAR_INPUT_REQUIRED')
        with args.input.open('rb') as stream: raw = stream.read(2_000_001)
        if len(raw) > 2_000_000: raise ValueError('INPUT_TOO_LARGE')
        data = strict_json(raw)
        if set(data) != {'scope', 'currency', 'opening', 'investment_paid', 'summary'} or data['scope'] != 'SIMULATED' or data['currency'] != 'simulated-microUSD':
            raise ValueError('EXACT_SIMULATED_INPUT_REQUIRED')
        result = diagnose(data['opening'], data['summary'], investment_paid=data['investment_paid'])
        if args.commitment_microUSD is not None:
            result['contract_requirement'] = required_tail_release(data['opening'], data['summary'], args.commitment_microUSD,
                added_cost=args.arrangement_cost_microUSD, investment_paid=data['investment_paid'])
        if args.output.is_symlink(): raise ValueError('OUTPUT_SYMLINK_REFUSED')
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')
    print('Native arithmetic checked; no execution or reserve-release authority.')


if __name__ == '__main__': main()
