"""Source-bound *synthetic* first-party risk reassessment after governance changes.

This composes impact140 with native risk152 without changing either engine.
It cannot authenticate policies, raw observations, reviewers, or procurement eligibility.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import re

from . import engine as impact
from . import native_risk152 as risk

SCHEMA = "agi-alpha/governance-native-reassessment153/input-v1"
RESULT_SCHEMA = "agi-alpha/governance-native-reassessment153/result-v1"
POLICY_FIELDS = {"system_id", "requirement_id", "version", "metric", "thresholds"}
AUTHORIZATION = "NO_AUTHENTICATED_REVIEW_NO_COMPLIANCE_NO_REAL_WORLD_QUALITY"


def _object(value, fields, code):
    if type(value) is not dict or set(value) != fields:
        raise ValueError(code)


def _observations(value, known):
    if type(value) is not list:
        raise ValueError("OBSERVATIONS_LIST_REQUIRED")
    out = {}
    for item in value:
        _object(item, {"system_id", "rows"}, "INVALID_OBSERVATION_SCHEMA")
        sid = item["system_id"]
        if type(sid) is not str or sid not in known or sid in out:
            raise ValueError("UNKNOWN_OR_DUPLICATE_OBSERVATION_SYSTEM")
        if type(item["rows"]) is not list or not item["rows"]:
            raise ValueError("NONEMPTY_RAW_OBSERVATIONS_REQUIRED")
        out[sid] = item["rows"]
    return out


def _policies(value, stage, requirements, systems):
    if type(value) is not list:
        raise ValueError("POLICIES_LIST_REQUIRED")
    out = {}
    for item in value:
        _object(item, POLICY_FIELDS, "INVALID_POLICY_BINDING_FIELDS")
        sid, rid, metric = item["system_id"], item["requirement_id"], item["metric"]
        if type(sid) is not str or sid not in systems or type(rid) is not str or rid not in requirements:
            raise ValueError("UNKNOWN_POLICY_SYSTEM_OR_REQUIREMENT")
        requirement = requirements[rid]
        if type(item["version"]) is not str or item["version"] != requirement["version"]:
            raise ValueError("STALE_POLICY_REQUIREMENT_VERSION")
        if not impact._applies(requirement, systems[sid]):
            raise ValueError("OUT_OF_SCOPE_NATIVE_RISK_BINDING")
        if type(metric) is not str or metric not in risk.SCORE_NAMES:
            raise ValueError("UNSUPPORTED_NATIVE_RISK_MEASURE")
        key = (sid, rid, metric)
        if key in out:
            raise ValueError("DUPLICATE_NATIVE_RISK_BINDING")
        thresholds = item["thresholds"]
        # Validation, including exact decimal types, is owned by the real native
        # evaluator when raw observations are present. Use it even for missing data
        # with one temporary *authored* probe to reject malformed policy parameters.
        probe = {
            "schema": risk.SCHEMA, "system_id": sid,
            "rows": [{"case_id": "policy-schema-only", "truth": None,
                      "prediction": 0, "repeat_prediction": None,
                      "group": None, "claimed_violation": False}],
            "thresholds": thresholds,
        }
        risk.evaluate(probe)
        out[key] = item
    return out


def reassess(data):
    """Recompute all registered before/after policies from their same raw cases.

    A favorable threshold is a synthetic numerical signal only. Every current
    governance finding stays pending/unable unless a separate authorized system
    validates it; no such authority is implemented here.
    """
    _object(data, {"schema", "governance", "observations",
                   "before_policies", "after_policies"}, "INVALID_REASSESSMENT_SCHEMA")
    if data["schema"] != SCHEMA:
        raise ValueError("UNSUPPORTED_REASSESSMENT_SCHEMA")
    governance = data["governance"]
    original = impact.assess(governance)
    systems = {r["id"]: r for r in governance["systems"]}
    before = {r["id"]: r for r in governance["requirements_before"]}
    after = {r["id"]: r for r in governance["requirements_after"]}
    raw = _observations(data["observations"], systems)
    prior = _policies(data["before_policies"], "before", before, systems)
    current = _policies(data["after_policies"], "after", after, systems)
    findings = {(r["system_id"], r["requirement_id"]): r for r in original["findings"]}
    if len(findings) != len(original["findings"]):
        raise ValueError("AMBIGUOUS_GOVERNANCE_FINDINGS")
    changes = {(r["id"]): r["kind"] for r in original["changes"]}

    def compute(stage_policies):
        rows = []
        for key, policy in sorted(stage_policies.items()):
            sid, rid, metric = key
            report = None
            if sid in raw:
                report = risk.evaluate({
                    "schema": risk.SCHEMA, "system_id": sid,
                    "thresholds": policy["thresholds"], "rows": raw[sid]})
                signal = report["signals"][metric]
            else:
                signal = {"observed": None, "threshold": None,
                          "signal": "UNABLE_TO_DETERMINE"}
            rows.append({
                "system_id": sid, "requirement_id": rid, "version": policy["version"],
                "metric": metric, "policy_thresholds": policy["thresholds"],
                "source_input_sha256": report["source_input_sha256"] if report else None,
                "native_receipt_sha256": report["receipt_sha256"] if report else None,
                "native_case_count": report["case_count"] if report else 0,
                "native_signal": signal,
                "authorization": AUTHORIZATION,
                "reason": "AUTHORED_RAW_CASES_RECOMPUTED_NOT_AUTHENTICATED"
                          if report else "NO_REGISTERED_RAW_OBSERVATIONS",
            })
        return rows

    before_results = compute(prior)
    after_results = compute(current)
    previous_by_key = {(r["system_id"], r["requirement_id"], r["metric"]): r
                       for r in before_results}
    reassessments = []
    for row in after_results:
        key = (row["system_id"], row["requirement_id"], row["metric"])
        old = previous_by_key.get(key)
        finding = findings[(row["system_id"], row["requirement_id"])]
        if finding["status"] == "not_applicable":
            raise ValueError("RETIRED_OR_UNAPPLICABLE_CURRENT_POLICY")
        # A newly introduced or changed control always requires renewed review,
        # even when numerical signals happen to coincide.
        changed = finding["change_impacts_system"] or old is None or (
            old["policy_thresholds"] != row["policy_thresholds"])
        reassessments.append({
            **row,
            "old_version": old["version"] if old else None,
            "old_native_signal": old["native_signal"] if old else None,
            "change_kind": changes.get(row["requirement_id"], "unchanged"),
            "reassessment_required": changed,
            "governance_status_unchanged": finding["status"],
            "review_status_unchanged": finding["review_status"],
        })

    # Coverage is measured against every applicable current governance finding,
    # not merely those the author chose to provide native signals for.
    current_pairs = {(r["system_id"], r["requirement_id"]) for r in after_results}
    uncovered = [
        {"system_id": row["system_id"], "requirement_id": row["requirement_id"],
         "reason": "NO_REGISTERED_NATIVE_RISK_POLICY_NOT_EVIDENCE_OF_SAFETY"}
        for row in original["findings"]
        if row["status"] != "not_applicable"
        and (row["system_id"], row["requirement_id"]) not in current_pairs
    ]
    uncovered.sort(key=lambda r: (r["system_id"], r["requirement_id"]))
    result = {
        "schema": RESULT_SCHEMA,
        "scope": "OFFLINE_SYNTHETIC_LINKED_REASSESSMENT_ONLY",
        "governance_receipt_sha256": original["receipt_sha256"],
        "governance_findings": original["findings"],
        "governance_impacted_systems": original["impacted_systems"],
        "prior_policy_results": before_results,
        "current_reassessments": reassessments,
        "current_findings_without_native_risk_policy": uncovered,
        "input_observation_systems": sorted(raw),
        "authorization": AUTHORIZATION,
        "limitation": "Authored data/policy bindings, unknown real compliance, review, platform integration and costs",
    }
    result["receipt_sha256"] = impact.sha256(result)
    return result


def verify_receipt(report, *, anchored_receipt_sha256, anchored_governance_sha256):
    if not all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v)
               for v in (anchored_receipt_sha256, anchored_governance_sha256)):
        raise ValueError("INDEPENDENT_RECEIPT_AND_GOVERNANCE_ANCHORS_REQUIRED")
    if type(report) is not dict or report.get("schema") != RESULT_SCHEMA or (
        report.get("authorization") != AUTHORIZATION):
        raise ValueError("WRONG_REASSESSMENT_RECEIPT_SCHEMA")
    if not hmac.compare_digest(report.get("governance_receipt_sha256", ""),
                               anchored_governance_sha256):
        raise ValueError("GOVERNANCE_ANCHOR_MISMATCH")
    observed = report.get("receipt_sha256", "")
    plain = {k: v for k, v in report.items() if k != "receipt_sha256"}
    if not hmac.compare_digest(observed, anchored_receipt_sha256) or not (
        hmac.compare_digest(impact.sha256(plain), anchored_receipt_sha256)):
        raise ValueError("REASSESSMENT_RECEIPT_ANCHOR_MISMATCH")
    return True


def _strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        raise ValueError("INPUT_OUTPUT_MUST_DIFFER")
    raw = args.input.read_bytes().decode("utf-8", errors="strict")
    data = json.loads(raw, object_pairs_hook=_strict_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON_CONSTANT")))
    report = reassess(data)
    with args.output.open("x", encoding="utf-8") as dest:
        json.dump(report, dest, indent=2, sort_keys=True, ensure_ascii=False,
                  allow_nan=False)
        dest.write("\n")
    return report


if __name__ == "__main__":
    main()
