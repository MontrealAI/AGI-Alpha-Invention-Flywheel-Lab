"""Finite shared-qualification discovery; no accounts, payments or field claims.

Purpose: supplier cohorts jointly obtain a qualified industrial sensor adapter.
All acceptance envelopes, costs, values, probabilities and commitment rights are
authored assumptions. A supplied certificate covers only its declared interfaces
and error limit. Conditional commitments activate together, settle on declared
days, and promise a stated refund if qualification fails. Refund exposure remains
reserved; a pledge is never treated as current cash. Costs precede settlement on
the same day. An ordinary organizer has identical information, rights and actions.

This is a read-only feasibility instrument, not another financial ledger. Use the
native JournalAccount for any later authorized simulated financial operation.
"""
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import time


@dataclass(frozen=True)
class Buyer:
    id: str
    interface: str
    maximum_error_ppm: int
    deadline_day: int
    settlement_day: int
    budget_cents: int
    accepted_value_cents: int
    adoption_cents: int
    outside_utility_cents: int
    permits_shared_qualification: bool = True


@dataclass(frozen=True)
class Qualification:
    id: str
    interfaces: tuple[str, ...]
    error_ppm: int
    duration_days: int
    start_days: tuple[int, ...]
    capacity_units: int
    # (offset day, task label, complete declared task cost in cents)
    costs: tuple[tuple[int, str, int], ...]
    assurance_threshold_cents: int


@dataclass(frozen=True)
class Cohort:
    id: str
    buyers: tuple[Buyer, ...]
    qualifications: tuple[Qualification, ...]
    fee_menu_cents: tuple[int, ...]
    available_capacity: tuple[int, ...]
    available_cash_cap_cents: int
    success_probability: Fraction
    failure_refund_fraction: Fraction
    failure_handling_cents: int


@dataclass(frozen=True)
class Plan:
    qualification: str
    start_day: int
    fees: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Witness:
    plan: Plan
    finish_day: int
    declared_cost_cents: int
    expected_supplier_margin_cents: Fraction
    minimum_unrestricted_cash_cents: Fraction
    success_margin_cents: int
    failure_margin_cents: Fraction
    buyer_net_utilities_cents: tuple[tuple[str, Fraction], ...]


def _integer(value, name, *, positive=False):
    if type(value) is not int or value < int(positive):
        raise ValueError('INVALID_NONNEGATIVE_INTEGER:' + name)


def validate(case):
    """Reject ambiguous/inexact inputs before either constructor runs."""
    if not isinstance(case, Cohort) or not case.id or not case.buyers or not case.qualifications:
        raise ValueError('INVALID_COHORT')
    if len({b.id for b in case.buyers}) != len(case.buyers):
        raise ValueError('DUPLICATE_BUYER')
    if len({q.id for q in case.qualifications}) != len(case.qualifications):
        raise ValueError('DUPLICATE_QUALIFICATION')
    for name in ('success_probability', 'failure_refund_fraction'):
        p = getattr(case, name)
        if type(p) is not Fraction or not 0 <= p <= 1:
            raise ValueError('INVALID_EXACT_PROBABILITY:' + name)
    for name in ('available_cash_cap_cents', 'failure_handling_cents'):
        _integer(getattr(case, name), name)
    if not case.fee_menu_cents or len(set(case.fee_menu_cents)) != len(case.fee_menu_cents):
        raise ValueError('INVALID_FEE_MENU')
    for fee in case.fee_menu_cents:
        _integer(fee, 'fee', positive=True)
    if not case.available_capacity:
        raise ValueError('MISSING_CAPACITY')
    for amount in case.available_capacity:
        _integer(amount, 'capacity')
    for b in case.buyers:
        if not b.id or not b.interface or type(b.permits_shared_qualification) is not bool:
            raise ValueError('INVALID_BUYER')
        for name in ('maximum_error_ppm', 'deadline_day', 'settlement_day',
                     'budget_cents', 'accepted_value_cents', 'adoption_cents',
                     'outside_utility_cents'):
            _integer(getattr(b, name), name)
    for q in case.qualifications:
        if not q.id or not q.interfaces or any(not x for x in q.interfaces):
            raise ValueError('INVALID_QUALIFICATION')
        _integer(q.error_ppm, 'error_ppm')
        _integer(q.duration_days, 'duration_days', positive=True)
        _integer(q.capacity_units, 'capacity_units', positive=True)
        _integer(q.assurance_threshold_cents, 'threshold')
        if not q.start_days or len(set(q.start_days)) != len(q.start_days) or not q.costs:
            raise ValueError('INVALID_SCHEDULE')
        for start in q.start_days:
            _integer(start, 'start_day')
        for offset, label, amount in q.costs:
            _integer(offset, 'cost_day')
            _integer(amount, 'cost')
            if not label or offset > q.duration_days:
                raise ValueError('INVALID_COST_TASK')


