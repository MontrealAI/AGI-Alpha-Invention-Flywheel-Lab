"""Exact posted-price decisions over an explicitly declared synthetic offer set.

No universal game-theoretic optimum, verified demand, or external access is inferred.
Future option value is deliberately excluded from spendable funds.
"""
from __future__ import annotations
from typing import Any
from .common import digest, integer, text

SERVICES = ('reconciliation', 'kpi_variance', 'evidence_matrix')
METHODS = ('generated', 'conventional', 'ordinary_reuse')
LEGACY_TAIL_FEE_CENTS = 20  # Current permanent native engine reserves principal + $0.20.
COST_FIELDS = ('production_cents', 'verification_cents', 'support_cents',
               'maintenance_cents', 'integration_cents')


def validate(config: dict[str, Any]) -> None:
    required = {'schema', 'evidence_scope', 'opening_cents', 'working_reserve_cents',
                'setup_cents', 'discovery_cents', 'acquisition_cents', 'fee_bps',
                'fee_fixed_cents', 'tax_bps', 'cohort_seed', 'cycles', 'methods', 'offers', 'successor_research_cents', 'successor_expected_benefit_cents', 'continuation_funding_policy'}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError('EXACT_REGISTERED_CONFIGURATION_REQUIRED')
    if config['continuation_funding_policy'] not in ('EARNED_ONLY', 'AVAILABLE_NATIVE_CASH'):
        raise ValueError('DECLARED_CONTINUATION_FUNDING_POLICY_REQUIRED')
    if config['schema'] != 'genesis002/config/v1' or config['evidence_scope'] != 'AUTHORED_SYNTHETIC':
        raise ValueError('ONLY_EXPLICIT_SYNTHETIC_COMMERCE_SUPPORTED')
    for key in required - {'schema', 'evidence_scope', 'methods', 'offers', 'continuation_funding_policy'}:
        integer(config[key], key)
    if config['opening_cents'] <= config['working_reserve_cents']:
        raise ValueError('OPENING_MUST_EXCEED_PROTECTED_WORKING_RESERVE')
    if not 1 <= config['cycles'] or not 0 <= config['cohort_seed'] <= 10**15 - 101:
        raise ValueError('DECLARED_FINITE_DEMO_ENVELOPE_EXCEEDED')
    if config['fee_bps'] > 10_000 or config['tax_bps'] > 10_000:
        raise ValueError('INVALID_BASIS_POINTS')
    if config['setup_cents'] + config['discovery_cents'] > config['opening_cents'] - config['working_reserve_cents']:
        raise ValueError('UNFUNDED_INITIAL_RESEARCH')
    methods = config['methods']
    if not isinstance(methods, list) or not methods:
        raise ValueError('NONEMPTY_METHOD_PORTFOLIO_REQUIRED')
    seen = set()
    for method in methods:
        fields = {'id', 'adapter', 'access', 'supported_services', 'costs', 'construction_origin'}
        if not isinstance(method, dict) or set(method) != fields:
            raise ValueError('EXACT_METHOD_CONTRACT_REQUIRED')
        ident = text(method['id'], 'method.id', 80)
        if ident in seen:
            raise ValueError('DUPLICATE_METHOD')
        seen.add(ident)
        if method['adapter'] not in METHODS:
            raise ValueError('UNQUALIFIED_EXECUTION_ADAPTER')
        if method['access'] not in {'local_public_code', 'restricted', 'unverified'}:
            raise ValueError('EXPLICIT_ACCESS_STATUS_REQUIRED')
        if method['construction_origin'] not in {'existing', 'inherited', 'frontier_candidate'}:
            raise ValueError('EXPLICIT_METHOD_ORIGIN_REQUIRED')
        sids = method['supported_services']
        if not isinstance(sids, list) or not sids or len(sids) != len(set(sids)) or any(s not in SERVICES for s in sids):
            raise ValueError('SUPPORTED_SERVICE_SET_REQUIRED')
        if not isinstance(method['costs'], dict) or set(method['costs']) != set(COST_FIELDS):
            raise ValueError('COMPLETE_DECLARED_METHOD_COST_ENVELOPE_REQUIRED')
        for key in COST_FIELDS:
            integer(method['costs'][key], key)
    if not isinstance(config['offers'], list) or not config['offers']:
        raise ValueError('NONEMPTY_OPPORTUNITY_PORTFOLIO_REQUIRED')
    seen = set()
    for offer in config['offers']:
        fields = {'id', 'service_id', 'buyer_value_cents', 'outside_utility_cents',
                  'buyer_friction_cents', 'buyer_budget_cents', 'prices_cents', 'demand_evidence'}
        if not isinstance(offer, dict) or set(offer) != fields:
            raise ValueError('EXACT_OFFER_CONTRACT_REQUIRED')
        ident = text(offer['id'], 'offer.id', 80)
        if ident in seen:
            raise ValueError('DUPLICATE_OFFER')
        seen.add(ident)
        if offer['service_id'] not in SERVICES or offer['demand_evidence'] != 'hypothetical':
            raise ValueError('QUALIFIED_ADAPTER_AND_HYPOTHETICAL_DEMAND_REQUIRED')
        for key in ('buyer_value_cents', 'outside_utility_cents', 'buyer_friction_cents', 'buyer_budget_cents'):
            integer(offer[key], key)
        prices = offer['prices_cents']
        if not isinstance(prices, list) or not prices or len(prices) != len(set(prices)):
            raise ValueError('DISTINCT_FINITE_PRICE_SET_REQUIRED')
        for p in prices:
            integer(p, 'price', 1)


