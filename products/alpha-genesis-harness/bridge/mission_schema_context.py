# SPDX-License-Identifier: Apache-2.0
"""Expose exact operator-approved shapes without giving a constructor new authority."""

from . import mission_evidence
from .adapters import BridgeError
from .mission_tools import TABLE_COLUMN
from .workflows import NAME, digest, encoded, require


DECLARATION = "MISSION_APPROVED_SCHEMA"
FIELD_METADATA = frozenset({"unit", "dimension", "temporal_basis", "nullable", "range"})
SQL_TYPES = frozenset({"INTEGER", "TEXT"})
JSON_TYPES = {bool: "BOOLEAN", int: "INTEGER", float: "JSON_NUMBER", str: "TEXT", list: "ARRAY", dict: "OBJECT"}
MAX_SAFE_INTEGER = 2**53 - 1
CLAIM_REASONS = {
    "AUTHORIZED_INPUT_MISSING": "The approved input has no observed payload.",
    "INPUT_ORIGIN_INELIGIBLE": "The declared input or a parent is development, synthetic or simulated data.",
    "INPUT_BYTES_CHANGED": "The payload digest does not match the approved input.",
    "INPUT_PARENT_CHANGED": "A derived input's parent digest has changed.",
    "INPUT_LINEAGE_CYCLE": "The derived input lineage is cyclic.",
}


def _plain_text(value, maximum):
    return isinstance(value, str) and 0 < len(value) <= maximum and value.isprintable()


def _sql_identifier(value):
    return isinstance(value, str) and TABLE_COLUMN.fullmatch(value) is not None


def _dataset_id(value):
    return isinstance(value, str) and NAME.fullmatch(value) is not None


def _bounded_name(value):
    return value[:100] if _plain_text(value[:100], 100) else "<invalid identifier>"


def _field_path(tables, path):
    return (isinstance(path, list) and len(path) == 2 and all(_sql_identifier(part) for part in path)
            and path[0] in tables and path[1] in tables[path[0]])


def _validate_metadata(meta):
    require(isinstance(meta, dict) and set(meta) <= FIELD_METADATA, "Unknown approved field metadata.", DECLARATION)
    for key in {"unit", "dimension", "temporal_basis"}.intersection(meta):
        require(_plain_text(meta[key], 120), "Approved unit, dimension and time labels must be printable.", DECLARATION)
    if "nullable" in meta:
        require(type(meta["nullable"]) is bool, "Approved nullability must be boolean.", DECLARATION)
    if "range" in meta:
        span = meta["range"]
        require(isinstance(span, list) and len(span) == 2 and all(type(x) in (int, float) for x in span)
                and span[0] <= span[1], "An approved numerical range needs two ordered endpoints.", DECLARATION)


def validate_declarations(requirements):
    """Validate optional metadata in the operator's frozen requirements, before model dispatch."""
    declarations = requirements.get("approved_schemas", {})
    grants = requirements.get("approved_tables", {})
    records = requirements.get("evidence", {}).get("inputs", {})
    require(isinstance(declarations, dict) and len(declarations) <= 32,
            "Approved schemas must be keyed by exact approved dataset IDs.", DECLARATION)
    for ident, declaration in declarations.items():
        record = records.get(ident)
        require(_dataset_id(ident) and (ident in grants or record is not None)
                and (record is None or record["kind"] == "table"),
                "An approved table schema needs a current dataset grant.", DECLARATION)
        require(isinstance(declaration, dict) and "tables" in declaration and set(declaration) <= {
            "tables", "fields", "primary_keys", "relationships", "approved_transformations",
        }, "An approved schema needs a tables declaration and recognized metadata.", DECLARATION)
        tables = declaration["tables"]
        require(isinstance(tables, dict) and 1 <= len(tables) <= 6,
                "An approved schema needs one to six relational tables.", DECLARATION)
        for table, columns in tables.items():
            require(_sql_identifier(table) and isinstance(columns, dict) and 1 <= len(columns) <= 12
                    and all(_sql_identifier(name) and isinstance(kind, str) and kind in SQL_TYPES
                            for name, kind in columns.items()), "Approved table and field types are invalid.", DECLARATION)
        fields = declaration.get("fields", {})
        require(isinstance(fields, dict) and all(table in tables and isinstance(items, dict) for table, items in fields.items()),
                "Approved field metadata names an unknown table.", DECLARATION)
        for table, items in fields.items():
            for name, meta in items.items():
                require(_field_path(tables, [table, name]), "Approved metadata names an unknown field.", DECLARATION)
                _validate_metadata(meta)
                require("range" not in meta or tables[table][name] == "INTEGER",
                        "A numerical range needs a numerical field.", DECLARATION)
        primary_keys = declaration.get("primary_keys", {})
        require(isinstance(primary_keys, dict), "Approved primary keys must be grouped by table.", DECLARATION)
        for table, fields in primary_keys.items():
            require(isinstance(fields, list) and 1 <= len(fields) <= 12
                    and all(_field_path(tables, [table, field]) for field in fields) and len(set(fields)) == len(fields),
                    "An approved key must name distinct fields in its table.", DECLARATION)
        relationships = declaration.get("relationships", [])
        require(isinstance(relationships, list) and len(relationships) <= 24 and all(
            isinstance(link, dict) and set(link) == {"from", "to"} and all(_field_path(tables, path) for path in link.values())
            for link in relationships), "An approved relationship needs two exact field paths.", DECLARATION)
        transformations = declaration.get("approved_transformations", [])
        require(isinstance(transformations, list) and len(transformations) <= 12
                and all(_plain_text(item, 120) for item in transformations),
                "Approved transformation descriptions must be printable.", DECLARATION)


