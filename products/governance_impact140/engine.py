"""Offline, source-bound AI-governance requirement impact *proposal*, not a compliance certificate.

Standard library only. No real-system data, signing keys or native financial accounts.
Every evidence assertion remains unverified without an external authorized reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "agi-alpha/governance-change-impact140/v1"
CLAIM_STATUSES = {"met", "partial", "not_met", "not_applicable"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(row, key):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"NONEMPTY_{key.upper()}_REQUIRED")
    return value


def _sequence(data, key):
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"LIST_{key.upper()}_REQUIRED")
    return value


def _tags(value, key):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f"VALID_{key.upper()}_TAGS_REQUIRED")
    if len(set(value)) != len(value):
        raise ValueError(f"DUPLICATE_{key.upper()}_TAG")
    return value


def _indexed(rows, kind):
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"INVALID_{kind.upper()}_ROW")
        ident = _text(row, "id")
        if ident in found:
            raise ValueError(f"DUPLICATE_{kind.upper()}_ID")
        if kind == "system":
            if set(row) != {"id", "tags"}:
                raise ValueError("INVALID_SYSTEM_FIELDS")
            _tags(row["tags"], "system")
        elif kind == "requirement":
            if set(row) != {"id", "version", "control", "applies_to"}:
                raise ValueError("INVALID_REQUIREMENT_FIELDS")
            _text(row, "version")
            _text(row, "control")
            _tags(row["applies_to"], "requirement")
        found[ident] = row
    return found


def _applies(requirement, system):
    return bool(requirement and
                ("*" in requirement["applies_to"] or
                 bool(set(requirement["applies_to"]) & set(system["tags"])))


def _read_evidence(rows, systems, before, after):
    observed = {}
    seen_ids = set()
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("INVALID_EVIDENCE_ROW")
        if not set(item).issubset({"id", "system_id", "requirement_id", "version",
                                   "claimed_status", "review_claim"}):
            raise ValueError("INVALID_EVIDENCE_FIELDS")
        for field in ("id", "system_id", "requirement_id", "version", "claimed_status"):
            _text(item, field)
        if item["id"] in seen_ids:
            raise ValueError("DUPLICATE_EVIDENCE_ID")
        seen_ids.add(item["id"])
        sid, rid, version = item["system_id"], item["requirement_id"], item["version"]
        if sid not in systems or rid not in before and rid not in after:
            raise ValueError("UNKNOWN_EVIDENCE_SYSTEM_OR_REQUIREMENT")
        versions = {row["version"] for row in (before.get(rid), after.get(rid)) if row}
        if version not in versions:
            raise ValueError("UNKNOWN_EVIDENCE_REQUIREMENT_VERSION")
        if item["claimed_status"] not in CLAIM_STATUSES:
            raise ValueError("INVALID_EVIDENCE_CLAIM")
        if "review_claim" in item and not isinstance(item["review_claim"], str):
            raise ValueError("INVALID_UNTRUSTED_REVIEW_CLAIM")
        key = (sid, rid, version)
        if key in observed:
            raise ValueError("DUPLICATE_EVIDENCE_IDENTITY")
        observed[key] = item
    return observed


def assess(input_data):
    """Compute *pending* reassessments from explicitly registered synthetic inputs.

    A matching claim never becomes a compliant finding without separate authenticated
    reviewer authority. An SHA256 digest is only an integrity reference when anchored
    independently; it is not a signature or authorization.
    """
    if not isinstance(input_data, dict) or set(input_data) != {
        "systems", "requirements_before", "requirements_after", "evidence"
    }:
        raise ValueError("INVALID_GOVERNANCE_INPUT_SCHEMA")
    systems = _indexed(_sequence(input_data, "systems"), "system")
    before = _indexed(_sequence(input_data, "requirements_before"), "requirement")
    after = _indexed(_sequence(input_data, "requirements_after"), "requirement")
    if not systems or not (before or after):
        raise ValueError("NONEMPTY_GOVERNANCE_SYSTEMS_AND_REQUIREMENTS_REQUIRED")
    evidence = _read_evidence(_sequence(input_data, "evidence"), systems, before, after)

    changes = []
    for rid in sorted(set(before) | set(after)):
        old, new = before.get(rid), after.get(rid)
        if old == new:
            continue
        kind = "added" if old is None else "retired" if new is None else "modified"
        changes.append({"id": rid, "kind": kind, "before": old, "after": new})

    findings = []
    impacted = set()
    for sid, system in sorted(systems.items()):
        for rid in sorted(set(before) | set(after)):
            old, new = before.get(rid), after.get(rid)
            was, now = _applies(old, system), _applies(new, system)
            if not was and not now:
                continue
            changed = old != new
            if changed:
                impacted.add(sid)
            if not now:
                findings.append({
                    "system_id": sid, "requirement_id": rid, "before_version":
                    old["version"] if old else None, "after_version":
                    new["version"] if new else None, "change_impacts_system": changed,
                    "status": "not_applicable", "review_status": "no_current_requirement",
                    "claimed_status": None, "evidence_id": None,
                    "historical_evidence_id": (evidence.get((sid, rid, old["version"]), {}).get("id")
                                               if old else None),
                    "reason": "retired_or_out_of_scope; prior history retained in changes",
                })
                continue
            current = evidence.get((sid, rid, new["version"]))
            historical = evidence.get((sid, rid, old["version"])) if old else None
            reason = ("requirement_added_or_modified; prior claims do not authorize"
                      if changed else "independent_reviewer_not_integrated"
                      if current else "no_evidence")
            if changed and historical:
                reason = "changed_requirement_invalidates_prior_evidence"
            findings.append({
                "system_id": sid, "requirement_id": rid,
                "before_version": old["version"] if old else None,
                "after_version": new["version"], "change_impacts_system": changed,
                "status": "unable_to_determine" if changed or current is None
                else "pending_review",
                "review_status": "pending_authorized_independent_review",
                "claimed_status": current["claimed_status"] if current else None,
                "evidence_id": current["id"] if current else None,
                "historical_evidence_id": historical["id"] if historical else None,
                "reported_approval_ignored": bool(current and
                    current.get("review_claim", "").lower() in {"approved", "passed"}),
                "reason": reason,
            })

    result = {
        "schema": SCHEMA,
        "scope": "OFFLINE_SYNTHETIC_ENGINEERING_ONLY",
        "source_input_sha256": sha256(input_data),
        "changes": changes,
        "impacted_systems": sorted(impacted),
        "findings": findings,
        "authorization": "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE",
        "hash_limit": "SHA256 is not a signature; compare to independently anchored digest",
    }
    result["receipt_sha256"] = sha256(result)
    return result


def _strict_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_FIELD")
        obj[key] = value
    return obj


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_text(encoding="utf-8"),
                      object_pairs_hook=_strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON_VALUE")))
    report = assess(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, sort_keys=True, indent=2, ensure_ascii=False,
                  allow_nan=False)
        out.write("\n")
    print(f"{SCHEMA} receipt={report['receipt_sha256']}")


if __name__ == "__main__":
    main()
