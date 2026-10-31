"""Exact finite leader/follower strategic-response calculation for native decisions.

Only an explicitly supplied, bounded synthetic game can be optimized. The
follower maximizes its declared cash payoff; tie responses are pessimistic for
the leader. This is NOT a calibrated market, dominant-strategy implementation,
proof of buyer incentive compatibility, or permission to commit native funds.
"""
from __future__ import annotations
from commercial.ledger import digest

SCHEMA = 'agi-alpha/strategic-game042/v1'
ACTION_IDS = ('continue_direct', 'partner_access', 'add_capacity')


def ensure(condition, error):
    if not condition:
        raise ValueError(error)


def amount(n, label, bound=10**15):
    ensure(type(n) is int and 0 <= n <= bound, 'GAME_BOUNDED_INTEGER_REQUIRED:' + label)
    return n


def identifier(value):
    ensure(type(value) is str and 0 < len(value) <= 36 and value.isascii()
           and value[0].islower() and all(c.islower() or c.isdigit() or c in '-_' for c in value),
           'GAME_SAFE_IDENTIFIER_REQUIRED')
    return value


def validate(game):
    ensure(type(game) is dict and set(game) == {'schema', 'objective', 'max_downside_microUSD',
                                                  'rival_margin_microUSD', 'supplier_minimum_microUSD',
                                                  'scenarios'}, 'EXACT_FINITE_GAME_SCHEMA_REQUIRED')
    ensure(game['schema'] == SCHEMA and game['objective'] == 'minimax_regret', 'SUPPORTED_GAME_OBJECTIVE_REQUIRED')
    for k in ('max_downside_microUSD', 'rival_margin_microUSD', 'supplier_minimum_microUSD'):
        amount(game[k], k)
    sc = game['scenarios']
    ensure(type(sc) is list and 1 <= len(sc) <= 8, 'FINITE_GAME_SCENARIOS_REQUIRED')
    seen = set(); weight = 0
    for s in sc:
        ensure(type(s) is dict and set(s) == {'id', 'weight_bps', 'demand_bps',
                  'supplier_reliability_bps', 'rival_responses'}, 'EXACT_GAME_SCENARIO_REQUIRED')
        ident = identifier(s['id']); ensure(ident not in seen, 'DUPLICATE_GAME_SCENARIO'); seen.add(ident)
        for k in ('weight_bps', 'demand_bps', 'supplier_reliability_bps'):
            amount(s[k], k, 10000)
        ensure(s['weight_bps'] > 0, 'POSITIVE_SCENARIO_WEIGHT_REQUIRED')
        weight += s['weight_bps']
        rs = s['rival_responses']
        ensure(type(rs) is list and 1 <= len(rs) <= 6, 'FINITE_RIVAL_RESPONSES_REQUIRED')
        names = set()
        for r in rs:
            ensure(type(r) is dict and set(r) == {'id', 'rival_capture_bps',
                                                      'response_cost_microUSD'}, 'EXACT_RIVAL_ACTION_REQUIRED')
            rid = identifier(r['id']); ensure(rid not in names, 'DUPLICATE_RIVAL_RESPONSE'); names.add(rid)
            amount(r['rival_capture_bps'], 'rival_capture_bps', 10000)
            amount(r['response_cost_microUSD'], 'response_cost_microUSD')
    ensure(weight == 10000, 'SCENARIO_WEIGHTS_SUM_10000_REQUIRED')
    return game


def validate_basis(basis):
    ensure(type(basis) is dict and 'continue_direct' in basis
           and set(basis) <= set(ACTION_IDS), 'CANONICAL_GAME_ACTION_SHORTLIST_REQUIRED')
    for ident, a in basis.items():
        ensure(type(a) is dict and set(a) == {'count', 'margin_microUSD',
                       'complete_incremental_cost_microUSD', 'native_invoice_microUSD', 'eligible'},
               'EXACT_GAME_ACTION_BASIS_REQUIRED')
        amount(a['count'], ident + ':count', 100000)
        for k in ('margin_microUSD','complete_incremental_cost_microUSD','native_invoice_microUSD'):
            amount(a[k], ident + ':' + k)
        ensure(type(a['eligible']) is bool, 'EXPLICIT_NATIVE_LIQUIDITY_ELIGIBILITY_REQUIRED')
    h = basis['continue_direct']
    ensure(h == {'count':0,'margin_microUSD':0,'complete_incremental_cost_microUSD':0,
                 'native_invoice_microUSD':0,'eligible':True}, 'CANONICAL_RETAIN_CASH_ACTION_REQUIRED')
    return basis


