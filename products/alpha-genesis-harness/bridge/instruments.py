# SPDX-License-Identifier: Apache-2.0
"""Portable bounded instrument evaluator. Never evaluates Python or shell source."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def finite(value, depth=0):
    if depth > 32:
        raise ValueError("Input nesting bound exceeded.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite numbers are not supported.")
    if type(value) in {int, float} and (type(value) is int or value.is_integer()) and abs(value) > 9007199254740991:
        raise ValueError("Integer exceeds the exact portable numerical range.")
    if isinstance(value, (list, dict)):
        for item in (value.values() if isinstance(value, dict) else value):
            finite(item, depth + 1)
    return value


def evaluate(spec, inputs, max_operations=10000):
    """Evaluate a JSON expression grammar, with no IO or dynamic code execution."""
    if not isinstance(spec, dict) or set(spec) - {"name", "inputs", "outputs", "description", "conditions", "limitations"}:
        raise ValueError("Unsupported instrument specification.")
    if not isinstance(spec.get("inputs"), list) or any(not isinstance(k, str) for k in spec["inputs"]):
        raise ValueError("Instrument inputs must be field names.")
    if not isinstance(inputs, dict) or any(k not in inputs for k in spec["inputs"]):
        raise ValueError("A declared instrument input is missing.")
    if not isinstance(spec.get("outputs"), dict) or not spec["outputs"]:
        raise ValueError("An instrument needs named output expressions.")
    if type(max_operations) is not int or max_operations < 1:
        raise ValueError("A positive operation bound is required.")
    count = 0

    def number(v):
        if type(v) not in {int, float}:
            raise ValueError("Arithmetic requires numeric operands.")
        return finite(v)

    def visit(value, depth=0):
        nonlocal count
        count += 1
        if count > max_operations or depth > 32:
            raise ValueError("Instrument operation or nesting bound exhausted.")
        if value is None or type(value) in {str, int, float, bool}:
            return finite(value)
        if isinstance(value, list):
            return [visit(v, depth + 1) for v in value]
        if not isinstance(value, dict):
            raise ValueError("Only JSON expressions are supported.")
        if set(value) == {"field"}:
            path = value["field"]
            if not isinstance(path, str) or not path:
                raise ValueError("Invalid input field.")
            if path.split(".")[0] not in spec["inputs"]:
                raise ValueError("Input field root was not declared.")
            at = inputs
            for part in path.split("."):
                if part in {"__proto__", "prototype", "constructor"} or not isinstance(at, dict) or part not in at:
                    raise ValueError("Missing or unsafe input field.")
                at = at[part]
            return finite(at)
        if set(value) != {"op", "args"} or not isinstance(value["args"], list):
            raise ValueError("Expressions require only op and args.")
        op, raw = value["op"], value["args"]
        if op == "if":
            if len(raw) != 3:
                raise ValueError("if needs three operands.")
            cond = visit(raw[0], depth + 1)
            if type(cond) is not bool:
                raise ValueError("if condition must be boolean.")
            return visit(raw[1] if cond else raw[2], depth + 1)
        args = [visit(v, depth + 1) for v in raw]
        if op in {"add", "mul", "min", "max"}:
            if not args:
                raise ValueError("Arithmetic needs operands.")
            vals = [number(v) for v in args]
            result = vals[0]
            for val in vals[1:]:
                result = finite(result + val if op == "add" else result * val if op == "mul" else min(result, val) if op == "min" else max(result, val))
        elif op in {"sub", "div"}:
            if len(args) != 2:
                raise ValueError("Binary arithmetic needs two operands.")
            a, b = map(number, args)
            if op == "div" and b == 0:
                raise ValueError("Division by zero.")
            result = a - b if op == "sub" else a / b
        elif op in {"eq", "lt", "lte", "gt", "gte"}:
            if len(args) != 2:
                raise ValueError("Comparison needs two operands.")
            a, b = args
            if op == "eq":
                result = (type(a) is type(b) or (type(a) in {int, float} and type(b) in {int, float})) and a == b
            else:
                a, b = number(a), number(b)
                result = a < b if op == "lt" else a <= b if op == "lte" else a > b if op == "gt" else a >= b
        elif op in {"and", "or", "not"}:
            if not args or any(type(v) is not bool for v in args) or (op == "not" and len(args) != 1):
                raise ValueError("Boolean operation needs boolean operands.")
            result = all(args) if op == "and" else any(args) if op == "or" else not args[0]
        elif op in {"sum", "count"}:
            if len(args) != 1 or not isinstance(args[0], list):
                raise ValueError("sum/count needs one array.")
            result = len(args[0]) if op == "count" else 0
            if op == "sum":
                for item in args[0]:
                    count += 1
                    if count > max_operations:
                        raise ValueError("Instrument operation bound exhausted.")
                    result = finite(result + number(item))
        else:
            raise ValueError("Unsupported expression operation.")
        return finite(result)

    finite(inputs)
    result = {key: visit(expr) for key, expr in spec["outputs"].items()}
    return {"output": result, "operations": count, "scope": "Bounded declarative execution; acceptance must be checked separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instrument", type=Path)
    parser.add_argument("input", type=Path)
    parser.add_argument("--max-operations", type=int, default=10000)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.instrument.read_text()), json.loads(args.input.read_text()), args.max_operations), ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