def _buyer_utility(case, buyer, fee):
    refund = fee * case.failure_refund_fraction
    return (case.success_probability * buyer.accepted_value_cents
            - buyer.adoption_cents - fee + (1 - case.success_probability) * refund)


def _eligible(case, q, start, buyer, fee):
    finish = start + q.duration_days
    return (buyer.interface in q.interfaces and q.error_ppm <= buyer.maximum_error_ppm
            and finish <= buyer.deadline_day and buyer.settlement_day < finish
            and fee + buyer.adoption_cents <= buyer.budget_cents
            and _buyer_utility(case, buyer, fee) > max(0, buyer.outside_utility_cents))


def check(case, plan):
    """Event-prefix witness, retaining worst promised refund through acceptance.

    Return None for infeasible/declined plans. Equal-utility buyers choose their
    outside option. All named commitments are required; an unselected buyer owes
    nothing. A missing collection is not silently substituted with the pledge.
    """
    validate(case)
    if not isinstance(plan, Plan) or type(plan.start_day) is not int:
        return None
    q = next((q for q in case.qualifications if q.id == plan.qualification), None)
    lookup = {b.id: b for b in case.buyers}
    ids = [ident for ident, fee in plan.fees]
    if (q is None or plan.start_day not in q.start_days or not ids
            or len(ids) != len(set(ids)) or any(i not in lookup for i in ids)):
        return None
    if any(type(fee) is not int or fee not in case.fee_menu_cents for _, fee in plan.fees):
        return None
    start, finish = plan.start_day, plan.start_day + q.duration_days
    if finish > len(case.available_capacity):
        return None
    if any(case.available_capacity[d] < q.capacity_units for d in range(start, finish)):
        return None
    if any(not _eligible(case, q, start, lookup[i], fee) for i, fee in plan.fees):
        return None
    if len(ids) > 1 and any(not lookup[i].permits_shared_qualification for i in ids):
        return None
    pledged = sum(fee for _, fee in plan.fees)
    if pledged < q.assurance_threshold_cents:
        return None

    # No cash is created here: these are prospective arithmetic checks, not posts.
    cash = Fraction(case.available_cash_cap_cents)
    reserve = Fraction(case.failure_handling_cents)
    minimum = cash - reserve
    if minimum < 0:
        return None
    events = [(start + offset, 0, label, Fraction(amount)) for offset, label, amount in q.costs]
    events += [(lookup[i].settlement_day, 1, i, Fraction(fee)) for i, fee in plan.fees]
    for day, phase, label, amount in sorted(events):
        if phase == 0:
            cash -= amount
        else:
            cash += amount
            reserve += amount * case.failure_refund_fraction
        minimum = min(minimum, cash - reserve)
        if cash - reserve < 0:
            return None
    cost = sum(amount for _, _, amount in q.costs)
    success_margin = pledged - cost
    failure_margin = success_margin - pledged * case.failure_refund_fraction - case.failure_handling_cents
    # Failure consumes its reserved refunds/handling; success releases the same
    # reserve. Neither branch can worsen the pre-acceptance unrestricted prefix.
    expected = case.success_probability * success_margin + (1 - case.success_probability) * failure_margin
    utilities = tuple(sorted((i, _buyer_utility(case, lookup[i], fee)) for i, fee in plan.fees))
    return Witness(plan, finish, cost, expected, minimum, success_margin, failure_margin, utilities)


def _key(witness):
    p = witness.plan
    return (-witness.expected_supplier_margin_cents, -len(p.fees),
            witness.declared_cost_cents, p.qualification, p.start_day, p.fees)


