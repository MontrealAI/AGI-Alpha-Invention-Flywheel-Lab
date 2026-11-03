"""Independent voluntary bundle choice under explicit authored buyer assumptions.

This module does not inspect a seller policy, hidden market state or its profit.
It is a finite expected-utility calculation, not observed willingness to pay.
Capability 0/1 denotes the declared workflow stage, not an artificial free tier.
"""
from __future__ import annotations

from itertools import combinations
import hashlib
import json

PRODUCTS = ('self_hosted', 'group_webinar', 'founder_private')
MICRO_PER_CENT = 10_000
PERSONA_FIELDS = {'id', 'budget_cents', 'value_cents', 'software_setup_cents',
                  'webinar_learning_cents', 'founder_access_cents', 'switching_cents',
                  'buyer_compute_cents', 'webinar_setup_reduction_cents',
                  'private_session_prerequisites_met', 'required_capability', 'outside_options'}
OFFER_FIELDS = {'id', 'product', 'price_cents', 'capability', 'effort_cents',
                'trust_bps', 'reliability_bps'}
OUTSIDE_FIELDS = OFFER_FIELDS - {'product'}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(value, fields, label):
    if type(value) is not dict or set(value) != fields:
        raise ValueError('EXACT_MARKET_BUYER_FIELDS:' + label)


def _money(value):
    if type(value) is not int or value < 0:
        raise ValueError('NONNEGATIVE_INTEGER_CENTS_REQUIRED')


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise ValueError('NONEMPTY_BUYER_ID_REQUIRED')


def validate(persona, offers):
    _exact(persona, PERSONA_FIELDS, 'persona')
    _identifier(persona['id'])
    for key in PERSONA_FIELDS - {'id', 'outside_options', 'private_session_prerequisites_met', 'required_capability'}:
        _money(persona[key])
    if type(persona['private_session_prerequisites_met']) is not bool:
        raise ValueError('EXPLICIT_PRIVATE_SESSION_PREREQUISITES_REQUIRED')
    if type(persona['required_capability']) is not int or persona['required_capability'] not in (0, 1):
        raise ValueError('DECLARED_REQUIRED_WORKFLOW_STAGE_REQUIRED')
    if type(offers) is not list or len(offers) > 12:
        raise ValueError('FINITE_BUNDLE_COMPARISON_RESOURCE_BOUND_NOT_MARKET_CEILING')
    if type(persona['outside_options']) is not list or len(persona['outside_options']) > 8:
        raise ValueError('FINITE_OUTSIDE_COMPARISON_RESOURCE_BOUND')
    identities = []
    for rows, fields in ((offers, OFFER_FIELDS), (persona['outside_options'], OUTSIDE_FIELDS)):
        for row in rows:
            _exact(row, fields, 'offer_or_outside')
            _identifier(row['id'])
            identities.append(row['id'])
            if row['id'] == 'no_purchase':
                raise ValueError('NO_PURCHASE_IS_RESERVED_FREE_OUTSIDE_OPTION')
            _money(row['price_cents'])
            _money(row['effort_cents'])
            if type(row['capability']) is not int or row['capability'] not in (0, 1):
                raise ValueError('DECLARED_WORKFLOW_STAGE_REQUIRED')
            for key in ('trust_bps', 'reliability_bps'):
                if type(row[key]) is not int or not 0 <= row[key] <= 10_000:
                    raise ValueError('EXPLICIT_PROBABILITY_BASIS_POINTS_REQUIRED')
            if fields == OFFER_FIELDS and row['product'] not in PRODUCTS:
                raise ValueError('KNOWN_PRODUCT_REQUIRED')
    if len(identities) != len(set(identities)):
        raise ValueError('UNIQUE_OFFER_AND_OUTSIDE_IDENTITIES_REQUIRED')
    return persona, offers


def _probability(row):
    return row['trust_bps'] * row['reliability_bps']


def _expected(cents, probability_numerator):
    return cents * MICRO_PER_CENT * probability_numerator // 100_000_000