def _source(requirements, ident):
    grants = requirements.get("approved_tables", {})
    record = requirements.get("evidence", {}).get("inputs", {}).get(ident)
    if record is not None:
        primary, lineage = mission_evidence._lineage(requirements, ident, record["kind"])
        return {**primary, "lineage": lineage}, mission_evidence._payload(requirements, ident, record)
    data = grants.get(ident)
    if not isinstance(data, dict):
        raise mission_evidence.ClaimRefused("AUTHORIZED_INPUT_MISSING", "ABSTAIN")
    return {"kind": "table", "origin": "OPERATOR_APPROVED_DATASET", "sha256": digest(data)}, data


def _required_paths(requirements, ident, kind):
    for claim in requirements.get("evidence", {}).get("claims", ()):
        if claim["dataset"] == ident and mission_evidence.TOOLS[claim["tool"]] == kind:
            yield from claim.get("required_fields", ())


def _native_scalar(value, kind):
    return ((kind == "INTEGER" and type(value) is int and abs(value) <= MAX_SAFE_INTEGER)
            or (kind == "TEXT" and isinstance(value, str) and len(value.encode("utf-8")) <= 512))


def _observe_field(values, declared, metadata, row_count):
    concrete = [v for v in values if v is not None]
    kinds = sorted({JSON_TYPES.get(type(value), "UNSUPPORTED") for value in concrete})
    kind = declared if declared is not None else kinds[0] if len(kinds) == 1 and kinds[0] in SQL_TYPES else None
    missing = row_count - len(values)
    null = len(values) - len(concrete)
    reasons = []
    if not kind or any(not _native_scalar(v, kind) for v in concrete):
        reasons.append("APPROVED_FIELD_TYPE_UNRESOLVED" if not kind else "APPROVED_FIELD_TYPE_CONFLICT")
    if missing:
        reasons.append("APPROVED_FIELD_ABSENT_FROM_ROWS")
    if null and metadata.get("nullable") is False:
        reasons.append("APPROVED_FIELD_NULLABILITY_CONFLICT")
    if kind == "INTEGER" and "range" in metadata and any(
            type(v) is int and not metadata["range"][0] <= v <= metadata["range"][1] for v in concrete):
        reasons.append("APPROVED_FIELD_RANGE_CONFLICT")
    field = {"type": kind, "observed_types": kinds, "missing_rows": missing, "null_rows": null}
    if metadata:
        field["declared"] = metadata
    return field, reasons


