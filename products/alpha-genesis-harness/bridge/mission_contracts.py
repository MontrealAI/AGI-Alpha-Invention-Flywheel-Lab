# SPDX-License-Identifier: Apache-2.0
"""Independent scope checks and the allowlisted native mission operations."""

from copy import deepcopy
from datetime import date, datetime, timedelta
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unicodedata


_UTC_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2})?(?:Z|\+00:00)\Z")
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_COORDINATE = re.compile(r"[+-]?[0-9]{1,3}(?:\.[0-9]{1,12})?\Z")
_DECIMAL = re.compile(r"[0-9]{1,24}(?:\.[0-9]{1,24})?\Z")
_ROW_ID = re.compile(r"[a-zA-Z0-9._:-]{1,100}\Z")
_ENDPOINT_SCHEMA = "frontier/endpoint-screen-v1"
_ENDPOINT_LIMIT = 256_000
_ENDPOINT_CODE_SHA256 = "d4312e2a4650cbf8310d65989271e34578e165944ca542a38b4e465d6497486b"
_ENDPOINT_SCOPE = ("model", "workload", "system")
_ENDPOINT_SETTINGS = ("source", "scope", "cutoff", "minimum_tokens_per_s", "maximum_p90_ttft_ms")
_NOAA_POINT = ("issued_at", "valid_at", "latitude", "longitude")

_NOAA_FACTS = {
    "version": "1.0.0",
    "source": "NOAA GFS public archive",
    "quantity": "air_temperature_at_2m",
    "result_kind": "model_forecast",
    "unit": "K",
    "time_basis": "UTC",
    "grid_degrees": "0.25",
}
_ENDPOINT_FACTS = {
    "version": "1.0.0",
    "objective": "highest-tested-load",
    "time_basis": "publication_utc_day",
    "rate_unit": "tokens/s/user",
    "latency_metric": "p90-time-to-first-token",
    "latency_unit": "ms",
    "load_unit": "concurrent_queries",
}

_CATALOG = {
    "noaa-archive": {
        "id": "noaa-archive", "version": "1.0.0",
        "title": {"en": "NOAA Archive Point", "fr": "Point d’archive NOAA"},
        "summary": "Archived GFS f024, exact 24 h lead, native 0.25-degree grid, air temperature at 2 m in K.",
        "dispatch": "assess_only",
        "action_input": {key: "exact operator-bound value" for key in _NOAA_POINT},
        "required_requirements": sorted((*_NOAA_FACTS, *_NOAA_POINT)),
        "scope": {**_NOAA_FACTS, "forecast_horizon_hours": 24, "utc_cycles": [0, 6, 12, 18]},
        "inputs": {"point": {
            "quantity": "native_grid_coordinate", "unit": "degree", "grid_degrees": "0.25",
            "time_basis": "UTC", "dimensions": ["latitude", "longitude", "issue_time", "valid_time"],
        }},
        "outputs": {"temperature": {
            "quantity": "air_temperature_at_2m", "unit": "K", "result_kind": "model_forecast",
            "time_basis": "UTC", "horizon_hours": 24, "provenance": "NOAA GFS public archive",
        }},
        "preconditions": [
            "Exact supported archive origin, product, grid, packing and mapped field.",
            "An independently admitted source record is needed to qualify a resulting value.",
        ],
        "limitations": [
            "The local mission registry checks scope only. Archive retrieval requires separate public-source authority.",
            "A forecast is a model value. Observation, rounding and interpolation require different contracts.",
        ],
        "qualification": {
            "source_revision": "6a635b77012fb45b4d96c404a33fa04327c19674",
            "package_sha256": "a17ab75332f11a71f7acd5121418d46cf116fc43d521098e11cbea1ea620499f",
            "artifact": "noaa-archive-point-1.0.0.zip",
            "reference": "Signed ecCodes archive-point comparisons within their six registered cases.",
        },
    },
    "endpoint-screen": {
        "id": "endpoint-screen", "version": "1.0.0",
        "title": {"en": "Endpoint Evidence Screen", "fr": "Filtre de données probantes Endpoint"},
        "summary": "Highest observed load meeting an exact P90 TTFT ceiling and per-user throughput floor in one scope.",
        "dispatch": "local",
        "action_input": {"use": "verified_batch"},
        "required_requirements": sorted((*_ENDPOINT_FACTS, *_ENDPOINT_SETTINGS, "batch_sha256")),
        "scope": _ENDPOINT_FACTS,
        "inputs": {"batch": {
            "schema": _ENDPOINT_SCHEMA, "result_kind": "documented_measurements",
            "dimensions": list(_ENDPOINT_SCOPE), "time_basis": "publication_utc_day",
            "rate_unit": "tokens/s/user", "latency_unit": "ms",
            "latency_metric": "p90-time-to-first-token",
        }},
        "outputs": {"screen": {
            "schema": "frontier/endpoint-result-v1", "quantity": "highest_tested_load",
            "unit": "concurrent_queries", "result_kind": "evidence_screen",
            "time_basis": "publication_utc_day", "operating_adoption": "ABSTAIN",
        }},
        "preconditions": [
            "A bounded operator-bound batch for one unchanged model, workload and system.",
            "Exact limits and cutoff agree with the mission's authorized facts.",
            "Local Node compatible with Endpoint Evidence Screen 1.0.0.",
        ],
        "limitations": [
            "Only tested loads participate. Missing dates or measurements are retained as abstentions.",
            "Screening gives no production adoption, quality, cost or availability conclusion.",
        ],
        "resource_limits": {"batch_bytes": _ENDPOINT_LIMIT, "rows": 10_000, "network": False},
        "qualification": {
            "source_revision": "522542e525e96556285560e65e4443c85cc7b709",
            "package_sha256": "e546212a8b79203c8618b0817a5079d3ce4f51a23b13664b62334a9649528443",
            "executable_sha256": _ENDPOINT_CODE_SHA256,
            "artifact": "endpoint-evidence-screen-1.0.0.zip",
            "reference": "Independent exact-decimal SQLite screening of the published scope.",
        },
    },
}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return sha256(_canonical(value)).hexdigest()


