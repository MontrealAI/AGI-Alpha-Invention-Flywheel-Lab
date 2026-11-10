# SPDX-License-Identifier: Apache-2.0
"""Generation syntax for explicit schema-capable models; never an acceptance oracle.

Local acyclic definitions cover the evaluator's 32 expression levels without
recursive references or exponential schema expansion. Runtime validation still
checks numerical safety, input declarations, operation bounds and actual outputs.
No task inputs, output names or expected answers are used to build these schemas.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

INSTRUMENT_GRAMMAR = (
    'Instrument syntax: the root is an object with inputs (field-name strings) and outputs '
    '(a nonempty object mapping arbitrary output names to expressions). Optional root keys '
    'are name, description, conditions and limitations. These metadata keys do not execute '
    'checks or produce outputs. Every named calculation belongs inside outputs. '
    'An expression is a raw JSON scalar, an array of expressions, exactly {"field":"name"}, '
    'or exactly {"op":"operator","args":[expressions]}. A constant is a bare number, '
    'string, boolean or null; for example 7, never {"literal":7}, {"value":7} or {"const":7}. '
    'Nested operators are supported up to the existing depth32 bound. Operators are '
    'add/sub/mul/div/min/max/sum/count/eq/lt/lte/gt/gte/and/or/not/if. '
    'Arithmetic and ordered comparisons require numbers; eq compares JSON values '
    'without equating booleans to numbers. and/or/not require booleans; if takes '
    'a boolean condition and two branches; sum/count take one array. '
    'Use the recorded deterministic errors and actual-versus-expected checks to repair '
    'the artifact. A model critique cannot change this grammar or the frozen acceptance. '
)


def _object(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def _ref(name):
    return {"$ref": "#/$defs/" + name}


def _scalars():
    return [{"type": kind} for kind in ("null", "boolean", "number", "string")]


def _definitions():
    definitions = {}
    for depth in range(33):
        # Generic JSON for run inputs and inert metadata. Field access and all
        # interpreter limits remain enforced against actual operator inputs.
        values = _scalars()
        expressions = _scalars() + [_object({"field": {"type": "string", "minLength": 1}})]
        if depth:
            child, expression = _ref("json" + str(depth - 1)), _ref("expr" + str(depth - 1))
            values += [{"type": "array", "items": child},
                       {"type": "object", "additionalProperties": child}]
            expressions.append({"type": "array", "items": expression})
            for operators, minimum, maximum in (
                (("add", "mul", "min", "max", "and", "or"), 1, None),
                (("sub", "div", "eq", "lt", "lte", "gt", "gte"), 2, 2),
                (("sum", "count", "not"), 1, 1),
                (("if",), 3, 3),
            ):
                args = {"type": "array", "items": expression, "minItems": minimum}
                if maximum is not None:
                    args["maxItems"] = maximum
                expressions.append(_object({"op": {"type": "string", "enum": list(operators)}, "args": args}))
        else:
            values += [{"type": "array", "items": {"type": "null"}, "maxItems": 0}, _object({})]
            expressions.append({"type": "array", "items": {"type": "null"}, "maxItems": 0})
        definitions["json" + str(depth)] = {"anyOf": values}
        definitions["expr" + str(depth)] = {"anyOf": expressions}
    return definitions


def response_schema(role, permissions=(), remaining_actions=8):
    """Return a fresh syntax schema derived only from role and tool authority.

    This is a generation aid, not a replacement evaluator. In particular, schemas
    do not prove nonempty outputs, declared field roots, CSV widths, safe filenames,
    portable arithmetic, resource bounds or any operator's expected result.
    """
    if role == "critic":
        return _object({"verdict": {"type": "string", "enum": ["accept", "revise"]},
                        "feedback": {"type": "string", "maxLength": 12000}})
    if role != "builder":
        raise ValueError("Only builder and critic roles have workflow response schemas.")
    if type(remaining_actions) is not int or remaining_actions < 0:
        raise ValueError("Remaining actions must be a nonnegative integer.")
    fields = {"name": {"type": "string"},
              "inputs": {"type": "array", "items": {"type": "string"}},
              "outputs": {"type": "object", "additionalProperties": _ref("expr32")},
              "description": _ref("json32"), "conditions": _ref("json32"), "limitations": _ref("json32")}
    arguments = {
        "write_document": {"content": {"type": "string"}},
        "write_dataset": {"columns": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                          "rows": {"type": "array", "items": {"type": "array", "items": {"anyOf": _scalars()}}}},
        "construct_instrument": {"spec": _object(fields, ["inputs", "outputs"])},
        "run_instrument": {"input": {"type": "object", "additionalProperties": _ref("json32")}},
        "read_artifact": {},
        "retrieve_source": {"url": {"type": "string"}},
    }
    if not isinstance(permissions, (list, tuple, set, frozenset)) or any(tool not in arguments for tool in permissions):
        raise ValueError("Unknown workflow tool permission.")
    actions = [_object({"tool": {"const": tool}, "name": {"type": "string"}, **arguments[tool]})
               for tool in sorted(set(permissions))]
    array = {"type": "array", "maxItems": min(8, remaining_actions) if actions else 0,
             "items": {"anyOf": actions} if actions else {"type": "null"}}
    schema = _object({"summary": {"type": "string"}, "actions": array, "done": {"type": "boolean"}})
    if any(tool in permissions for tool in ("construct_instrument", "run_instrument")):
        schema["$defs"] = _definitions()
    return schema