def fee(price: int, config: dict) -> int:
    """Explicit rounded-up modeled payment tariff, not a processor quotation."""
    return (price * config['fee_bps'] + 9_999) // 10_000 + config['fee_fixed_cents']


def options(config: dict, *, available_cents: int, earned_cents: int,
            earned_only: bool, qualification: dict[str, dict]) -> list[dict]:
    validate(config)
    integer(available_cents, 'available')
    integer(earned_cents, 'earned')
    rows = []
    for offer in config['offers']:
        cap = min(offer['buyer_budget_cents'], offer['buyer_value_cents'] -
                  offer['outside_utility_cents'] - offer['buyer_friction_cents'] - 1)
        for method in config['methods']:
            row = {'offer_id': offer['id'], 'service_id': offer['service_id'],
                   'method_id': method['id'], 'adapter': method['adapter'],
                   'status': 'UNAVAILABLE', 'price_cents': None, 'contribution_cents': None}
            if method['access'] != 'local_public_code':
                rows.append(row); continue
            if offer['service_id'] not in method['supported_services']:
                row['status'] = 'UNSUPPORTED'; rows.append(row); continue
            record = qualification.get(method['id'], {}).get(offer['service_id'])
            if not record or record.get('accepted') is not True:
                row['status'] = 'UNQUALIFIED'; rows.append(row); continue
            prices = [p for p in offer['prices_cents'] if p <= cap]
            if not prices:
                row['status'] = 'BUYER_DECLINES'; rows.append(row); continue
            # Each admitted method pays its complete declared carrying/integration burden.
            base = sum(method['costs'].values()) + config['acquisition_cents']
            candidates = []
            for price in prices:
                complete = base + fee(price, config)
                net = price - complete
                # Permanent native principal/fee protection may need seed backing.
                # A forecast contribution is never part of available cash.
                liquidity = max(price, LEGACY_TAIL_FEE_CENTS) + complete
                status = ('NO_POSITIVE_MARGIN' if net <= 0 else
                          'INSUFFICIENT_AVAILABLE_CASH' if available_cents < liquidity else
                          'INSUFFICIENT_EARNED_FUNDS' if earned_only and earned_cents < complete else
                          'ELIGIBLE_IN_MODEL')
                candidates.append({**row, 'status': status, 'price_cents': price,
                                   'complete_cost_cents': complete, 'fee_cents': fee(price, config),
                                   'contribution_cents': net, 'required_liquidity_cents': liquidity,
                                   'buyer_surplus_cents': offer['buyer_value_cents'] - price -
                                   offer['buyer_friction_cents'] - offer['outside_utility_cents']})
            eligible = [c for c in candidates if c['status'] == 'ELIGIBLE_IN_MODEL']
            rows.append(max(eligible or candidates, key=lambda c: (c['contribution_cents'], -c['price_cents'])))
    return rows


def select(config: dict, **kwargs) -> dict:
    rows = options(config, **kwargs)
    viable = [r for r in rows if r['status'] == 'ELIGIBLE_IN_MODEL']
    chosen = sorted(viable, key=lambda r: (-r['contribution_cents'], r['complete_cost_cents'],
                                         r['offer_id'], r['method_id']))[0] if viable else None
    return {'action': 'OPERATE' if chosen else 'NONENTRY', 'selected': chosen, 'alternatives': rows,
            'tie_break': 'lower complete cost then lexical identifiers; not a strategic theorem',
            'configuration_sha256': digest(config),
            'scope': 'Exact one-order finite complete-information price choice; authored demand and costs. '
                     'No portfolio-wide or open-world optimality, equilibrium, or real demand claim.'}


def startup_screen(config):
    """A finite-model upper-bound screen, not discovery or empirical demand proof.

    No feasibility or willingness-to-pay fact is inferred from this calculation.
    A negative optimistic bound is a reason not to pay for this registered route.
    A positive bound only admits qualification; it cannot authorize external trade.
    """
    validate(config)
    assumed={m['id']:{sid:{'accepted':True} for sid in m['supported_services']} for m in config['methods']}
    decision=select(config,available_cents=config['opening_cents']-config['working_reserve_cents']-config['setup_cents']-config['discovery_cents'],
                    earned_cents=0,earned_only=False,qualification=assumed)
    selected=decision['selected']
    total=(config['cycles']*selected['contribution_cents']-config['setup_cents']-config['discovery_cents']) if selected else None
    return {'action':'QUALIFY_CANDIDATE' if total is not None and total>0 else 'DECLINE_REGISTERED_STARTUP',
            'optimistic_pretax_surplus_cents':total,'configuration_sha256':digest(config),
            'assumptions':['every scheduled buyer purchases at the modeled price','listed production methods qualify',
                           'listed costs are complete within the authored model','liquidity still checked at each native action'],
            'scope':'Finite declared route screen only. No forecast is revenue or funding; positive screen is not a commercial claim.'}