def _observe_tables(data, declaration, required_paths, include_examples):
    declared = declaration.get("tables", {})
    required = {}
    for table, field in required_paths:
        required.setdefault(table, set()).add(field)
    result = {"tables": {}, "schema": {}, "issues": []}
    issues = result["issues"]
    names = sorted(set(data) | set(declared) | set(required))
    if not 1 <= len(names) <= 6:
        issues.append({"code": "APPROVED_TABLE_COUNT_UNSUPPORTED", "count": len(names)})
    for table in names[:6]:
        table_label = _bounded_name(table)
        if not _sql_identifier(table):
            issues.append({"code": "APPROVED_TABLE_IDENTIFIER_UNSUPPORTED", "table": table_label})
        rows = data.get(table)
        if not isinstance(rows, list) or len(rows) > 512 or any(not isinstance(row, dict) for row in rows):
            issues.append({"code": "APPROVED_TABLE_ROWS_UNAVAILABLE", "table": table_label})
            continue
        if declared and table not in declared:
            issues.append({"code": "APPROVED_TABLE_NOT_DECLARED", "table": table_label})
        columns = declared.get(table, {})
        observed = set().union(*(row.keys() for row in rows))
        fields = sorted(observed | set(columns) | required.get(table, set()))
        if not 1 <= len(fields) <= 12:
            issues.append({"code": "APPROVED_FIELD_COUNT_UNSUPPORTED", "table": table_label, "count": len(fields)})
        view = {"row_count": len(rows), "fields": {}}
        result["tables"][table_label] = view
        result["schema"][table_label] = {}
        for field in fields[:12]:
            field_label = _bounded_name(field)
            if not _sql_identifier(field):
                issues.append({"code": "APPROVED_FIELD_IDENTIFIER_UNSUPPORTED", "table": table_label, "field": field_label})
            if columns and field not in columns:
                issues.append({"code": "APPROVED_FIELD_NOT_DECLARED", "table": table_label, "field": field_label})
            metadata = declaration.get("fields", {}).get(table, {}).get(field, {})
            observed_field, reasons = _observe_field([row[field] for row in rows if field in row], columns.get(field), metadata, len(rows))
            view["fields"][field_label] = observed_field
            result["schema"][table_label][field_label] = observed_field["type"]
            issues.extend({"code": code, "table": table_label, "field": field_label} for code in reasons)
        if include_examples and rows and all(_sql_identifier(name) for name in fields) and len(fields) <= 12:
            examples = [rows[0]]
            incomplete = next((row for row in rows[1:] if set(row) != set(fields) or None in row.values()), None)
            if incomplete is not None:
                examples.append(incomplete)
            if all(len(encoded(row)) <= 512 for row in examples):
                view["examples"] = examples
    for key in ("primary_keys", "relationships", "approved_transformations"):
        if key in declaration:
            result[key] = declaration[key]
    missing = []
    for table, field in sorted({tuple(path) for path in required_paths}):
        rows = data.get(table)
        if not isinstance(rows, list) or not rows:
            missing.append({"path": [table, field], "reason": "NO_OBSERVATIONS"})
        else:
            count = sum(not isinstance(row, dict) or row.get(field) is None for row in rows)
            if count:
                missing.append({"path": [table, field], "unavailable_rows": count})
    if missing:
        result["missing_requirements"] = missing[:32]
    if issues:
        result.pop("schema")
    return result


def _observe_values(data, paths, include_examples):
    fields = [{"path": [name], "type": JSON_TYPES.get(type(value)), "null": value is None}
              for name, value in sorted(data.items()) if _plain_text(name, 100)][:32]
    issues = [{"code": "REQUIRED_FIELD_MISSING", "path": path}
              for path in paths if mission_evidence._select(data, path) is None]
    result = {"fields": fields, "issues": issues, "omitted_fields": len(data) - len(fields)}
    if include_examples and len(encoded(data)) <= 512:
        result["examples"] = [data]
    return result


def inspect_dataset(requirements, dataset, *, include_examples=False, max_bytes=8000):
    """Read the shape of one exact approved dataset, independent of model assertions."""
    records = requirements.get("evidence", {}).get("inputs", {})
    grants = requirements.get("approved_tables", {})
    require(_dataset_id(dataset) and (dataset in grants or dataset in records),
            "Choose an exact operator-approved dataset ID.", "TABLE_DATASET_AUTHORITY")
    try:
        source, data = _source(requirements, dataset)
    except mission_evidence.ClaimRefused as error:
        return {"status": error.status, "issues": [{"code": error.reason}]}
    required = list(_required_paths(requirements, dataset, source["kind"]))
    declaration = requirements.get("approved_schemas", {}).get(dataset, {})
    if source["kind"] == "table":
        view = _observe_tables(data, declaration, required, include_examples)
    else:
        view = _observe_values(data, required, include_examples)
    result = {**source, **view, "status": "CONFLICT" if view["issues"] else "AVAILABLE"}
    if max_bytes is not None and len(encoded(result)) > max_bytes:
        summary = {key: value for key, value in result.items() if key in {
            "kind", "origin", "version", "sha256", "schema", "status", "source",
        }}
        summary["issues"] = result["issues"][:4]
        summary["metadata_omitted"] = True
        if len(encoded(summary)) <= max_bytes:
            return summary
        return {"status": result["status"], "schema_omitted": True, "sha256": source["sha256"]}
    return result