def describe():
    """Return copies of the public contracts, never authority or member inputs."""
    return deepcopy(list(_CATALOG.values()))


def _decision(capability_id, status, reason, **facts):
    if not isinstance(capability_id, str) or len(capability_id) > 64:
        capability_id = None
    result = {"capability_id": capability_id, "status": status, "reason": reason, **facts}
    if capability_id in _CATALOG:
        contract = _CATALOG[capability_id]
        result.update(contract_sha256=_digest(contract), source_revision=contract["qualification"]["source_revision"])
    return result


def _same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, (dict, list)):
        try:
            return _canonical(left) == _canonical(right)
        except (ValueError, TypeError, RecursionError):
            return False
    return left == right


def _missing(record, keys):
    return sorted(key for key in keys if key not in record or record[key] is None)


def _fixed_facts(required, contract, capability_id):
    differences = [key for key, expected in contract.items()
                   if key in required and required[key] is not None and not _same(required[key], expected)]
    if not differences:
        return None
    if capability_id == "noaa-archive" and differences == ["unit"] and required["unit"] in ("°C", "degC", "°F", "degF"):
        return _decision(capability_id, "ADAPTATION_REQUIRED", "EXPLICIT_TEMPERATURE_CONVERSION_REQUIRED", fields=differences)
    return _decision(capability_id, "INCOMPATIBLE", "OPERATING_SCOPE_MISMATCH", fields=differences)


def _utc(value):
    if not isinstance(value, str) or not _UTC_STAMP.fullmatch(value):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("INVALID_UTC_TIMESTAMP") from None


def _coordinate(raw, *, latitude):
    if type(raw) is int:
        raw = str(raw)
    if not isinstance(raw, str) or not _COORDINATE.fullmatch(raw):
        raise ValueError("EXACT_DECIMAL_COORDINATE_REQUIRED")
    coordinate = Fraction(raw)
    bound = 90 if latitude else 360
    if not -bound <= coordinate <= bound:
        raise ValueError("COORDINATE_OUTSIDE_GLOBAL_GRID")
    if (coordinate * 4).denominator != 1:
        raise ValueError("POINT_NOT_ON_NATIVE_QUARTER_DEGREE_GRID")
    return coordinate if latitude else coordinate % 360


def _point(requirements):
    issued = _utc(requirements["issued_at"]) if requirements.get("issued_at") is not None else None
    valid = _utc(requirements["valid_at"]) if requirements.get("valid_at") is not None else None
    if issued is not None and (issued.hour not in (0, 6, 12, 18) or issued.minute or issued.second):
        raise ValueError("UNSUPPORTED_NOAA_ISSUE_CYCLE")
    if issued is not None and valid is not None and valid - issued != timedelta(hours=24):
        raise ValueError("NOAA_F024_REQUIRES_EXACTLY_24_HOURS")
    coords = tuple(_coordinate(requirements[key], latitude=(key == "latitude"))
                   if requirements.get(key) is not None else None for key in _NOAA_POINT[2:])
    return (issued, valid, *coords)


