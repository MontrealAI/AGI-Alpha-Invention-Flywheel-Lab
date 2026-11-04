"""Finite, source-bound economic-game constructor. Research only; no native account authority.

Synthesizes complementary operating arrangements, solves a declared Stackelberg
seller/rival/buyer game exactly, and preserves refusal, cash and negative cases.
All input preferences and costs are PUBLIC AUTHOR-ASSUMED common knowledge, not
learned private buyer data, real demand, or proof of an invented physical means.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from itertools import combinations
import json
from pathlib import Path

from mechanism_harness.core import canonical, digest

SCHEMA = 'agi-alpha/economic-game-maker/v1'
MAX_OPERATORS = 12
MAX_BUYERS = 12
MAX_SCENARIOS = 12
MAX_PRICE_GRID = 40


def integer(v, lo=0, hi=10**9):
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError('FINITE_EXACT_INTEGER_REQUIRED')
    return v


def exact(v, keys, label):
    if type(v) is not dict or set(v) != set(keys):
        raise ValueError('EXACT_' + label + '_FIELDS_REQUIRED')


def validate(spec):
    exact(spec, {'schema','basis','outcome','opening_cash','protected_cash','buyer_profiles',
                 'production','operators','rival','scenarios','price_grid','limits'}, 'GAME')
    if spec['schema'] != SCHEMA or spec['basis'] != 'DECLARED_COMPLETE_INFORMATION_SYNTHETIC':
        raise ValueError('EXPLICIT_SYNTHETIC_INFORMATION_BASIS_REQUIRED')
    if not isinstance(spec['outcome'], str) or not spec['outcome'].strip():
        raise ValueError('FIXED_ACCEPTED_OUTCOME_REQUIRED')
    opening = integer(spec['opening_cash']); protected = integer(spec['protected_cash'])
    if protected > opening: raise ValueError('PROTECTED_CASH_EXCEEDS_OPENING')
    buyers = spec['buyer_profiles']
    if type(buyers) is not list or not 1 <= len(buyers) <= MAX_BUYERS:
        raise ValueError('BOUNDED_BUYERS_REQUIRED')
    ids = []
    for b in buyers:
        exact(b, {'id','value','budget','outside_utility'}, 'BUYER')
        if type(b['id']) is not str or not b['id'] or len(b['id']) > 60:
            raise ValueError('BUYER_ID_REQUIRED')
        ids.append(b['id'])
        for k in ('value','budget','outside_utility'): integer(b[k])
    if ids != sorted(set(ids)): raise ValueError('SORTED_UNIQUE_BUYERS_REQUIRED')
    prod = spec['production']
    exact(prod, {'fixed','unit','quote'}, 'PRODUCTION')
    for v in prod.values(): integer(v)
    operators = spec['operators']
    if type(operators) is not list or len(operators) > MAX_OPERATORS:
        raise ValueError('BOUNDED_OPERATORS_REQUIRED')
    names = []
    for op in operators:
        exact(op, {'id','requires','exclusive','fixed_delta','unit_delta','build','partner_payment','partner_outside'}, 'OPERATOR')
        if type(op['id']) is not str or not op['id'] or len(op['id'])>60:
            raise ValueError('OPERATOR_ID_REQUIRED')
        names.append(op['id'])
        if type(op['requires']) is not list or len(set(op['requires'])) != len(op['requires']):
            raise ValueError('UNIQUE_OPERATOR_REQUIREMENTS_REQUIRED')
        if type(op['exclusive']) is not str: raise ValueError('EXCLUSION_GROUP_REQUIRED')
        for k in ('fixed_delta','unit_delta'): integer(op[k], -10**9, 10**9)
        for k in ('build','partner_payment','partner_outside'): integer(op[k])
    if names != sorted(set(names)) or any(set(op['requires']) - set(names) for op in operators):
        raise ValueError('SORTED_UNIQUE_OPERATORS_AND_KNOWN_DEPENDENCIES_REQUIRED')
    rival = spec['rival']
    exact(rival, {'fixed','unit','quote','price_grid'}, 'RIVAL')
    for k in ('fixed','unit','quote'): integer(rival[k])
    for grid in (spec['price_grid'], rival['price_grid']):
        if type(grid) is not list or not 1 <= len(grid) <= MAX_PRICE_GRID or grid != sorted(set(grid)):
            raise ValueError('FINITE_SORTED_PRICE_GRID_REQUIRED')
        for p in grid: integer(p,1)
    scenarios = spec['scenarios']
    if type(scenarios) is not list or not 1 <= len(scenarios) <= MAX_SCENARIOS:
        raise ValueError('BOUNDED_SCENARIOS_REQUIRED')
    seen = []
    for s in scenarios:
        exact(s, {'id','weight_bps','active_buyers','rival_can_copy','accepted','collected','fixed_extra','unit_extra'}, 'SCENARIO')
        if type(s['id']) is not str or not s['id']: raise ValueError('SCENARIO_ID_REQUIRED')
        seen.append(s['id']); integer(s['weight_bps'],1,10000)
        if type(s['active_buyers']) is not list or s['active_buyers'] != sorted(set(s['active_buyers'])) or set(s['active_buyers'])-set(ids):
            raise ValueError('DECLARED_AVAILABLE_BUYERS_REQUIRED')
        if any(type(s[k]) is not bool for k in ('rival_can_copy','accepted','collected')) or (s['collected'] and not s['accepted']):
            raise ValueError('ACCEPTANCE_COLLECTION_STATES_CONFLICT')
        integer(s['fixed_extra']); integer(s['unit_extra'])
    if seen != sorted(set(seen)) or sum(s['weight_bps'] for s in scenarios) != 10000:
        raise ValueError('SORTED_WEIGHTED_SCENARIOS_REQUIRED')
    limits=spec['limits']; exact(limits, {'max_operators','max_states','max_loss','downside_penalty_bps'}, 'LIMITS')
    integer(limits['max_operators'],0,MAX_OPERATORS)
    integer(limits['max_states'],1,50000)
    integer(limits['max_loss']); integer(limits['downside_penalty_bps'],0,10000)
    return spec


def ordered_subset(ops, selected):
    pending = set(selected); order=[]; exclusive=[]
    while pending:
        ready = sorted(k for k in pending if set(ops[k]['requires']) <= set(order))
        if not ready: return None
        k=ready[0]; order.append(k); pending.remove(k)
        group=ops[k]['exclusive']
        if group:
            if group in exclusive: return None
            exclusive.append(group)
        op=ops[k]
        if op['partner_payment'] < op['partner_outside']: return None
    return tuple(order)


def cost_terms(spec, ordered, s):
    ops = {o['id']:o for o in spec['operators']}
    fixed = spec['production']['fixed'] + s['fixed_extra'] + sum(ops[k]['fixed_delta'] for k in ordered)
    unit = spec['production']['unit'] + s['unit_extra'] + sum(ops[k]['unit_delta'] for k in ordered)
    build = sum(ops[k]['build'] for k in ordered)
    partner = sum(ops[k]['partner_payment'] for k in ordered)
    if min(fixed,unit) < 0: return None
    return {'fixed':fixed,'unit':unit,'build':build,'partner_payment':partner,'quote':spec['production']['quote']}


def choices(buyers,active,seller_price,rival_price):
    ours=[]; rivals=[]; gain=0
    for b in buyers:
        if b['id'] not in active: continue
        u_ours=b['value']-seller_price if seller_price <= b['budget'] else -10**18
        u_rival=b['value']-rival_price if rival_price is not None and rival_price <= b['budget'] else -10**18
        outside=b['outside_utility']
        # Ties belong to a competent outside option or a responding rival.
        if u_ours > max(outside,u_rival):
            ours.append(b['id']);gain += u_ours-outside
        elif u_rival>outside and u_rival>=u_ours:
            rivals.append(b['id'])
    return ours,rivals,gain


def _admit_candidate(spec, ordered, quote):
    """Normalize a public proposal to a state in the declared seller grammar."""
    validate(spec)
    operators = {op['id']: op for op in spec['operators']}
    if (not isinstance(ordered, (list, tuple)) or
            len(ordered) > spec['limits']['max_operators'] or
            any(type(name) is not str or name not in operators for name in ordered) or
            len(set(ordered)) != len(ordered)):
        raise ValueError('ADMISSIBLE_OPERATOR_SELECTION_REQUIRED')
    order = ordered_subset(operators, ordered)
    if order is None:
        raise ValueError('ADMISSIBLE_OPERATOR_SELECTION_REQUIRED')
    if type(quote) is not int or quote not in spec['price_grid']:
        raise ValueError('DECLARED_SELLER_PRICE_REQUIRED')
    return order


def follower(spec, ordered, s, quote):
    """Return the rival's best response conditional on an admitted seller proposal."""
    order = _admit_candidate(spec, ordered, quote)
    if not any(canonical(s) == canonical(scenario) for scenario in spec['scenarios']):
        raise ValueError('DECLARED_RIVAL_SCENARIO_REQUIRED')
    return _follower(spec, order, s, quote)


