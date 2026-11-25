# SPDX-License-Identifier: Apache-2.0
"""Construct and execute portable, read-only table instruments.

The model supplies data and a bounded SQLite query. The qualified relational
evaluator runs in a separate Python process so its SQLite limits are local to
that evaluation. The process runs only trusted, source-bound interpreter code.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys


TOOL_NAMES = frozenset({"construct_table", "run_table"})
ARTIFACT_KIND = "table_instrument"
FORMAT = "frontier/bounded-table-instrument-v1"
EVALUATOR_SHA256 = "48d0ab154a4fd5d09f8edc7b65dbcb916c7967d68c78901bdeb3c949a534084d"
MAX_PACKET = 1_048_576
MAX_WORKER_REPLY = 65_536
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
TABLE_COLUMN = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
QUERY_ERRORS = frozenset({"SCHEMA", "INPUT", "QUERY_SIZE", "READ_ONLY", "QUERY_LIMIT", "SQL_ERROR", "OUTPUT_LIMIT"})


def describe():
    return (
        'construct_table {tool:"construct_table",name:"table.json",schema:{events:{score:"INTEGER"}},'
        'sql:"SELECT SUM(score) FROM events"} creates a portable query. '
        'run_table {tool:"run_table",name:"table.json",input:{dataset:"approved-id"}} computes on an '
        'operator-approved dataset. For development use input:{fixtures:{events:[{score:2}]}}. '
        'Use INTEGER or TEXT columns, explicit output columns and ORDER BY when row order matters. '
        'Recorded executions are evidence for review. Independent qualification is separate.'
    )


def tool_schemas():
    def object_type(properties):
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

    row = {"type": "object", "additionalProperties": {
        "anyOf": [{"type": "null"}, {"type": "integer"}, {"type": "string", "maxLength": 512}]
    }}
    tables = {"type": "object", "additionalProperties": {"type": "array", "maxItems": 512, "items": row}}
    columns = {"type": "object", "additionalProperties": {"type": "string", "enum": ["INTEGER", "TEXT"]}}
    return {
        "construct_table": {
            "schema": {"type": "object", "additionalProperties": columns},
            "sql": {"type": "string", "minLength": 1, "maxLength": 6000},
        },
        "run_table": {"input": {"anyOf": [
            object_type({"dataset": {"type": "string", "minLength": 1, "maxLength": 100}}),
            object_type({"fixtures": tables}),
        ]}},
    }


def _object(pairs):
    fields = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError("TABLE_JSON")
        fields[key] = value
    return fields


def _invalid_number(_):
    raise ValueError("TABLE_JSON")


def _decode(raw, limit=MAX_PACKET):
    if not isinstance(raw, bytes) or len(raw) > limit:
        raise ValueError("TABLE_PACKET_SIZE")
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_number)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("TABLE_JSON") from None
    if not isinstance(value, dict):
        raise ValueError("TABLE_JSON")
    return value


def _encode(value):
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("TABLE_JSON") from None
    if len(encoded) > MAX_PACKET:
        raise ValueError("TABLE_PACKET_SIZE")
    return encoded


def _digest(raw):
    return sha256(raw).hexdigest()


def _file_bytes(path):
    if not path.is_file():
        raise ValueError("TABLE_FILE")
    with path.open("rb") as stream:
        raw = stream.read(MAX_PACKET + 1)
    if len(raw) > MAX_PACKET:
        raise ValueError("TABLE_PACKET_SIZE")
    return raw


def _artifact(schema, sql):
    if not isinstance(schema, dict) or not 1 <= len(schema) <= 6:
        raise ValueError("TABLE_SCHEMA")
    for table, columns in schema.items():
        if not isinstance(table, str) or not TABLE_COLUMN.fullmatch(table) or not isinstance(columns, dict) or not 1 <= len(columns) <= 12:
            raise ValueError("TABLE_SCHEMA")
        if any(not isinstance(name, str) or not TABLE_COLUMN.fullmatch(name) or kind not in ("INTEGER", "TEXT")
               for name, kind in columns.items()):
            raise ValueError("TABLE_SCHEMA")
    try:
        valid_size = isinstance(sql, str) and 1 <= len(sql.encode()) <= 6000
    except UnicodeError:
        valid_size = False
    if not valid_size:
        raise ValueError("TABLE_QUERY_SIZE")
    return {"schema": FORMAT, "table_schema": schema, "sql": sql, "evaluator_sha256": EVALUATOR_SHA256}


def _evaluate(artifact, tables):
    if not isinstance(artifact, dict) or artifact != _artifact(artifact.get("table_schema"), artifact.get("sql")):
        raise ValueError("TABLE_ARTIFACT_IDENTITY")
    if sqlite3.sqlite_version_info < (3, 37):
        raise ValueError("TABLE_ENGINE_VERSION")
    script = Path(__file__).resolve()
    evaluator = script.with_name("relational.py")
    if not evaluator.is_file():
        evaluator = script.parent.parent.parent / "frontier-member-tools" / "inventor" / "relational.py"
    source = _file_bytes(evaluator)
    if _digest(source) != EVALUATOR_SHA256:
        raise ValueError("TABLE_ENGINE_IDENTITY")
    # Load the exact shipped evaluator bytes just checked against the source pin.
    # The artifact can supply SQL and data, never executable Python or a path.
    functions = {}
    exec(compile(source, str(evaluator), "exec", dont_inherit=True), functions)
    try:
        rows = functions["evaluate"](artifact["table_schema"], tables, artifact["sql"])
    except functions["QueryRefused"] as error:
        reason = str(error)
        raise ValueError("TABLE_" + reason if reason in QUERY_ERRORS else "TABLE_WORKER_REFUSED") from None
    return {"rows": rows, "sqlite_version": sqlite3.sqlite_version, "evaluator_sha256": EVALUATOR_SHA256}


def _run(artifact, tables):
    packet = _encode({"artifact": artifact, "tables": tables})
    environment = {"SystemRoot": os.environ["SystemRoot"]} if os.name == "nt" and "SystemRoot" in os.environ else {}
    try:
        process = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), "--table-worker"],
            input=packet, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment, timeout=30, check=False,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("TABLE_WORKER_LIMIT") from None
    except OSError:
        raise ValueError("TABLE_WORKER_UNAVAILABLE") from None
    if process.returncode:
        raise ValueError("TABLE_WORKER_FAILED")
    reply = _decode(process.stdout, MAX_WORKER_REPLY)
    if set(reply) == {"error"}:
        code = reply["error"]
        raise ValueError(code if isinstance(code, str) and re.fullmatch(r"TABLE_[A-Z_]{2,40}", code) else "TABLE_WORKER_REFUSED")
    if set(reply) != {"rows", "sqlite_version", "evaluator_sha256"} or reply["evaluator_sha256"] != EVALUATOR_SHA256:
        raise ValueError("TABLE_WORKER_PROTOCOL")
    return reply


def _replay(raw, tables):
    response = _run(_decode(raw), tables)
    return {
        **response, "artifact_sha256": _digest(raw), "input_sha256": _digest(_encode(tables)),
        "output_sha256": _digest(_encode(response["rows"])), "status": "EXECUTED", "qualification": "UNVERIFIED",
    }


def execute(action, *, read, write, kind, approved_tables):
    """Dispatch only on the caller's already authorized local mission scope."""
    if not isinstance(action, dict) or not isinstance(action.get("tool"), str) or action["tool"] not in TOOL_NAMES:
        raise ValueError("TABLE_ACTION")
    name = action.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name) or ".." in name or not name.endswith(".json"):
        raise ValueError("TABLE_ARTIFACT_NAME")
    if action["tool"] == "construct_table":
        if set(action) != {"tool", "name", "schema", "sql"}:
            raise ValueError("TABLE_ACTION")
        existing = kind(name)
        if existing not in (None, ARTIFACT_KIND):
            raise ValueError("TABLE_ARTIFACT_KIND")
        raw = _encode(_artifact(action["schema"], action["sql"]))
        artifact = _decode(raw)
        compiled = _run(artifact, {table: [] for table in artifact["table_schema"]})
        previous = _digest(read(name)) if existing is not None else None
        return {
            **write(name, raw.decode(), ARTIFACT_KIND),
            "previous_sha256": previous, "evaluator_sha256": compiled["evaluator_sha256"],
            "sqlite_version": compiled["sqlite_version"], "status": "CANDIDATE_VALIDATED_ON_EMPTY_TABLES",
            "qualification": "UNVERIFIED",
        }

    if set(action) != {"tool", "name", "input"} or not isinstance(action["input"], dict):
        raise ValueError("TABLE_ACTION")
    if kind(name) != ARTIFACT_KIND:
        raise ValueError("TABLE_ARTIFACT_KIND")
    configuration = action["input"]
    dataset = None
    if set(configuration) == {"dataset"}:
        dataset = configuration["dataset"]
        if not isinstance(dataset, str) or not NAME.fullmatch(dataset) or dataset not in approved_tables:
            raise ValueError("TABLE_DATASET_AUTHORITY")
        tables, origin = approved_tables[dataset], "OPERATOR_APPROVED_DATASET"
    elif set(configuration) == {"fixtures"}:
        tables, origin = configuration["fixtures"], "MODEL_DEVELOPMENT_FIXTURE"
    else:
        raise ValueError("TABLE_ACTION")
    return {
        **_replay(read(name), tables), "artifact": name, "input_origin": origin, "dataset": dataset,
    }


def main(arguments):
    worker = arguments == ["--table-worker"]
    try:
        if worker:
            request = _decode(sys.stdin.buffer.read(MAX_PACKET + 1))
            if set(request) != {"artifact", "tables"}:
                raise ValueError("TABLE_WORKER_PROTOCOL")
            result = _evaluate(request["artifact"], request["tables"])
        elif len(arguments) == 2:
            artifact_file, tables_file = map(Path, arguments)
            result = _replay(_file_bytes(artifact_file), _decode(_file_bytes(tables_file)))
        else:
            raise ValueError("Usage: mission_tools.py ARTIFACT.json APPROVED-TABLES.json")
    except (ValueError, OSError, TypeError, AttributeError, sqlite3.Error) as error:
        reason = str(error) if isinstance(error, ValueError) else "TABLE_WORKER_REFUSED"
        if not worker:
            print(reason, file=sys.stderr)
            return 2
        result = {"error": reason}
    sys.stdout.buffer.write(_encode(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
