"""Independently implemented proof-certificate auditor.

Uses no inference and does not trust the producer's computed reachability.
An honest PASS replays every reachable state and transition from the frozen model.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json


class AuditError(Exception):
    pass


def _value(expr, env):
    if isinstance(expr, bool):
        return expr
    if isinstance(expr, int):
        return expr
    if isinstance(expr, str):
        return env[expr]
    op, *x = expr
    v = [_value(s, env) for s in x]
    if op == "add": return v[0] + v[1]
    if op == "sub": return v[0] - v[1]
    if op == "mul": return v[0] * v[1]
    if op == "eq": return v[0] == v[1]
    if op == "ne": return v[0] != v[1]
    if op == "lt": return v[0] < v[1]
    if op == "le": return v[0] <= v[1]
    if op == "gt": return v[0] > v[1]
    if op == "ge": return v[0] >= v[1]
    if op == "not": return not v[0]
    if op == "and": return v[0] and v[1]
    if op == "or": return v[0] or v[1]
    raise AuditError("unknown operation")


def audit(model, certificate, max_states=100_000):
    """Fail closed on missing states, forged edges, altered specs or failures."""
    from engine import canonical, validate   # Syntax validation only; semantics below independent.
    validate(model)
    if certificate.get("status") != "PASS" or certificate.get("schema") != "proof-omega.certificate.v1":
        raise AuditError("not a passing certificate")
    checksum = hashlib.sha256(canonical(model).encode()).hexdigest()
    if certificate.get("model_sha256") != checksum:
        raise AuditError("certificate is not bound to this policy")
    fields = sorted(model["variables"])
    if certificate.get("variables") != fields:
        raise AuditError("state schema mismatch")
    initial = tuple(model["initial"][v] for v in fields)
    seen = {initial}
    todo = deque([initial])
    edges = []
    while todo:
        here = todo.popleft()
        env = dict(zip(fields, here))
        for name, (lo, hi) in model["variables"].items():
            if not lo <= env[name] <= hi:
                raise AuditError("out-of-domain reachable state")
        for assertion in model["invariants"]:
            if _value(assertion["assert"], env) is not True:
                raise AuditError(f"invariant disproven: {assertion['name']}")
        for action in sorted(model["actions"], key=lambda x: x["name"]):
            guard = _value(action["when"], env)
            if type(guard) is not bool:
                raise AuditError("nonboolean guard")
            if not guard:
                continue
            after = dict(env)
            for key, expression in action["set"].items():
                nxt = _value(expression, env)
                if type(nxt) is not int:
                    raise AuditError("noninteger update")
                after[key] = nxt
            target = tuple(after[k] for k in fields)
            edges.append({"from": list(here), "action": action["name"], "to": list(target)})
            if target not in seen:
                seen.add(target)
                if len(seen) > max_states:
                    raise AuditError("auditor state limit exceeded")
                todo.append(target)
    expected_states = [list(x) for x in sorted(seen)]
    expected_edges = sorted(edges, key=lambda e: (e["from"], e["action"], e["to"]))
    if certificate.get("states") != expected_states:
        raise AuditError("certificate omitted or invented reachable states")
    if certificate.get("edges") != expected_edges:
        raise AuditError("certificate omitted or altered transitions")
    if certificate.get("state_count") != len(seen) or certificate.get("edge_count") != len(edges):
        raise AuditError("certificate count mismatch")
    return {"status": "AUDIT_PASS", "model_sha256": checksum,
            "independently_checked_states": len(seen), "independently_checked_edges": len(edges)}


def apply_verified(model, certificate, state, action):
    """Execute a proved transition from the frozen reachable-state graph."""
    audit(model, certificate)
    if set(state) != set(model["variables"]) or any(type(v) is not int for v in state.values()):
        raise AuditError("invalid state shape")
    fields = certificate["variables"]
    here = [state[k] for k in fields]
    for edge in certificate["edges"]:
        if edge["from"] == here and edge["action"] == action:
            return dict(zip(fields, edge["to"]))
    raise AuditError("refused: action disabled or state not reachable")
