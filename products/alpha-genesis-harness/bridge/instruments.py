# SPDX-License-Identifier: Apache-2.0
"""Portable bounded instrument evaluator. Never evaluates Python or shell source."""
from __future__ import annotations

import argparse
import ast
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import re
import tokenize


# Pin source at this module's own load, before a later lazy GENESIS import.
LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

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


def _json_equal(left, right):
    """Compare JSON values recursively without treating booleans as numbers."""
    if type(left) in {int, float} and type(right) in {int, float}:
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return set(left) == set(right) and all(_json_equal(left[key], right[key]) for key in left)
    return left == right


_BINARY = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div"}
_COMPARISONS = {ast.Eq: "eq", ast.Lt: "lt", ast.LtE: "lte", ast.Gt: "gt", ast.GtE: "gte"}
_FUNCTIONS = {"abs", "min", "max", "sum", "count", "choose"}
_JSON_LITERALS = {"true": True, "false": False, "null": None}


def compile_formula(source, bindings):
    """Translate a small expression syntax to evaluator operations. Never compile Python bytecode."""
    if not isinstance(source, str) or not 0 < len(source) <= 1024:
        raise ValueError("Formula text must be between 1 and 1024 characters.")
    source = source.strip()
    if "\n" in source or "\r" in source:
        raise ValueError("Each formula must fit on one line.")
    try:
        if "&&" in source or "||" in source:
            # Accept common boolean spellings only at operator tokens, never
            # inside a literal or an identifier.
            tokens = list(tokenize.generate_tokens(StringIO(source).readline))
            aliases = {"&": " and ", "|": " or "}
            replacements = [(left.start[1], right.end[1], aliases[left.string])
                            for left, right in zip(tokens, tokens[1:])
                            if left.type == right.type == tokenize.OP and left.string in aliases
                            and left.string == right.string and left.end == right.start]
            for start, end, replacement in reversed(replacements):
                source = source[:start] + replacement + source[end:]
        expression = ast.parse(source, mode="eval").body
    except (SyntaxError, RecursionError, tokenize.TokenError) as error:
        raise ValueError("Formula syntax is invalid.") from error

    def operation(name, *args):
        return {"op": name, "args": list(args)}

    def translate(node, depth=0):
        if depth > 24:
            raise ValueError("Formula nesting bound exhausted.")
        def child(value):
            return translate(value, depth + 1)
        if isinstance(node, ast.Constant) and type(node.value) in {type(None), bool, int, float, str}:
            return finite(node.value)
        if isinstance(node, ast.Name):
            if node.id in _JSON_LITERALS:
                return _JSON_LITERALS[node.id]
            return {"ref" if node.id in bindings else "field": node.id}
        if isinstance(node, ast.List):
            return [child(item) for item in node.elts]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return operation(_BINARY[type(node.op)], child(node.left), child(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub)):
            return operation("not", child(node.operand)) if isinstance(node.op, ast.Not) else operation("sub", 0, child(node.operand))
        if isinstance(node, ast.BoolOp):
            return operation("and" if isinstance(node.op, ast.And) else "or", *(child(item) for item in node.values))
        if isinstance(node, ast.Compare) and all(type(op) in _COMPARISONS for op in node.ops):
            operands = [node.left, *node.comparators]
            terms = [operation(_COMPARISONS[type(op)], child(operands[i]), child(operands[i + 1])) for i, op in enumerate(node.ops)]
            return terms[0] if len(terms) == 1 else operation("and", *terms)
        if isinstance(node, ast.IfExp):
            return operation("if", child(node.test), child(node.body), child(node.orelse))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords:
            return operation("if" if node.func.id == "choose" else node.func.id, *(child(arg) for arg in node.args))
        raise ValueError("Formula uses an unsupported expression or function.")

    return translate(expression)


