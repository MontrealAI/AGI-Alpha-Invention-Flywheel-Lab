"""Finite, data-only artifact language. No proposal can name a tool or run code."""

import base64
import binascii
import copy
import hashlib
import json
import re


class ConstructionError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(f"{code}: {detail}")


MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2048
MAX_FIELDS = 32
MAX_FILES = 256
MAX_NUMBER = 2**53 - 1
TYPES = {"text", "integer", "boolean"}
SEPARATORS = (" ", "-", "_", "/", ".", ",", ":", "|")
KINDS = ("record_migration", "manifest_audit")


def require(condition, code, detail):
    if not condition:
        raise ConstructionError(code, detail)


def canonical(value):
    """Bound the complete JSON tree before serialization (also used by the CLI)."""
    remaining = MAX_BYTES * 4
    nodes = 0

    def visit(item, depth):
        nonlocal remaining, nodes
        nodes += 1
        require(depth <= 18 and nodes <= 100000, "budget", "JSON tree exceeds envelope")
        if type(item) is str:
            require(len(item) <= MAX_BYTES, "budget", "string exceeds envelope")
            try:
                remaining -= len(item.encode("utf-8"))
            except UnicodeEncodeError:
                raise ConstructionError("invalid_value", "invalid Unicode scalar") from None
        elif type(item) is dict:
            for key, child in item.items():
                require(type(key) is str, "invalid_value", "JSON object keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
        elif type(item) is list:
            for child in item:
                visit(child, depth + 1)
        elif type(item) is int:
            require(abs(item) <= MAX_NUMBER, "invalid_value", "integer outside interoperable range")
        else:
            require(item is None or type(item) in (bool, float), "invalid_value", "JSON data required")
        require(remaining >= 0, "budget", "JSON text exceeds envelope")

    visit(value, 0)
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError):
        raise ConstructionError("invalid_value", "finite JSON values required") from None
    require(len(encoded) <= 4 * MAX_BYTES, "budget", "JSON exceeds envelope")
    return encoded


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _keys(obj, keys, code="invalid_program"):
    require(type(obj) is dict and obj.keys() == set(keys), code, "unexpected or missing keys")


def _field(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9. -]{0,79}", value), "invalid_program", "invalid field name")
    return value


def _field_list(fields):
    require(type(fields) is list and 1 <= len(fields) <= MAX_FIELDS, "invalid_program", "1..32 input fields required")
    require(len({_field(f) for f in fields}) == len(fields), "invalid_program", "duplicate field")
    return fields


def _kind_type(value):
    require(type(value) is str and value in TYPES, "invalid_program", "unknown conversion")


def _logical_path(path):
    require(type(path) is str and 1 <= len(path) <= 240, "invalid_path", "invalid logical name")
    require(all(part not in (".", "..") and re.fullmatch(r"[A-Za-z0-9_. -]+", part) for part in path.split("/")),
            "invalid_path", "expected a relative portable logical name")


def _manifest(config):
    _keys(config, {"manifest"})
    mapping = config["manifest"]
    require(type(mapping) is dict and 1 <= len(mapping) <= MAX_FILES, "invalid_program", "1..256 trusted digests required")
    for name, digest in mapping.items():
        _logical_path(name)
        require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid_program", "invalid SHA-256 digest")


