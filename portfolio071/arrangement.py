from __future__ import annotations
from fractions import Fraction
from itertools import combinations


def _money(value, name):
    if type(value) is not int or value < 0:
        raise ValueError('NONNEGATIVE_INTEGER_USD_REQUIRED:' + name)
    return value


def validate_buyers(buyers):
    if not isinstance(buyers, list) or not 1 <= len(buyers) <= 12:
        raise ValueError('FINITE_IDENTIFIED_BUYERS_REQUIRED')
    seen = set()
    fields = {'id', 'value_usd', 'budget_usd', 'adoption_usd', 'outside_surplus_usd'}
    for buyer in buyers:
        if not isinstance(buyer, dict) or set(buyer) != fields or not isinstance(buyer['id'], str) or not buyer['id']:
            raise ValueError('EXPLICIT_BUYER_AND_OUTSIDE_OPTIONS_REQUIRED')
        if buyer['id'] in seen:
            raise ValueError('DUPLICATE_BUYER')
        seen.add(buyer['id'])
        for field in fields - {'id'}:
            _money(buyer[field], field)
    return buyers


def _rat(value):
    return {'numerator': value.numerator, 'denominator': value.denominator}


def finite_project(buyers, *, capital_usd, setup_usd, adapter_usd, coordination_usd,
                   supplier_cost_usd, supplier_hurdle_usd, supplier_quote_usd,
                   support_usd, rights_review_usd, price_menu_usd,
                   qualification=(1, 1), shared=True, pooled=True,
                   rights_available=True, supplier_available=True,
                   collateral=True, financing_available=False,
                   tax_bps=2500):
    validate_buyers(buyers)
    amounts = locals().copy()
    for field in ('capital_usd', 'setup_usd', 'adapter_usd', 'coordination_usd',
                  'supplier_cost_usd', 'supplier_hurdle_usd', 'supplier_quote_usd',
                  'support_usd', 'rights_review_usd'):
        _money(amounts[field], field)
    if (not isinstance(price_menu_usd, (list, tuple)) or not price_menu_usd
        or any(type(p) is not int or p <= 0 for p in price_menu_usd)
        or len(set(price_menu_usd)) != len(price_menu_usd)):
        raise ValueError('FINITE_POSITIVE_PRICE_MENU_REQUIRED')
    if not isinstance(qualification, (list, tuple)) or len(qualification) != 2:
        raise ValueError('EXPLICIT_QUALIFICATION_BELIEF_REQUIRED')
    p = Fraction(*qualification)
    if not 0 <= p <= 1 or type(tax_bps) is not int or not 0 <= tax_bps <= 10000:
        raise ValueError('DECLARED_PROBABILITY_AND_TAX_REQUIRED')
    if financing_available:
        raise ValueError('EXTERNAL_FINANCING_NATIVE_OPERATION_UNSUPPORTED')
    best = {'decision': 'NON_ENTRY', 'expected_after_tax_usd': _rat(Fraction(0)),
            'members': [], 'reason': 'NO_POSITIVE_VOLUNTARY_FUNDED_PLAN'}
    best_value = Fraction(0)
    evaluated = []
    max_size = len(buyers) if pooled else 1
    for size in range(1, max_size + 1):
        for group in combinations(buyers, size):
            for price in sorted(price_menu_usd):
                total_price = size * price
                construction = setup_usd * (1 if shared else size)
                upfront = (construction + coordination_usd * (size - 1) + size * adapter_usd
                           + supplier_quote_usd + support_usd + rights_review_usd)
                expected_before_tax = p * total_price - upfront
                tax = max(Fraction(0), expected_before_tax) * Fraction(tax_bps, 10000)
                expected = expected_before_tax - tax
                utilities = {b['id']: p * (b['value_usd'] - price) - b['adoption_usd']
                             for b in group}
                refusals = [b['id'] for b in group
                            if price > b['budget_usd'] or utilities[b['id']] <= b['outside_surplus_usd']]
                supplier_ok = supplier_available and supplier_quote_usd >= supplier_cost_usd + supplier_hurdle_usd
                tax_cash_bound = (total_price * tax_bps + 9999) // 10000
                prefunding = upfront + (total_price + tax_cash_bound + 1 if collateral else 0)
                reasons = []
                if refusals:
                    reasons.append('BUYER_REFUSAL')
                if not supplier_ok:
                    reasons.append('SUPPLIER_REFUSAL')
                if shared and not rights_available:
                    reasons.append('SHARED_RIGHTS_UNAVAILABLE')
                if expected <= 0:
                    reasons.append('NONPOSITIVE_EXPECTED_COMPLETE_COST_PROFIT')
                if prefunding > capital_usd:
                    reasons.append('UNFUNDED_PRECOLLECTION_PREFIX')
                row = {'decision': 'ENTER' if not reasons else 'REFUSE',
                       'members': [b['id'] for b in group], 'price_each_usd': price,
                       'contract_price_usd': total_price, 'upfront_complete_cost_usd': upfront,
                       'minimum_prefunding_usd': prefunding,
                       'tax_cash_bound_usd': tax_cash_bound,
                       'expected_before_tax_usd': _rat(expected_before_tax),
                       'expected_after_tax_usd': _rat(expected),
                       'buyer_surpluses_usd': {k: _rat(v) for k, v in utilities.items()},
                       'supplier_surplus_usd': supplier_quote_usd - supplier_cost_usd,
                       'refusals': reasons, 'refusing_buyers': refusals,
                       'shared': shared, 'pooled': pooled}
                evaluated.append(row)
                if not reasons and expected > best_value:
                    best, best_value = row, expected
    feasible = [r for r in evaluated if r['decision'] == 'ENTER']
    maximum = max([Fraction(**r['expected_after_tax_usd']) for r in feasible] + [Fraction(0)])
    return {'selected': best, 'candidate_count': len(evaluated), 'feasible_count': len(feasible),
            'evaluated': evaluated, 'best_response_regret_usd': _rat(maximum - best_value),
            'solution': 'EXACT_FINITE_FULL_INFORMATION_OFFER_ENUMERATION_WITH_BUYER_AND_SUPPLIER_REFUSAL',
            'limits': ['Inputs are authored public scenario assumptions, not elicited private values.',
                       'No incentive-compatibility, universal equilibrium, market calibration or actual consent claim.',
                       'Tax is a scenario rate on positive modeled contribution, not jurisdictional tax advice.',
                       'Native prospective collateral is conservatively rounded upward by USD 1 here.']}