def _follower(spec, ordered, s, quote):
    buyers = spec['buyer_profiles']
    active = set(s['active_buyers'])
    rival = spec['rival']
    # Each plan's costs are (fixed, unit, build, partner payment).
    plans = [('unchanged', rival['fixed'], rival['unit'], 0, 0)]
    if s['rival_can_copy'] and ordered:
        selected = [op for op in spec['operators'] if op['id'] in ordered]
        fixed = rival['fixed'] + sum(op['fixed_delta'] for op in selected)
        unit = rival['unit'] + sum(op['unit_delta'] for op in selected)
        if min(fixed, unit) >= 0:
            plans.append(('copy', fixed, unit, sum(op['build'] for op in selected),
                          sum(op['partner_payment'] for op in selected)))

    ours, rivals, gain = choices(buyers, active, quote, None)
    best = (0, -len(ours), False, 0)
    response = {'quote': None, 'rival_profit': 0, 'tactic': 'nonentry',
                'seller_buyers': ours, 'rival_buyers': rivals, 'buyer_gain_over_outside': gain}
    for price in rival['price_grid']:
        # Buyer allocation depends on prices and outside options. Both production
        # plans deliver the same specified outcome, so they share this allocation.
        ours, rivals, gain = choices(buyers, active, quote, price)
        n = len(rivals)
        for tactic, fixed, unit, build, partner in plans:
            cost = rival['quote'] + build + (fixed + n * unit + partner if n else 0)
            net = n * price - cost
            rank = (net, -len(ours), True, price)
            if rank > best:  # An exact same-price plan tie keeps the incumbent.
                best = rank
                response = {'quote': price, 'rival_profit': net, 'tactic': tactic,
                            'seller_buyers': ours, 'rival_buyers': rivals, 'buyer_gain_over_outside': gain}
    return response


