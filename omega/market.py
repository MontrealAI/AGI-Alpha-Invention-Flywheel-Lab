"""Causal conditional commerce with independent whole-buyer choices.

This is an authored finite market, not measured demand or optimal enterprise
design. The policy receives PublicState only. The environment alone receives
Scenario/seeds/personas. Money is integer USD cents; buyer receipts use microUSD.
Native execution lives in market_native and reuses JournalAccount.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from fractions import Fraction
import hashlib
import itertools
import json
import math

from omega import market_buyer

CENT = 10_000
ROUND_HOURS = 2160
MATURITY_DELAY_HOURS = 721
PRODUCTS = ('self_hosted', 'group_webinar', 'founder_private')
POLICIES = ('nonentry', 'simple', 'existing', 'staged', 'ordinary_reuse', 'joint')
SEGMENTS = ('commodity', 'convenience', 'process', 'training')
CHANNELS = {'community': (4, 500, 0), 'targeted': (12, 3000, 0),
            'partner': (8, 1200, 1000)}  # leads, paid acquisition cents, commission bps
EVALUATION_SEEDS = (202611031901, 202611031907, 202611031921, 202611031939)
SOFTWARE_PRICES_CENTS = (4900, 9900, 14900, 29900, 49900)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Rates:
    # Authored resource rates/quantities for sensitivities, not actual API bills.
    input_cents_per_million: int = 500
    output_cents_per_million: int = 2500
    cpu_cents_per_hour: int = 50
    founder_cents_per_hour: int = 20000
    tax_bps: int = 2500
    cost_multiplier_bps: int = 10000
    quarter_founder_minutes: int = 960
    security_compliance_cents_per_active_quarter: int = 1500
    webinar_platform_cents: int = 23700
    webinar_material_cents: int = 2500
    webinar_minutes: int = 330
    private_minutes: int = 105
    launch_qualification_hours: int = 12
    process_qualification_hours: int = 72
    information_hours: int = 1
    buyer_window_hours: int = 720

    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in asdict(self).values()):
            raise ValueError('EXPLICIT_NONNEGATIVE_INTEGER_RESOURCE_RATES')
        if self.tax_bps > 10000:
            raise ValueError('TAX_RATE_RANGE')
        # This finite compiler settles one round before the next decision.
        # Longer windows require a pending-obligation scheduler, not a credit
        # from future maturity. This is no general business latency ceiling.
        if self.buyer_window_hours + MATURITY_DELAY_HOURS > ROUND_HOURS:
            raise ValueError('FINITE_ROUND_REQUIRES_MATURITY_BEFORE_NEXT_DECISION')


# Quantities are prospective assumptions, never disguised as measured necessity.
# No charge is made unless the named action is selected and actually executed.
TASKS = {
    'launch': {'input_tokens': 400000, 'output_tokens': 80000, 'cpu_seconds': 600},
    'package_process': {'input_tokens': 1600000, 'output_tokens': 400000, 'cpu_seconds': 3600},
    'information': {'input_tokens': 100000, 'output_tokens': 20000, 'cpu_seconds': 120},
}


def task_cost(name, rates=Rates()):
    task = TASKS[name]
    raw = (Fraction(task['input_tokens'] * rates.input_cents_per_million, 1_000_000)
           + Fraction(task['output_tokens'] * rates.output_cents_per_million, 1_000_000)
           + Fraction(task['cpu_seconds'] * rates.cpu_cents_per_hour, 3600))
    return math.ceil(raw * rates.cost_multiplier_bps / 10000)


def opportunity_cost(minutes, rates):
    return (minutes * rates.founder_cents_per_hour + 59) // 60


@dataclass(frozen=True)
class PublicState:
    quarter: int = 0
    available_cents: int = 10_000_000
    earned_cents: int = 0
    launched: bool = False
    capability: int = 0
    information_bought: bool = False
    weights: tuple[float, ...] = (.35, .30, .25, .10)
    rival_ready: bool = False
    rival_price_cents: int = 9900
    observed_leads: int = 0
    observed_sales: int = 0
    stopped: bool = False
    elapsed_hours: int = 0

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in (self.quarter, self.elapsed_hours)):
            raise ValueError('NONNEGATIVE_INTEGER_PUBLIC_CLOCK_REQUIRED')


@dataclass(frozen=True)
class Action:
    kind: str = 'preserve'
    price_cents: int = 29900
    channel: str = 'community'
    products: tuple[str, ...] = ()
    construct_process: bool = False


@dataclass(frozen=True)
class Scenario:
    name: str
    seed: int
    mixture: tuple[int, int, int, int]
    adverse: bool = False
    imitation_lag: int = 2
    imitation_threshold: int = 4
    trust_bps: int = 9900


def registered_cases(*, development=False):
    seeds = (1103, 1109, 1117, 1123) if development else EVALUATION_SEEDS
    mixtures = ((8000, 1000, 500, 500), (1000, 6000, 2000, 1000),
                (1000, 1500, 6500, 1000), (1000, 1000, 1500, 6500))
    names = ('weak_free_substitutes', 'convenience', 'process', 'training')
    return tuple(Scenario(names[i] + ('-adverse' if adverse else '-normal'), seeds[i], mix,
                          adverse, 1 if adverse else 2, 1 if adverse else 4,
                          9500 if adverse else 9900)
                 for i, mix in enumerate(mixtures) for adverse in (False, True))


def _draw(seed, quarter, prospect, event):
    # Potential outcomes are addressed by event, not consumed from a policy RNG.
    return int(digest([seed, quarter, prospect, event])[:12], 16) / 16**12


def persona(segment, ident, *, required=None, scale_bps=10000, rival_ready=False,
            rival_price=9900, founder_access=False):
    values = dict(zip(SEGMENTS, (60000, 150000, 500000, 150000)))
    efforts = dict(zip(SEGMENTS, (1000, 50000, 70000, 90000)))
    setup = 60000 if segment == 'training' else 4000
    value = values[segment] * scale_bps // 10000
    outside_effort = efforts[segment] * scale_bps // 10000
    outside = [
        {'id': 'free_core', 'price_cents': 0, 'effort_cents': outside_effort,
         'capability': 1, 'trust_bps': 9900, 'reliability_bps': 9900},
        {'id': 'ordinary_reuse', 'price_cents': 0, 'effort_cents': outside_effort,
         'capability': 1, 'trust_bps': 9900, 'reliability_bps': 9900},
        {'id': 'specialist', 'price_cents': 75000, 'effort_cents': 1000,
         'capability': 1, 'trust_bps': 10000, 'reliability_bps': 10000},
    ]
    if rival_ready:
        outside.append({'id': 'imitating_rival', 'price_cents': rival_price,
                        'effort_cents': 5000, 'capability': 1,
                        'trust_bps': 9900, 'reliability_bps': 9900})
    return {'id': ident, 'budget_cents': 2600000 if founder_access else (120000 if segment == 'process' else 70000),
            'value_cents': value, 'software_setup_cents': setup,
            'webinar_learning_cents': 2000, 'founder_access_cents': 2500000 if founder_access else 0,
            'switching_cents': 1000, 'buyer_compute_cents': 11,
            'webinar_setup_reduction_cents': 55000,
            'private_session_prerequisites_met': founder_access,
            'required_capability': (int(segment == 'process') if required is None else required),
            'outside_options': outside}


def quoted_offers(action, state, *, trust_bps=9900):
    capability = int(state.capability == 1 or action.construct_process)
    prices = {'self_hosted': action.price_cents, 'group_webinar': 9900, 'founder_private': 2000000}
    return [{'id': p, 'product': p, 'price_cents': prices[p], 'capability': capability,
             'effort_cents': 500 if p == 'self_hosted' else 1000,
             'trust_bps': trust_bps, 'reliability_bps': 9900} for p in action.products]


def fixed_costs(action, state, rates):
    if action.kind == 'information':
        return {'information': task_cost('information', rates)}
    if action.kind != 'operate':
        return {}
    rows = {'acquisition': CHANNELS[action.channel][1],
            'security_compliance': rates.security_compliance_cents_per_active_quarter}
    if not state.launched:
        rows['launch'] = task_cost('launch', rates)
    if action.construct_process:
        rows['package_process'] = task_cost('package_process', rates)
    if 'group_webinar' in action.products:
        rows['webinar_platform'] = rates.webinar_platform_cents
        rows['webinar_material'] = rates.webinar_material_cents
    return rows


def qualification_delay(action, state, rates):
    """Declared supplier/qualification latency; it is not CPU or human effort."""
    if action.kind == 'information':
        return rates.information_hours
    if action.kind != 'operate':
        return 0
    return max(rates.launch_qualification_hours if not state.launched else 0,
               rates.process_qualification_hours if action.construct_process else 0)


def variable_costs(product, price, channel, *, paid=True):
    if not paid:
        return {'failed_payment_attempt': 30}
    bps, fixed = (700, 200) if product == 'group_webinar' else (350, 30)
    return {'processing': (price * bps + 9999) // 10000 + fixed,
            'delivery_compute': {'self_hosted': 75, 'group_webinar': 25, 'founder_private': 100}[product],
            'hosting_download': 15, 'security_verification': 25,
            'fraud_remedy_envelope': 50,
            'channel_commission': (price * CHANNELS[channel][2] + 9999) // 10000}


def feasible_actions(state, mode, rates=Rates()):
    if mode not in POLICIES:
        raise ValueError('REGISTERED_POLICY_REQUIRED')
    if state.stopped or mode == 'nonentry' or state.quarter >= 4:
        return (Action(),)
    if mode == 'simple':
        candidates = [Action(), Action('operate', 29900, 'community', ('self_hosted',))]
    else:
        products = tuple(tuple(c) for n in (1, 2, 3) for c in itertools.combinations(PRODUCTS, n))
        upgrades = (False, True) if state.capability == 0 and mode != 'existing' else (False,)
        if mode == 'staged' and state.quarter == 0:
            upgrades = (False,)
        candidates = [Action()] + [Action('operate', price, channel, offered, upgrade)
            for price in SOFTWARE_PRICES_CENTS for channel in CHANNELS
            for offered in products for upgrade in upgrades]
    return tuple(a for a in candidates if a.kind == 'preserve' or (
                 sum(fixed_costs(a, state, rates).values()) <= state.available_cents
                 and state.elapsed_hours + qualification_delay(a, state, rates) <= rates.buyer_window_hours
                 and ('group_webinar' not in a.products
                      or rates.webinar_minutes <= rates.quarter_founder_minutes)))


@lru_cache(maxsize=200000)
def _prototype_selection(segment, action, capability, rival_ready, rival_price):
    s = PublicState(capability=capability, rival_ready=rival_ready, rival_price_cents=rival_price)
    p = persona(segment, 'public-prior-prototype', rival_ready=rival_ready, rival_price=rival_price)
    d = market_buyer.decide(p, quoted_offers(action, s))
    return tuple(d['selected_offer_ids'])


def forecast(action, state, rates=Rates()):
    """Public-prior one-round expected economic value, no actual cohort input.

    The declared 96% payment and 97% delivery beliefs are imperfect priors.
    Forecasts cannot be posted as income or used as available cash.
    """
    if action.kind != 'operate':
        return 0.0
    cost = sum(fixed_costs(action, state, rates).values())
    minutes = rates.webinar_minutes if 'group_webinar' in action.products else 0
    result = -cost - opportunity_cost(minutes, rates)
    leads = CHANNELS[action.channel][0]
    for weight, segment in zip(state.weights, SEGMENTS):
        selected = _prototype_selection(segment, action, state.capability, state.rival_ready, state.rival_price_cents)
        if not selected:
            continue
        price = {'self_hosted': action.price_cents, 'group_webinar': 9900, 'founder_private': 2000000}
        order_cost = sum(sum(variable_costs(p, price[p], action.channel).values()) for p in selected)
        order_revenue = sum(price[p] for p in selected)
        if state.available_cents - cost < order_revenue + order_cost + 20 * len(selected):
            # A positive expected margin cannot finance its own present exposure.
            continue
        per = .96 * (.97 * order_revenue - order_cost) - .04 * 30 * len(selected)
        if 'founder_private' in selected:
            per -= opportunity_cost(rates.private_minutes, rates)
        result += leads * weight * per
    return result


def _posterior(weights, signal):
    likelihood = (.10, .40, .80, .60)
    values = [w * (p if signal == 'positive' else 1 - p) for w, p in zip(weights, likelihood)]
    total = sum(values)
    return tuple(round(v / total, 12) for v in values)


def choose(state, mode='joint', rates=Rates()):
    """Receding-horizon heuristic; ordinary reuse has the SAME full action access.

    Research is selected only if the public-prior value of changing the action
    exceeds its explicit task cost. No global/exhaustive optimum is claimed.
    """
    if type(state) is not PublicState:
        raise ValueError('POLICY_ACCEPTS_PUBLIC_STATE_ONLY')
    actions = feasible_actions(state, mode, rates)
    scored = [(forecast(a, state, rates), a) for a in actions]
    best, selected = max(scored, key=lambda x: (x[0], -sum(fixed_costs(x[1], state, rates).values()),
                                               -len(x[1].products), not x[1].construct_process))
    info = {'selector': 'public-prior receding-horizon heuristic', 'best_one_round_expected_cents': best,
            'ordinary_reuse_has_equal_actions_and_content': True, 'information_value_cents': None,
            'source_of_cash': 'actual available state; forecast is never income'}
    if mode in ('joint', 'ordinary_reuse', 'staged') and not state.information_bought and not state.stopped:
        expense = task_cost('information', rates)
        if expense <= state.available_cents and state.elapsed_hours + rates.information_hours <= rates.buyer_window_hours:
            p_positive = sum(w * p for w, p in zip(state.weights, (.10, .40, .80, .60)))
            after = []
            for signal in ('positive', 'negative'):
                leaf = replace(state, weights=_posterior(state.weights, signal),
                               available_cents=state.available_cents - expense, information_bought=True,
                               elapsed_hours=state.elapsed_hours + rates.information_hours)
                after.append(max(forecast(a, leaf, rates) for a in feasible_actions(leaf, mode, rates)))
            value = p_positive * after[0] + (1 - p_positive) * after[1] - expense
            info['information_value_cents'] = value - best
            if value > best:
                selected = Action('information')
                info['best_one_round_expected_cents'] = value
    return selected, info


def _observe_weights(state, public_buyers, action):
    weights = list(state.weights)
    for observed in public_buyers:
        for i, segment in enumerate(SEGMENTS):
            # Declared noisy observation model. Actual hidden segment is NEVER read.
            expected_requirement = int(segment == 'process')
            predicted_sale = bool(_prototype_selection(segment, action, state.capability,
                                                       state.rival_ready, state.rival_price_cents))
            weights[i] *= (.85 if expected_requirement == observed['required_capability'] else .15)
            weights[i] *= (.75 if predicted_sale == observed['chose_seller'] else .25)
        total = sum(weights)
        weights = [v / total for v in weights]
    return tuple(round(v, 12) for v in weights)


def simulate(scenario, mode, *, rates=Rates(), capital_cents=10_000_000):
    """Compile a policy path using only observations available at each decision.

    Compilation is not revenue. market_native must then execute and independently
    reconcile the path; only that record is native simulated commerce.
    """
    if type(scenario) is not Scenario or mode not in POLICIES:
        raise ValueError('DECLARED_SCENARIO_AND_POLICY_REQUIRED')
    if type(capital_cents) is not int or capital_cents < 0:
        raise ValueError('DECLARED_INTEGER_OPENING_CAPITAL')
    state = PublicState(available_cents=capital_cents)
    trace, total_revenue, total_cost, total_minutes, total_accepted, total_residual = [], 0, 0, 0, 0, 0
    for q in range(4):
        rival = q >= scenario.imitation_lag and total_accepted >= scenario.imitation_threshold
        state = replace(state, quarter=q, rival_ready=rival, elapsed_hours=0)
        for _ in range(2):
            action, rationale = choose(state, mode, rates)
            before = asdict(state)
            fixed = fixed_costs(action, state, rates)
            if action.kind != 'information':
                break
            signal_probability = sum(m / 10000 * p for m, p in zip(scenario.mixture, (.10, .40, .80, .60)))
            signal = 'positive' if _draw(scenario.seed, q, 0, 'paid-information') < signal_probability else 'negative'
            expense = sum(fixed.values())
            total_cost += expense
            state = replace(state, available_cents=state.available_cents - expense,
                            earned_cents=max(0, state.earned_cents - expense), information_bought=True,
                            weights=_posterior(state.weights, signal), elapsed_hours=state.elapsed_hours + rates.information_hours)
            trace.append({'quarter': q, 'hour': q * ROUND_HOURS + before['elapsed_hours'], 'public_before': before,
                          'action': asdict(action), 'rationale': rationale, 'fixed_costs_cents': fixed,
                          'signal': signal, 'signal_available_hour': q * ROUND_HOURS + state.elapsed_hours,
                          'bundles': [], 'public_buyers': [], 'founder_minutes': 0,
                          'revenue_cents': 0, 'cost_cents': expense, 'new_residual_cents': 0,
                          'closing_available_cents': state.available_cents})
        if action.kind == 'preserve':
            trace.append({'quarter': q, 'hour': q * ROUND_HOURS + state.elapsed_hours, 'public_before': before,
                          'action': asdict(action), 'rationale': rationale, 'fixed_costs_cents': {},
                          'bundles': [], 'public_buyers': [], 'founder_minutes': 0,
                          'revenue_cents': 0, 'cost_cents': 0, 'new_residual_cents': 0,
                          'closing_available_cents': state.available_cents})
            state = replace(state, stopped=True)
            continue
        capability = int(state.capability or action.construct_process)
        delivery_hour = q * ROUND_HOURS + state.elapsed_hours + qualification_delay(action, state, rates)
        quotes = quoted_offers(action, state, trust_bps=scenario.trust_bps)
        row_cost = sum(fixed.values())
        available = state.available_cents - row_cost
        row_revenue, row_residual, row_accepted = 0, 0, 0
        minutes = rates.webinar_minutes if 'group_webinar' in action.products else 0
        bundles, observations = [], []
        for prospect in range(CHANNELS[action.channel][0]):
            u = _draw(scenario.seed, q, prospect, action.channel + ':segment') * 10000
            running = 0
            segment = SEGMENTS[-1]
            for name, probability in zip(SEGMENTS, scenario.mixture):
                running += probability
                if u < running:
                    segment = name
                    break
            scale = 8000 + int(_draw(scenario.seed, q, prospect, 'value-effort') * 4001)
            access = _draw(scenario.seed, q, prospect, 'founder-access') < .005
            ident = f'q{q}-b{prospect}'
            buyer = persona(segment, ident, scale_bps=scale, rival_ready=rival, founder_access=access)
            offered = [r for r in quotes if r['product'] != 'founder_private'
                       or minutes + rates.private_minutes <= rates.quarter_founder_minutes]
            decision = market_buyer.decide(buyer, offered)
            chosen = decision['selected_offer_ids']
            willingness = _draw(scenario.seed, q, prospect, 'voluntary-transaction') < (.90 if scenario.adverse else .98)
            consent = bool(chosen and willingness)
            observations.append({'buyer_id': ident, 'required_capability': buyer['required_capability'],
                                 'chose_seller': consent})
            if not consent:
                continue
            paid = _draw(scenario.seed, q, prospect, 'payment') >= (.12 if scenario.adverse else .04)
            accepted = _draw(scenario.seed, q, prospect, 'delivery') >= (.18 if scenario.adverse else .03)
            selected_quotes = [r for r in offered if r['id'] in chosen]
            item_costs = [variable_costs(r['product'], r['price_cents'], action.channel, paid=paid)
                          for r in selected_quotes]
            expense = sum(sum(x.values()) for x in item_costs)
            price = sum(r['price_cents'] for r in selected_quotes)
            # Full present price exposure plus costs and conservative tail buffer.
            required = expense + (price + 20 * len(chosen) if paid else 0)
            if available < required:
                bundles.append({'buyer_id': ident, 'status': 'liquidity_deferred', 'items': [],
                                'required_cents': required, 'available_cents': available})
                continue
            status = 'unpaid' if not paid else ('released' if accepted else 'refunded')
            items = []
            for offer, costs in zip(selected_quotes, item_costs):
                receipt = market_buyer.to_receipt(buyer, offered, offer['id'], consent=True, choice_id=ident)
                market_buyer.verify_quote_receipt(buyer, offered, receipt)
                items.append({'product': offer['product'], 'price_cents': offer['price_cents'],
                              'costs_cents': costs, 'choice': receipt,
                              'workflow': 'process' if capability and buyer['required_capability'] and offer['product'] == 'self_hosted' else 'water'})
            row_cost += expense
            available -= expense + (20 * len(chosen) if paid and accepted else 0)
            if paid and accepted:
                row_revenue += price
                row_residual += sum(r['price_cents'] // 100 for r in selected_quotes)
                row_accepted += 1
            if paid and 'founder_private' in chosen:
                minutes += rates.private_minutes
            bundles.append({'buyer_id': ident, 'status': status, 'paid': paid, 'accepted': accepted,
                            'persona': buyer, 'quotes': offered, 'items': items,
                            'expected_buyer_net_microUSD': decision['buyer_net_benefit_microUSD'],
                            'expected_increment_over_outside_microUSD': decision['increment_over_best_outside_microUSD'],
                            'expected_value_before_fees_microUSD': decision['value_before_fees_microUSD'],
                            'realized_buyer_value_not_measured': True})
        total_revenue += row_revenue
        total_cost += row_cost
        total_minutes += minutes
        total_accepted += row_accepted
        total_residual += row_residual
        closing = state.available_cents + row_revenue - row_cost - row_residual
        next_weights = _observe_weights(state, observations, action)
        trace.append({'quarter': q, 'hour': q * ROUND_HOURS + state.elapsed_hours,
                      'delivery_hour': delivery_hour, 'maturity_hour': delivery_hour + MATURITY_DELAY_HOURS,
                      'public_before': before, 'action': asdict(action), 'rationale': rationale,
                      'fixed_costs_cents': fixed, 'bundles': bundles, 'public_buyers': observations,
                      'founder_minutes': minutes, 'revenue_cents': row_revenue, 'cost_cents': row_cost,
                      'new_residual_cents': row_residual, 'closing_available_cents': closing})
        state = replace(state, available_cents=closing,
                        earned_cents=max(0, total_revenue - total_cost - total_residual),
                        launched=True, capability=capability, weights=next_weights,
                        observed_leads=state.observed_leads + len(observations),
                        observed_sales=state.observed_sales + row_accepted)
    taxable = max(0, total_revenue - total_cost)
    tax = (taxable * rates.tax_bps + 9999) // 10000
    accounting_profit = total_revenue - total_cost - tax
    founder = opportunity_cost(total_minutes, rates)
    return {'schema': 'omega/causal-market-plan/v1', 'scenario': asdict(scenario), 'policy': mode,
            'rates': asdict(rates), 'capital_cents': capital_cents, 'trace': trace,
            'recognized_revenue_cents': total_revenue, 'pretax_cash_expense_cents': total_cost,
            'tax_cents': tax, 'accounting_profit_cents': accounting_profit,
            'founder_minutes': total_minutes, 'noncash_founder_opportunity_cents': founder,
            'economic_profit_cents': accounting_profit - founder, 'residual_cents': total_residual,
            'closing_available_cents': capital_cents + accounting_profit - total_residual,
            'accepted_complete_bundles': total_accepted, 'endpoint_hour': 8760,
            'scope': 'CONDITIONAL_CAUSAL_PLAN_REQUIRES_NATIVE_EXECUTION_NOT_PRIMARY_ACCOUNT'}


def audit_policy(plan):
    """Recompute every decision from the public information set, not world labels."""
    rates = Rates(**plan['rates'])
    for row in plan['trace']:
        raw = dict(row['public_before'])
        raw['weights'] = tuple(raw['weights'])
        action, rationale = choose(PublicState(**raw), plan['policy'], rates)
        if digest(asdict(action)) != digest(row['action']) or digest(rationale) != digest(row['rationale']):
            raise ValueError('CAUSAL_PUBLIC_POLICY_CHANGED')
        if fixed_costs(action, PublicState(**raw), rates) != row['fixed_costs_cents']:
            raise ValueError('COST_MUST_FOLLOW_SELECTED_ACTION')
        for bundle in row['bundles']:
            for item in bundle['items']:
                market_buyer.verify_quote_receipt(bundle['persona'], bundle['quotes'], item['choice'])
    scenario_raw = dict(plan['scenario']); scenario_raw['mixture'] = tuple(scenario_raw['mixture'])
    expected = simulate(Scenario(**scenario_raw), plan['policy'], rates=rates, capital_cents=plan['capital_cents'])
    if digest(expected) != digest(plan):
        raise ValueError('REGISTERED_ENVIRONMENT_OR_POLICY_TRACE_CHANGED')
    return {'accepted': True, 'decisions': len(plan['trace']), 'plan_sha256': digest(plan),
            'optimality_claim': 'HEURISTIC_ONLY; ordinary reuse has equal action/resource/content access'}


def cost_disclosure(rates=Rates()):
    return {'currency': 'USD', 'commercial_currency_finalized': False,
            'measured_expenditure': 'None; no real transactions or model APIs were used.',
            'resource_task_quantities': TASKS, 'resource_rate_assumptions': asdict(rates),
            'action_costs_cents': {k: task_cost(k, rates) for k in TASKS},
            'cost_provenance': {
                'task_quantities_and_rates': 'AUTHORED_RANGE_INPUT; not measured necessary effort or a supplier quote',
                'acquisition': 'AUTHORED_CHANNEL_CONTRACT; payable only when selected; lead count is finite scenario input',
                'payment': 'AUTHORED_USD_ENVELOPE: 3.5%+$0.30; webinar7%+$2; no CAD/USD mixing or platform quote claim',
                'security_compliance': 'AUTHORED_$15_per_active_quarter risk envelope, not a legal/security sufficiency finding',
                'founder': 'AUTHORED_$200/hour opportunity cost; no phantom employee payroll',
                'webinar': 'AUTHORED_330_minutes and $237 platform+$25 materials per selected session; capacity500',
                'private': 'AUTHORED_105_minutes total around the30-minute session; prerequisites required',
                'buyer_compute': 'AUTHORED_$0.11/task: hardware amortization $1/hour at0.1h plus0.3kW*$0.20/kWh*0.1h, roundedup',
                'tax': 'CONDITIONAL_25% positive annual taxable modeled cash profit; no jurisdiction/enforceability claim',
            },
            'capital_and_financing': 'No capex, depreciation or financing in seller model; buyer hardware amortization separate; seed not revenue.',
            'tax_treatment': 'Annual expense at hour8758; owner opportunity cost is noncash and not deducted for modeled tax; no loss credit.',
            'obligations': '30day inclusive claim window,1% residual reserve; reserves are not expenses; late claims stop investment under native rules.',
            'ongoing_support_updates': 'No personal support or ongoing update entitlement. Paid per-delivery verification/security envelope and mandatory claims remain.',
            'unknown_actual_costs': ['actual model/host bills', 'applicable taxes and platform eligibility',
                                     'mandatory obligations beyond authored envelope', 'actual acquisition and founder time'],
            'complete_actual_profit': None}


def scientific_claims(*, conventional_tie=True, physical_acceptance=False, primary_native=False):
    return {'super_alpha_demonstrated': False,
            'reason': 'Complete-outcome conventional ties; no physical/empirical market qualification.',
            'conventional_tie': conventional_tie, 'physical_acceptance': physical_acceptance,
            'primary_native_account_continued': primary_native,
            'three_billion_primary_objective_established': False,
            'global_optimality': False}