def evaluate(spec, inputs, max_operations=10000):
    """Evaluate a JSON expression grammar, with no IO or dynamic code execution."""
    allowed_keys = {"name", "inputs", "outputs", "description", "conditions", "limitations", "bindings"}
    if not isinstance(spec, dict):
        kind = {type(None): "null", bool: "boolean", int: "number", float: "number", str: "string", list: "array"}.get(type(spec), "non-JSON type")
        raise ValueError("Unsupported instrument specification. Expected a JSON object at the root; received " + kind + ".")
    unsupported_keys = set(spec) - allowed_keys
    if unsupported_keys:
        names = sorted(key for key in unsupported_keys if isinstance(key, str))
        # Names are untrusted too: escape controls, bound size, and never render values.
        shown = [key if len(key) <= 64 else key[:64] + "...[truncated]" for key in names[:8]]
        details = json.dumps(shown)
        if len(names) > len(shown):
            details += " (" + str(len(names) - len(shown)) + " additional key names omitted)"
        if len(unsupported_keys) != len(names):
            details += "; " + str(len(unsupported_keys) - len(names)) + " <non-string key> entries"
        raise ValueError("Unsupported instrument specification. Unsupported top-level keys: " + details
                         + ". Allowed top-level keys: " + json.dumps(sorted(allowed_keys))
                         + '. Named calculations belong inside the "outputs" object, not at the instrument root.')
    if not isinstance(spec.get("inputs"), list) or any(not isinstance(k, str) for k in spec["inputs"]):
        raise ValueError("Instrument inputs must be field names.")
    if not isinstance(inputs, dict) or any(k not in inputs for k in spec["inputs"]):
        raise ValueError("A declared instrument input is missing.")
    if not isinstance(spec.get("outputs"), dict) or not spec["outputs"]:
        raise ValueError("An instrument needs named output expressions.")
    if type(max_operations) is not int or max_operations < 1:
        raise ValueError("A positive operation bound is required.")
    bindings = spec.get("bindings", {})
    if not isinstance(bindings, dict) or len(bindings) > 128 or any(
        not isinstance(key, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key) is None for key in bindings
    ):
        raise ValueError("Instrument bindings require up to 128 simple names.")
    resolved, resolving, compiled = {}, set(), {}
    count = 0

    def number(v):
        if type(v) not in {int, float}:
            raise ValueError("Arithmetic requires numeric operands.")
        return finite(v)

    def visit(value, depth=0, location="$"):
        nonlocal count
        count += 1
        if count > max_operations or depth > 32:
            raise ValueError("Instrument operation or nesting bound exhausted.")
        if value is None or type(value) in {str, int, float, bool}:
            return finite(value)
        if isinstance(value, list):
            return [visit(v, depth + 1, f"{location}[{index}]") for index, v in enumerate(value)]
        if not isinstance(value, dict):
            raise ValueError("Only JSON expressions are supported.")
        if set(value) == {"formula"}:
            source = value["formula"]
            if not isinstance(source, str):
                raise ValueError("Formula text is required.")
            if source not in compiled:
                compiled[source] = compile_formula(source, bindings)
            return visit(compiled[source], depth + 1, location + ".formula")
        if set(value) == {"ref"}:
            name = value["ref"]
            if not isinstance(name, str) or name not in bindings:
                raise ValueError("Unknown instrument binding.")
            if name in resolving:
                raise ValueError("Instrument bindings cannot reference a cycle.")
            if name not in resolved:
                resolving.add(name)
                try:
                    resolved[name] = visit(bindings[name], depth + 1, "$.bindings." + name)
                finally:
                    resolving.remove(name)
            return resolved[name]
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
            if set(value) in ({"literal"}, {"value"}, {"const"}):
                raise ValueError(location + ': a literal is a raw JSON value (for example 7), not a literal/value/const object. Input references use exactly {"field":"name"}.')
            raise ValueError(location + ': an operation must contain exactly "op" and an "args" array; received keys ' + ", ".join(sorted(map(str, value))) + ".")
        op, raw = value["op"], value["args"]
        if op == "if":
            if len(raw) != 3:
                raise ValueError("if needs three operands.")
            cond = visit(raw[0], depth + 1, location + ".args[0]")
            if type(cond) is not bool:
                raise ValueError("if condition must be boolean.")
            branch = 1 if cond else 2
            return visit(raw[branch], depth + 1, f"{location}.args[{branch}]")
        args = [visit(v, depth + 1, f"{location}.args[{index}]") for index, v in enumerate(raw)]
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
        elif op == "abs":
            if len(args) != 1:
                raise ValueError("abs needs one numeric operand.")
            result = abs(number(args[0]))
        elif op in {"eq", "lt", "lte", "gt", "gte"}:
            if len(args) != 2:
                raise ValueError("Comparison needs two operands.")
            a, b = args
            if op == "eq":
                result = _json_equal(a, b)
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
    result = {key: visit(expr, location="$.outputs[" + json.dumps(key) + "]") for key, expr in spec["outputs"].items()}
    return {"output": result, "operations": count, "scope": "Bounded declarative execution; acceptance must be checked separately."}



def strict_portable_json(raw):
    """Refuse ambiguous or nonstandard JSON before standalone artifact execution."""
    def unique_members(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Invalid JSON: duplicate object member.")
            result[key] = value
        return result

    def nonfinite_constant(_token):
        raise ValueError("Invalid JSON: non-finite number token.")

    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError("Invalid JSON: floating-point overflow.")
        return value

    return json.loads(raw, object_pairs_hook=unique_members,
                      parse_constant=nonfinite_constant, parse_float=finite_float)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instrument", type=Path)
    parser.add_argument("input", type=Path)
    parser.add_argument("--max-operations", type=int, default=10000)
    args = parser.parse_args()
    print(json.dumps(evaluate(strict_portable_json(args.instrument.read_text()), strict_portable_json(args.input.read_text()), args.max_operations), ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