def evaluate(spec, ordered, price):
    """Score one admitted candidate; invent separately screens its reported worst loss."""
    return _evaluate(spec, _admit_candidate(spec, ordered, price), price)


def _evaluate(spec,ordered,price):
    rows=[]
    for s in spec['scenarios']:
        terms=cost_terms(spec,ordered,s)
        if terms is None:return None
        response=_follower(spec,ordered,s,price)
        n=len(response['seller_buyers']); sunk=terms['quote']+terms['build']
        full_cost=sunk+(terms['fixed']+terms['unit']*n+terms['partner_payment'] if n else 0)
        opening=spec['opening_cash']; protected=spec['protected_cash']
        if full_cost>opening-protected: return None  # pre-collection liquidity, including refusals
        delivered=bool(n) and s['accepted']
        recognized=n*price if delivered else 0
        collected=recognized if s['collected'] else 0
        profit=recognized-full_cost
        cash_end=opening-full_cost+collected
        if cash_end<protected: return None
        rows.append({'scenario':s['id'],'weight_bps':s['weight_bps'],'rival_quote':response['quote'],
                     'rival_profit':response['rival_profit'],'rival_tactic':response['tactic'],'won':response['seller_buyers'],
                     'rival_won':response['rival_buyers'],'buyer_gain_over_outside':response['buyer_gain_over_outside'] if delivered else 0,
                     'accepted':delivered,'recognized':recognized,'collected':collected,
                     'full_cost':full_cost,'profit':profit,'cash_end':cash_end,
                     'unrestricted_cash_end':cash_end-protected})
    expected=sum((Fraction(row['weight_bps']*row['profit'],10000) for row in rows),Fraction(0))
    downside=max(0,-min(row['profit'] for row in rows))
    return {'operators':list(ordered),'quote':price,'scenarios':rows,'expected_profit':str(expected),
            'worst_loss':downside,'risk_adjusted':str(expected-Fraction(spec['limits']['downside_penalty_bps']*downside,10000))}