def scenario_outcome(action, scenario, game):
    """A follower's cash-maximizing response; tie is pessimistic for seller.

    Declared demand is an opt-in buyer participation prior, NOT observed
    willingness to pay. The actual native buyer remains free to refuse.
    """
    if action['count'] == 0:
        return {'rival_action': 'not_applicable', 'seller_net_microUSD':0,
                'rival_net_microUSD':0, 'gross_contribution_microUSD':0,
                'forecast_scope':'DECLARED_REDUCED_FORM_BUYER_PRIOR_NOT_NATIVE_BUYER_DECISION'}
    k = action['count']; market = k * scenario['demand_bps'] * scenario['supplier_reliability_bps']
    candidates=[]
    for r in scenario['rival_responses']:
        sold = market * (10000 - r['rival_capture_bps'])
        rival = market * r['rival_capture_bps']
        gross = sold * action['margin_microUSD'] // 10**12
        rival_net = rival * game['rival_margin_microUSD'] // 10**12 - r['response_cost_microUSD']
        seller_net = gross - action['complete_incremental_cost_microUSD']
        candidates.append({'rival_action':r['id'], 'seller_net_microUSD': seller_net,
                           'rival_net_microUSD':rival_net, 'gross_contribution_microUSD':gross,
                           'forecast_scope':'DECLARED_REDUCED_FORM_BUYER_PRIOR_NOT_NATIVE_BUYER_DECISION'})
    # The rival chooses its optimal cash payoff; a rival-indifferent response is
    # assumed to be worst for us. This closes optimistic tie-breaking loopholes.
    return sorted(candidates, key=lambda x:(-x['rival_net_microUSD'],
                                              x['seller_net_microUSD'],x['rival_action']))[0]


def solve(game, basis):
    """Exact minimax-regret choice after every modeled rival best response.

    No seller action can spend on a future receipt. The caller must enforce
    current native reservation and actual service/contract acceptance again.
    """
    validate(game);validate_basis(basis)
    eligible = {}
    reasons={}
    for name in ACTION_IDS:
        if name not in basis:continue
        a=basis[name]
        if not a['eligible']:
            reasons[name]='CURRENT_NATIVE_AVAILABLE_EARNINGS_INSUFFICIENT';continue
        if name == 'partner_access' and a['native_invoice_microUSD'] < game['supplier_minimum_microUSD']:
            reasons[name]='DECLARED_SUPPLIER_OUTSIDE_OPTION_NOT_MET';continue
        if name!='continue_direct' and (a['count']==0 or a['complete_incremental_cost_microUSD'] < a['native_invoice_microUSD']):
            reasons[name]='NO_PRODUCTIVE_OPPORTUNITY_OR_INCOMPLETE_COSTS';continue
        outcomes = {s['id']:scenario_outcome(a,s,game) for s in game['scenarios']}
        worst=min(x['seller_net_microUSD'] for x in outcomes.values())
        if worst < -game['max_downside_microUSD']:
            reasons[name]='DECLARED_MAX_DOWNSIDE_VIOLATION';continue
        expected_num=sum(s['weight_bps']*outcomes[s['id']]['seller_net_microUSD'] for s in game['scenarios'])
        eligible[name]={'scenarios':outcomes,'worst_net_microUSD':worst,
                        'expected_net_numerator_bps_microUSD':expected_num}
    ensure('continue_direct' in eligible, 'RETAIN_CASH_MUST_BE_FEASIBLE')
    maximum={s['id']:max(row['scenarios'][s['id']]['seller_net_microUSD'] for row in eligible.values())
             for s in game['scenarios']}
    for name,row in eligible.items():
        regret = {s['id']:maximum[s['id']] - row['scenarios'][s['id']]['seller_net_microUSD']
                  for s in game['scenarios']}
        row['max_regret_microUSD']=max(regret.values())
        row['regret_by_scenario_microUSD']=regret
    winner=min(eligible, key=lambda name:(eligible[name]['max_regret_microUSD'],
                           -eligible[name]['expected_net_numerator_bps_microUSD'],
                           basis[name]['native_invoice_microUSD'],
                           ACTION_IDS.index(name)))
    certificate={'schema':'agi-alpha/strategic-game042-certificate/v1','selected':winner,
       'optimality_scope':'EXACT_FINITE_PESSIMISTIC_FOLLOWER_BEST_RESPONSE_MINIMAX_REGRET_UNDER_DECLARED_SCENARIOS',
       'game_sha256':digest(game),'basis_sha256':digest(basis),
       'modeled_nature_information':'The rival observes the seller commitment and the declared scenario; seller observes only weights.',
       'explicit_outside_option':'continue_direct: zero incremental investment, ordinary native fulfillment remains eligible',
       'no_current_native_funding_authority':True,
       'eligible':eligible,'excluded':reasons,
       'scenario_best_attainable_net_microUSD':maximum,
       'selected_max_regret_microUSD':eligible[winner]['max_regret_microUSD'],
       'limitations':['Small finite reduced-form follower game, not a complete market equilibrium, buyer incentive-compatible auction or empirical conversion.',
          'Supplier participation floor and rival costs are authored premises; true rights/consent and partner utility are unverified.',
          'Forecasts do not finance actions; native liquidity, buyer choice, acceptance, collection and obligations remain authoritative.',
          'The search does not create a new physical or technical capability; it changes selection among implemented productive means.']}
    return certificate
