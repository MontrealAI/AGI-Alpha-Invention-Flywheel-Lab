#!/usr/bin/env python3
"""Exact, authored studies accompanying ALPHA GENESIS FLYWHEEL OMEGA.

Standard library only. No model calls, network, hardware, or real transactions.
The supplied response laws, search grammar, update events, costs and prices are
illustrative assumptions, not measured performance of the proposed product.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
from itertools import product, permutations
from pathlib import Path
import csv
import json
import math
from typing import Iterable

EDITION = "1.1.0"


def require(condition: bool, message: str) -> None:
    """An executed scientific check: never disabled by python -O."""
    if not condition:
        raise ValueError(message)


def exact(value) -> F:
    """Accept exact rational inputs, not booleans or binary floating-point guesses."""
    if isinstance(value, bool) or not isinstance(value, (int, str, F)):
        raise ValueError("Use integers, fraction strings or Fraction values.")
    try:
        return F(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid rational value.") from exc


def vector2(values) -> tuple[F, F]:
    values = tuple(values)
    if len(values) != 2:
        raise ValueError("Exactly two components are required.")
    return exact(values[0]), exact(values[1])


def matrix2(rows) -> tuple[tuple[F, F], tuple[F, F]]:
    rows = tuple(rows)
    if len(rows) != 2:
        raise ValueError("Exactly two observation rows are required.")
    return vector2(rows[0]), vector2(rows[1])

Row = tuple[F, F]

def inverse2(rows: tuple[Row, Row]) -> tuple[Row, Row]:
    (a, b), (c, d) = matrix2(rows)
    determinant = a*d-b*c
    if not determinant:
        raise ValueError('The observation matrix is singular.')
    return ((d/determinant, -b/determinant), (-c/determinant, a/determinant))

def apply(rows: tuple[Row, Row], vector: Row) -> Row:
    rows, vector = matrix2(rows), vector2(vector)
    return (sum(a*b for a,b in zip(rows[0],vector)),
            sum(a*b for a,b in zip(rows[1],vector)))

def bound(inv: tuple[Row, Row], epsilon: F) -> F:
    inv, epsilon = matrix2(inv), exact(epsilon)
    if epsilon < 0:
        raise ValueError('Noise bound must be nonnegative.')
    return epsilon * max(sum(abs(v) for v in row) for row in inv)

def instrument_study() -> dict:
    baseline=(F(1),F(1)); epsilon=F(1,10)
    rows=[(F(a),F(b)) for a,b in product((-1,0,1),repeat=2) if (a,b)!=(0,0)]
    candidates=[]
    for row in rows:
        try:
            inv=inverse2((baseline,row)); radius=bound(inv,epsilon)
            candidates.append({'row':list(map(str,row)), 'rank':2, 'radius':str(radius)})
        except ValueError:
            candidates.append({'row':list(map(str,row)), 'rank':1, 'radius':None})
    valid=[x for x in candidates if x['rank']==2]
    # Minimize the certified infinity-norm radius; prefer positive first coefficient
    # only to choose between algebraically equivalent signed observations.
    winner=min(valid,key=lambda x:(F(x['radius']),-F(x['row'][0]),F(x['row'][1])))
    row=tuple(F(x) for x in winner['row'])
    matrix=(baseline,row); inv=inverse2(matrix)
    states=list(product(map(F,range(-2,3)),repeat=2))
    noises=list(product((-epsilon,F(0),epsilon),repeat=2))
    worst=F(0); count=0
    for state in states:
        for noise in noises:
            clean=apply(matrix,state)
            observed=tuple(a+b for a,b in zip(clean,noise))
            estimate=apply(inv,observed)
            error=max(abs(a-b) for a,b in zip(estimate,state))
            worst=max(worst,error); count+=1
            require(error <= epsilon, "Observer exceeded its supplied noise bound.")
    # A second implementation uses the ordinary sum-and-difference formula.
    conventional_matches=all(
        apply(inv,(F(x),F(y))) == ((F(x)+F(y))/2,(F(x)-F(y))/2)
        for x,y in product(range(-4,5),repeat=2))
    # Third mechanism d affects both observations: its contribution aliases s.
    unseen=F(1,2)
    third_mechanism_error=max(abs(x) for x in apply(inv,(unseen,unseen)))
    # An inherited formula produces four supplied coefficient variants. This is
    # algebraic reuse, not autonomous discovery or an empirical cross-domain test.
    successor_cases=0
    for k in range(2,6):
        m=((F(1),F(k)),(F(1),F(-k)))
        for s,c in product(map(F,range(-3,4)),repeat=2):
            for n1,n2 in noises:
                y=apply(m,(s,c)); estimates=((y[0]+n1+y[1]+n2)/2,(y[0]+n1-y[1]-n2)/(2*k))
                require(abs(estimates[0]-s) <= epsilon, "Successor first-coordinate bound failed.")
                require(abs(estimates[1]-c) <= epsilon/k, "Successor second-coordinate bound failed.")
                successor_cases+=1
    return {'status':'EXACT_AUTHORED_LINEAR_MODEL', 'candidate_count':len(rows),
            'full_rank_candidates':len(valid), 'candidates':candidates,
            'selected_row':winner['row'], 'worst_error':str(worst),
            'enumerated_state_noise_cases':count, 'conventional_control_matches':conventional_matches,
            'baseline_indistinguishable_states':[['-2','2'],['2','-2']],
            'baseline_minimax_error_lower_bound':'2',
            'third_mechanism_error':str(third_mechanism_error),
            'third_mechanism_verdict':'OUTSIDE_MODEL_NOT_QUALIFIED',
            'supplied_successor_variants':4, 'successor_algebra_cases':successor_cases,
            'scope':'No EIT forward solver, physical measurement, frontier-model discovery, or commercial result.'}

REQUIREMENTS={
 'A':{'representation'}, 'B':{'geometry'}, 'C':{'control'}, 'D':{'material'},
 'E':{'representation','geometry'}, 'F':{'measurement'},
 'G':{'representation','measurement'}, 'H':{'chemistry'}}
RELEASES=[{'representation'},{'geometry'},{'presentation'},{'measurement'}]

def replay(mode: str, requirements=None, releases=None) -> dict:
    requirements = requirements if requirements is not None else REQUIREMENTS
    releases = releases if releases is not None else RELEASES
    if mode not in ('blanket','dependency'):
        raise ValueError('Mode must be blanket or dependency.')
    available=set(); complete=set(); evaluations=0; trace=[]
    for i,delta in enumerate(releases,1):
        available |= set(delta)
        pending=sorted(set(requirements)-complete)
        chosen=pending if mode=='blanket' else [k for k in pending if set(requirements[k])<=available]
        passed=[k for k in chosen if set(requirements[k])<=available]
        evaluations+=len(chosen); complete.update(passed)
        trace.append({'release':i,'new':sorted(delta),'evaluated':chosen,'completed':passed})
    return {'mode':mode,'evaluations':evaluations,'completed':sorted(complete),'trace':trace}

def conventional_schedule(requirements, releases) -> dict:
    """Independent static oracle: compute the first event satisfying each job.

    Unlike replay(), this computes a per-job earliest release from cumulative
    release prefixes, then assembles a schedule. It never calls replay().
    """
    available = set()
    prefixes = []
    for released in releases:
        available = available.union(set(released))
        prefixes.append(frozenset(available))
    earliest = {}
    for name, needs in requirements.items():
        for event, supplied in enumerate(prefixes):
            if all(need in supplied for need in needs):
                earliest[name] = event
                break
    trace = []
    for event, released in enumerate(releases):
        names = sorted(name for name, first in earliest.items() if first == event)
        trace.append({'release':event+1, 'new':sorted(released), 'evaluated':names, 'completed':names.copy()})
    return {'mode':'independent_earliest_feasible', 'evaluations':len(earliest),
            'completed':sorted(earliest), 'trace':trace}


def replay_margin(blanket: int, selective: int, evaluation_cost, routing_cost, missed_value) -> F:
    """Conditional net saving. All monetary-equivalent inputs are stipulated."""
    for count in (blanket, selective):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('Evaluation counts must be nonnegative integers.')
    c, k, loss = map(exact, (evaluation_cost, routing_cost, missed_value))
    if min(c,k,loss) < 0:
        raise ValueError('Costs and forgone value must be nonnegative.')
    return (blanket-selective)*c-k-loss


def audit_access_trace(requirements, events) -> list[dict]:
    """A finite reference state machine, not a deployed permission controller.

    add/remove are explicit capability changes. announced is informational only.
    Historical qualification is preserved separately from present eligibility.
    """
    available=set(); qualified=set(); previous_eligible=set(); trace=[]
    for index,event in enumerate(events,1):
        additions, removals=set(event.get('add',())),set(event.get('remove',()))
        if additions & removals:
            raise ValueError('An event cannot add and remove the same capability.')
        available=(available-removals)|additions
        eligible={name for name,needs in requirements.items() if set(needs)<=available}
        newly_qualified=eligible-qualified
        qualified.update(eligible)
        trace.append({'event':index, 'announced':sorted(event.get('announced',())),
            'accessible':sorted(available), 'eligible_now':sorted(eligible),
            'historically_qualified':sorted(qualified),
            'newly_qualified':sorted(newly_qualified),
            'suspended':sorted(previous_eligible-eligible)})
        previous_eligible=eligible
    return trace


def adversarial_replay_study() -> dict:
    events=[{'announced':['solver']}, {'add':['solver']}, {'remove':['solver']}, {'add':['solver']}]
    history=audit_access_trace({'job':{'solver'}}, events)
    require(history[0]['eligible_now'] == [], 'Announcement wrongly granted access.')
    require(history[1]['eligible_now'] == ['job'], 'Available dependency not admitted.')
    require(history[2]['eligible_now'] == [] and history[2]['historically_qualified'] == ['job'],
            'Revocation or history preservation failed.')
    # The supplied index is wrong: an alternative operation satisfies the same task.
    recorded={'task':{'old_solver'}}
    actual_routes={'task':[{'old_solver'},{'new_representation'}]}
    available={'new_representation'}
    routed={key for key,needed in recorded.items() if needed<=available}
    attainable={key for key,routes in actual_routes.items() if any(route<=available for route in routes)}
    require(routed == set() and attainable == {'task'}, 'Missing-route counterexample failed.')
    scenarios=[('low_routing_burden',F(3),F(0)),('expensive_routing',F(25),F(0)),
               ('missed_valuable_route',F(3),F(30))]
    return {'status':'EXACT_AUTHORED_ADVERSARIAL_CASES',
            'access_trace':history,
            'omitted_route':{'recorded_index_selected':sorted(routed),
                             'actual_supplied_routes_allow':sorted(attainable)},
            'economic_scenarios':[{'name':name, 'evaluation_cost':'1','routing_cost':str(k),
                                  'missed_value':str(loss),'net_saving':str(replay_margin(25,5,1,k,loss))}
                                 for name,k,loss in scenarios],
            'scope':'Explicit synthetic cases. No real provider access, security enforcement, demand or measured savings. Regained access still requires operational requalification in a real system.'}


def replay_study() -> dict:
    naive=replay('blanket'); selective=replay('dependency')
    ordinary = conventional_schedule(REQUIREMENTS, RELEASES)
    require(naive['completed'] == selective['completed'], 'Replay completions disagree.')
    require(ordinary['evaluations'] == selective['evaluations'] and ordinary['completed'] == selective['completed'] and ordinary['trace'] == selective['trace'], 'Independent conventional schedule disagrees.')
    # Exhaustive cross-check: all nonempty requirements on a three-capability
    # alphabet, under each release order. Direct subset logic is the strong control.
    alphabet=('a','b','c'); requirements={str(i):{x for j,x in enumerate(alphabet) if i&(1<<j)} for i in range(1,8)}
    checks=0
    for perm in permutations(alphabet):
        current=set(); output=replay('dependency',requirements,[{v} for v in perm])
        for entry,value in zip(output['trace'],perm):
            before={k for k,r in requirements.items() if r<=current}
            current.add(value)
            after={k for k,r in requirements.items() if r<=current}
            require(set(entry['completed']) == after-before, 'Replay subset-oracle mismatch.')
        require(len(output['completed']) == 7, 'Incomplete exhaustive replay.')
        control = conventional_schedule(requirements, [{v} for v in perm])
        require(control['trace'] == output['trace'], 'Independent scheduler trace mismatch.')
        checks+=len(requirements)
    return {'status':'EXACT_SUPPLIED_DEPENDENCY_MODEL','blanket':naive,'selective':selective,
            'conventional_dependency_control':ordinary,
            'control_implementation':'Independent earliest-feasible-event schedule; no call to replay().',
            'candidate_evaluations_saved':naive['evaluations']-selective['evaluations'],
            'verification_cases':checks,
            'scope':'Complete blocker records and deterministic success laws are supplied. Routing, discovery and maintenance costs are not modeled; no total-cost speedup is inferred.'}

def funding_need(cashflows: Iterable[F], reserves: Iterable[F] | None=None) -> F:
    flows=[exact(x) for x in cashflows]
    locks=[exact(x) for x in reserves] if reserves is not None else [F(0)]*(len(flows)+1)
    if len(locks)!=len(flows)+1 or any(r<0 for r in locks):
        raise ValueError('Provide one nonnegative reserve per prefix, including the initial state.')
    balance=F(0); minimum=locks[0]
    for flow,reserve in zip(flows,locks[1:]):
        balance+=flow
        minimum=max(minimum,reserve-balance)
    return max(F(0),minimum)

def paths(fixed=F(40),unit=F(4),price=F(12),n=10):
    fixed, unit, price = exact(fixed), exact(unit), exact(price)
    if isinstance(n, bool) or not isinstance(n, int) or n < 0 or min(fixed,unit,price)<0:
        raise ValueError('Nonnegative inputs and an integer count are required.')
    staged=[-fixed]+[x for _ in range(n) for x in (-unit,price)]
    delayed=[-fixed]+[-unit]*n+[price*n]
    return staged,delayed

def economic_study() -> dict:
    staged, delayed=paths()
    reserve=[F(10)]*(len(staged)+1)
    # Independent brute-force prefix test validates the minimal integer opening cash.
    comparisons=0
    for fixed,unit,price,n in product(range(0,9,2),range(1,5),range(1,7),range(1,7)):
        for flows in paths(F(fixed),F(unit),F(price),n):
            bound_needed=funding_need(flows)
            brute=next(b for b in range(1000) if min([F(b)]+[F(b)+sum(flows[:k]) for k in range(1,len(flows)+1)])>=0)
            require(F(brute) == bound_needed, "Cash-prefix oracle mismatch.")
            comparisons+=1
    next_flows,_=paths(F(30),F(4),F(12),5)
    require(funding_need(next_flows) <= F(40), "Illustrated successor is not financeable.")
    return {'status':'EXACT_STIPULATED_CASH_MODEL','currency':'abstract units, not dollars',
      'fixed_cost':'40','unit_cost':'4','price':'12','orders':10,
      'profit':str(sum(staged)), 'staged_minimum_cash':str(funding_need(staged)),
      'delayed_minimum_cash':str(funding_need(delayed)),
      'staged_cash_with_protected_reserve_10':str(funding_need(staged,reserve)),
      'staged_cashflows':list(map(str,staged)), 'delayed_cashflows':list(map(str,delayed)),
      'low_demand_orders':3, 'low_demand_profit':str(sum(paths(n=3)[0])),
      'imitated_price':'8','imitated_price_profit':str(sum(paths(price=F(8))[0])),
      'successor_minimum_cash':str(funding_need(next_flows)),
      'successor_profit':str(sum(next_flows)), 'earned_cash_after_successor':str(F(40)+sum(next_flows)),
      'exhaustive_schedule_checks':comparisons,
      'scope':'All orders, costs, prices and receipts are authored assumptions. No actual buyer, invoicing, hardware, taxes or native enterprise ledger. All declared burdens are expensed when paid.'}

def lag_study() -> dict:
    doubling=12.0
    return {'status':'CONDITIONAL_ALGEBRA_NOT_FORECAST','doubling_time_weeks':doubling,
            'points':[{'lag_weeks':t,'fraction':2**(-t/doubling)} for t in (0,1,3,6,12,24)],
            'scope':'Assumed exponential growth of a specified reference throughput, not a measured law of intelligence or profit.'}

def all_results() -> dict:
    return {'edition':EDITION, 'instrument':instrument_study(),'replay':replay_study(),
            'economics':economic_study(),'adoption_lag':lag_study(),
            'adversarial_replay': adversarial_replay_study()}

def emit_results(output: Path) -> dict:
    """Create one new result directory. Never overwrite or follow a directory link."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Output exists; choose a new directory to preserve earlier evidence.')
    results = all_results()
    # mkdir(exist_ok=False) is the final no-overwrite check, including concurrent runs.
    output.mkdir(parents=True, exist_ok=False)
    def write(name: str, value: str) -> None:
        with (output/name).open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(value)
    write('results.json', json.dumps(results, indent=2, sort_keys=True)+'\n')
    write('measurement_plan.json', json.dumps({
        'status':'ANALYTICAL_MODEL_ONLY', 'rows':[['1','1'],results['instrument']['selected_row']],
        'noise_bound':'1/10','scope':'Two-dimensional supplied linear response model; not a hardware protocol.'},indent=2)+'\n')
    write('compiled_observer.py', '\n'.join([
        '"""Generated observer: supplied linear model only, not a hardware protocol."""',
        'from fractions import Fraction',
        'def estimate(y_sum, y_difference):',
        '    a, b = Fraction(y_sum), Fraction(y_difference)',
        '    return (a+b)/2, (a-b)/2', '']))
    with (output/'lag.csv').open('x', newline='', encoding='utf-8') as handle:
        writer=csv.DictWriter(handle, fieldnames=('lag_weeks','fraction'), lineterminator='\n')
        writer.writeheader(); writer.writerows(results['adoption_lag']['points'])
    return results


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='A new output directory. Existing paths are refused.')
    args=parser.parse_args()
    try:
        results=emit_results(args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Cannot create study output: {exc}\n')
    print(json.dumps({k:v.get('status',v) if isinstance(v,dict) else v for k,v in results.items()},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