def construct(case, *, allow_pooling=True):
    """Candidate: prefilter buyer options, then jointly enumerate arrangements."""
    validate(case)
    accepted = []
    buyers = tuple(sorted(case.buyers, key=lambda b: b.id))
    for q in case.qualifications:
        for start in q.start_days:
            menus = [(None,) + tuple(f for f in case.fee_menu_cents if _eligible(case, q, start, b, f))
                     for b in buyers]
            for selected in product(*menus):
                fees = tuple((b.id, f) for b, f in zip(buyers, selected) if f is not None)
                if not fees or (not allow_pooling and len(fees) != 1):
                    continue
                witness = check(case, Plan(q.id, start, fees))
                if witness is not None and witness.expected_supplier_margin_cents > 0:
                    accepted.append(witness)
    return min(accepted, key=_key) if accepted else None


def ordinary(case):
    """Unrestricted specialist control with separate algebraic prefix checks.

    Enumerates every supplied coalition/fee/schedule without using candidate
    eligibility or check(). This is a second authored implementation, not a
    measured human operator or an independent real-world acceptance authority.
    """
    validate(case)
    accepted = []
    for count in range(1, len(case.buyers) + 1):
        for group in combinations(sorted(case.buyers, key=lambda b: b.id), count):
            for prices in product(case.fee_menu_cents, repeat=count):
                for q in case.qualifications:
                    for start in q.start_days:
                        finish = start + q.duration_days
                        if (finish > len(case.available_capacity)
                                or any(case.available_capacity[d] < q.capacity_units for d in range(start, finish))):
                            continue
                        if count > 1 and any(not b.permits_shared_qualification for b in group):
                            continue
                        nets = tuple((b.id, case.success_probability * b.accepted_value_cents
                                      - b.adoption_cents - fee * (1 - (1 - case.success_probability)
                                                                * case.failure_refund_fraction))
                                     for b, fee in zip(group, prices))
                        if any(b.interface not in q.interfaces or q.error_ppm > b.maximum_error_ppm
                               or finish > b.deadline_day or b.settlement_day >= finish
                               or fee + b.adoption_cents > b.budget_cents
                               or net <= max(0, b.outside_utility_cents)
                               for b, fee, (_, net) in zip(group, prices, nets)):
                            continue
                        total = sum(prices)
                        if total < q.assurance_threshold_cents:
                            continue
                        # At any morning cost prefix only earlier-day collections
                        # are usable. Same-day costs precede evening settlements.
                        slacks = [Fraction(case.available_cash_cap_cents - case.failure_handling_cents)]
                        spent = 0
                        for offset, label, amount in sorted(q.costs):
                            spent += amount
                            already_settled = sum(f for b, f in zip(group, prices) if b.settlement_day < start + offset)
                            slacks.append(case.available_cash_cap_cents - case.failure_handling_cents - spent
                                          + already_settled * (1 - case.failure_refund_fraction))
                        if min(slacks) < 0:
                            continue
                        cost = sum(item[2] for item in q.costs)
                        good = total - cost
                        bad = total * (1 - case.failure_refund_fraction) - cost - case.failure_handling_cents
                        margin = good * case.success_probability + bad * (1 - case.success_probability)
                        if margin <= 0:
                            continue
                        plan = Plan(q.id, start, tuple((b.id, f) for b, f in zip(group, prices)))
                        accepted.append(Witness(plan, finish, cost, margin, min(slacks), good, bad, nets))
    return min(accepted, key=_key) if accepted else None


