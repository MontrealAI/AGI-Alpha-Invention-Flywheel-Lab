#!/usr/bin/env python3
"""PROOF Ω. Complete enumeration of a bounded *declarative* rule specification.

Not a proof of arbitrary Python/machine code, not a Lean/SMT proof.
Unknown, unbounded, vacuous and undefined cases all fail closed.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

MAX_STATES = 1_000_000
MAX_ABS = 1_000_000_000
SAFE_NAME = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")

class ProofError(ValueError):
    pass

def unique_pairs(pairs):
    obj = {}
    for name, value in pairs:
        if name in obj:
            raise ProofError("duplicate JSON field: " + name)
        obj[name] = value
    return obj

def read(path):
    raw = Path(path).read_bytes()
    if len(raw) > 100_000:
        raise ProofError("input exceeds 100KB")
    return json.loads(raw, object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ProofError("nonfinite JSON")))

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)

def sha(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()

def parse(source, names):
    if not isinstance(source, str) or not source or len(source) > 512:
        raise ProofError("invalid expression size")
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ProofError("invalid expression grammar") from exc
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ProofError("expression too complex")
    def check(node, depth=0):
        if depth > 24:
            raise ProofError("expression too deep")
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
            if type(node.value) is int and abs(node.value) > MAX_ABS:
                raise ProofError("literal exceeds limit")
        elif isinstance(node, ast.Name) and node.id in names:
            pass
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)):
            check(node.left, depth + 1); check(node.right, depth + 1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            check(node.operand, depth + 1)
        elif isinstance(node, ast.Compare) and all(isinstance(x, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for x in node.ops):
            check(node.left, depth + 1)
            for x in node.comparators: check(x, depth + 1)
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)) and len(node.values) >= 2:
            for x in node.values: check(x, depth + 1)
        elif isinstance(node, ast.IfExp):
            check(node.test, depth + 1); check(node.body, depth + 1); check(node.orelse, depth + 1)
        else:
            raise ProofError("unsafe/unsupported expression: " + type(node).__name__)
    check(tree.body)
    return tree.body

def integer(v):
    if type(v) is not int:
        raise ProofError("noninteger in arithmetic")
    if v.bit_length() > 128:
        raise ProofError("arithmetic size exceeded")
    return v

def boolean(v):
    if type(v) is not bool:
        raise ProofError("predicate did not return boolean")
    return v

def evaluate(n, env):
    if isinstance(n, ast.Constant): return n.value
    if isinstance(n, ast.Name): return env[n.id]
    if isinstance(n, ast.BinOp):
        x, y = integer(evaluate(n.left, env)), integer(evaluate(n.right, env))
        if isinstance(n.op, ast.Add): v = x + y
        elif isinstance(n.op, ast.Sub): v = x - y
        elif isinstance(n.op, ast.Mult): v = x * y
        elif isinstance(n.op, ast.FloorDiv):
            if y == 0: raise ProofError("division by zero")
            v = x // y
        else:
            if y == 0: raise ProofError("modulo by zero")
            v = x % y
        return integer(v)
    if isinstance(n, ast.UnaryOp):
        x = evaluate(n.operand, env)
        if isinstance(n.op, ast.Not): return not boolean(x)
        return integer(-integer(x) if isinstance(n.op, ast.USub) else integer(x))
    if isinstance(n, ast.BoolOp):
        if isinstance(n.op, ast.And):
            for x in n.values:
                if not boolean(evaluate(x, env)): return False
            return True
        for x in n.values:
            if boolean(evaluate(x, env)): return True
        return False
    if isinstance(n, ast.Compare):
        x = evaluate(n.left, env)
        for op, expr in zip(n.ops, n.comparators):
            y = evaluate(expr, env)
            if type(x) is not type(y): raise ProofError("mixed comparison types")
            if isinstance(op, ast.Eq): ok = x == y
            elif isinstance(op, ast.NotEq): ok = x != y
            elif isinstance(op, ast.Lt): ok = x < y
            elif isinstance(op, ast.LtE): ok = x <= y
            elif isinstance(op, ast.Gt): ok = x > y
            else: ok = x >= y
            if not ok: return False
            x = y
        return True
    if isinstance(n, ast.IfExp):
        return evaluate(n.body if boolean(evaluate(n.test, env)) else n.orelse, env)
    raise ProofError("unsupported runtime node")

def prepare(c):
    if not isinstance(c, dict) or set(c) != {"schema", "name", "domain", "reference", "candidate", "preconditions", "invariants"} or type(c["schema"]) is not int or c["schema"] != 1:
        raise ProofError("invalid contract schema")
    if not isinstance(c["name"], str) or not 1 <= len(c["name"]) <= 120:
        raise ProofError("invalid contract name")
    dom = c["domain"]
    if not isinstance(dom, dict) or not 1 <= len(dom) <= 4: raise ProofError("1–4 variables required")
    states = 1
    for name, pair in dom.items():
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or name == "out":
            raise ProofError("invalid variable name")
        if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int or abs(x) > MAX_ABS for x in pair) or pair[1] < pair[0]:
            raise ProofError("invalid finite bounds")
        states *= pair[1] - pair[0] + 1
    if states > MAX_STATES: raise ProofError("domain too large for exhaustive proof: HOLD, never sample")
    pre, inv = c["preconditions"], c["invariants"]
    if not isinstance(pre, list) or not isinstance(inv, list) or len(pre) > 12 or not 1 <= len(inv) <= 12:
        raise ProofError("invariants required; max 12 predicates each")
    vars_ = set(dom)
    parsed = {"reference": parse(c["reference"], vars_), "candidate": parse(c["candidate"], vars_),
              "preconditions": [parse(x, vars_) for x in pre],
              "invariants": [parse(x, vars_ | {"out"}) for x in inv]}
    return parsed, states

def proxy(node):
    """Operator-count proxy; never infer elapsed time or financial gains."""
    return sum(3 if isinstance(n.op, ast.Mult) else 8 if isinstance(n.op, (ast.FloorDiv, ast.Mod)) else 1
               for n in ast.walk(node) if isinstance(n, ast.BinOp))

def prove(contract):
    p, total = prepare(contract)
    names = sorted(contract["domain"])
    ranges = [range(contract["domain"][k][0], contract["domain"][k][1] + 1) for k in names]
    result = {"product": "PROOF Ω / finite declarative scope", "schema": 1,
              "status": "HOLD", "scope": "ALL_ADMITTED_FINITE_INPUTS_NOT_GENERAL_SOFTWARE",
              "contract_sha256": sha(contract), "states_total": total,
              "states_admitted": 0, "states_checked": 0,
              "reference_cost_proxy": proxy(p["reference"]), "candidate_cost_proxy": proxy(p["candidate"]),
              "counterexample": None, "witness_stream_sha256": None}
    stream = hashlib.sha256()
    for row in itertools.product(*ranges):
        env = dict(zip(names, row))
        try:
            if not all(boolean(evaluate(x, env)) for x in p["preconditions"]): continue
            result["states_admitted"] += 1
            old = integer(evaluate(p["reference"], env))
            new = integer(evaluate(p["candidate"], env))
            if old != new:
                result["counterexample"] = {"input": env, "reference": old, "candidate": new, "violation": "non_equivalence"}
                break
            for index, invariant in enumerate(p["invariants"]):
                if not boolean(evaluate(invariant, {**env, "out": new})):
                    result["counterexample"] = {"input": env, "output": new, "violation": "invariant", "index": index}
                    break
            if result["counterexample"] is not None: break
            result["states_checked"] += 1
            stream.update((canonical({"input": env, "output": new}) + "\n").encode())
        except ProofError as exc:
            result["counterexample"] = {"input": env, "violation": "undefined", "reason": str(exc)}
            break
    result["witness_stream_sha256"] = stream.hexdigest()
    if result["counterexample"] is None and result["states_admitted"]:
        result["status"] = "VERIFIED_BOUNDED"
    elif not result["states_admitted"] and result["counterexample"] is None:
        result["counterexample"] = {"violation": "vacuous_preconditions"}
    return result

def factor(source):
    """One *known* algebraic rewrite; this is not a novel algorithm discovery."""
    tree = ast.parse(source, mode="eval")
    def same(a, b): return ast.dump(a) == ast.dump(b)
    class Rewriter(ast.NodeTransformer):
        def visit_BinOp(self, node):
            node = self.generic_visit(node)
            if not isinstance(node.op, (ast.Add, ast.Sub)) or not all(isinstance(x, ast.BinOp) and isinstance(x.op, ast.Mult) for x in (node.left, node.right)):
                return node
            for a, b in ((node.left.left, node.left.right), (node.left.right, node.left.left)):
                for c, d in ((node.right.left, node.right.right), (node.right.right, node.right.left)):
                    if same(a, c):
                        return ast.BinOp(left=a, op=ast.Mult(), right=ast.BinOp(left=b, op=node.op, right=d))
            return node
    return ast.unparse(Rewriter().visit(tree))

def invent(contract):
    prepare(contract)
    proposed = dict(contract)
    proposed["candidate"] = factor(contract["reference"])
    report = prove(proposed)
    if report["status"] != "VERIFIED_BOUNDED" or report["candidate_cost_proxy"] >= report["reference_cost_proxy"]:
        report["status"] = "HOLD"
        report["admission"] = "NO_LOWER_OPERATOR_COST_VERIFIED"
    else:
        report["admission"] = "LOWER_STATIC_PROXY_ONLY_NOT_MEASURED_SPEED"
    return proposed, report

def write(path, data):
    if path:
        Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

def main(argv=None):
    app = argparse.ArgumentParser(description="PROOF Ω: fully replayable bounded proof certificates")
    s = app.add_subparsers(dest="action", required=True)
    p = s.add_parser("verify"); p.add_argument("contract"); p.add_argument("--output")
    p = s.add_parser("invent"); p.add_argument("contract"); p.add_argument("--output", required=True); p.add_argument("--report", required=True)
    p = s.add_parser("replay"); p.add_argument("contract"); p.add_argument("report")
    s.add_parser("demo")
    args = app.parse_args(argv)
    try:
        if args.action == "demo":
            example = {"schema": 1, "name": "synthetic invoice math", "domain": {"hours": [0, 20], "rate": [0, 30], "rebate": [0, 10]},
                       "reference": "hours * rate - hours * rebate", "candidate": "hours * rate - hours * rebate",
                       "preconditions": ["rebate <= rate"], "invariants": ["out >= 0"]}
            _, report = invent(example)
        elif args.action == "replay":
            contract = read(args.contract)
            verified = prove(contract)
            supplied = read(args.report)
            if (isinstance(supplied, dict) and supplied.get("admission") == "LOWER_STATIC_PROXY_ONLY_NOT_MEASURED_SPEED"
                and verified["status"] == "VERIFIED_BOUNDED"
                and verified["candidate_cost_proxy"] < verified["reference_cost_proxy"]):
                verified["admission"] = "LOWER_STATIC_PROXY_ONLY_NOT_MEASURED_SPEED"
            report = {"status": "REPLAY_VERIFIED" if verified["status"] == "VERIFIED_BOUNDED" and verified == supplied else "HOLD",
                      "contract_sha256": sha(contract)}
        elif args.action == "invent":
            proposed, report = invent(read(args.contract))
            write(args.output, proposed); write(args.report, report)
        else:
            report = prove(read(args.contract)); write(args.output, report)
    except (ProofError, OSError, TypeError, KeyError, json.JSONDecodeError, RecursionError) as exc:
        report = {"status": "HOLD", "reason": str(exc)[:400]}
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] in ("VERIFIED_BOUNDED", "REPLAY_VERIFIED") else 2

if __name__ == "__main__":
    sys.exit(main())