def _alternative(persona, bundle, outside):
    selected = {offer['product']: offer for offer in bundle}
    routes = list(bundle) + ([outside] if outside else [])
    # Sessions deliver learning or scoped access, not a completed deployment.
    # Only software or a complete outside method can earn ordinary outcome value.
    productive = ([selected['self_hosted']] if 'self_hosted' in selected else []) + ([outside] if outside else [])
    eligible = [r for r in productive if r['capability'] >= persona['required_capability']]
    ordinary_probability = max((_probability(r) for r in eligible), default=0)
    ordinary_value = _expected(persona['value_cents'], ordinary_probability)
    access_value = (_expected(persona['founder_access_cents'], _probability(selected['founder_private']))
                    if 'founder_private' in selected else 0)
    setup = persona['software_setup_cents'] * MICRO_PER_CENT if 'self_hosted' in selected else 0
    learning = persona['webinar_learning_cents'] * MICRO_PER_CENT if 'group_webinar' in selected else 0
    saving = 0
    if ('group_webinar' in selected and
            selected['group_webinar']['capability'] >= persona['required_capability']):
        # A webinar can ease one relevant route. Do not add two savings merely
        # because a bundle redundantly includes software and an outside method.
        learning_burdens = []
        if selected.get('self_hosted') in eligible:
            learning_burdens.append(persona['software_setup_cents'])
        if outside is not None and outside in eligible:
            learning_burdens.append(outside['effort_cents'])
        bounded_benefit = min(persona['webinar_setup_reduction_cents'], max(learning_burdens, default=0))
        saving = _expected(bounded_benefit, _probability(selected['group_webinar']))
    outside_price = outside['price_cents'] * MICRO_PER_CENT if outside else 0
    compute = persona['buyer_compute_cents'] * MICRO_PER_CENT if eligible else 0
    cash_operating = outside_price + compute
    effort = (sum(r['effort_cents'] for r in routes) + persona['switching_cents']) * MICRO_PER_CENT
    adoption = cash_operating + effort + setup + learning - saving
    lineitems = [{'id': r['id'], 'product': r['product'], 'price_microUSD': r['price_cents'] * MICRO_PER_CENT}
                 for r in sorted(bundle, key=lambda row: row['id'])]
    price = sum(r['price_microUSD'] for r in lineitems)
    ident = 'choice-' + _digest({'offers': [r['id'] for r in lineitems], 'outside': outside['id'] if outside else None})[:24]
    row = {'id': ident, 'offers': lineitems, 'value_before_fees_microUSD': ordinary_value + access_value,
           'adoption_operating_cost_microUSD': adoption, 'cash_operating_cost_microUSD': cash_operating,
           'net_utility_microUSD': ordinary_value + access_value - price - adoption}
    explanation = {'outside_id': outside['id'] if outside else None, 'ordinary_outcome_value_microUSD': ordinary_value,
                   'founder_access_value_microUSD': access_value, 'complementary_setup_saving_microUSD': saving,
                   'noncash_adoption_effort_microUSD': effort + setup + learning - saving,
                   'buyer_compute_cost_microUSD': compute, 'outside_cash_price_microUSD': outside_price,
                   'seller_price_microUSD': price, 'cash_outlay_microUSD': price + cash_operating,
                   'affordable': price + cash_operating <= persona['budget_cents'] * MICRO_PER_CENT}
    return row, explanation