def factorial(buyers, **terms):
    arms = {}
    for shared, pooled, name in ((False, False, 'original'), (True, False, 'technical_only'),
                                  (False, True, 'arrangement_only'), (True, True, 'joint')):
        arms[name] = finite_project(buyers, shared=shared, pooled=pooled, **terms)
    arms['unrestricted_conventional'] = finite_project(buyers, shared=True, pooled=True, **terms)
    joint = arms['joint']['selected']['expected_after_tax_usd']
    ordinary = arms['unrestricted_conventional']['selected']['expected_after_tax_usd']
    return {'arms': arms, 'ordinary_ties_joint': joint == ordinary,
            'claim': 'Restricted-factorial attribution is separate from superiority over unrestricted conventional entrepreneurship.'}


def buyer_choice(buyer, price_usd, *, rival_price_usd, own_value_bps=10000,
                 rival_value_bps=10000, self_service_cost_usd=18000, delay_surplus_usd=0):
    validate_buyers([buyer])
    for name, value in (('price', price_usd), ('rival_price', rival_price_usd),
                        ('own_value_bps', own_value_bps), ('rival_value_bps', rival_value_bps),
                        ('self_service_cost', self_service_cost_usd), ('delay_surplus', delay_surplus_usd)):
        _money(value, name)
    options = {'refuse': Fraction(0), 'delay': Fraction(delay_surplus_usd),
               'outside': Fraction(buyer['outside_surplus_usd'])}
    if self_service_cost_usd <= buyer['budget_usd']:
        options['self_service'] = Fraction(buyer['value_usd'] - self_service_cost_usd)
    if rival_price_usd <= buyer['budget_usd']:
        options['rival'] = Fraction(buyer['value_usd'] * rival_value_bps, 10000) - rival_price_usd - buyer['adoption_usd']
    if price_usd <= buyer['budget_usd']:
        options['company'] = Fraction(buyer['value_usd'] * own_value_bps, 10000) - price_usd - buyer['adoption_usd']
    maximum = max(options.values())
    choices = sorted(k for k, v in options.items() if v == maximum)
    choice = 'company' if choices == ['company'] and maximum > 0 else next((x for x in choices if x != 'company'), 'refuse')
    return {'choice': choice, 'utility_usd': _rat(options.get(choice, Fraction(0))),
            'options_usd': {k: _rat(v) for k, v in options.items()},
            'tie_rule': 'Company must strictly improve the best outside option; equal alternatives can refuse.'}


def rival_best_response(buyers, company_price_usd, *, rival_price_menu_usd, rival_variable_usd,
                        rival_fixed_usd, own_value_bps=10000, rival_payment_bps=0):
    validate_buyers(buyers)
    _money(rival_variable_usd, 'rival_variable')
    _money(rival_fixed_usd, 'rival_fixed')
    _money(rival_payment_bps, 'rival_payment_bps')
    if rival_payment_bps > 10000:
        raise ValueError('PAYMENT_FEE_BPS_REQUIRED')
    rows = []
    for price in rival_price_menu_usd:
        _money(price, 'rival_price')
        if price < rival_variable_usd:
            continue
        choices = [buyer_choice(b, company_price_usd, rival_price_usd=price,
                                own_value_bps=own_value_bps) for b in buyers]
        rival_units = sum(c['choice'] == 'rival' for c in choices)
        payment_fee = (rival_units * price * rival_payment_bps + 9999) // 10000
        complete_cost = (rival_units * rival_variable_usd
                         + (rival_fixed_usd if rival_units else 0) + payment_fee)
        profit = rival_units * price - complete_cost
        rows.append({'price_usd': price, 'rival_profit_usd': profit,
                     'rival_complete_cost_usd': complete_cost,
                     'company_members': [b['id'] for b, c in zip(buyers, choices) if c['choice'] == 'company'],
                     'choices': choices})
    no_entry_price = max([b['budget_usd'] for b in buyers] + [company_price_usd]) + 1
    no_entry_choices = [buyer_choice(b, company_price_usd, rival_price_usd=no_entry_price,
                                    own_value_bps=own_value_bps) for b in buyers]
    rows.append({'price_usd': None, 'rival_profit_usd': 0,
                 'rival_complete_cost_usd': 0,
                 'company_members': [b['id'] for b, c in zip(buyers, no_entry_choices) if c['choice'] == 'company'],
                 'choices': no_entry_choices})
    selected = max(rows, key=lambda r: (r['rival_profit_usd'], -len(r['company_members']), -(r['price_usd'] or 10**20)))
    return {'selected': selected, 'evaluated': rows,
            'best_response_regret_usd': max(r['rival_profit_usd'] for r in rows) - selected['rival_profit_usd'],
            'solution': 'Finite profit-maximizing rival response; adverse tie-break against company.'}
