# SPDX-License-Identifier: Apache-2.0
"""Bounded JSON Schema subset for explicitly configured local generation.

No network resolution, regular expressions, recursive references or silent
keyword removal. The native grammar assists generation; this validator checks
the completed response independently of the provider's enforcement.
"""
import json
import hashlib
import math
from pathlib import Path
import re

LOADED_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

MAX_SCHEMA_BYTES = 262_144
MAX_SCHEMA_NODES = 8192
MAX_SCHEMA_DEPTH = 48
MAX_VALUE_NODES = 262_144
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,63}\Z")
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
METADATA = {"title", "description"}


class SchemaError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise SchemaError(message)


def _has_type(value, kind):
    if kind == "number":
        return type(value) in {int, float}
    if kind == "integer":
        return type(value) in {int, float} and value == int(value)
    return type(value) is {"object": dict, "array": list, "string": str,
                           "boolean": bool, "null": type(None)}.get(kind)


def _finite_tree(value, max_nodes, max_depth):
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        _require(count <= max_nodes and depth <= max_depth, "JSON structure exceeds the validation resource bounds.")
        kind = type(item)
        if kind is dict:
            _require(count + len(stack) + len(item) <= max_nodes, "JSON structure exceeds the validation resource bounds.")
            _require(all(type(key) is str for key in item), "JSON object keys must be strings.")
            stack.extend((child, depth + 1) for child in item.values())
        elif kind is list:
            _require(count + len(stack) + len(item) <= max_nodes, "JSON structure exceeds the validation resource bounds.")
            stack.extend((child, depth + 1) for child in item)
        else:
            _require(kind in {str, int, float, bool, type(None)}, "Only finite JSON values are supported.")
            if kind is float:
                _require(math.isfinite(item), "Only finite JSON values are supported.")


def prepare_schema(value):
    """Validate and detach an acyclic, supported schema before any dispatch."""
    _finite_tree(value, MAX_SCHEMA_NODES, MAX_SCHEMA_DEPTH)
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SchemaError("Schema must contain ordinary finite JSON.") from None
    _require(len(raw) <= MAX_SCHEMA_BYTES, "Schema exceeds 256 KiB.")
    schema = json.loads(raw)
    _require(type(schema) is dict and bool(schema), "Provide a nonempty schema object.")
    definitions = schema.get("$defs", {})
    _require(type(definitions) is dict and len(definitions) <= 128 and
             all(NAME.fullmatch(name) for name in definitions), "Use at most 128 named top-level definitions.")
    edges = {name: set() for name in definitions}

    def visit(node, owner=None, root=False):
        _require(type(node) is dict and bool(node), "Empty or boolean schemas are not supported.")
        keys = set(node) - METADATA - ({"$defs"} if root else set())
        for key in METADATA & node.keys():
            _require(type(node[key]) is str and len(node[key]) <= 2048, "Schema descriptions must be bounded strings.")
        if "$ref" in node:
            ref = node["$ref"]
            _require(keys == {"$ref"} and type(ref) is str and ref.startswith("#/$defs/") and
                     ref[8:] in definitions, "Only standalone references to named top-level definitions are supported.")
            if owner is not None:
                edges[owner].add(ref[8:])
            return
        if "anyOf" in node:
            branches = node["anyOf"]
            _require(keys == {"anyOf"} and type(branches) is list and 1 <= len(branches) <= 32,
                     "Use standalone anyOf with 1–32 supported branches.")
            for branch in branches:
                visit(branch, owner)
            return
        if "const" in node or "enum" in node:
            keyword = "const" if "const" in node else "enum"
            _require(keys <= {keyword, "type"}, "const and enum cannot be combined with other constraints.")
            if keyword == "enum":
                _require(type(node[keyword]) is list and 1 <= len(node[keyword]) <= 256,
                         "Use 1–256 enum choices.")
            if "type" in node:
                kind = node["type"]
                _require(type(kind) is str and kind in TYPES, "Literal type must be a supported scalar type.")
                choices = node["enum"] if keyword == "enum" else [node["const"]]
                _require(all(_has_type(choice, kind) for choice in choices), "Literal choices must match their declared type.")
            return
        kind = node.get("type")
        _require(type(kind) is str and kind in TYPES, "Every schema requires a supported type or explicit union, reference or literal.")
        allowed = {"type"}
        if kind == "object":
            allowed |= {"properties", "required", "additionalProperties"}
            props, required = node.get("properties", {}), node.get("required", [])
            _require(type(props) is dict and len(props) <= 256 and all(len(name) <= 256 for name in props),
                     "Object properties must be a bounded mapping.")
            _require(type(required) is list and all(type(name) is str and name in props for name in required)
                     and len(set(required)) == len(required), "Required fields must name distinct declared properties.")
            _require("additionalProperties" in node, "Declare additionalProperties explicitly for every object.")
            for child in props.values():
                visit(child, owner)
            additional = node["additionalProperties"]
            _require(additional is False or type(additional) is dict,
                     "Additional properties must be forbidden or constrained by a supported schema.")
            if type(additional) is dict:
                visit(additional, owner)
        elif kind == "array":
            allowed |= {"items", "minItems", "maxItems"}
            visit(node.get("items"), owner)
            bounds(node, "minItems", "maxItems", 4096)
        elif kind == "string":
            allowed |= {"minLength", "maxLength"}
            bounds(node, "minLength", "maxLength", 65536)
        elif kind == "integer":
            allowed |= {"minimum", "maximum"}
            for key in ("minimum", "maximum"):
                if key in node:
                    _require(type(node[key]) is int and abs(node[key]) <= 2**53 - 1,
                             "Integer bounds must be safe finite integers.")
            _require(node.get("minimum", -(2**53)) <= node.get("maximum", 2**53), "Schema bounds are reversed.")
        _require(keys <= allowed, "Schema contains unsupported keywords or incompatible constraints.")

    def bounds(node, minimum, maximum, ceiling):
        for key in (minimum, maximum):
            if key in node:
                _require(type(node[key]) is int and 0 <= node[key] <= ceiling, "Schema length bounds exceed supported resources.")
        _require(node.get(minimum, 0) <= node.get(maximum, ceiling), "Schema bounds are reversed.")

    visit(schema, root=True)
    for name, node in definitions.items():
        visit(node, name)
    completed, active = {}, set()
    def reference_depth(name):
        _require(name not in active, "Recursive schema references are not supported.")
        if name not in completed:
            active.add(name)
            depth = 1 + max((reference_depth(child) for child in edges[name]), default=0)
            _require(depth <= 64, "Schema reference chain exceeds 64 definitions.")
            completed[name] = depth
            active.remove(name)
        return completed[name]
    for name in definitions:
        reference_depth(name)
    return schema


