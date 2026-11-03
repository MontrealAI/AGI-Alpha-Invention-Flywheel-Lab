from __future__ import annotations
from copy import deepcopy

MAX_ROUTE_EVALUATIONS = 50_000
LOCAL_PASSES = 12


class Routes:
    def __init__(self, window, orders, *, ready=None, budget=MAX_ROUTE_EVALUATIONS):
        self.window = window
        self.orders = {row['order_id']: row for row in orders}
        self.ready = window['ready_time'] if ready is None else ready
        self.duration = window['duration']
        self.depot = window['customers'].get(0, window['customers'].get('0'))
        if self.depot is None: raise ValueError('ORDINARY075_DEPOT_REQUIRED')
        self.budget, self.evaluations, self.safety_evaluations = budget, 0, 0
        self.improvements = 0
        self.insertion_options = 0

    @property
    def exhausted(self):
        return self.evaluations >= self.budget

    def evaluate(self, route, *, search=True):
        if search:
            if self.exhausted: return None
            self.evaluations += 1
        else:
            self.safety_evaluations += 1
        if not route: return 0
        current, load, elapsed, distance = 0, 0, self.ready, 0
        for order_id in route:
            row = self.orders[order_id]
            customer = row['customer_id']
            load += row['demand']
            if load > self.window['capacity']: return None
            travel = self.duration[current][customer]
            distance += travel
            elapsed = max(elapsed + travel, row['tw_start'])
            if elapsed > row['tw_end']: return None
            elapsed += row['service_time']
            current = customer
        back = self.duration[current][0]
        if elapsed + back > self.depot['tw_end']: return None
        return distance + back

    def best_insert(self, order_id, routes, costs, solos):
        options = []
        if solos[order_id] is not None:
            self.insertion_options += 1
            options.append((solos[order_id], len(routes), 0, [order_id], solos[order_id]))
        for index, route in enumerate(routes):
            if self.exhausted: break
            if sum(self.orders[x]['demand'] for x in route) + self.orders[order_id]['demand'] > self.window['capacity']: continue
            for position in range(len(route) + 1):
                self.insertion_options += 1
                trial = route[:position] + [order_id] + route[position:]
                value = self.evaluate(trial)
                if value is not None: options.append((value - costs[index], index, position, trial, value))
                if self.exhausted: break
        options.sort(key=lambda x: (x[0], x[1], x[2]))
        return options

    @staticmethod
    def place(option, routes, costs):
        _, index, _, trial, value = option
        if index == len(routes): routes.append(trial); costs.append(value)
        else: routes[index], costs[index] = trial, value

    def initial(self, sequence, solos, *, regret=False):
        remaining, routes, costs = list(sequence), [], []
        while remaining:
            chosen = None
            if regret and not self.exhausted:
                for order_id in remaining:
                    options = self.best_insert(order_id, routes, costs, solos)
                    if options:
                        gap = options[1][0] - options[0][0] if len(options) > 1 else 0
                        score = (-gap, self.orders[order_id]['tw_end'], order_id)
                        if chosen is None or score < chosen[0]: chosen = (score, order_id, options[0])
                    if self.exhausted: break
            else:
                for order_id in remaining:
                    options = self.best_insert(order_id, routes, costs, solos)
                    if options:
                        chosen = ((), order_id, options[0]); break
            if chosen is None:
                for order_id in remaining:
                    if solos[order_id] is not None:
                        chosen = ((), order_id, (solos[order_id], len(routes), 0, [order_id], solos[order_id])); break
            if chosen is None:
                paired = None
                for first in remaining:
                    for second in remaining:
                        if first == second: continue
                        value = self.evaluate([first, second])
                        if value is not None: paired = (first, second, value); break
                    if paired is not None or self.exhausted: break
                if paired is None: return None
                first, second, value = paired
                routes.append([first, second]); costs.append(value)
                remaining.remove(first); remaining.remove(second)
            else:
                _, order_id, option = chosen
                self.place(option, routes, costs)
                remaining.remove(order_id)
        return routes, costs

    def improve(self, routes, costs):
        for _ in range(LOCAL_PASSES):
            if self.exhausted: break
            best = None
            for index, route in enumerate(routes):
                for left in range(len(route)):
                    for right in range(left + 1, len(route)):
                        trial = route[:left] + list(reversed(route[left:right + 1])) + route[right + 1:]
                        value = self.evaluate(trial)
                        if value is not None:
                            gain = value - costs[index]
                            if gain < -1e-9 and (best is None or gain < best[0]): best = (gain, 'single', index, trial, value)
                        if self.exhausted: break
                    if self.exhausted: break
                if self.exhausted: break
            for source, route in enumerate(routes):
                if self.exhausted: break
                for offset, order_id in enumerate(route):
                    remainder = route[:offset] + route[offset + 1:]
                    source_cost = self.evaluate(remainder)
                    if source_cost is None: continue
                    for target, destination in enumerate(routes):
                        if target == source: continue
                        if sum(self.orders[x]['demand'] for x in destination) + self.orders[order_id]['demand'] > self.window['capacity']: continue
                        for position in range(len(destination) + 1):
                            trial = destination[:position] + [order_id] + destination[position:]
                            value = self.evaluate(trial)
                            if value is not None:
                                gain = source_cost + value - costs[source] - costs[target]
                                if gain < -1e-9 and (best is None or gain < best[0]): best = (gain, 'pair', source, remainder, source_cost, target, trial, value)
                            if self.exhausted: break
                        if self.exhausted: break
                    if self.exhausted: break
            for first in range(len(routes)):
                if self.exhausted: break
                for second in range(first + 1, len(routes)):
                    for a, order_a in enumerate(routes[first]):
                        for b, order_b in enumerate(routes[second]):
                            one, two = list(routes[first]), list(routes[second])
                            one[a], two[b] = order_b, order_a
                            value_one, value_two = self.evaluate(one), self.evaluate(two)
                            if value_one is not None and value_two is not None:
                                gain = value_one + value_two - costs[first] - costs[second]
                                if gain < -1e-9 and (best is None or gain < best[0]): best = (gain, 'pair', first, one, value_one, second, two, value_two)
                            if self.exhausted: break
                        if self.exhausted: break
                    if self.exhausted: break
            if best is None: break
            if best[1] == 'single':
                _, _, index, trial, value = best
                routes[index], costs[index] = trial, value
            else:
                _, _, first, one, value_one, second, two, value_two = best
                routes[first], costs[first], routes[second], costs[second] = one, value_one, two, value_two
                kept = [(route, value) for route, value in zip(routes, costs) if route]
                routes, costs = [row[0] for row in kept], [row[1] for row in kept]
            self.improvements += 1
        return routes, costs

    def solve(self):
        ids = sorted(self.orders)
        solos = {order_id: self.evaluate([order_id], search=False) for order_id in ids}
        earliest = sorted(ids, key=lambda x: (self.orders[x]['tw_end'], self.orders[x]['tw_start'], x))
        farthest = sorted(ids, key=lambda x: (-self.duration[0][self.orders[x]['customer_id']], self.orders[x]['tw_end'], x))
        largest = sorted(ids, key=lambda x: (-self.orders[x]['demand'], self.orders[x]['tw_end'], x))
        candidates = []
        for sequence, regret in ((earliest, False), (farthest, False), (largest, False), (earliest, True)):
            candidate = self.initial(sequence, solos, regret=regret)
            if candidate is not None: candidates.append(candidate)
            if self.exhausted: break
        if not candidates: raise ValueError('ORDINARY075_NO_FEASIBLE_CURRENT_PARTITION_FOUND')
        routes, costs = min(candidates, key=lambda item: (sum(item[1]), tuple(tuple(r) for r in item[0])))
        routes, costs = self.improve(deepcopy(routes), list(costs))
        if sorted(x for route in routes for x in route) != ids or any(self.evaluate(route, search=False) is None for route in routes): raise ValueError('ORDINARY075_INTERNAL_PARTITION_INVALID')
        return routes


