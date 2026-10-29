"""Immutable capability evidence. Retrieval returns data, never executable authority."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re

MAX_RECORD_BYTES = 65536
HEX = re.compile(r"^[0-9a-f]{64}$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _data(value, depth=0):
    if depth > 16:
        raise ValueError("RECORD_DEPTH_LIMIT")
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _data(item, depth + 1)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            _data(item, depth + 1)
        return
    raise ValueError("NON_JSON_RECORD")


def _conditions(conditions):
    if type(conditions) is not dict or not conditions:
        raise ValueError("APPLICABILITY_CONDITIONS_REQUIRED")
    for key, value in conditions.items():
        if not NAME.fullmatch(key) or type(value) not in (str, bool, int, float) or (type(value) is float and not math.isfinite(value)):
            raise ValueError("INVALID_TYPED_CONDITION")


def _list_strings(value, message):
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ValueError(message)


def validate(record):
    _data(record)
    required = {"instrument", "applicability", "generative_operator", "provenance", "verification", "costs", "exposure", "supersedes"}
    if type(record) is not dict or set(record) != required:
        raise ValueError("RECORD_SCHEMA_MISMATCH")
    instrument = record["instrument"]
    if type(instrument) is not dict or set(instrument) != {"path", "sha256"}:
        raise ValueError("INSTRUMENT_SCHEMA_MISMATCH")
    path = Path(instrument["path"])
    if path.is_absolute() or ".." in path.parts or not path.parts or not HEX.fullmatch(str(instrument["sha256"])):
        raise ValueError("INVALID_SOURCE_IDENTITY")
    applicability = record["applicability"]
    if type(applicability) is not dict or set(applicability) != {"schema_version", "conditions", "assumptions", "uncertainty", "failures"}:
        raise ValueError("APPLICABILITY_SCHEMA_MISMATCH")
    if type(applicability["schema_version"]) is not int or applicability["schema_version"] != 1:
        raise ValueError("STALE_APPLICABILITY_SCHEMA")
    _conditions(applicability["conditions"])
    _list_strings(applicability["assumptions"], "INVALID_ASSUMPTIONS")
    if type(applicability["uncertainty"]) is not str or not applicability["uncertainty"]:
        raise ValueError("UNCERTAINTY_REQUIRED")
    if type(applicability["failures"]) is not list:
        raise ValueError("INVALID_FAILURES")
    for failure in applicability["failures"]:
        if type(failure) is not dict or set(failure) != {"conditions", "reason"} or type(failure["reason"]) is not str:
            raise ValueError("INVALID_SCOPED_FAILURE")
        _conditions(failure["conditions"])
    operator = record["generative_operator"]
    if type(operator) is not dict or set(operator) != {"language", "program"} or not NAME.fullmatch(str(operator["language"])) or type(operator["program"]) not in (dict, list):
        raise ValueError("GENERATOR_SCHEMA_MISMATCH")
    for name in ("provenance", "costs"):
        if type(record[name]) is not dict:
            raise ValueError("INVALID_" + name.upper())
    verification = record["verification"]
    if type(verification) is not dict or set(verification) != {"status", "receipt_sha256"} or verification["status"] not in {"verified-in-scope", "failed", "unknown"} or not HEX.fullmatch(str(verification["receipt_sha256"])):
        raise ValueError("INVALID_VERIFICATION")
    _list_strings(record["exposure"], "INVALID_EXPOSURE")
    _list_strings(record["supersedes"], "INVALID_SUPERSESSION")
    if any(not HEX.fullmatch(item) for item in record["supersedes"]):
        raise ValueError("INVALID_SUPERSESSION")
    if len(canonical(record)) > MAX_RECORD_BYTES:
        raise ValueError("RECORD_SIZE_LIMIT")


def store(root, record):
    """Append one content-addressed record; an identical duplicate is idempotent."""
    validate(record)
    data = canonical(record)
    identity = hashlib.sha256(data).hexdigest()
    root = Path(root)
    if root.is_symlink():
        raise ValueError("SYMLINK_STORE")
    root.mkdir(parents=True, exist_ok=True)
    destination = root / (identity + ".json")
    if destination.is_symlink():
        raise ValueError("SYMLINK_RECORD")
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    except FileExistsError:
        if destination.read_bytes() != data:
            raise ValueError("CORRUPTED_DUPLICATE")
        return identity
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return identity


def _matches(expected, observed):
    return all(key in observed and type(observed[key]) is type(value) and observed[key] == value for key, value in expected.items())


def _check_source(instrument, source_root):
    root = Path(source_root).resolve(strict=True)
    source = root / instrument["path"]
    relative = source.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("SYMLINK_SOURCE")
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != instrument["sha256"]:
        raise ValueError("CORRUPTED_SOURCE")


def retrieve(root, target, source_root):
    """Recheck typed scope and source; do not compile, evaluate or import content."""
    if type(target) is not dict or set(target) != {"schema_version", "conditions"} or type(target["schema_version"]) is not int or target["schema_version"] != 1:
        raise ValueError("TARGET_SCHEMA_MISMATCH")
    _conditions(target["conditions"])
    report = {"records": [], "refused": [], "failures": []}
    root = Path(root)
    if root.is_symlink():
        raise ValueError("SYMLINK_STORE")
    if not root.exists():
        return report
    for path in sorted(root.glob("*.json")):
        identity = path.stem
        try:
            if path.is_symlink() or not HEX.fullmatch(identity):
                raise ValueError("INVALID_RECORD_PATH")
            if path.stat().st_size > MAX_RECORD_BYTES:
                raise ValueError("RECORD_SIZE_LIMIT")
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != identity:
                raise ValueError("CORRUPTED_RECORD")
            record = json.loads(data)
            validate(record)
            _check_source(record["instrument"], source_root)
            applicability = record["applicability"]
            if not _matches(applicability["conditions"], target["conditions"]):
                raise ValueError("INAPPLICABLE_TYPED_CONDITIONS")
            failures = [failure for failure in applicability["failures"] if _matches(failure["conditions"], target["conditions"])]
            if failures:
                report["failures"].append({"id": identity, "counterexamples": failures})
                raise ValueError("SCOPED_COUNTEREXAMPLE")
            if record["verification"]["status"] != "verified-in-scope":
                raise ValueError("UNVERIFIED_RECORD")
            report["records"].append({"id": identity, "record": record})
        except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as error:
            report["refused"].append({"id": identity, "reason": str(error)})
    superseded = {old for item in report["records"] for old in item["record"]["supersedes"]}
    active = []
    for item in report["records"]:
        if item["id"] in superseded:
            report["refused"].append({"id": item["id"], "reason": "SUPERSEDED_IN_TARGET_SCOPE"})
        else:
            active.append(item)
    report["records"] = active
    return report


def compatible(records):
    """Conservative composition gate: shared conditions and language must agree."""
    seen, language = {}, None
    for item in records:
        record = item.get("record", item)
        validate(record)
        current = record["generative_operator"]["language"]
        if language is not None and current != language:
            return False
        language = current
        for key, value in record["applicability"]["conditions"].items():
            if key in seen and (type(seen[key]) is not type(value) or seen[key] != value):
                return False
            seen[key] = value
    return True