def _equal(left, right):
    if type(left) in {int, float} and type(right) in {int, float}:
        return left == right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def validate_output(value, schema):
    """Check a completed JSON value against an already prepared schema."""
    _finite_tree(value, MAX_VALUE_NODES, 128)
    definitions, remaining = schema.get("$defs", {}), [MAX_VALUE_NODES]
    def matches(item, node, depth=0):
        remaining[0] -= 1
        _require(remaining[0] >= 0 and depth <= 256, "Response schema validation exceeds the resource bounds.")
        if "$ref" in node:
            return matches(item, definitions[node["$ref"][8:]], depth + 1)
        if "anyOf" in node:
            return any(matches(item, branch, depth + 1) for branch in node["anyOf"])
        if "const" in node:
            return _equal(item, node["const"])
        if "enum" in node:
            return any(_equal(item, choice) for choice in node["enum"])
        kind = node["type"]
        if kind == "object":
            if type(item) is not dict or any(key not in item for key in node.get("required", [])):
                return False
            props, extra = node.get("properties", {}), node["additionalProperties"]
            return all(matches(child, props[key], depth + 1) if key in props else
                       extra is not False and matches(child, extra, depth + 1) for key, child in item.items())
        if kind == "array":
            return type(item) is list and node.get("minItems", 0) <= len(item) <= node.get("maxItems", MAX_VALUE_NODES) and all(
                matches(child, node["items"], depth + 1) for child in item)
        if kind == "string":
            return type(item) is str and node.get("minLength", 0) <= len(item) <= node.get("maxLength", len(item))
        if kind in {"number", "integer"}:
            return type(item) in {int, float} and (kind == "number" or item == int(item)) and (
                node.get("minimum", item) <= item <= node.get("maximum", item))
        return type(item) is bool if kind == "boolean" else item is None
    _require(matches(value, schema), "Completed JSON does not satisfy the requested schema.")
