"""Construct complete OR-License wave assignments with ordinary CPU algorithms.

This code is written by the included agent during development, then executes
deterministically after freeze. It is not a model API or autonomous generator.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import resource
import time


class ConstructionFailure(ValueError):
    def __init__(self, message, trace=None):
        super().__init__(message)
        self.trace = trace or {}


def canonical_identity(value):
    """Preserve exact JSON integer/string identity; reject coercions and bools."""
    if type(value) is int:
        return ("int", value)
    if type(value) is str and value:
        return ("str", value)
    raise ValueError("identifier must be an exact integer or nonempty string")


def exact_cover(expected, groups):
    """Reusable discrete coverage instrument, without inferred missing values."""
    expected = set(expected)
    counts = Counter(item for group in groups for item in group)
    return {
        "missing": sorted(expected - counts.keys()),
        "unknown": sorted(counts.keys() - expected),
        "repeated": sorted(k for k, n in counts.items() if n != 1),
    }


@dataclass
class WaveContract:
    orders: dict
    slots: dict
    max_orders: int
    max_lines: int


def canonical_contract(data):
    """Build an applicability-checked representation of the source contract."""
    if not isinstance(data, dict):
        raise ValueError("input must be an object")
    for field in ("max_orders_per_wave", "max_lines_per_wave"):
        if type(data.get(field)) is not int or data[field] <= 0:
            raise ValueError(field + " must be a positive exact integer")
    slot_rows = data.get("time_slots")
    if not isinstance(slot_rows, list) or not slot_rows:
        raise ValueError("time_slots must be a nonempty array")
    slots = {}
    for row in slot_rows:
        if not isinstance(row, dict):
            raise ValueError("invalid time slot")
        sid = canonical_identity(row.get("slot_id"))
        cap = row.get("max_waves")
        if sid in slots or type(cap) is not int or cap < 0:
            raise ValueError("duplicate slot or invalid wave quota")
        slots[sid] = {"slot_id": row["slot_id"], "max_waves": cap}
    if not isinstance(data.get("orders"), list):
        raise ValueError("orders must be an array")
    orders = {}
    for row in data["orders"]:
        if not isinstance(row, dict):
            raise ValueError("invalid order")
        oid = row.get("order_id")
        if type(oid) is not str or not oid or oid in orders:
            raise ValueError("order_id must be a unique nonempty string")
        skus = row.get("skus")
        if not isinstance(skus, list) or not skus:
            raise ValueError("each order must contain SKU rows")
        codes = set()
        for sku in skus:
            code = sku.get("sku_code") if isinstance(sku, dict) else None
            qty = sku.get("loose_pick_qty") if isinstance(sku, dict) else None
            if type(code) is not str or not code or code in codes:
                raise ValueError("SKU codes must be unique nonempty strings per order")
            if (type(qty) not in (int, float) or qty <= 0
                    or (type(qty) is float and not math.isfinite(qty))):
                raise ValueError("loose_pick_qty must be positive and finite")
            codes.add(code)
        if len(skus) > data["max_lines_per_wave"]:
            raise ValueError("an indivisible order exceeds wave line capacity")
        allowed = row.get("eligible_slots")
        if not isinstance(allowed, list) or not allowed:
            raise ValueError("eligible_slots must be a nonempty array")
        eligible = [canonical_identity(s) for s in allowed]
        if len(eligible) != len(set(eligible)) or any(s not in slots for s in eligible):
            raise ValueError("eligible_slots has duplicate or undeclared typed identifiers")
        orders[oid] = {"skus": frozenset(codes), "lines": len(skus), "eligible": frozenset(eligible)}
    for field, actual in (("order_count", len(orders)), ("sku_line_count", sum(o["lines"] for o in orders.values()))):
        if field in data and (type(data[field]) is not int or data[field] != actual):
            raise ValueError(field + " disagrees with actual records")
    return WaveContract(orders, slots, data["max_orders_per_wave"], data["max_lines_per_wave"])


def validate_wave(data, artifact):
    """Independent local check of coverage, exact types, eligibility and capacity.

    This is an included instrument; original client acceptance remains separate.
    """
    contract = canonical_contract(data)
    if not isinstance(artifact, dict) or not isinstance(artifact.get("waves"), list):
        raise ValueError("artifact must contain a waves array")
    groups, usage = [], Counter()
    unique_lines = 0
    for wave in artifact["waves"]:
        if not isinstance(wave, dict) or not isinstance(wave.get("order_ids"), list):
            raise ValueError("wave must contain an order_ids array")
        ids = wave["order_ids"]
        if not ids or len(ids) > contract.max_orders or any(type(i) is not str or not i for i in ids):
            raise ValueError("invalid whole-order wave cardinality or identity")
        sid = canonical_identity(wave.get("slot_id"))
        if sid not in contract.slots:
            raise ValueError("wave slot has undeclared exact type/value")
        if any(i not in contract.orders for i in ids):
            raise ValueError("unknown order")
        if any(sid not in contract.orders[i]["eligible"] for i in ids):
            raise ValueError("wave slot outside at least one order's eligibility")
        if sum(contract.orders[i]["lines"] for i in ids) > contract.max_lines:
            raise ValueError("wave line capacity exceeded")
        usage[sid] += 1
        groups.append(ids)
        unique_lines += len(set().union(*(contract.orders[i]["skus"] for i in ids)))
    cover = exact_cover(contract.orders, groups)
    if any(cover.values()):
        raise ValueError("coverage failure: " + repr(cover))
    if any(n > contract.slots[s]["max_waves"] for s, n in usage.items()):
        raise ValueError("slot wave quota exceeded")
    total = sum(o["lines"] for o in contract.orders.values())
    return {"accepted": True, "orders": len(contract.orders), "sku_lines": total,
            "waves": len(groups), "unique_sku_lines": unique_lines,
            "score": unique_lines / total - 1 if total else None,
            "overlap_rate": 1 - unique_lines / total if total else None}


class _Flow:
    def __init__(self, size):
        self.graph = [[] for _ in range(size)]

    def add(self, source, target, capacity):
        edge = [target, len(self.graph[target]), capacity]
        back = [source, len(self.graph[source]), 0]
        self.graph[source].append(edge)
        self.graph[target].append(back)
        return edge

    def run(self, source, sink):
        total = 0
        while True:
            level = [-1] * len(self.graph)
            level[source] = 0
            queue = deque([source])
            while queue:
                node = queue.popleft()
                for target, _, capacity in self.graph[node]:
                    if capacity and level[target] < 0:
                        level[target] = level[node] + 1
                        queue.append(target)
            if level[sink] < 0:
                return total
            pointer = [0] * len(self.graph)

            def send(node, amount):
                if node == sink:
                    return amount
                while pointer[node] < len(self.graph[node]):
                    edge = self.graph[node][pointer[node]]
                    target, reverse, capacity = edge
                    if capacity and level[target] == level[node] + 1:
                        sent = send(target, min(amount, capacity))
                        if sent:
                            edge[2] -= sent
                            self.graph[target][reverse][2] += sent
                            return sent
                    pointer[node] += 1
                return 0

            while True:
                sent = send(source, len(self.graph))
                if not sent:
                    break
                total += sent


def _flow_assignment(contract):
    order_ids = sorted(contract.orders, key=lambda i: (len(contract.orders[i]["eligible"]), -contract.orders[i]["lines"], i))
    slot_ids = list(contract.slots)
    slot_number = {s: len(order_ids) + 1 + n for n, s in enumerate(slot_ids)}
    sink = len(order_ids) + len(slot_ids) + 1
    flow = _Flow(sink + 1)
    edges = {}
    for n, oid in enumerate(order_ids, 1):
        flow.add(0, n, 1)
        edges[oid] = []
        for sid in slot_ids:
            if sid in contract.orders[oid]["eligible"] and contract.slots[sid]["max_waves"]:
                edges[oid].append((sid, flow.add(n, slot_number[sid], 1)))
    for sid in slot_ids:
        flow.add(slot_number[sid], sink, contract.slots[sid]["max_waves"] * contract.max_orders)
    maximum = flow.run(0, sink)
    if maximum != len(order_ids):
        raise ConstructionFailure("proven infeasible: eligible-slot maximum flow covers " + str(maximum) + " of " + str(len(order_ids)))
    assigned = {s: [] for s in slot_ids}
    for oid in order_ids:
        used = [sid for sid, edge in edges[oid] if edge[2] == 0]
        if len(used) != 1:
            raise ConstructionFailure("internal flow extraction failure")
        assigned[used[0]].append(oid)
    return assigned


def _group_orders(contract, assigned):
    waves = []
    for sid, ids in assigned.items():
        remaining = set(ids)
        while remaining:
            if len(remaining) >= 2:
                pairs = ((a, b) for a in sorted(remaining) for b in sorted(remaining) if a < b)
                a, b = min(pairs, key=lambda pair: (-len(contract.orders[pair[0]]["skus"] & contract.orders[pair[1]]["skus"]), pair))
                group = [a, b] if contract.max_orders >= 2 else [a]
            else:
                group = [min(remaining)]
            remaining.difference_update(group)
            union = set().union(*(contract.orders[i]["skus"] for i in group))
            while remaining and len(group) < contract.max_orders:
                oid = min(remaining, key=lambda i: (-len(union & contract.orders[i]["skus"]), i))
                group.append(oid)
                union.update(contract.orders[oid]["skus"])
                remaining.remove(oid)
            waves.append({"slot_id": contract.slots[sid]["slot_id"], "order_ids": group})
    return waves


def _milp_waves(contract, trace):
    """Ordinary complete wave-indexed binary formulation for binding line caps."""
    import numpy as np
    import scipy
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    order_ids = list(contract.orders)
    oid_row = {oid: n for n, oid in enumerate(order_ids)}
    bins = [(sid, wave) for sid in contract.slots for wave in range(contract.slots[sid]["max_waves"])]
    bin_index = {item: n for n, item in enumerate(bins)}
    variables = [(oid, sid, wave) for oid in order_ids for sid in contract.slots
                 if sid in contract.orders[oid]["eligible"] for wave in range(contract.slots[sid]["max_waves"])]
    if order_ids and not variables:
        raise ConstructionFailure("proven infeasible: no eligible wave capacity")
    rows, cols, values = [], [], []
    norders, nbins = len(order_ids), len(bins)
    for column, (oid, sid, wave) in enumerate(variables):
        b = bin_index[(sid, wave)]
        rows.extend((oid_row[oid], norders + b, norders + nbins + b))
        cols.extend((column, column, column))
        values.extend((1, 1, contract.orders[oid]["lines"]))
    matrix = coo_matrix((values, (rows, cols)), shape=(norders + 2 * nbins, len(variables))).tocsc()
    lower = np.concatenate((np.ones(norders), np.zeros(2 * nbins)))
    upper = np.concatenate((np.ones(norders), np.full(nbins, contract.max_orders), np.full(nbins, contract.max_lines)))
    result = milp(np.zeros(len(variables)), integrality=np.ones(len(variables)), bounds=Bounds(0, 1), constraints=LinearConstraint(matrix, lower, upper), options={"presolve": True})
    trace["milp"] = {"library": "scipy.optimize.milp", "version": scipy.__version__, "status": int(result.status), "message": str(result.message), "variables": len(variables), "constraints": len(lower), "mip_node_count": getattr(result, "mip_node_count", None)}
    if result.x is None:
        status = "proven infeasible" if result.status == 2 else "unresolved solver outcome"
        raise ConstructionFailure(status + ": " + str(result.message))
    grouped = {item: [] for item in bins}
    for value, (oid, sid, wave) in zip(result.x, variables):
        if value > 0.5:
            grouped[(sid, wave)].append(oid)
    return [{"slot_id": contract.slots[sid]["slot_id"], "order_ids": ids}
            for (sid, _), ids in grouped.items() if ids]


def _improve_overlap(contract, waves):
    """Conventional exact-integer local descent; feasibility is preserved."""
    accepted_moves, passes = 0, 0
    while True:
        passes += 1
        unions = [set().union(*(contract.orders[o]["skus"] for o in w["order_ids"])) for w in waves]
        lines = [sum(contract.orders[o]["lines"] for o in w["order_ids"]) for w in waves]
        inverse = {}
        for n, skus in enumerate(unions):
            for sku in skus:
                inverse.setdefault(sku, []).append(n)
        pairs = set()
        for ids in inverse.values():
            pairs.update((a, b) for a in ids for b in ids if a < b)
        changed = False
        for a, b in sorted(pairs):
            wa, wb = waves[a], waves[b]
            ia, ib = wa["order_ids"], wb["order_ids"]
            if not ia or not ib:
                continue
            sa, sb = canonical_identity(wa["slot_id"]), canonical_identity(wb["slot_id"])
            old = len(unions[a]) + len(unions[b])
            best = None
            def consider(na, nb):
                nonlocal best
                ua = set().union(*(contract.orders[o]["skus"] for o in na))
                ub = set().union(*(contract.orders[o]["skus"] for o in nb))
                cost = len(ua) + len(ub)
                candidate = (cost, tuple(na), tuple(nb))
                if cost < old and (best is None or candidate < best[0]):
                    best = (candidate, na, nb, ua, ub)
            if len(ib) < contract.max_orders:
                for oid in ia:
                    if sb in contract.orders[oid]["eligible"] and lines[b] + contract.orders[oid]["lines"] <= contract.max_lines:
                        consider([i for i in ia if i != oid], ib + [oid])
            if len(ia) < contract.max_orders:
                for oid in ib:
                    if sa in contract.orders[oid]["eligible"] and lines[a] + contract.orders[oid]["lines"] <= contract.max_lines:
                        consider(ia + [oid], [i for i in ib if i != oid])
            for oa in ia:
                for ob in ib:
                    if sb not in contract.orders[oa]["eligible"] or sa not in contract.orders[ob]["eligible"]:
                        continue
                    la = lines[a] - contract.orders[oa]["lines"] + contract.orders[ob]["lines"]
                    lb = lines[b] - contract.orders[ob]["lines"] + contract.orders[oa]["lines"]
                    if la <= contract.max_lines and lb <= contract.max_lines:
                        consider([ob if i == oa else i for i in ia], [oa if i == ob else i for i in ib])
            if best:
                _, wa["order_ids"], wb["order_ids"], unions[a], unions[b] = best
                lines[a] = sum(contract.orders[o]["lines"] for o in wa["order_ids"])
                lines[b] = sum(contract.orders[o]["lines"] for o in wb["order_ids"])
                accepted_moves += 1
                changed = True
        waves = [w for w in waves if w["order_ids"]]
        if not changed:
            return waves, {"accepted_strict_improvements": accepted_moves, "passes": passes, "termination": "no improving eligible pair move/swap; local optimum only"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build(data, retained=None):
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    trace = {"procedure": "typed-capacity-wave-construction-v1", "attempts": [], "input_sha256": _digest(data), "generation": "Actual included-agent development; deterministic frozen ordinary software execution", "retained_supplied": retained is not None}
    try:
        contract = canonical_contract(data)
        trace["primitive_calls"] = ["canonical_contract", "canonical_identity", "exact_cover", "validate_wave"]
        trace["counts"] = {"orders": len(contract.orders), "lines": sum(o["lines"] for o in contract.orders.values()), "slots": len(contract.slots)}
        largest = {sid: sum(sorted((o["lines"] for o in contract.orders.values() if sid in o["eligible"]), reverse=True)[:contract.max_orders]) for sid in contract.slots}
        redundant = all(n <= contract.max_lines for n in largest.values())
        trace["applicability"] = {"line_capacity_redundant_for_any_cardinality_legal_wave": redundant, "max_slot_top_k_line_sum": max(largest.values(), default=0), "max_lines": contract.max_lines}
        if redundant:
            trace["attempts"].append({"method": "ordinary bipartite maximum flow, then SKU-overlap grouping", "status": "started"})
            assigned = _flow_assignment(contract)
            waves = _group_orders(contract, assigned)
            trace["attempts"][-1]["status"] = "constructed"
        else:
            trace["attempts"].append({"method": "ordinary wave-indexed binary MILP", "status": "started"})
            waves = _milp_waves(contract, trace)
            trace["attempts"][-1]["status"] = "constructed"
        initial = validate_wave(data, {"waves": waves})
        waves, trace["local_search"] = _improve_overlap(contract, waves)
        artifact = {"waves": [{"wave_id": n, **w} for n, w in enumerate(waves, 1)]}
        trace["initial_local_check"] = initial
        trace["final_local_check"] = validate_wave(data, artifact)
        trace["artifact_sha256"] = _digest(artifact)
        trace["decision"] = "constructed_pending_original_client_acceptance"
        return artifact, trace
    except (ValueError, KeyError, TypeError) as error:
        trace["decision"], trace["error"] = "failed_or_unsupported", str(error)
        raise ConstructionFailure(str(error), trace) from error
    finally:
        trace["resources"] = {"wall_seconds": time.perf_counter() - start_wall, "process_cpu_seconds": time.process_time() - start_cpu, "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "model_api_calls": 0, "actual_billing": None}


def construct(data, retained=None):
    return build(data, retained)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--trace", required=True)
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.input).read_text())
        artifact, trace = build(data)
        Path(args.output).write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n")
        code = 0
    except ConstructionFailure as error:
        trace, code = error.trace, 2
    except (OSError, ValueError) as error:
        trace, code = {"decision": "failed_or_unsupported", "error": str(error),
                       "error_type": type(error).__name__, "resources": {"actual_billing": None}}, 2
    Path(args.trace).write_text(json.dumps(trace, sort_keys=True, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
