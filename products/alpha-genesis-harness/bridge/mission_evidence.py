# SPDX-License-Identifier: Apache-2.0
"""Bind numerical mission claims to executed results and frozen operator evidence."""

from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import re

from .adapters import BridgeError, strict_json
from .workflows import NAME, digest, require


ORIGINS = frozenset({"AUTHORIZED_MISSION_INPUT", "OPERATOR_SUPPLIED_OBSERVATION", "VERIFIED_EXTERNAL_SOURCE",
                     "DEVELOPMENT_FIXTURE", "SYNTHETIC_EXAMPLE", "SIMULATION_OUTPUT", "DERIVED_DATA"})
ADMISSIBLE_ROOTS = ORIGINS - {"DEVELOPMENT_FIXTURE", "SYNTHETIC_EXAMPLE", "SIMULATION_OUTPUT", "DERIVED_DATA"}
TOOLS = {"run_table": "table", "run_instrument": "values"}
SELECTORS = {"run_table": "rows", "run_instrument": "output"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
NUMBER = re.compile(r"[+-]?[0-9]{1,40}(?:/[0-9]{1,40}|(?:\.[0-9]{1,40})?(?:[eE][+-]?[0-9]{1,3})?)\Z")
INSTRUMENT_VERSION = sha256(Path(__file__).with_name("instruments.py").read_bytes()).hexdigest()
LEGACY_INSTRUMENT_VERSION = "46d43d4a017f1d32fcd9e05b32316a6fffac27e1a9572ab9ffbbf87338f00322"
SCOPE = "Case-specific numerical agreement and source binding. Independent custody and production admission are separate."
RECEIPT_SCHEMA = "frontier/mission-claim-execution/v1"


class ClaimRefused(ValueError):
    def __init__(self, reason, status="REJECTED"):
        self.reason, self.status = reason, status
        super().__init__(reason)


def _check(condition, reason, status="REJECTED"):
    if not condition:
        raise ClaimRefused(reason, status)


def _label(value, limit=100):
    return isinstance(value, str) and 0 < len(value) <= limit and value.isprintable() and bool(value.strip())


def _identity(value):
    return isinstance(value, str) and NAME.fullmatch(value) is not None


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _rational(value):
    if type(value) in {int, float}:
        value = str(value)
    if not isinstance(value, str) or NUMBER.fullmatch(value) is None:
        raise ValueError("Evidence requires a finite decimal or rational scalar.")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError("Evidence requires a rational scalar with nonzero denominator.") from None


def _location(tool, value):
    return isinstance(value, list) and bool(value) and value[0] == SELECTORS[tool] and (
        len(value) == 3 and all(type(part) is int and 0 <= part <= 65535 for part in value[1:])
        if tool == "run_table" else len(value) == 2 and _label(value[1]))


def validate_requirements(plan, tools):
    """Check operator-authored shape; input availability is classified during the run."""
    following = "MISSION_EVIDENCE_PLAN"
    require(isinstance(plan, dict) and set(plan) == {"inputs", "claims"}, "Evidence needs inputs and claims.", following)
    inputs, claims = plan["inputs"], plan["claims"]
    require(isinstance(inputs, dict) and len(inputs) <= 32 and isinstance(claims, list) and 1 <= len(claims) <= 12,
            "Evidence scope supports up to 32 inputs and 12 claims.", following)
    for ident, record in inputs.items():
        required = {"kind", "origin", "version", "sha256", "facts"}
        require(_identity(ident) and isinstance(record, dict) and required <= set(record) <= required | {"values", "parents", "source"},
                "Evidence input metadata is invalid.", following)
        kind, origin = record["kind"], record["origin"]
        require(kind in ("table", "values") and isinstance(origin, str) and origin in ORIGINS
                and _label(record["version"]) and _sha(record["sha256"]) and isinstance(record["facts"], dict),
                "An evidence input needs a recognized origin, version, digest and factual scope.", following)
        require(("values" not in record or kind == "values" and isinstance(record["values"], dict))
                and ("source" not in record or _label(record["source"], 300))
                and (origin != "VERIFIED_EXTERNAL_SOURCE" or "source" in record), "Evidence input source or payload is invalid.", following)
        parents = record.get("parents")
        require((origin != "DERIVED_DATA" and "parents" not in record) or
                (origin == "DERIVED_DATA" and isinstance(parents, dict) and 1 <= len(parents) <= 16
                 and all(_identity(key) and _sha(value) for key, value in parents.items())),
                "Derived data needs exact parent identities and digests.", following)
    seen = set()
    for claim in claims:
        required = {"id", "dataset", "tool", "locator", "unit", "dimension", "version", "requires"}
        require(isinstance(claim, dict) and required <= set(claim) <= required | {"reference", "required_fields"},
                "Evidence claims need the registered input, operation, result locator and semantics.", following)
        ident, tool = claim["id"], claim["tool"]
        require(_identity(ident) and ident not in seen and _identity(claim["dataset"]) and isinstance(tool, str)
                and tool in TOOLS and tool in tools and _location(tool, claim["locator"])
                and all(_label(claim[k]) for k in ("unit", "dimension", "version")) and isinstance(claim["requires"], dict),
                "Evidence claim identifiers, tools and quantities must match the operator contract.", following)
        seen.add(ident)
        fields = claim.get("required_fields", [])
        require(isinstance(fields, list) and len(fields) <= 32 and all(
            isinstance(path, list) and all(_label(part) for part in path)
            and (len(path) == 2 if tool == "run_table" else 1 <= len(path) <= 8) for path in fields),
            "Required fields need explicit paths into the approved data.", following)
        if "reference" in claim:
            reference = claim["reference"]
            require(isinstance(reference, dict) and {"value", "source"} <= set(reference) <= {"value", "source", "tolerance"}
                    and _label(reference["source"], 250), "Reference checks need a separate source and exact value.", following)
            try:
                require(_rational(reference.get("tolerance", "0")) >= 0, "Reference tolerance cannot be negative.", following)
                _rational(reference["value"])
            except ValueError as error:
                raise BridgeError(following, str(error)) from None


def for_constructor(requirements):
    """Supply the task and available data without releasing the reference answer."""
    if "evidence" not in requirements:
        return requirements
    plan = requirements["evidence"]
    return {**requirements, "evidence": {**plan, "claims": [
        {key: value for key, value in claim.items() if key != "reference"} for claim in plan["claims"]]}}


def _payload(requirements, ident, record):
    return requirements.get("approved_tables", {}).get(ident) if record["kind"] == "table" else record.get("values")


def _lineage(requirements, ident, required_kind):
    records = requirements["evidence"]["inputs"]
    resolved, visiting = {}, set()

    def visit(key):
        _check(key not in visiting, "INPUT_LINEAGE_CYCLE")
        if key in resolved:
            return resolved[key]
        record = records.get(key)
        _check(record is not None, "AUTHORIZED_INPUT_MISSING", "ABSTAIN")
        origin = record["origin"]
        _check(origin in ADMISSIBLE_ROOTS or origin == "DERIVED_DATA", "INPUT_ORIGIN_INELIGIBLE")
        data = _payload(requirements, key, record)
        _check(isinstance(data, dict), "AUTHORIZED_INPUT_MISSING", "ABSTAIN")
        _check(digest(data) == record["sha256"], "INPUT_BYTES_CHANGED")
        visiting.add(key)
        for parent, expected in record.get("parents", {}).items():
            _check(visit(parent)["sha256"] == expected, "INPUT_PARENT_CHANGED")
        visiting.remove(key)
        resolved[key] = {"id": key, "kind": record["kind"], "origin": origin, "version": record["version"],
                         "sha256": record["sha256"], "parents": record.get("parents", {})}
        if "source" in record:
            resolved[key]["source"] = record["source"]
        return resolved[key]

    primary = visit(ident)
    _check(primary["kind"] == required_kind, "INPUT_PORT_INCOMPATIBLE")
    return primary, list(resolved.values())


def _select(value, locator):
    for part in locator:
        if isinstance(value, dict) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
            value = value[part]
        else:
            return None
    return value


def _inputs_for(requirements, claim):
    ident, tool = claim["dataset"], claim["tool"]
    primary, lineage = _lineage(requirements, ident, TOOLS[tool])
    record = requirements["evidence"]["inputs"][ident]
    _check(primary["version"] == claim["version"], "INPUT_VERSION_MISMATCH")
    facts = record["facts"]
    _check(all(key in facts and digest(facts[key]) == digest(value) for key, value in claim["requires"].items()),
           "INPUT_ASSUMPTIONS_INCOMPATIBLE")
    data = _payload(requirements, ident, record)
    for path in claim.get("required_fields", []):
        if tool == "run_table":
            table, field = path
            rows = data.get(table)
            present = isinstance(rows, list) and bool(rows) and all(isinstance(row, dict) and row.get(field) is not None for row in rows)
        else:
            present = _select(data, path) is not None
        _check(present, "REQUIRED_FIELD_MISSING", "ABSTAIN")
    return primary, lineage, data


def prepare_action(requirements, action):
    annotation = action.get("claim")
    fields = {"id", "unit", "dimension"}
    _check("evidence" in requirements and isinstance(annotation, dict) and fields <= set(annotation) <= fields | {"value"},
           "CLAIM_NOT_AUTHORIZED")
    claim = next((item for item in requirements["evidence"]["claims"] if item["id"] == annotation["id"]), None)
    _check(claim is not None, "CLAIM_NOT_AUTHORIZED")
    _check(action["tool"] == claim["tool"], "CLAIM_OPERATION_MISMATCH")
    if isinstance(action.get("input"), dict) and "fixtures" in action["input"]:
        raise ClaimRefused("INPUT_ORIGIN_INELIGIBLE")
    _check(action.get("input") == {"dataset": claim["dataset"]}, "CLAIM_DATASET_MISMATCH")
    _check(all(annotation[key] == claim[key] for key in ("unit", "dimension")), "CLAIM_UNITS_MISMATCH")
    asserted = None
    if "value" in annotation:
        try:
            asserted = str(_rational(annotation["value"]))
        except ValueError:
            raise ClaimRefused("CLAIM_VALUE_INVALID") from None
    primary, lineage, data = _inputs_for(requirements, claim)
    dispatch = {key: value for key, value in action.items() if key != "claim"}
    if claim["tool"] == "run_instrument":
        dispatch["input"] = data
    return dispatch, {"claim": claim, "primary": primary, "lineage": lineage, "asserted": asserted}


def _version(tool):
    if tool == "run_table":
        from .mission_tools import EVALUATOR_SHA256
        return EVALUATOR_SHA256
    return INSTRUMENT_VERSION


def _compatible_operation(tool, operation, read):
    if operation["version_sha256"] == _version(tool):
        return True
    # Existing 1.1 checkpoints used the same portable arithmetic semantics.
    # An exact-rational artifact requires an execution by its own evaluator.
    return (tool == "run_instrument" and operation["version_sha256"] == LEGACY_INSTRUMENT_VERSION
            and "numeric_mode" not in strict_json(read(operation["artifact"])))


def record_execution(state, name, artifact_sha256, binding, outcome, result_artifact=None):
    claim = binding["claim"]
    tool = claim["tool"]
    version = _version(tool)
    operation = {"tool": tool, "artifact": name, "artifact_sha256": artifact_sha256, "version_sha256": version}
    if tool == "run_table":
        _check(outcome["evaluator_sha256"] == version and outcome["input_origin"] == "OPERATOR_APPROVED_DATASET"
               and outcome["dataset"] == claim["dataset"] and outcome["input_sha256"] == binding["primary"]["sha256"]
               and outcome["artifact_sha256"] == artifact_sha256 and outcome["output_sha256"] == digest(outcome["rows"]),
               "EXECUTOR_IDENTITY_MISMATCH")
        operation["sqlite_version"] = outcome["sqlite_version"]
    receipt = {"schema": RECEIPT_SCHEMA, "mission_id": state["id"], "revision_sha256": state["spec_hash"],
               "claim_id": claim["id"], "claim_contract_sha256": digest(claim), "operation": operation,
               "input": binding["primary"], "lineage": binding["lineage"], "locator": claim["locator"],
               "output_sha256": digest(outcome[SELECTORS[tool]]), "asserted_value": binding["asserted"],
               "result_artifact": result_artifact}
    return {**receipt, "sha256": digest(receipt)}


def assess_claims(state, read):
    """Project actual journal entries. Candidate narratives never supply a displayed value."""
    requirements = state["spec"]["mission"]["requirements"]
    plan = requirements.get("evidence")
    if not plan:
        return {"status": "UNVERIFIED", "claims": [], "scope": SCOPE}
    latest = {}
    for item in state["events"]:
        if item["kind"] == "tool_completed":
            receipt = item["detail"].get("outcome", {}).get("claim_execution")
            ident = receipt.get("claim_id") if isinstance(receipt, dict) else None
        elif item["kind"] == "claim_refused":
            ident = item["detail"].get("claim_id")
        else:
            continue
        if _identity(ident):
            latest[ident] = item
    claims = [_claim_report(state, requirements, claim, latest.get(claim["id"]), read) for claim in plan["claims"]]
    states = {item["status"] for item in claims}
    if len(states) == 1:
        status = next(iter(states))
    elif "REJECTED" in states:
        status = "REJECTED"
    else:
        status = "SOURCE_BOUND" if states <= {"SOURCE_BOUND", "VERIFIED"} else "UNVERIFIED"
    return {"status": status, "claims": claims, "scope": SCOPE}


def _claim_report(state, requirements, claim, event, read):
    report = {key: claim[key] for key in ("id", "dataset", "unit", "dimension", "locator", "requires")}
    report.update(mission_id=state["id"], revision_sha256=state["spec_hash"], source_version=claim["version"],
                  claim_contract_sha256=digest(claim))
    try:
        primary, lineage, _ = _inputs_for(requirements, claim)
        _check(event is not None, "NO_BOUND_EXECUTION", "ABSTAIN")
        if event["kind"] == "claim_refused":
            raise ClaimRefused(event["detail"]["reason"], event["detail"]["status"])
        detail = event["detail"]
        outcome = detail["outcome"]
        receipt = outcome["claim_execution"]
        signable = {key: value for key, value in receipt.items() if key != "sha256"}
        _check(digest(signable) == receipt["sha256"] and digest({key: value for key, value in event.items() if key != "sha256"})
               == event["sha256"], "EXECUTION_RECEIPT_CHANGED")
        _check(outcome.get("operation_executed") is True and receipt["schema"] == RECEIPT_SCHEMA
               and receipt["mission_id"] == state["id"] and receipt["revision_sha256"] == state["spec_hash"]
               and receipt["claim_contract_sha256"] == digest(claim) and receipt["locator"] == claim["locator"]
               and receipt["input"] == primary and receipt["lineage"] == lineage, "EXECUTION_SCOPE_MISMATCH")
        operation = receipt["operation"]
        _check(detail["tool"] == operation["tool"] == claim["tool"]
               and state["artifacts"].get(operation["artifact"], {}).get("sha256") == operation["artifact_sha256"]
               and _compatible_operation(claim["tool"], operation, read),
               "EXECUTION_OPERATION_STALE")
        saved = receipt["result_artifact"]
        if saved is not None:
            name = saved["artifact"]
            raw = read(name)
            _check(sha256(raw).hexdigest() == saved["sha256"], "EXECUTION_RESULT_CHANGED")
            outcome = strict_json(raw)
        _check(digest(outcome[SELECTORS[claim["tool"]]]) == receipt["output_sha256"], "EXECUTION_RESULT_CHANGED")
        actual = _rational(_select(outcome, claim["locator"]))
        report.update(execution_receipt=receipt, event_sha256=event["sha256"], executed_value=str(actual))
        asserted = receipt["asserted_value"]
        _check(asserted is None or _rational(asserted) == actual, "CLAIM_CONTRADICTS_EXECUTED_RESULT")
        reference = claim.get("reference")
        if reference is None:
            return {**report, "status": "SOURCE_BOUND", "reason": "INDEPENDENT_REFERENCE_REQUIRED", "value": str(actual)}
        _check(abs(actual - _rational(reference["value"])) <= _rational(reference.get("tolerance", "0")), "REFERENCE_DISAGREES")
        return {**report, "status": "VERIFIED", "reason": "MATCHES_FROZEN_REFERENCE", "value": str(actual), "reference": reference}
    except ClaimRefused as error:
        return {**report, "status": error.status, "reason": error.reason}
    except (BridgeError, KeyError, TypeError, ValueError):
        return {**report, "status": "REJECTED", "reason": "RESULT_OR_RECEIPT_INVALID"}