def _assess_noaa(requirements, arguments):
    capability_id = "noaa-archive"
    failed = _fixed_facts(requirements, _NOAA_FACTS, capability_id)
    if failed:
        return failed
    try:
        trusted_point = _point(requirements)
    except ValueError as error:
        return _decision(capability_id, "INCOMPATIBLE", error.args[0])
    missing = _missing(requirements, (*_NOAA_FACTS, *_NOAA_POINT))
    if missing:
        return _decision(capability_id, "MISSING_INPUT", "OPERATOR_FACTS_MISSING", fields=missing)
    if not isinstance(arguments, dict) or _missing(arguments, _NOAA_POINT):
        return _decision(capability_id, "MISSING_INPUT", "REQUEST_POINT_REQUIRED", fields=list(_NOAA_POINT))
    if set(arguments) != set(_NOAA_POINT):
        return _decision(capability_id, "UNDETERMINED", "UNSUPPORTED_POINT_ARGUMENTS")
    try:
        proposed_point = _point(arguments)
    except ValueError as error:
        return _decision(capability_id, "INCOMPATIBLE", error.args[0])
    if proposed_point != trusted_point:
        return _decision(capability_id, "INCOMPATIBLE", "POINT_DIFFERS_FROM_OPERATOR_REQUIREMENT")
    return _decision(capability_id, "COMPATIBLE", "EXACT_FORECAST_SCOPE_MATCH", evidence_status="ARCHIVE_BYTES_UNCHECKED")


def _matches(regex, value):
    return isinstance(value, str) and regex.fullmatch(value) is not None


def _day(value):
    if _matches(_DAY, value):
        try:
            return date.fromisoformat(value).isoformat() == value
        except ValueError:
            pass
    return False


def _text(value, maximum):
    return (isinstance(value, str) and 0 < len(value) <= maximum and value.strip() == value
            and all(unicodedata.category(ch) not in ("Cc", "Cf", "Cs") for ch in value))


def _validate_endpoint_batch(batch):
    if not isinstance(batch, dict) or set(batch) != {"schema", "rows", *_ENDPOINT_SETTINGS}:
        raise ValueError("ENDPOINT_BATCH_SCHEMA")
    scope = batch["scope"]
    if (batch["schema"] != _ENDPOINT_SCHEMA or not _text(batch["source"], 220)
            or not isinstance(scope, dict) or set(scope) != set(_ENDPOINT_SCOPE)
            or any(not _text(value, 170) for value in scope.values())):
        raise ValueError("ENDPOINT_SCOPE")
    if not _day(batch["cutoff"]):
        raise ValueError("ENDPOINT_CUTOFF")
    if any(not _matches(_DECIMAL, batch[key]) for key in _ENDPOINT_SETTINGS[-2:]):
        raise ValueError("ENDPOINT_LIMITS")
    rows = batch["rows"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10_000:
        raise ValueError("ENDPOINT_ROWS")
    ids, loads = set(), set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"id", "published", "load", "tokens_per_s", "p90_ttft_ms"}
                or not _matches(_ROW_ID, row["id"]) or type(row["load"]) is not int
                or not 1 <= row["load"] <= 2**53 - 1 or (row["published"] is not None and not _day(row["published"]))
                or any(row[key] is not None and not _matches(_DECIMAL, row[key]) for key in ("tokens_per_s", "p90_ttft_ms"))):
            raise ValueError("ENDPOINT_MEASUREMENT_ROW")
        if row["id"] in ids or row["load"] in loads:
            raise ValueError("ENDPOINT_AMBIGUOUS_LOAD_OR_ID")
        ids.add(row["id"])
        loads.add(row["load"])
    if len(_canonical(batch)) > _ENDPOINT_LIMIT:
        raise ValueError("ENDPOINT_BATCH_EXCEEDS_ENVELOPE")


def endpoint_requirements(batch):
    """An operator-side binding of the authorized data and intended exact limits."""
    _validate_endpoint_batch(batch)
    return deepcopy({**_ENDPOINT_FACTS, **{key: batch[key] for key in _ENDPOINT_SETTINGS},
                     "batch_sha256": _digest(batch), "batch": batch})