def _migration(config):
    require(type(config) is dict, "invalid_program", "migration program must be an object")
    keys = {"columns", "extra_fields"}
    if "input_fields" in config:
        keys.add("input_fields")
    _keys(config, keys)
    require(config["extra_fields"] in ("drop", "reject"), "invalid_program", "explicit extra_fields policy required")
    columns = config["columns"]
    require(type(columns) is list and 1 <= len(columns) <= MAX_FIELDS, "invalid_program", "1..32 columns required")
    sources, targets = set(), set()
    for col in columns:
        require(type(col) is dict, "invalid_program", "invalid column")
        if "sources" in col:
            _keys(col, {"sources", "separator", "target", "type"})
            require(type(col["sources"]) is list and 2 <= len(col["sources"]) <= 4, "invalid_program", "join requires 2..4 fields")
            sources.update(_field(f) for f in col["sources"])
            require(col["separator"] in SEPARATORS, "invalid_program", "unsupported join separator")
        else:
            keys = {"source", "target", "type"}
            if "split" in col:
                keys.add("split")
                s = col["split"]
                _keys(s, {"separator", "index"})
                require(s["separator"] in SEPARATORS and type(s["index"]) is int and -8 <= s["index"] <= 7,
                        "invalid_program", "invalid component selector")
            _keys(col, keys)
            sources.add(_field(col["source"]))
        _kind_type(col["type"])
        target = _field(col["target"])
        require(target not in targets, "invalid_program", "duplicate target")
        targets.add(target)
    if "input_fields" in config:
        declared = set(_field_list(config["input_fields"]))
        require(sources <= declared, "invalid_program", "operation uses undeclared field")
        return declared
    return sources


def _convert(value, kind):
    if kind == "text" and type(value) is str:
        return value
    if kind == "integer":
        if type(value) is int:
            return value
        if type(value) is str and len(value) <= 17 and re.fullmatch(r"0|-?[1-9][0-9]*", value):
            n = int(value)
            if abs(n) <= MAX_NUMBER:
                return n
    if kind == "boolean":
        if type(value) is bool:
            return value
        if type(value) is str and value in ("true", "false"):
            return value == "true"
    raise ConstructionError("invalid_value", f"value does not meet {kind} contract")


def _records(program, payload):
    _keys(payload, {"rows"}, "invalid_input")
    rows = payload["rows"]
    require(type(rows) is list and len(rows) <= MAX_ROWS, "invalid_input", "expected bounded list of rows")
    required = _migration(program)
    output = []
    emitted = 0
    for row in rows:
        require(type(row) is dict and required <= row.keys(), "missing_field", "source field missing")
        require(program["extra_fields"] == "drop" or row.keys() == required, "extra_field", "undeclared source field")
        projected = {}
        for column in program["columns"]:
            if "sources" in column:
                parts = [row[f] for f in column["sources"]]
                require(all(type(part) is str for part in parts), "invalid_value", "join requires text")
                value = column["separator"].join(parts)
            else:
                value = row[column["source"]]
                if "split" in column:
                    segment = column["split"]
                    require(type(value) is str, "invalid_value", "split requires text")
                    # Avoid allocating one string for every delimiter in an untrusted field.
                    index = segment["index"]
                    if index >= 0:
                        parts = value.split(segment["separator"], index + 1)
                    else:
                        parts = value.rsplit(segment["separator"], -index)
                    require(-len(parts) <= index < len(parts), "invalid_value", "component missing")
                    value = parts[index]
            converted = _convert(value, column["type"])
            emitted += len(converted) if type(converted) is str else 1
            require(emitted <= MAX_BYTES, "budget", "output exceeds 2 MiB JSON")
            projected[column["target"]] = converted
        output.append(projected)
    return {"rows": output}


def _audit(program, payload):
    _keys(payload, {"files"}, "invalid_input")
    files = payload["files"]
    require(type(files) is dict and len(files) <= MAX_FILES, "invalid_input", "expected a bounded object of file contents")
    trusted = program["manifest"]
    actual = {}
    for path, encoded in files.items():
        _logical_path(path)
        require(type(encoded) is str, "invalid_value", "file contents must be base64")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ConstructionError("invalid_value", "invalid base64 file bytes") from None
        require(base64.b64encode(data).decode("ascii") == encoded, "invalid_value", "noncanonical base64")
        actual[path] = hashlib.sha256(data).hexdigest()
    return classify_manifest(trusted, actual)