def constructor_context(requirements, *, max_bytes=6500, include_examples=False):
    """Put claim-linked shapes first and omit entire records once the context budget is used."""
    granted = set(requirements.get("approved_tables", {})) | set(requirements.get("evidence", {}).get("inputs", {}))
    linked = {claim["dataset"] for claim in requirements.get("evidence", {}).get("claims", ())}
    datasets = {}
    result = {"datasets": datasets, "omitted_datasets": len(granted)}
    for ident in sorted(granted, key=lambda name: (name not in linked, name)):
        if not _dataset_id(ident):
            continue
        result["omitted_datasets"] -= 1
        datasets[ident] = inspect_dataset(requirements, ident, include_examples=include_examples,
                                          max_bytes=max_bytes - len(encoded(result)) - len(ident) - 6)
        if len(encoded(result)) > max_bytes:
            datasets.pop(ident)
            result["omitted_datasets"] += 1
    return result


def bind_table_construction(action, requirements):
    """Resolve a selected dataset to the existing isolated table tool's exact schema."""
    if action.get("tool") != "construct_table" or "dataset" not in action:
        return action
    require(set(action) == {"tool", "name", "dataset", "sql"},
            "Choose an approved dataset or supply an explicit development schema.", "TABLE_ACTION")
    approved = inspect_dataset(requirements, action["dataset"], max_bytes=None)
    issues = approved["issues"]
    if "schema" not in approved:
        code = issues[0]["code"] if issues else "APPROVED_TABLE_KIND_INCOMPATIBLE"
        message = CLAIM_REASONS.get(code, "An exact approved relational schema is unavailable.")
        details = ", ".join(".".join(part for part in (item.get("table"), item.get("field")) if part)
                            for item in issues[:4] if "table" in item)
        raise BridgeError(code, message + (" Affected names: " + details if details else ""))
    return {"tool": action["tool"], "name": action["name"], "schema": approved["schema"], "sql": action["sql"]}


def verify_table_input_schema(action, requirements, schema):
    """Check explicit schema reuse against actual approved inputs before evaluation."""
    inputs = action.get("input")
    if action.get("tool") != "run_table" or not isinstance(inputs, dict) or set(inputs) != {"dataset"}:
        return
    approved = inspect_dataset(requirements, inputs["dataset"], max_bytes=None)
    if approved["status"] in {"REJECTED", "ABSTAIN"}:
        reason = approved["issues"][0]["code"]
        raise BridgeError(reason, CLAIM_REASONS.get(reason, "The approved input is unavailable."))
    if "schema" not in approved:
        return  # The existing bounded evaluator handles incomplete or ambiguous payloads.
    trusted = approved["schema"]
    if schema != trusted:
        fields = ", ".join(f"{name}({', '.join(columns)})" for name, columns in trusted.items())
        raise BridgeError("TABLE_INPUT_SCHEMA_MISMATCH", "The artifact does not match the approved input. "
                          f"Approved tables and columns: {fields[:320]}.")


def table_feedback(action, requirements, reason):
    """Attach bounded approved names to an already refused structural query."""
    if not str(reason).startswith(("TABLE_SQL_ERROR", "TABLE_INPUT", "TABLE_SCHEMA")):
        return reason
    inputs = action.get("input")
    dataset = action.get("dataset", inputs.get("dataset") if isinstance(inputs, dict) else None)
    if dataset is None:
        return reason
    try:
        schema = inspect_dataset(requirements, dataset, max_bytes=None).get("schema", {})
    except BridgeError:
        return reason
    if not schema:
        return reason
    fields = ", ".join(f"{name}({', '.join(columns)})" for name, columns in schema.items())
    return ValueError(f"{str(reason)[:140]}. Approved tables and columns: {fields[:320]}.")
