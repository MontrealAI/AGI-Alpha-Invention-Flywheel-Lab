"""Exact finite minimum cover, with portable optimality certificates.

This is a new implementation using established branch-and-bound and hitting-set
methods. It is not an algorithmic novelty claim. There is no chemistry-specific
logic, pretrained answer, filesystem/network access, or successor-specific data.
The independent verifier must not import this module.
"""
from __future__ import annotations

import hashlib
import json
import time


def canonical_problem(option_ids, requirements):
    """Return a stable, validated finite incidence problem."""
    if not isinstance(option_ids, list) or any(not isinstance(x, str) or not x for x in option_ids):
        raise ValueError("option_ids must be a list of nonempty strings")
    if len(set(option_ids)) != len(option_ids):
        raise ValueError("duplicate option identifier")
    if not isinstance(requirements, list):
        raise ValueError("requirements must be a list")
    rows = []
    for row in requirements:
        if not isinstance(row, (list, tuple)):
            raise ValueError("each requirement must be a list of option indices")
        if any(type(x) is not int or x < 0 or x >= len(option_ids) for x in row):
            raise ValueError("invalid option index")
        if len(row) != len(set(row)):
            raise ValueError("duplicate option in a requirement")
        rows.append(sorted(row))
    return {"schema": "frontier-cover-instance/v1", "option_ids": list(option_ids), "requirements": rows}


def problem_digest(problem):
    return hashlib.sha256(json.dumps(problem, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _indices(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def solve_cover(option_ids, requirements, *, node_limit=1_000_000):
    """Find a minimum-cardinality cover and prove no smaller cover exists.

    A certificate is a DAG of exhaustive branches and combinatorial lower
    bounds. Every dominated branch has an explicit dominating option. A checker
    can verify it using integer set operations only, without trusting a floating
    point solver or this constructor. ``node_limit`` is a computational safeguard;
    exhaustion raises an error, never an optimum or a feasibility verdict.
    """
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    if type(node_limit) is not int or node_limit <= 0:
        raise ValueError("node_limit must be a positive integer")
    problem = canonical_problem(option_ids, requirements)
    rows = [sum(1 << x for x in row) for row in problem["requirements"]]
    covers = [0] * len(option_ids)
    for r, row in enumerate(problem["requirements"]):
        for c in row:
            covers[c] |= 1 << r
    all_rows = (1 << len(rows)) - 1
    nodes, memo = [], {}
    counters = {"search_calls": 0, "memo_hits": 0, "bounds": 0, "branches": 0}

    def record(node):
        nodes.append(node)
        return len(nodes) - 1

    def packing(uncovered):
        # Pairwise-disjoint candidate sets each require a different selected
        # option. Try two deterministic orders; both remain easily checkable.
        active = list(_indices(uncovered))
        orders = [sorted(active, key=lambda r: (rows[r].bit_count(), r)), active[::-1]]
        best = []
        for order in orders:
            used, packed = 0, []
            for r in order:
                if not rows[r] & used:
                    packed.append(r)
                    used |= rows[r]
            if len(packed) > len(best):
                best = packed
        return best

    def greedy(uncovered):
        chosen = []
        while uncovered:
            c = max(range(len(covers)), key=lambda x: ((covers[x] & uncovered).bit_count(), -x))
            gain = covers[c] & uncovered
            if not gain:
                return None
            chosen.append(c)
            uncovered &= ~gain
        return chosen

    def search(uncovered, budget):
        counters["search_calls"] += 1
        if counters["search_calls"] > node_limit:
            raise RuntimeError("SEARCH_RESOURCE_LIMIT: no qualification verdict")
        if not uncovered:
            return [], None
        key = (uncovered, budget)
        if key in memo:
            counters["memo_hits"] += 1
            return None, memo[key]
        active = list(_indices(uncovered))
        empty = next((r for r in active if not rows[r]), None)
        if empty is not None:
            p = record({"type": "empty", "row": empty})
            memo[key] = p
            return None, p
        packed = packing(uncovered)
        if len(packed) > budget:
            counters["bounds"] += 1
            p = record({"type": "packing", "rows": packed})
            memo[key] = p
            return None, p
        max_gain = max((c & uncovered).bit_count() for c in covers)
        if (uncovered.bit_count() + max_gain - 1) // max_gain > budget:
            counters["bounds"] += 1
            p = record({"type": "capacity"})
            memo[key] = p
            return None, p
        easy = greedy(uncovered)
        if easy is not None and len(easy) <= budget:
            return easy, None
        r = min(active, key=lambda q: (rows[q].bit_count(), q))
        choices = list(_indices(rows[r]))
        # Branch on representatives with maximal current coverage. For every
        # omitted candidate, retain a domination witness that a checker validates.
        choices.sort(key=lambda c: (-(covers[c] & uncovered).bit_count(), c))
        representatives, dominated = [], []
        for c in choices:
            cc = covers[c] & uncovered
            dominator = next((d for d in representatives if cc & ~covers[d] == 0), None)
            if dominator is None:
                representatives.append(c)
            else:
                dominated.append([c, dominator])
        children = []
        counters["branches"] += 1
        for c in representatives:
            suffix, proof = search(uncovered & ~covers[c], budget - 1)
            if suffix is not None:
                return [c] + suffix, None
            children.append([c, proof])
        p = record({"type": "branch", "row": r, "children": children, "dominated": dominated})
        memo[key] = p
        return None, p

    if any(not row for row in rows):
        bad = next(i for i, r in enumerate(rows) if not r)
        return {"status": "INFEASIBLE", "problem_sha256": problem_digest(problem), "empty_requirement": bad}
    initial = greedy(all_rows) if all_rows else []
    if initial is None:
        raise AssertionError("internal coverage inconsistency")
    chosen = initial
    # Starting from zero makes the lower-bound certificate available even if
    # the greedy upper bound is already optimal. Memoization preserves failed
    # search work; the serialized proof later retains only reachable nodes.
    lower_proof = None
    for budget in range(len(initial)):
        answer, proof = search(all_rows, budget)
        if answer is not None:
            chosen = answer
            break
        lower_proof = proof
    optimum = len(chosen)
    # Export just the proof required for k-1. Earlier failed attempts still
    # contribute to search counters and measured time, not redundant output.
    reachable, remap = [], {}

    def copy_node(index):
        if index in remap:
            return remap[index]
        node = dict(nodes[index])
        if node["type"] == "branch":
            node["children"] = [[c, copy_node(p)] for c, p in node["children"]]
        remap[index] = len(reachable)
        reachable.append(node)
        return remap[index]

    root = copy_node(lower_proof) if lower_proof is not None else None
    cert = {"schema": "frontier-min-cover-proof/v1", "problem_sha256": problem_digest(problem),
            "optimum": optimum, "selected": sorted(chosen), "root": root, "nodes": reachable}
    return {"status": "OPTIMAL", "selected": sorted(chosen), "cardinality": optimum,
            "certificate": cert, "stats": {**counters, "proof_nodes": len(reachable),
            "wall_seconds": time.perf_counter() - wall_start, "cpu_seconds": time.process_time() - cpu_start}}