def _endpoint_input(requirements, arguments):
    if isinstance(arguments, dict) and arguments == {"use": "verified_batch"}:
        return requirements.get("batch")
    if isinstance(arguments, dict) and set(arguments) == {"batch"}:
        return arguments["batch"]
    return None


def _assess_endpoint(requirements, arguments):
    capability_id = "endpoint-screen"
    failed = _fixed_facts(requirements, _ENDPOINT_FACTS, capability_id)
    if failed:
        return failed
    missing = _missing(requirements, (*_ENDPOINT_FACTS, *_ENDPOINT_SETTINGS, "batch_sha256"))
    if missing:
        return _decision(capability_id, "MISSING_INPUT", "OPERATOR_FACTS_MISSING", fields=missing)
    batch = _endpoint_input(requirements, arguments)
    if batch is None:
        return _decision(capability_id, "MISSING_INPUT", "OPERATOR_BOUND_BATCH_REQUIRED")
    try:
        _validate_endpoint_batch(batch)
    except ValueError as error:
        return _decision(capability_id, "INCOMPATIBLE", error.args[0])
    differences = [key for key in _ENDPOINT_SETTINGS if not _same(batch[key], requirements[key])]
    if differences:
        return _decision(capability_id, "INCOMPATIBLE", "BATCH_DIFFERS_FROM_OPERATOR_REQUIREMENT", fields=differences)
    input_sha256 = _digest(batch)
    if input_sha256 != requirements["batch_sha256"]:
        return _decision(capability_id, "INCOMPATIBLE", "BATCH_IDENTITY_MISMATCH")
    return _decision(capability_id, "COMPATIBLE", "BOUND_SCREENING_CONTRACT_MATCH", input_sha256=input_sha256)


def assess(capability_id, requirements, arguments, authorized=True):
    """Check trusted mission requirements against immutable tool scope and proposed inputs.

    The caller owns the provenance of requirements and the active authorization.
    Model actions must never supply either one.
    """
    if authorized is not True:
        return _decision(capability_id, "UNAUTHORIZED", "CAPABILITY_AUTHORITY_ABSENT")
    if not isinstance(capability_id, str) or capability_id not in _CATALOG:
        return _decision(None, "UNDETERMINED", "NO_QUALIFIED_CAPABILITY_CONTRACT")
    if not isinstance(requirements, dict) or not requirements:
        return _decision(capability_id, "UNDETERMINED", "INDEPENDENT_MISSION_REQUIREMENTS_ABSENT")
    engine = _assess_noaa if capability_id == "noaa-archive" else _assess_endpoint
    return engine(requirements, arguments)


_ENDPOINT_RUNNER = '''
let raw = "";
for await (const part of process.stdin.setEncoding("utf8")) raw += part;
process.stdout.write(JSON.stringify(screen(JSON.parse(raw))));
'''


def _verified_endpoint_program():
    here = Path(__file__).resolve().parent
    paths = (here / "mission_assets" / "endpoint-screen.mjs",
             here.parents[2] / "docs" / "research" / "frontier-omega-alpha" / "endpoint-screen.mjs")
    for path in paths:
        try:
            with path.open("rb") as source:
                raw = source.read(16_385)
        except OSError:
            continue
        if sha256(raw).hexdigest() == _ENDPOINT_CODE_SHA256:
            return raw.decode("utf-8")
    raise ValueError("QUALIFIED_ENDPOINT_BYTES_UNAVAILABLE")