def invent(spec):
    """Exact solution over a generated finite grammar, NOT an optimal real economy."""
    validate(spec); ops={o['id']:o for o in spec['operators']}
    entries=[]; enumerated=0; feasible=0
    for k in range(min(len(ops),spec['limits']['max_operators'])+1):
        for selected in combinations(sorted(ops),k):
            ordered=ordered_subset(ops,selected)
            if ordered is None: continue
            for quote in spec['price_grid']:
                if enumerated >= spec['limits']['max_states']:
                    return {'schema':SCHEMA+'/result','status':'SEARCH_BOUND_EXHAUSTED',
                            'spec_sha256':digest(spec),'states_evaluated':enumerated,'winner':None,
                            'scope':'NO_OPTIMALITY_CERTIFICATE_AND_NO_FINANCIAL_AUTHORITY'}
                enumerated+=1
                result=_evaluate(spec,ordered,quote)
                if result is None: continue
                feasible+=1
                if result['worst_loss'] <= spec['limits']['max_loss']:entries.append(result)
    # Non-entry is a true feasible alternative. Every built alternative pays sunk costs.
    hold={'operators':[],'quote':None,'scenarios':[{'scenario':s['id'],'profit':0,'unrestricted_cash_end':spec['opening_cash']-spec['protected_cash']} for s in spec['scenarios']],
          'expected_profit':'0','worst_loss':0,'risk_adjusted':'0'}
    winner=max([hold,*entries],key=lambda x:(Fraction(x['risk_adjusted']),Fraction(x['expected_profit']),-len(x['operators']),-(x['quote'] or 0)))
    return {'schema':SCHEMA+'/result','status':'EXACT_DECLARED_FINITE_GAME_OPTIMUM',
            'spec_sha256':digest(spec),'states_evaluated':enumerated,'feasible_states':feasible,
            'eligible_states':len(entries),'winner':winner,
            'optimality_gap_fraction':'0','strong_same_grammar_comparator':'EXACT_TIE_BY_IDENTICAL_FEASIBLE_ACTIONS',
            'scope':'Declared synthetic common-knowledge Stackelberg game; prospective mechanism compositions only. No buyer observations, real contracts, physical qualification, competitive moat, native settlement or authority.'}


def rederive(spec,report):
    expected=invent(spec)
    payload={key:value for key,value in report.items() if key!='replay'}
    if canonical(expected)!=canonical(payload):
        raise ValueError('SOURCE_BOUND_COMPLETE_GAME_CERTIFICATE_CHANGED')
    receipt={'accepted':True,'spec_sha256':digest(spec),'report_sha256':digest(payload),
             'scope':'DETERMINISTIC_REDERIVATION_NOT_INDEPENDENT_ECONOMIC_VERIFICATION'}
    if 'replay' in report and report['replay'] != receipt:
        raise ValueError('SOURCE_BOUND_REPLAY_RECEIPT_CHANGED')
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('Output exists; preserve prior evidence')
    spec=json.loads(args.spec.read_text(encoding='utf-8'))
    report=invent(spec)
    report['replay']=rederive(spec,report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(canonical(report)+b'\n')
    print(json.dumps({'status':report['status'],'winner':report['winner'],'report':str(args.output)},indent=2))

if __name__=='__main__':main()