def classify_manifest(trusted, actual):
    """Classify measured file identities against the same independently supplied manifest."""
    common = trusted.keys() & actual.keys()
    matched = sorted(name for name in common if actual[name] == trusted[name])
    changed = sorted(common - set(matched))
    missing = sorted(trusted.keys() - actual.keys())
    unexpected = sorted(actual.keys() - trusted.keys())
    return {"ok": not (missing or changed or unexpected), "matched": matched, "changed": changed,
            "missing": missing, "unexpected": unexpected}


def _examples_definition(definition):
    _keys(definition, {"input_fields", "targets", "extra_fields", "demonstrations"})
    fields = set(_field_list(definition["input_fields"]))
    require(len(fields) <= 12, "budget", "example-based search supports up to 12 source fields")
    require(definition["extra_fields"] in ("drop", "reject"), "invalid_program", "explicit extra_fields policy required")
    targets = definition["targets"]
    require(type(targets) is list and 1 <= len(targets) <= 12, "invalid_program", "1..12 targets required")
    for target in targets:
        _keys(target, {"name", "type"})
        _field(target["name"])
        _kind_type(target["type"])
    names = {t["name"] for t in targets}
    require(len(names) == len(targets), "invalid_program", "duplicate target")
    demos = definition["demonstrations"]
    require(type(demos) is list and 1 <= len(demos) <= 16, "invalid_contract", "development demonstrations required")
    examples = {}
    for demo in demos:
        _keys(demo, {"input", "expected"}, "invalid_contract")
        for side in ("input", "expected"):
            _keys(demo[side], {"rows"}, "invalid_contract")
            require(type(demo[side]["rows"]) is list, "invalid_contract", "demonstrations require rows")
        source, dest = demo["input"]["rows"], demo["expected"]["rows"]
        require(1 <= len(source) == len(dest) <= 32, "invalid_contract", "unpaired development rows")
        for row, out in zip(source, dest):
            require(type(row) is dict and row.keys() == fields and type(out) is dict and out.keys() == names,
                    "invalid_contract", "development row schema differs")
            for value in (*row.values(), *out.values()):
                require(value is None or type(value) in (bool, int) or type(value) is str and len(value) <= 1024,
                        "budget", "development cells require scalar data and at most 1024 characters")
            for target in targets:
                value = out[target["name"]]
                require(type(value) is {"text": str, "boolean": bool, "integer": int}[target["type"]],
                        "invalid_contract", "development target has wrong type")
            key = fingerprint(row)
            require(key not in examples, "invalid_contract", "duplicate development row")
            examples[key] = out
    require(2 <= len(examples) <= 32, "invalid_contract", "2..32 separate development rows required")
    return set(examples)


