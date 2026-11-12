"""Frozen, public-window-only directed temporal route construction.

Written by the included agent during K2 development.  These are conventional
deterministic CPU algorithms, not a Python model callable or a novelty claim.
Only decide's arguments are inspected; diagnostics are returned as own state.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

from .wave import canonical_identity, exact_cover


MAX_ROUTE_CHECKS = 50000
POLICY = "directed-merge-fragment-neighborhood-v1"


class BudgetExhausted(RuntimeError):
    pass


def _number(value, name, minimum=None):
    if (type(value) not in (int, float)
            or (type(value) is float and not math.isfinite(value))
            or (minimum is not None and value < minimum)):
        raise ValueError("invalid " + name)
    return value


@dataclass(frozen=True)
class Route:
    ids: tuple
    cost: int
    load: object
    finish: object


class Oracle:
    """Every complete-route feasibility/objective evaluation goes here.

    Reusing an immutable already checked Route does not reevaluate its objective.
    Screening by a raw directed arc or deadline is not a full-route evaluation.
    Empty-route evaluations, failed candidates, solos and safety all count.
    """
    def __init__(self, orders, duration, departure, capacity, depot_end):
        self.orders = orders
        self.duration = duration
        self.departure = departure
        self.capacity = capacity
        self.depot_end = depot_end
        self.checks = 0
        self.by_phase = {}

    def check(self, ids, phase, departure=None):
        if self.checks >= MAX_ROUTE_CHECKS:
            raise BudgetExhausted("registered complete-route check budget exhausted")
        self.checks += 1
        self.by_phase[phase] = self.by_phase.get(phase, 0) + 1
        ids = tuple(ids)
        if len(ids) != len(set(ids)):
            return None
        time = self.departure if departure is None else departure
        previous, cost, load = 0, 0, 0
        for oid in ids:
            order = self.orders[oid]
            load += order["demand"]
            if load > self.capacity:
                return None
            customer = order["customer_id"]
            travel = self.duration[previous][customer]
            cost += travel
            time = max(time + travel, order["tw_start"])
            if time > order["tw_end"]:
                return None
            time += order["service_time"]
            previous = customer
        cost += self.duration[previous][0]
        time += self.duration[previous][0]
        if time > self.depot_end:
            return None
        return Route(ids, cost, load, time)


def _ordered(routes):
    return sorted((route for route in routes if route.ids), key=lambda route: route.ids)


def _cost(routes):
    # Sum stored evaluated objectives, not a new candidate route evaluation.
    return sum(route.cost for route in routes)


def _cover(orders, groups):
    result = exact_cover(
        (canonical_identity(oid) for oid in orders),
        [[canonical_identity(oid) for oid in group] for group in groups],
    )
    if any(result.values()):
        raise ValueError("typed whole-order coverage failure: " + repr(result))
    return result


def _small_cover(oracle, ids, limit):
    """Bounded subset route enumeration for a nonmetric singleton failure.

    An infeasible singleton does not prove infeasibility with directed roads.
    Every partial ordering considered as a complete depot route is checked and
    charged.  A feasible cover, if found, survives budget exhaustion.  This is
    not a general proof of infeasibility when enumeration is cut short.
    """
    ids = tuple(ids)
    bit = {oid: 1 << i for i, oid in enumerate(ids)}
    candidates = {}

    def visit(path, mask, previous, time, load):
        if oracle.checks >= limit:
            return
        checked = oracle.check(path, "nonmetric_cover")
        old = candidates.get(mask)
        if checked is not None and (old is None or (checked.cost, checked.ids) < (old.cost, old.ids)):
            candidates[mask] = checked
        for oid in ids:
            if mask & bit[oid] or oracle.checks >= limit:
                continue
            order = oracle.orders[oid]
            next_load = load + order["demand"]
            arrival = max(time + oracle.duration[previous][order["customer_id"]], order["tw_start"])
            # Partial path pruning does not assume a depot-return triangle.
            if next_load <= oracle.capacity and arrival <= order["tw_end"]:
                visit(path + (oid,), mask | bit[oid], order["customer_id"],
                      arrival + order["service_time"], next_load)

    visit((), 0, 0, oracle.departure, 0)
    full = (1 << len(ids)) - 1
    best = {0: (0, ())}
    containing = {1 << i: [] for i in range(len(ids))}
    for mask, route in candidates.items():
        if mask:
            for atom in containing:
                if mask & atom:
                    containing[atom].append((mask, route))
    for mask in range(full + 1):
        if mask not in best or mask == full:
            continue
        first = (full ^ mask) & -(full ^ mask)
        old_cost, old_routes = best[mask]
        for route_mask, route in containing[first]:
            if route_mask & mask:
                continue
            new = mask | route_mask
            proposal = (old_cost + route.cost, old_routes + (route,))
            if new not in best or proposal[0] < best[new][0]:
                best[new] = proposal
    return list(best[full][1]) if full in best else None


def _near_pairs(routes, oracle, width=14):
    """Raw road-arc proximity shortlist, without symmetry/metric assumptions."""
    pairs = set()
    for i, route in enumerate(routes):
        end = oracle.orders[route.ids[-1]]["customer_id"]
        start = oracle.orders[route.ids[0]]["customer_id"]
        nearby = sorted(
            (j for j in range(len(routes)) if i != j),
            key=lambda j: (
                min(oracle.duration[end][oracle.orders[routes[j].ids[0]]["customer_id"]],
                    oracle.duration[oracle.orders[routes[j].ids[-1]]["customer_id"]][start]),
                routes[j].ids,
            ),
        )[:width]
        pairs.update((min(i, j), max(i, j)) for j in nearby)
    return sorted(pairs)


def _merge(routes, oracle, limit, phase):
    """Directed savings heap with reversed/forward concatenation candidates."""
    if oracle.checks >= limit:
        return _ordered(routes)
    active = {i: route for i, route in enumerate(_ordered(routes))}
    next_key, heap, offered = len(active), [], set()

    def offer(a, b):
        pair = (min(a, b), max(a, b))
        if a == b or pair in offered or oracle.checks >= limit:
            return
        offered.add(pair)
        ra, rb = active[a], active[b]
        aa = [ra.ids] + ([ra.ids[::-1]] if len(ra.ids) > 1 else [])
        bb = [rb.ids] + ([rb.ids[::-1]] if len(rb.ids) > 1 else [])
        best = None
        for left in aa:
            for right in bb:
                for ids in (left + right, right + left):
                    if oracle.checks >= limit:
                        break
                    route = oracle.check(ids, phase)
                    if route is not None and route.cost < ra.cost + rb.cost:
                        if best is None or (route.cost, route.ids) < (best.cost, best.ids):
                            best = route
        if best is not None:
            heapq.heappush(heap, (best.cost - ra.cost - rb.cost, best.ids, pair[0], pair[1], best))

    initial = list(active.values())
    for a, b in _near_pairs(initial, oracle):
        offer(a, b)
        if oracle.checks >= limit:
            break
    while heap:
        _, _, a, b, route = heapq.heappop(heap)
        if a not in active or b not in active:
            continue
        del active[a], active[b]
        key, next_key = next_key, next_key + 1
        active[key] = route
        if oracle.checks < limit:
            # Boundary arc ranking selects candidates; each full concatenation
            # objective and all temporal/capacity constraints use Oracle.check.
            end = oracle.orders[route.ids[-1]]["customer_id"]
            start = oracle.orders[route.ids[0]]["customer_id"]
            other = sorted((j for j in active if j != key), key=lambda j: (
                min(oracle.duration[end][oracle.orders[active[j].ids[0]]["customer_id"]],
                    oracle.duration[oracle.orders[active[j].ids[-1]]["customer_id"]][start]),
                active[j].ids,
            ))[:28]
            for j in other:
                offer(key, j)
                if oracle.checks >= limit:
                    break
    return _ordered(active.values())


def _proposals(routes, oracle, kind):
    if kind == "within":
        for a, route in enumerate(routes):
            ids = route.ids
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    yield (a,), (ids[:i] + ids[i:j + 1][::-1] + ids[j + 1:],)
            for i in range(len(ids)):
                rest = ids[:i] + ids[i + 1:]
                for j in range(len(rest) + 1):
                    if j != i:
                        yield (a,), (rest[:j] + (ids[i],) + rest[j:],)
        return
    for a, b in _near_pairs(routes, oracle, 10):
        aa, bb = routes[a].ids, routes[b].ids
        if kind == "relocate":
            for source, target, src, dst in ((a, b, aa, bb), (b, a, bb, aa)):
                for length in (1, 2):
                    for i in range(len(src) - length + 1):
                        chain, rest = src[i:i + length], src[:i] + src[i + length:]
                        for j in range(len(dst) + 1):
                            yield (source, target), (rest, dst[:j] + chain + dst[j:])
        elif kind == "swap":
            for i in range(len(aa)):
                for j in range(len(bb)):
                    yield (a, b), (aa[:i] + (bb[j],) + aa[i + 1:],
                                   bb[:j] + (aa[i],) + bb[j + 1:])
        else:
            for i in range(len(aa) + 1):
                for j in range(len(bb) + 1):
                    if (i, j) not in ((0, 0), (len(aa), len(bb))):
                        yield (a, b), (aa[:i] + bb[j:], bb[:j] + aa[i:])


def _local(routes, oracle, limit, label):
    """Adaptive deterministic descent across four complementary neighborhoods."""
    routes = _ordered(routes)
    priorities = ["relocate", "tails", "within", "swap"]
    gains = {kind: 0 for kind in priorities}
    accepted = {kind: 0 for kind in priorities}
    while oracle.checks < limit:
        changed = False
        for kind in sorted(priorities, key=lambda k: (-gains[k], priorities.index(k))):
            remaining = limit - oracle.checks
            allowance = max(1, remaining // len(priorities))
            end = min(limit, oracle.checks + allowance)
            best, best_delta = None, 0
            for indices, sequences in _proposals(routes, oracle, kind):
                if oracle.checks + len(sequences) > end:
                    break
                checked = []
                for sequence in sequences:
                    route = oracle.check(sequence, label + "_" + kind)
                    if route is None:
                        break
                    checked.append(route)
                if len(checked) != len(sequences):
                    continue
                delta = _cost(checked) - sum(routes[i].cost for i in indices)
                if delta < best_delta:
                    best, best_delta = (indices, checked), delta
            if best is not None:
                indices, checked = best
                routes = _ordered([route for i, route in enumerate(routes) if i not in indices] + checked)
                gains[kind] += -best_delta
                accepted[kind] += 1
                changed = True
        if not changed:
            break
    return routes, accepted


def _fragments(routes, oracle, limit, attempt):
    fragments = []
    for route in routes:
        if len(route.ids) < 3:
            fragments.append(route)
            continue
        # Deterministic alternative route decompositions, no random state/input.
        cut = 1 + (attempt % (len(route.ids) - 1))
        sequences = (route.ids[:cut], route.ids[cut:])
        if oracle.checks + 2 > limit:
            return None
        checked = [oracle.check(ids, "fragment_safety") for ids in sequences]
        if any(piece is None for piece in checked):
            # Nonmetric roads: a feasible whole route need not have feasible
            # depot-anchored fragments. Keep the whole route in that case.
            fragments.append(route)
        else:
            fragments.extend(checked)
    return fragments


def _input(window, state):
    if (not isinstance(window, dict) or window.get("information_mode") != "rolling_batch_v1"
            or window.get("capacity") != 1000 or window.get("total_rounds") != 6):
        raise ValueError("unsupported public rolling contract")
    day, round_number = window.get("service_day_id"), window.get("dispatch_round")
    if type(day) is not str or not day or type(round_number) is not int or not 1 <= round_number <= 6:
        raise ValueError("invalid service day or dispatch round")
    ready = _number(window.get("ready_time"), "absolute departure seconds")
    customers, duration = window["customers"], window["duration"]
    depot_end = _number(customers[0]["tw_end"], "depot return deadline")
    orders = {}
    for row in window["orders"]:
        oid = row["order_id"]
        canonical_identity(oid)
        if type(oid) is not str or not oid or oid in orders:
            raise ValueError("orders require distinct nonempty original string IDs")
        if (row["service_day_id"] != day or type(row["dispatch_round"]) is not int
                or not 1 <= row["dispatch_round"] <= round_number
                or _number(row["ready_time"], "order confirmation seconds") > ready):
            raise ValueError("order not in this public confirmation window")
        cid = row["customer_id"]
        if type(cid) is not int or cid < 0 or cid not in customers:
            raise ValueError("customer IDs must preserve nonnegative integer matrix indices")
        for field in ("demand", "service_time"):
            _number(row[field], "order " + field, 0)
        if _number(row["tw_start"], "order opening seconds") > _number(row["tw_end"], "order closing seconds"):
            raise ValueError("reversed order window")
        orders[oid] = row
    largest = max([0] + [row["customer_id"] for row in orders.values()])
    if not isinstance(duration, list) or len(duration) <= largest:
        raise ValueError("incomplete directed road matrix")
    for row in duration:
        if not isinstance(row, list) or len(row) != len(duration):
            raise ValueError("directed road matrix must be square")
        if any(type(value) is not int or value < 0 for value in row):
            raise ValueError("directed travel durations require nonnegative integer seconds")
    if state is None:
        days, records = {}, []
    elif isinstance(state, dict) and state.get("policy") == POLICY:
        days = {key: {"last_round": value["last_round"], "dispatched": list(value["dispatched"])}
                for key, value in state["days"].items()}
        records = list(state["records"])
    else:
        raise ValueError("unsupported own policy state")
    previous = days.get(day, {"last_round": 0, "dispatched": []})
    if previous["last_round"] != round_number - 1:
        raise ValueError("own history does not precede this irrevocable round")
    history = previous["dispatched"]
    _cover(orders, [history, [oid for oid in orders if oid not in set(history)]])
    return day, round_number, ready, depot_end, duration, orders, days, records, history


def decide(window, state):
    """Return the exact round envelope and own state; never inspect future data."""
    (day, round_number, ready, depot_end, duration, orders,
     days, records, history) = _input(window, state)
    pending = sorted(set(orders) - set(history))
    oracle = Oracle(orders, duration, ready, window["capacity"], depot_end)
    now, next_solo = {}, {}
    prior_routes, witnessed = [], set()
    if (records and records[-1]["service_day_id"] == day
            and records[-1]["dispatch_round"] == round_number - 1
            and records[-1]["next_departure_seconds"] == ready):
        # A nonmetric whole-route witness may remain feasible when one of its
        # singleton routes does not. Revalidate and retain the known partition.
        for group in records[-1]["next_round_witness"]:
            if not group or not set(group) <= set(pending) or witnessed.intersection(group):
                raise ValueError("own deferred witness is inconsistent with pending orders")
            route = oracle.check(group, "retained_witness_current")
            if route is not None:
                prior_routes.append(route)
                witnessed.update(group)
    for oid in pending:
        if oid not in witnessed:
            now[oid] = oracle.check((oid,), "solo_current")
    if round_number < 6:
        for oid in pending:
            # A missing next witness means dispatch now, never assume deferral.
            next_solo[oid] = (oracle.check((oid,), "solo_next", ready + 3600)
                              if oracle.checks < MAX_ROUTE_CHECKS else None)
    # Leave enough checks for one next-round witness and one final current
    # safety evaluation per pending order. No search may spend that reserve.
    search_end = max(oracle.checks, MAX_ROUTE_CHECKS - 2 * len(pending))
    routes = prior_routes + [route for route in now.values() if route is not None]
    if len(witnessed) + sum(route is not None for route in now.values()) != len(pending):
        if len(pending) <= 11:
            recovered = _small_cover(oracle, pending, min(search_end, oracle.checks + 16000))
        else:
            recovered = None
        if recovered is None:
            raise ValueError("no feasible incumbent constructed within bounded nonmetric search; not a proof of infeasibility")
        routes = recovered
    initial_cost = _cost(routes)
    start = oracle.checks
    available = max(0, search_end - start)
    routes = _merge(routes, oracle, start + available * 28 // 100, "initial_merge")
    routes, local = _local(routes, oracle, start + available * 57 // 100, "initial_local")
    rebuilds = []
    for attempt, percentage in ((1, 80), (2, 100)):
        end = start + available * percentage // 100
        pieces = _fragments(routes, oracle, end, attempt)
        if pieces is None:
            break
        proposal = _merge(pieces, oracle, oracle.checks + max(0, end - oracle.checks) * 2 // 3,
                          "fragment_merge_" + str(attempt))
        proposal, moves = _local(proposal, oracle, end, "fragment_local_" + str(attempt))
        adopted = _cost(proposal) < _cost(routes)
        rebuilds.append({"attempt": attempt, "candidate_cost": _cost(proposal), "adopted": adopted, "moves": moves})
        if adopted:
            routes = proposal
    dispatch, deferred, next_witness = [], [], []
    safety_reused = 0
    for route in _ordered(routes):
        if round_number == 6:
            dispatch.append(route)
            continue
        next_route = (oracle.check(route.ids, "deferral_route", ready + 3600)
                      if oracle.checks < MAX_ROUTE_CHECKS else None)
        if next_route is not None:
            deferred.extend(route.ids)
            next_witness.append(list(route.ids))
        elif any(next_solo[oid] is None for oid in route.ids):
            dispatch.append(route)
        elif route.cost < sum(next_solo[oid].cost for oid in route.ids):
            # This known consolidation expires before the next public departure.
            # Dispatch a strictly cheaper known bundle; future demand is unknown.
            dispatch.append(route)
        else:
            deferred.extend(route.ids)
            next_witness.extend([[oid] for oid in route.ids])
    final_routes = []
    for route in dispatch:
        if oracle.checks < MAX_ROUTE_CHECKS:
            checked = oracle.check(route.ids, "final_safety")
        else:
            # Route is an immutable feasible result from this same departure.
            # Keeping that incumbent does not perform another route evaluation.
            checked = route
            safety_reused += 1
        if checked is None:
            raise ValueError("internal final temporal-route invariant failed")
        final_routes.append(list(checked.ids))
    _cover(orders, [history] + final_routes + [deferred])
    if round_number == 6 and deferred:
        raise ValueError("last round requires full irrevocable dispatch")
    if any(exact_cover([canonical_identity(oid) for oid in deferred],
                       [[canonical_identity(oid) for oid in group] for group in next_witness]).values()):
        raise ValueError("next-round feasibility witness does not cover deferred orders")
    sent = [oid for route in final_routes for oid in route]
    days[day] = {"last_round": round_number, "dispatched": history + sent}
    records.append({
        "service_day_id": day, "dispatch_round": round_number,
        "available_orders": len(orders), "pending_before": len(pending),
        "retained_next_witness_orders_revalidated": len(witnessed),
        "dispatched_now": len(sent), "deferred": len(deferred),
        "initial_known_partition_driving_seconds": initial_cost,
        "best_known_partition_driving_seconds": _cost(routes),
        "submitted_driving_seconds": _cost(dispatch),
        "route_checks": oracle.checks, "route_check_limit": MAX_ROUTE_CHECKS,
        "checks_by_phase": oracle.by_phase, "local_moves": local,
        "final_safety_checked_routes_reused": safety_reused,
        "fragment_rebuilds": rebuilds, "next_departure_seconds": ready + 3600 if round_number < 6 else None,
        "next_round_witness": next_witness,
        "primitive_calls": ["decide->_input->wave.canonical_identity",
                            "decide->_input->_cover->wave.exact_cover",
                            "decide->_cover->wave.exact_cover",
                            "decide->deferred_witness->wave.exact_cover"],
        "feedback_used": False,
    })
    submission = {"service_day_id": day, "dispatch_round": round_number, "routes": final_routes}
    return submission, {"policy": POLICY, "days": days, "records": records}