def decide(persona, offers):
    """Enumerate full bundles with at most one version of each product.

    Ordinary outcome value is counted once, using the strongest qualified
    software/outside route. Sessions alone cannot earn deployment value.
    Redundant routes do not receive invented independent-failure diversification.
    Trust times reliability is an explicitly authored effective success belief.
    Prices and attempt effort are charged even when expected value is discounted;
    hypothetical later refunds are not spent or assumed as current buyer cash.
    """
    validate(persona, offers)
    no_purchase = {'id': 'no_purchase', 'offers': [], 'value_before_fees_microUSD': 0,
                   'adoption_operating_cost_microUSD': 0, 'cash_operating_cost_microUSD': 0,
                   'net_utility_microUSD': 0}
    alternatives = [no_purchase]
    detail = {'no_purchase': {'outside_id': 'no_purchase', 'ordinary_outcome_value_microUSD': 0,
                              'founder_access_value_microUSD': 0, 'complementary_setup_saving_microUSD': 0,
                              'noncash_adoption_effort_microUSD': 0, 'buyer_compute_cost_microUSD': 0,
                              'outside_cash_price_microUSD': 0, 'seller_price_microUSD': 0,
                              'cash_outlay_microUSD': 0, 'affordable': True}}
    usable = sorted((r for r in offers if r['product'] != 'founder_private' or persona['private_session_prerequisites_met']),
                    key=lambda r: r['id'])
    outside_options = [None] + sorted(persona['outside_options'], key=lambda r: r['id'])
    for count in range(0, len(PRODUCTS) + 1):
        for bundle in combinations(usable, count):
            if len({r['product'] for r in bundle}) != len(bundle):
                continue
            for outside in outside_options:
                if not bundle and outside is None:
                    continue
                row, explanation = _alternative(persona, bundle, outside)
                alternatives.append(row)
                detail[row['id']] = explanation
    feasible = [row for row in alternatives if detail[row['id']]['affordable']]
    selected = min(feasible, key=lambda row: (-row['net_utility_microUSD'], row['id'] != 'no_purchase',
                                             bool(row['offers']), detail[row['id']]['cash_outlay_microUSD'],
                                             len(row['offers']), row['id']))
    outside_best = max(row['net_utility_microUSD'] for row in feasible if not row['offers'])
    return {'schema': 'omega/buyer-choice-comparison/v1', 'persona_id': persona['id'],
            'inputs_sha256': _digest({'persona': persona, 'offers': offers}), 'selected_id': selected['id'],
            'selected_offer_ids': [r['id'] for r in selected['offers']], 'consent': False,
            'budget_microUSD': persona['budget_cents'] * MICRO_PER_CENT,
            'value_before_fees_microUSD': selected['value_before_fees_microUSD'],
            'buyer_net_benefit_microUSD': selected['net_utility_microUSD'],
            'best_outside_net_utility_microUSD': outside_best,
            'increment_over_best_outside_microUSD': selected['net_utility_microUSD'] - outside_best,
            'selected_detail': detail[selected['id']], 'alternatives': alternatives,
            'reason_decline': ('NO_POSITIVE_NET_BENEFIT' if selected['id'] == 'no_purchase' else
                               'OUTSIDE_OPTION_WEAKLY_BETTER' if not selected['offers'] else None),
            'scope': 'AUTHORED_EXPECTED_UTILITY_NOT_DEMAND_CONSENT_OR_EARNED_REVENUE',
            'expected_value_rounding': 'Each expected benefit rounds down to one microUSD; inputs use integer USD cents.'}


def to_receipt(persona, offers, offer_id, *, consent, choice_id=None):
    """Bind one native line item to an explicitly consented complete choice.

    Every line item of one bundle must carry the same receipt apart from offer_id.
    The native adapter must verify bundle completion before releasing payments.
    This receipt is simulation input, never authorization to spend actual money.
    """
    if type(consent) is not bool:
        raise ValueError('EXPLICIT_BOOLEAN_BUYER_CONSENT_REQUIRED')
    decision = decide(persona, offers)
    if offer_id not in decision['selected_offer_ids']:
        raise ValueError('LINE_ITEM_NOT_IN_VOLUNTARY_SELECTED_BUNDLE')
    choice_id = persona['id'] if choice_id is None else choice_id
    _identifier(choice_id)
    return {'schema': 'omega/voluntary-choice/v1', 'choice_id': choice_id, 'offer_id': offer_id,
            'selected_id': decision['selected_id'], 'selected_offer_ids': decision['selected_offer_ids'],
            'consent': consent, 'budget_microUSD': decision['budget_microUSD'],
            'alternatives': decision['alternatives']}


def verify_quote_receipt(persona, offers, receipt):
    """Reject altered quotes, budgets, alternative utilities and inferred consent."""
    _exact(receipt, {'schema', 'choice_id', 'offer_id', 'selected_id', 'selected_offer_ids',
                     'consent', 'budget_microUSD', 'alternatives'}, 'receipt')
    if receipt['schema'] != 'omega/voluntary-choice/v1' or receipt['consent'] is not True:
        raise ValueError('EXPLICIT_CONSENTED_CHOICE_REQUIRED')
    expected = to_receipt(persona, offers, receipt['offer_id'], consent=True, choice_id=receipt['choice_id'])
    if _canonical(receipt) != _canonical(expected):
        raise ValueError('BUYER_QUOTE_OR_CHOICE_CHANGED')
    return {'accepted': True, 'choice_id': receipt['choice_id'], 'offer_id': receipt['offer_id'],
            'receipt_sha256': _digest(receipt), 'scope': 'SIMULATED_CHOICE_CONSISTENCY_NOT_REAL_BUYER_CONSENT'}