def freeze_contract(spec):
    """Copy and seal all acceptance inputs before exposing the public build view."""
    require(len(canonical(spec)) <= MAX_BYTES, "budget", "contract exceeds 2 MiB")
    if type(spec) is dict and "kind" in spec:
        require(spec["kind"] in KINDS, "unsupported_kind", "supported languages are record_migration and manifest_audit")
    _keys(spec, {"purpose", "kind", "definition", "cases"}, "invalid_contract")
    require(type(spec["purpose"]) is str and 1 <= len(spec["purpose"].strip()) <= 4096,
            "invalid_contract", "a specific purpose is required")
    kind = spec["kind"]
    definition = spec["definition"]
    require(type(definition) is dict, "invalid_contract", "definition must be an object")
    development = set()
    if kind == "manifest_audit":
        _manifest(definition)
    elif "demonstrations" in definition:
        development = _examples_definition(definition)
    else:
        _migration(definition)
    cases = spec["cases"]
    require(type(cases) is list and 1 <= len(cases) <= 64, "invalid_contract", "1..64 confirmation cases required")
    names, positive, seen = set(), 0, set()
    for case in cases:
        require(type(case) is dict, "invalid_contract", "invalid confirmation case")
        outcome = "expected" if "expected" in case else "error"
        _keys(case, {"name", "input", outcome}, "invalid_contract")
        name = case["name"]
        require(type(name) is str and 1 <= len(name) <= 120 and name not in names, "invalid_contract", "unique case names required")
        names.add(name)
        require(type(case["input"]) is dict, "invalid_contract", "object input required")
        if outcome == "expected":
            require(type(case["expected"]) is dict, "invalid_contract", "expected JSON object required")
            positive += 1
            if development:
                rows = case["input"].get("rows")
                require(type(rows) is list and rows, "invalid_contract", "unseen rows required")
                outputs = case["expected"].get("rows")
                require(type(outputs) is list and len(outputs) == len(rows), "invalid_contract", "unpaired confirmation rows")
                targets = {t["name"] for t in definition["targets"]}
                require(all(type(out) is dict and out.keys() == targets for out in outputs),
                        "invalid_contract", "confirmation output differs from target schema")
                ids = {fingerprint(row) for row in rows}
                require(not ids & (development | seen), "invalid_contract", "development or confirmation row reused")
                seen.update(ids)
        else:
            require(case["error"] in ("invalid_input", "missing_field", "extra_field", "invalid_value", "invalid_path", "budget"),
                    "invalid_contract", "unknown refusal outcome")
    require(positive >= (2 if development else 1), "invalid_contract", "positive confirmation cases required")
    body = {"format": "ignition-contract/1", "spec": copy.deepcopy(spec)}
    return {**body, "sha256": fingerprint(body)}


def check_contract(contract):
    require(type(contract) is dict and "spec" in contract, "invalid_contract", "missing frozen contract")
    actual = freeze_contract(contract["spec"])
    require(canonical(actual) == canonical(contract), "stale_contract", "frozen contract changed")
    return contract["spec"]


def build_view(contract):
    spec = check_contract(contract)
    return {"kind": spec["kind"], "purpose": spec["purpose"], "definition": copy.deepcopy(spec["definition"])}


def build(contract, proposal):
    spec = check_contract(contract)
    canonical(proposal)
    _keys(proposal, {"kind", "program"})
    require(proposal["kind"] == spec["kind"], "wrong_kind", "solution family differs from frozen mission")
    program = proposal["program"]
    if spec["kind"] == "manifest_audit":
        # The builder can refer to trusted operator bytes without retranscribing a cryptographic identity.
        if type(program) is dict and set(program) == {"use_frozen_manifest"} and program["use_frozen_manifest"] is True:
            program = spec["definition"]
        _manifest(program)
    else:
        fields = _migration(program)
        definition = spec["definition"]
        if "demonstrations" in definition:
            require(fields == set(definition["input_fields"]), "invalid_program", "input interface differs")
            signature = {c["target"]: c["type"] for c in program["columns"]}
            require(signature == {t["name"]: t["type"] for t in definition["targets"]},
                    "invalid_program", "output interface differs")
    body = {"format": "ignition-artifact/1", "contract_sha256": contract["sha256"],
            "kind": spec["kind"], "program": copy.deepcopy(program)}
    return {**body, "sha256": fingerprint(body)}


def execute(artifact, payload):
    _keys(artifact, {"format", "contract_sha256", "kind", "program", "sha256"}, "invalid_artifact")
    require(artifact["format"] == "ignition-artifact/1" and artifact["sha256"] == fingerprint(
        {k: v for k, v in artifact.items() if k != "sha256"}), "invalid_artifact", "artifact bytes changed")
    require(len(canonical(payload)) <= MAX_BYTES, "budget", "input exceeds 2 MiB JSON")
    if artifact["kind"] == "manifest_audit":
        _manifest(artifact["program"])
        return _audit(artifact["program"], payload)
    require(artifact["kind"] == "record_migration", "unsupported_kind", "unknown artifact language")
    result = _records(artifact["program"], payload)
    require(len(canonical(result)) <= MAX_BYTES, "budget", "output exceeds 2 MiB JSON")
    return result