def decide(window, state):
    updated = deepcopy(state) if state is not None else {}
    day_id, current_round = window['service_day_id'], window['dispatch_round']
    days = updated.setdefault('ordinary075_days', {})
    day = days.setdefault(day_id, {'round': 0, 'dispatched': {}, 'history': [], 'search_evaluations': 0, 'safety_evaluations': 0})
    if current_round != day['round'] + 1: raise ValueError('ORDINARY075_SEQUENTIAL_WINDOW_REQUIRED')
    visible = window['orders']
    if len({row['order_id'] for row in visible}) != len(visible): raise ValueError('ORDINARY075_UNIQUE_VISIBLE_ORDERS_REQUIRED')
    pending = [row for row in visible if row['order_id'] not in day['dispatched']]
    if any(row['dispatch_round'] > current_round for row in pending): raise ValueError('ORDINARY075_UNCONFIRMED_ORDER_REFUSED')
    if 4 * len(pending) > MAX_ROUTE_EVALUATIONS: raise ValueError('ORDINARY075_VISIBLE_POOL_EXCEEDS_FINITE_QUALIFICATION_ALLOWANCE')
    search_allowance = max(0, MAX_ROUTE_EVALUATIONS - 4 * len(pending))
    current = Routes(window, pending, budget=search_allowance)
    if current_round == window['total_rounds']:
        mandatory = {row['order_id'] for row in pending}
        next_checks = 0
    else:
        next_window = Routes(window, pending, ready=window['ready_time'] + 3600, budget=0)
        mandatory = {row['order_id'] for row in pending if next_window.evaluate([row['order_id']], search=False) is None}
        next_checks = next_window.safety_evaluations
    routes = current.solve() if mandatory else []
    selected = [route for route in routes if any(order_id in mandatory for order_id in route)]
    selected.sort(key=lambda route: tuple(route))
    dispatched_now = [order_id for route in selected for order_id in route]
    if not mandatory <= set(dispatched_now): raise ValueError('ORDINARY075_MANDATORY_ORDER_MISSING')
    travel = sum(current.evaluate(route, search=False) for route in selected)
    total_checks = current.evaluations + current.safety_evaluations + next_checks
    if total_checks > MAX_ROUTE_EVALUATIONS: raise ValueError('ORDINARY075_TOTAL_ROUTE_EVALUATION_ENVELOPE_EXCEEDED')
    for order_id in dispatched_now: day['dispatched'][order_id] = current_round
    day['round'] = current_round
    day['search_evaluations'] += current.evaluations
    day['safety_evaluations'] += current.safety_evaluations + next_checks
    day['history'].append({'dispatch_round': current_round, 'visible_order_count': len(visible), 'pending_order_count': len(pending), 'mandatory_order_count': len(mandatory), 'dispatched_order_count': len(dispatched_now), 'route_count': len(selected), 'known_directed_travel': travel, 'search_evaluations': current.evaluations, 'safety_evaluations': current.safety_evaluations + next_checks, 'route_evaluations': total_checks, 'insertion_options_considered': current.insertion_options, 'local_improvements': current.improvements, 'total_route_evaluation_budget': MAX_ROUTE_EVALUATIONS, 'search_budget': search_allowance, 'search_budget_exhausted': current.exhausted})
    return {'service_day_id': day_id, 'dispatch_round': current_round, 'routes': selected}, updated