def invoke(capability_id, requirements, arguments, authorized=True):
    """Repeat applicability before dispatch. Endpoint runs only sealed source bytes."""
    decision = assess(capability_id, requirements, arguments, authorized)
    if decision["status"] != "COMPATIBLE":
        return {"decision": decision, "executed": False}
    if capability_id != "endpoint-screen":
        return {"decision": _decision(capability_id, "UNAUTHORIZED", "NATIVE_ARCHIVE_RETRIEVAL_NOT_GRANTED"),
                "executed": False}
    node = shutil.which("node")
    if not node:
        return {"decision": _decision(capability_id, "UNDETERMINED", "QUALIFIED_NODE_RUNTIME_UNAVAILABLE"),
                "executed": False}
    try:
        program = _verified_endpoint_program()
    except ValueError as error:
        return {"decision": _decision(capability_id, "UNDETERMINED", error.args[0]), "executed": False}
    # This source is the hash-checked first-party package plus a fixed stdin
    # adapter. Member and model bytes enter exclusively as JSON data on stdin.
    raw = _canonical(_endpoint_input(requirements, arguments))
    if sha256(raw).hexdigest() != decision["input_sha256"]:
        return {"decision": _decision(capability_id, "INCOMPATIBLE", "BATCH_CHANGED_BEFORE_EXECUTION"), "executed": False}
    try:
        with TemporaryDirectory(prefix="frontier-endpoint-") as workspace:
            runner = Path(workspace) / "screen.mjs"
            runner.write_text(program + _ENDPOINT_RUNNER, encoding="utf-8")
            result = subprocess.run([node, str(runner)], input=raw, capture_output=True, check=True, cwd=workspace, env={})
        output = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {"decision": _decision(capability_id, "UNDETERMINED", "ENDPOINT_SCREEN_FAILED"), "executed": False}
    return {"decision": decision, "executed": True, "output": output, "output_sha256": _digest(output)}


def compare_requirements(required, provided, authorized=True):
    """Match independently trusted, typed operating facts for a consumer and producer."""
    if authorized is not True:
        return {"status": "UNAUTHORIZED", "reason": "COMPOSITION_AUTHORITY_ABSENT"}
    if not isinstance(required, dict) or not required or not isinstance(provided, dict):
        return {"status": "UNDETERMINED", "reason": "TYPED_INTERFACE_ABSENT"}
    missing = _missing(provided, required)
    differences = sorted(key for key in required if key not in missing and not _same(required[key], provided[key]))
    if differences:
        return {"status": "INCOMPATIBLE", "reason": "TYPED_INTERFACE_MISMATCH", "fields": differences}
    if missing:
        return {"status": "MISSING_INPUT", "reason": "PRODUCER_EVIDENCE_MISSING", "fields": missing}
    return {"status": "COMPATIBLE", "reason": "TYPED_INTERFACE_MATCH"}


def assess_composition(links, authorized=True):
    """Check declared dependencies in execution order against registry-owned ports."""
    if authorized is not True:
        return {"status": "UNAUTHORIZED", "reason": "COMPOSITION_AUTHORITY_ABSENT"}
    if not isinstance(links, list) or not 1 <= len(links) <= 32:
        return {"status": "MISSING_INPUT", "reason": "DECLARED_COMPOSITION_LINKS_REQUIRED"}
    checked = []
    bound_inputs = set()
    step_capabilities = {}
    for index, link in enumerate(links):
        required_fields = {"producer", "output", "consumer", "input", "producer_step", "consumer_step"}
        if not isinstance(link, dict) or set(link) != required_fields:
            return {"status": "UNDETERMINED", "reason": "UNSUPPORTED_COMPOSITION_LINK", "link": index}
        before, after = link["producer_step"], link["consumer_step"]
        if type(before) is not int or type(after) is not int or not 0 <= before < after:
            return {"status": "INCOMPATIBLE", "reason": "INVALID_COMPOSITION_ORDER", "link": index}
        if not all(isinstance(link[k], str) for k in ("producer", "output", "consumer", "input")):
            return {"status": "UNDETERMINED", "reason": "UNKNOWN_COMPOSITION_INTERFACE", "link": index}
        if (step_capabilities.setdefault(before, link["producer"]) != link["producer"]
                or step_capabilities.setdefault(after, link["consumer"]) != link["consumer"]):
            return {"status": "INCOMPATIBLE", "reason": "CONFLICTING_COMPOSITION_STEP_IDENTITY", "link": index}
        provided = _CATALOG.get(link["producer"], {}).get("outputs", {}).get(link["output"])
        expected = _CATALOG.get(link["consumer"], {}).get("inputs", {}).get(link["input"])
        target = (after, link["input"])
        if target in bound_inputs:
            return {"status": "INCOMPATIBLE", "reason": "DUPLICATE_INPUT_BINDING", "link": index}
        bound_inputs.add(target)
        if provided is None or expected is None:
            return {"status": "UNDETERMINED", "reason": "UNKNOWN_COMPOSITION_INTERFACE", "link": index}
        decision = compare_requirements(expected, provided)
        if decision["status"] != "COMPATIBLE":
            return {**decision, "link": index}
        checked.append(index)
    return {"status": "COMPATIBLE", "reason": "DECLARED_PORTS_MATCH", "checked_links": checked}