def fixtures():
    """Twelve authored cohorts, frozen in source; cash caps are not new seeds."""
    buyers = (
        Buyer('a', '4-20mA', 100, 4, 0, 600000, 1000000, 50000, 50000),
        Buyer('b', 'modbus', 100, 4, 0, 475000, 1000000, 50000, 50000),
        Buyer('c', 'pulse', 100, 4, 0, 400000, 1000000, 50000, 50000),
    )
    q = Qualification('standard', ('4-20mA', 'modbus', 'pulse'), 100, 3, (1,), 1,
                      ((0, 'design_and_setup', 300000), (1, 'independent_qualification', 400000),
                       (2, 'delivery_security_and_remedy_setup', 200000)), 900000)
    base = Cohort('compatible_pool', buyers, (q,), (250000, 400000, 550000), (1,) * 8,
                  200000, Fraction(9, 10), Fraction(1, 4), 10000)
    strict = replace(buyers[2], maximum_error_ppm=10)
    precise = replace(q, id='precision', error_ppm=10,
                      costs=q.costs[:-1] + ((2, 'precision_delivery_and_remedy_setup', 300000),),
                      assurance_threshold_cents=1000000)
    late = tuple(replace(b, settlement_day=5) for b in buyers)
    same_day = tuple(replace(b, settlement_day=1) for b in buyers)
    return (
        base,
        replace(base, id='heterogeneous_precision', buyers=buyers[:2] + (strict,), qualifications=(q, precise)),
        replace(base, id='unsupported_acceptance', buyers=tuple(replace(b, interface='unqualified_hazardous_area') for b in buyers)),
        replace(base, id='no_validation_capacity', available_capacity=(0,) * 8),
        replace(base, id='settlement_after_deadline', buyers=late),
        replace(base, id='same_day_cash_shortfall', buyers=same_day, available_cash_cap_cents=100000),
        replace(base, id='same_day_funded_bridge', buyers=same_day, available_cash_cap_cents=400000),
        replace(base, id='qualification_misses_deadline', buyers=tuple(replace(b, deadline_day=2) for b in buyers)),
        replace(base, id='outside_alternative_wins', buyers=tuple(replace(b, outside_utility_cents=1000000) for b in buyers)),
        replace(base, id='full_refund_reserve_unfunded', failure_refund_fraction=Fraction(1)),
        replace(base, id='buyer_budget_shortfall', buyers=tuple(replace(b, budget_cents=100000) for b in buyers)),
        replace(base, id='full_refund_funded_bridge', failure_refund_fraction=Fraction(1), available_cash_cap_cents=1000000),
    )


def _json_value(value):
    if isinstance(value, Fraction):
        return {'numerator': value.numerator, 'denominator': value.denominator}
    raise TypeError(type(value).__name__)


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':'), default=_json_value)


def run():
    started = time.process_time()
    cases = fixtures()
    rows = []
    for case in cases:
        candidate = construct(case)
        control = ordinary(case)
        individual = construct(case, allow_pooling=False)
        if candidate != control:
            raise AssertionError('CANDIDATE_ORDINARY_DISAGREEMENT:' + case.id)
        rows.append({'case': case.id, 'candidate': asdict(candidate) if candidate else None,
                     'ordinary_exact_tie': candidate == control,
                     'individual_only_positive_margin_route': individual is not None})
    return {
        'schema': 'omega/shared-qualification-discovery/v1', 'currency': 'USD',
        'money_unit': 'cents; exact fractions where specified',
        'scope': 'AUTHORED_FINITE_CONTRACT_NOT_PHYSICAL_QUALIFICATION_OR_NATIVE_FINANCE',
        'purpose': 'Supplier cohorts jointly obtain an independently qualified industrial sensor adapter.',
        'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'fixtures_sha256': sha256(_json([asdict(c) for c in cases]).encode()).hexdigest(),
        'cases': rows, 'cohort_count': len(rows),
        'feasible_positive_margin_cohorts': sum(r['candidate'] is not None for r in rows),
        'ordinary_ties': sum(r['ordinary_exact_tie'] for r in rows),
        'native_postings': 0, 'new_funded_accounts': 0,
        'observed_demand': False, 'physical_acceptance': False,
        'cost_scope': 'Declared setup/design, independent qualification, delivery/security/remedy setup, failure handling, buyer adoption and failure refunds; actual industrial costs and legal acceptance remain unmeasured.',
        'assumptions': 'Qualification success probability, reusable acceptance envelopes, risk-neutral expected buyer utilities, values, budgets, refund terms, capacity and settlement dates are authored. Full downside refund exposure is reserved. Seller cash caps are planning constraints, not seed accounts.',
        'verdict': 'CONDITIONAL_SHARED_FEASIBILITY_NO_HARNESS_METHOD_ADVANTAGE',
        'cpu_seconds': time.process_time() - started,
    }


if __name__ == '__main__':
    print(_json(run()))
