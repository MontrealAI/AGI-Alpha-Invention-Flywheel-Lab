"""Finite-state executable policy semantics and exhaustive reachability prover.

No eval/exec, no external calls, no implicit arithmetic wraparound.
The proof is about the reachable states of THIS declarative executable policy,
not about arbitrary code, network timing, compiled machine code or external services.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import re

SCHEMA = "proof-omega.finite-policy.v1"
OPERATIONS = {"add": 2, "sub": 2, "mul": 2, "eq": 2, "ne": 2, "lt": 2, "le": 2,
              "gt": 2, "ge": 2, "and": 2, "or": 2, "not": 1}
NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
MAX_EXPR_DEPTH = 16
MAX_VARIABLES = 16
MAX_ACTIONS = 64


class SpecificationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _check_expr(expr, names, depth=0):
    if depth > MAX_EXPR_DEPTH:
        raise SpecificationError("expression exceeds maximum depth")
    if type(expr) is bool or type(expr) is int:
        return
    if type(expr) is str:
        if expr not in names:
            raise SpecificationError(f"unknown variable {expr!r}")
        return
    if type(expr) is not list or not expr or type(expr[0]) is not str:
        raise SpecificationError(f"invalid expression: {expr!r}")
    operation = expr[0]
    if operation not in OPERATIONS or len(expr) - 1 != OPERATIONS[operation]:
        raise SpecificationError(f"unsupported operation/arity: {operation!r}")
    for value in expr[1:]:
        _check_expr(value, names, depth + 1)


def validate(model):
    if type(model) is not dict or set(model) != {"schema", "name", "variables", "initial", "actions", "invariants"}:
        raise SpecificationError("model must contain exactly schema,name,variables,initial,actions,invariants")
    if model["schema"] != SCHEMA or type(model["name"]) is not str or not model["name"]:
        raise SpecificationError("unsupported schema or empty name")
    bounds = model["variables"]
    if type(bounds) is not dict or not 1 <= len(bounds) <= MAX_VARIABLES:
        raise SpecificationError("invalid number of variables")
    for var, spec in bounds.items():
        if type(var) is not str or not NAME.fullmatch(var):
            raise SpecificationError("invalid variable name")
        if type(spec) is not list or len(spec) != 2 or any(type(x) is not int for x in spec):
            raise SpecificationError(f"{var}: bounds must be two integers")
        if spec[0] > spec[1] or spec[1] - spec[0] > 1_000_000:
            raise SpecificationError(f"{var}: unsupported bounds")
    initial = model["initial"]
    if type(initial) is not dict or set(initial) != set(bounds):
        raise SpecificationError("initial must define exactly the declared variables")
    for var, val in initial.items():
        if type(val) is not int or not bounds[var][0] <= val <= bounds[var][1]:
            raise SpecificationError(f"{var}: initial value outside domain")
    actions = model["actions"]
    if type(actions) is not list or not 1 <= len(actions) <= MAX_ACTIONS:
        raise SpecificationError("invalid actions")
    seen = set()
    for action in actions:
        if type(action) is not dict or set(action) != {"name", "when", "set"}:
            raise SpecificationError("each action requires name,when,set")
        name = action["name"]
        if type(name) is not str or not NAME.fullmatch(name) or name in seen:
            raise SpecificationError("action names must be unique and safe")
        seen.add(name)
        _check_expr(action["when"], bounds)
        if type(action["set"]) is not dict or not action["set"] or not set(action["set"]) <= set(bounds):
            raise SpecificationError(f"{name}: invalid set")
        for expr in action["set"].values():
            _check_expr(expr, bounds)
    invariants = model["invariants"]
    if type(invariants) is not list or not invariants:
        raise SpecificationError("at least one invariant required")
    names = set()
    for inv in invariants:
        if type(inv) is not dict or set(inv) != {"name", "assert"}:
            raise SpecificationError("invariant requires name,assert")
        if type(inv["name"]) is not str or not NAME.fullmatch(inv["name"]) or inv["name"] in names:
            raise SpecificationError("invariant names must be unique and safe")
        names.add(inv["name"])
        _check_expr(inv["assert"], bounds)
    return model


def evaluate(expr, state):
    if type(expr) in (int, bool):
        return expr
    if type(expr) is str:
        return state[expr]
    name = expr[0]
    args = [evaluate(arg, state) for arg in expr[1:]]
    if name in ("and", "or", "not"):
        if any(type(x) is not bool for x in args):
            raise SpecificationError("boolean operator requires booleans")
        return {"and": lambda: args[0] and args[1], "or": lambda: args[0] or args[1],
                "not": lambda: not args[0]}[name]()
    if any(type(x) is not int for x in args):
        raise SpecificationError("numeric or comparison operator requires integers")
    a, b = args
    return {
        "add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
        "eq": lambda: a == b, "ne": lambda: a != b, "lt": lambda: a < b,
        "le": lambda: a <= b, "gt": lambda: a > b, "ge": lambda: a >= b,
    }[name]()


def state_tuple(model, state):
    return tuple(state[k] for k in sorted(model["variables"]))


def state_dict(model, state):
    return dict(zip(sorted(model["variables"]), state))


def step(model, old, action):
    """Return new state or None if guard false. All updates are atomic."""
    guard = evaluate(action["when"], old)
    if type(guard) is not bool:
        raise SpecificationError("action guard must evaluate to a Boolean")
    if not guard:
        return None
    new = dict(old)
    for field, expr in action["set"].items():
        result = evaluate(expr, old)
        if type(result) is not int:
            raise SpecificationError("state updates must be integers")
        new[field] = result
    return new


def violations(model, state):
    problems = []
    for field, (minimum, maximum) in model["variables"].items():
        value = state[field]
        if type(value) is not int or not minimum <= value <= maximum:
            problems.append(f"domain:{field}")
    for invariant in model["invariants"]:
        outcome = evaluate(invariant["assert"], state)
        if outcome is not True:
            problems.append("invariant:" + invariant["name"])
    return problems


def explore(model, max_states=100_000):
    """Exact reachable-state closure: PASS only if all reachable edges checked."""
    validate(model)
    if type(max_states) is not int or max_states < 1:
        raise SpecificationError("positive state limit required")
    vars_ = sorted(model["variables"])
    initial = state_tuple(model, model["initial"])
    queue = deque([initial])
    reached = {initial}
    parent = {initial: None}
    edges = []
    checks = 0
    if (failure := violations(model, model["initial"])):
        return {"status": "FAIL", "counterexample": {"actions": [], "state": list(initial), "violations": failure},
                "model_sha256": fingerprint(model)}
    while queue:
        source = queue.popleft()
        old = dict(zip(vars_, source))
        for action in sorted(model["actions"], key=lambda a: a["name"]):
            try:
                updated = step(model, old, action)
            except SpecificationError as exc:
                return {"schema": "proof-omega.certificate.v1", "status": "HOLD_INVALID_POLICY",
                        "model_sha256": fingerprint(model), "observed_states": len(reached),
                        "checked_guards": checks + 1, "reason": str(exc)}
            checks += 1
            if updated is None:
                continue
            target = state_tuple(model, updated)
            if (failure := violations(model, updated)):
                history = [action["name"]]
                cursor = source
                while parent[cursor] is not None:
                    previous, previous_action = parent[cursor]
                    history.append(previous_action)
                    cursor = previous
                history.reverse()
                return {"schema": "proof-omega.certificate.v1", "status": "FAIL",
                        "model_sha256": fingerprint(model), "counterexample": {
                            "actions": history, "state": list(target), "violations": failure},
                        "observed_states": len(reached), "checked_guards": checks}
            edges.append({"from": list(source), "action": action["name"], "to": list(target)})
            if target not in reached:
                reached.add(target)
                parent[target] = (source, action["name"])
                if len(reached) > max_states:
                    return {"schema": "proof-omega.certificate.v1", "status": "HOLD_LIMIT",
                            "model_sha256": fingerprint(model), "observed_states": len(reached),
                            "limit": max_states, "reason": "incomplete reachable-state exploration"}
                queue.append(target)
    return {"schema": "proof-omega.certificate.v1", "status": "PASS",
            "model_sha256": fingerprint(model), "coverage": "EXACT_REACHABLE_CLOSURE_WITHIN_DECLARED_BOUNDS",
            "variables": vars_, "states": [list(s) for s in sorted(reached)],
            "edges": sorted(edges, key=lambda e: (e["from"], e["action"], e["to"])),
            "checked_guards": checks, "state_count": len(reached), "edge_count": len(edges),
            "claim": "specified invariants hold for all reachable states of this declared policy"}
