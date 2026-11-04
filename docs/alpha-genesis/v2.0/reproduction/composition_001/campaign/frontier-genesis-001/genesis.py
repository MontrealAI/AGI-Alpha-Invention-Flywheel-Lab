"""ALPHA GENESIS: source-bound frontier opportunity construction and finite-game audit.

No provider calls, spending, customer access, or native financial ledger operations.
This is a deliberately bounded research instrument, not a production agent.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import html
import json
from pathlib import Path
from typing import Any


class InvalidScenario(ValueError):
    pass


def _names(values: Any, where: str) -> frozenset[str]:
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise InvalidScenario(f"{where}: expected list of nonempty names")
    if len(values) != len(set(values)):
        raise InvalidScenario(f"{where}: duplicate name")
    return frozenset(values)


def _money(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise InvalidScenario(f"{name}: expected nonnegative integer cents")
    return value


def validate(s: dict[str, Any]) -> None:
    if not isinstance(s, dict) or s.get('evidence_scope') != 'AUTHORED_SYNTHETIC':
        raise InvalidScenario('evidence_scope must be AUTHORED_SYNTHETIC; real commercial claims not supported')
    _names(s.get('initial', []), 'initial')
    events = s.get('events', [])
    ops = s.get('operations', [])
    offers = s.get('offers', [])
    if not all(isinstance(v, list) for v in (events, ops, offers)):
        raise InvalidScenario('events, operations and offers must be arrays')
    seen: set[str] = set()
    for e in events:
        if not isinstance(e, dict) or not isinstance(e.get('id'), str) or not e['id'] or e['id'] in seen:
            raise InvalidScenario('event id missing or duplicate')
        seen.add(e['id'])
        if not isinstance(e.get('source_url'), str) or not e['source_url'].startswith('https://'):
            raise InvalidScenario('event requires HTTPS primary-source URL')
        if e.get('access') not in ('assumed_access_in_demo', 'unverified', 'restricted'):
            raise InvalidScenario('event access must be explicitly qualified')
        _names(e.get('provides', []), 'event provides')
    seen.clear()
    for op in ops:
        if not isinstance(op, dict) or not isinstance(op.get('id'), str) or not op['id'] or op['id'] in seen:
            raise InvalidScenario('operation id missing or duplicate')
        seen.add(op['id'])
        _names(op.get('requires', []), 'operation requires')
        provides = _names(op.get('provides', []), 'operation provides')
        if not provides:
            raise InvalidScenario('operation must provide an output')
        _money(op.get('cost_cents'), 'operation cost')
        if op.get('kind') not in ('existing', 'frontier', 'construct', 'partner'):
            raise InvalidScenario('operation kind invalid')
    seen.clear()
    for offer in offers:
        if not isinstance(offer, dict) or not isinstance(offer.get('id'), str) or not offer['id'] or offer['id'] in seen:
            raise InvalidScenario('offer id missing or duplicate')
        seen.add(offer['id'])
        if not _names(offer.get('requires', []), 'offer requires'):
            raise InvalidScenario('offer must require a capability')
        for k in ('buyer_value_floor_cents', 'outside_utility_cents', 'buyer_friction_cents', 'overhead_cents'):
            _money(offer.get(k), k)
        prices = offer.get('prices_cents')
        if not isinstance(prices, list) or not prices:
            raise InvalidScenario('offer requires price choices')
        for p in prices:
            _money(p, 'price')
        if offer.get('demand_evidence') not in ('hypothetical', 'observed'):
            raise InvalidScenario('demand_evidence must be labeled')


def initial(s: dict[str, Any], excluded: frozenset[str] = frozenset()) -> frozenset[str]:
    capabilities = set(s['initial'])
    for event in s['events']:
        if event['id'] not in excluded and event['access'] == 'assumed_access_in_demo':
            capabilities.update(event['provides'])
    return frozenset(capabilities)


def find_plan(s: dict[str, Any], required: frozenset[str], excluded: frozenset[str] = frozenset(),
              state_limit: int = 10000) -> dict[str, Any] | None:
    """Dijkstra on a monotone finite capability-state graph. Cost is one campaign's cost.

    Only the declared finite grammar is searched. This is NOT open-world invention.
    """
    start = initial(s, excluded)
    q: list[tuple[int, tuple[str, ...], frozenset[str]]] = [(0, (), start)]
    best: dict[frozenset[str], tuple[int, tuple[str, ...]]] = {start: (0, ())}
    actions = sorted(s['operations'], key=lambda a: a['id'])
    expanded = 0
    while q:
        cost, path, caps = heapq.heappop(q)
        if best.get(caps) != (cost, path):
            continue
        if required.issubset(caps):
            return {'cost_cents': cost, 'operations': list(path), 'capabilities': sorted(caps),
                    'states_expanded': expanded}
        expanded += 1
        if expanded > state_limit:
            raise InvalidScenario('experiment state limit reached: increase declared budget or reduce grammar')
        for action in actions:
            if not set(action['requires']).issubset(caps):
                continue
            next_caps = caps.union(action['provides'])
            if next_caps == caps:
                continue
            nxt = (cost + action['cost_cents'], path + (action['id'],))
            if next_caps not in best or nxt < best[next_caps]:
                best[next_caps] = nxt
                heapq.heappush(q, (nxt[0], nxt[1], next_caps))
    return None


def quote(offer: dict[str, Any], plan: dict[str, Any] | None) -> dict[str, Any]:
    """Finite complete-information posted-price game, not market-optimal pricing.

    A buyer may decline; their guaranteed participation requires value-floor minus price,
    friction and best outside utility >= 0. Seller may decline at nonpositive margin.
    """
    if plan is None:
        return {'status': 'UNREACHABLE', 'model_profit_cents': None}
    buyer_limit = offer['buyer_value_floor_cents'] - offer['buyer_friction_cents'] - offer['outside_utility_cents']
    viable_prices = [p for p in offer['prices_cents'] if p <= buyer_limit]
    if not viable_prices:
        return {'status': 'NO_VOLUNTARY_BUYER', 'model_profit_cents': None, 'buyer_limit_cents': buyer_limit}
    p = max(viable_prices)
    margin = p - plan['cost_cents'] - offer['overhead_cents']
    if margin <= 0:
        return {'status': 'NO_POSITIVE_COMPLETE_MARGIN', 'model_profit_cents': margin,
                'quote_cents': p, 'buyer_limit_cents': buyer_limit}
    return {'status': 'MODEL_POSITIVE_UNVERIFIED_DEMAND' if offer['demand_evidence'] == 'hypothetical'
            else 'MODEL_POSITIVE_ASSUMING_INPUTS',
            'model_profit_cents': margin, 'quote_cents': p, 'buyer_limit_cents': buyer_limit,
            'buyer_floor_surplus_cents': buyer_limit - p}


def analyze(s: dict[str, Any]) -> dict[str, Any]:
    validate(s)
    offers = []
    for offer in s['offers']:
        required = frozenset(offer['requires'])
        chosen = find_plan(s, required)
        without_frontier = find_plan(s, required, frozenset(e['id'] for e in s['events']))
        full_decision = quote(offer, chosen)
        baseline_decision = quote(offer, without_frontier)
        event_effects = []
        for event in s['events']:
            without = find_plan(s, required, frozenset([event['id']]))
            event_effects.append({'event_id': event['id'],
                                  'counterfactual_cost_cents': None if without is None else without['cost_cents'],
                                  'conditional_cost_saving_cents': None if chosen is None or without is None
                                  else without['cost_cents'] - chosen['cost_cents'],
                                  'becomes_reachable_in_model': chosen is not None and without is None})
        offers.append({'id': offer['id'], 'requirements': sorted(required), 'plan': chosen,
                       'no_frontier_plan': without_frontier, 'decision': full_decision,
                       'no_frontier_decision': baseline_decision, 'event_counterfactuals': event_effects,
                       'commercial_readiness': 'NOT_ESTABLISHED',
                       'independent_acceptance': 'NOT_TESTED',
                       'interpretation': 'Authored finite opportunity game; neither buyer demand nor complete costs are measured.'})
    offers.sort(key=lambda o: (10**18 if o['decision']['model_profit_cents'] is None
                               else -o['decision']['model_profit_cents'], o['id']))
    candidates = [o for o in offers if o['decision']['model_profit_cents'] is not None
                  and o['decision']['model_profit_cents'] > 0]
    return {'protocol': 'frontier-genesis-001', 'scope': 'AUTHORED_SYNTHETIC_FINITE_GAME',
            'not_demonstrated': ['real commercial profit', 'frontier exhaustiveness',
                                 'open-world invention', 'physical measurement', 'better discovery procedure'],
            'events': s['events'], 'opportunities': offers,
            'model_best_offer': candidates[0]['id'] if candidates else None,
            'real_world_authority': 'NONE',
            'message': 'Offers, routes, prices, and probabilities are author-supplied. All conclusions are conditional.'}


def report_html(r: dict[str, Any]) -> str:
    def esc(x: Any) -> str:
        return html.escape(str(x), quote=True)
    rows = []
    for x in r['opportunities']:
        dec = x['decision']
        plan = x['plan']
        steps = ' → '.join(plan['operations']) if plan else 'Not constructible in the declared grammar'
        delta = ', '.join(f"{v['event_id']}: {v['conditional_cost_saving_cents']}¢" for v in x['event_counterfactuals'])
        rows.append(f"<article><h2>{esc(x['id'])}</h2><p class='status'>{esc(dec['status'])}</p>"
                    f"<p>{esc(steps)}</p><p>Conditional modeled margin: {esc(dec['model_profit_cents'])} cents</p>"
                    f"<p>Remove-event counterfactuals: {esc(delta)}</p><p class='small'>"
                    "Real-world commercial qualification: NOT ESTABLISHED.</p></article>")
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ALPHA GENESIS Ω — Frontier to possibility</title><style>
:root{color-scheme:dark}body{background:#100d1c;color:#f5eee0;font:17px/1.6 system-ui;margin:0}
main{max-width:920px;margin:auto;padding:60px 22px}.over{color:#dcc28b;letter-spacing:.18em;font-size:.78rem}
h1{font-size:clamp(2rem,5vw,4rem);line-height:1.06;margin:12px 0}em{color:#c8a8ff}article{background:#211930;border:1px solid #75608f;border-radius:16px;padding:20px;margin:18px 0}
.status{color:#c9a8ff;font-weight:700}.small{font-size:.86rem;color:#d8cfe2}footer{margin-top:38px;color:#d8cfe2}
</style><main><div class='over'>TRANSFORMATIONAL INTELLIGENCE ∞ · RESEARCH EXPERIMENT</div>
<h1>See the frontier.<br><em>Construct the possibility.</em></h1>
<p>The frontier creates candidate means. A complete-value test determines whether to use them, build something new, or decline.</p>
<p class='small'>All values are illustrative, not market observations. No purchases, outreach or deployment.</p>""" + ''.join(rows) + "<footer>GENESIS Ω · Invent the means. Verify the value. Test the successor.</footer></main></html>"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    scenario_bytes = a.scenario.read_bytes()
    scenario = json.loads(scenario_bytes)
    result = analyze(scenario)
    result['input_sha256'] = hashlib.sha256(scenario_bytes).hexdigest()
    if a.out.exists():
        p.error('output exists; choose a new directory to preserve evidence')
    a.out.mkdir(parents=True)
    (a.out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (a.out / 'index.html').write_text(report_html(result), encoding='utf-8')
    print(json.dumps({'report': str(a.out / 'index.html'), 'model_best_offer': result['model_best_offer']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
