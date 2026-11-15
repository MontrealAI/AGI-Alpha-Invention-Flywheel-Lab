"""Narrow OSCAL-shaped catalog -> unchanged governance impact140 adapter.

Research only: not a full OSCAL validator, legal opinion, trusted policy feed,
authorized review, live deployment, or financial/account interface.
"""
from __future__ import annotations

import argparse
import copy
import hmac
import json
import re
from pathlib import Path
from uuid import UUID

from products.governance_impact140 import engine as native

SCHEMA = "agi-alpha/oscal-interop171/input-v1"
RESULT_SCHEMA = "agi-alpha/oscal-interop171/result-v1"
MAX_BYTES = 2_000_000
HEX = re.compile(r"[0-9a-f]{64}\Z")


def required(value, reason):
    if type(value) is not str or not value.strip():
        raise ValueError(reason)
    return value


def extract_catalog(source):
    if type(source) is not dict or set(source) != {"catalog"}:
        raise ValueError("OSCAL_CATALOG_ROOT_REQUIRED")
    doc = source["catalog"]
    if type(doc) is not dict or type(doc.get("metadata")) is not dict:
        raise ValueError("OSCAL_CATALOG_METADATA_REQUIRED")
    try:
        if type(doc.get("uuid")) is not str or str(UUID(doc["uuid"])) != doc["uuid"]:
            raise ValueError("noncanonical uuid")
    except (ValueError, AttributeError) as exc:
        raise ValueError("CANONICAL_CATALOG_UUID_REQUIRED") from exc
    meta = doc["metadata"]
    required(meta.get("title"), "CATALOG_TITLE_REQUIRED")
    required(meta.get("version"), "CATALOG_VERSION_REQUIRED")
    controls, seen = {}, set()

    def control_list(rows, parents):
        if type(rows) is not list:
            raise ValueError("CONTROLS_MUST_BE_LIST")
        for row in rows:
            if type(row) is not dict:
                raise ValueError("INVALID_OSCAL_CONTROL")
            ident = required(row.get("id"), "CONTROL_ID_REQUIRED")
            title = required(row.get("title"), "CONTROL_TITLE_REQUIRED")
            if ident in seen:
                raise ValueError("DUPLICATE_OSCAL_IDENTIFIER")
            seen.add(ident)
            own = {k: v for k, v in row.items() if k != "controls"}
            digest = native.sha256({"context": parents, "control": own})
            controls[ident] = {"title": title, "semantic_sha256": digest,
                               "version": "oscal-content-sha256:" + digest}
            control_list(row.get("controls", []), parents + [{"control": own}])

    def group_list(rows, parents):
        if type(rows) is not list:
            raise ValueError("GROUPS_MUST_BE_LIST")
        for row in rows:
            if type(row) is not dict:
                raise ValueError("INVALID_OSCAL_GROUP")
            ident = required(row.get("id"), "GROUP_ID_REQUIRED")
            required(row.get("title"), "GROUP_TITLE_REQUIRED")
            if ident in seen:
                raise ValueError("DUPLICATE_OSCAL_IDENTIFIER")
            seen.add(ident)
            own = {k: v for k, v in row.items() if k not in ("groups", "controls")}
            context = parents + [{"group": own}]
            control_list(row.get("controls", []), context)
            group_list(row.get("groups", []), context)

    control_list(doc.get("controls", []), [])
    group_list(doc.get("groups", []), [])
    if not controls:
        raise ValueError("NONEMPTY_OSCAL_CONTROLS_REQUIRED")
    source_meta = {"catalog_uuid": doc["uuid"], "catalog_version": meta["version"],
                   "catalog_sha256": native.sha256(source), "control_count": len(controls)}
    return controls, source_meta


def explicit_requirements(controls, scope, systems):
    if type(scope) is not dict or set(scope) != set(controls):
        raise ValueError("EVERY_OSCAL_CONTROL_NEEDS_EXPLICIT_SCOPE")
    known = {tag for system in systems for tag in system["tags"]}
    out = []
    for ident in sorted(controls):
        value = scope[ident]
        if type(value) is not dict or set(value) != {"applies_to"}:
            raise ValueError("EXACT_EXPLICIT_SCOPE_REQUIRED")
        tags = value["applies_to"]
        if type(tags) is not list or any(type(t) is not str or not t.strip() for t in tags):
            raise ValueError("INVALID_SCOPE_TAGS")
        if len(set(tags)) != len(tags):
            raise ValueError("DUPLICATE_SCOPE_TAG")
        if any(t not in known and t != "*" for t in tags):
            raise ValueError("SCOPE_MUST_MATCH_REGISTERED_SYSTEM_TAG")
        ctrl = controls[ident]
        out.append({"id": ident, "version": ctrl["version"],
                    "control": ctrl["title"] + " [unverified OSCAL content sha256:" +
                               ctrl["semantic_sha256"] + "]",
                    "applies_to": tags})
    return out


def assess(data):
    if type(data) is not dict or set(data) != {
        "schema", "before_catalog", "after_catalog", "systems",
        "before_scope", "after_scope", "evidence"
    } or data["schema"] != SCHEMA:
        raise ValueError("EXACT_OSCAL_BRIDGE_INPUT_REQUIRED")
    systems = data["systems"]
    if type(systems) is not list or not systems:
        raise ValueError("REGISTERED_SYSTEMS_REQUIRED")
    seen = set()
    for system in systems:
        if type(system) is not dict or set(system) != {"id", "tags"}:
            raise ValueError("EXACT_REGISTERED_SYSTEM_REQUIRED")
        ident = required(system["id"], "SYSTEM_ID_REQUIRED")
        if ident in seen:
            raise ValueError("DUPLICATE_SYSTEM_ID")
        seen.add(ident)
        tags = system["tags"]
        if type(tags) is not list or any(type(t) is not str or not t.strip() for t in tags) or len(set(tags)) != len(tags):
            raise ValueError("VALID_SYSTEM_TAGS_REQUIRED")
    before, bmeta = extract_catalog(data["before_catalog"])
    after, ameta = extract_catalog(data["after_catalog"])
    inner = {
        "systems": copy.deepcopy(systems),
        "requirements_before": explicit_requirements(before, data["before_scope"], systems),
        "requirements_after": explicit_requirements(after, data["after_scope"], systems),
        "evidence": copy.deepcopy(data["evidence"])
    }
    receipt = native.assess(inner)
    report = {
        "schema": RESULT_SCHEMA,
        "scope": "OFFLINE_OSCAL_SHAPED_SUBSET_SYNTHETIC_ONLY",
        "source_input_sha256": native.sha256(data),
        "before": bmeta, "after": ameta,
        "before_controls": [{"id": ident, **before[ident]} for ident in sorted(before)],
        "after_controls": [{"id": ident, **after[ident]} for ident in sorted(after)],
        "native_input": inner, "native_receipt": receipt,
        "authorization": "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE",
        "eligibility": None, "real_customer_accepted": None,
        "complete_actual_cost": None
    }
    report["receipt_sha256"] = native.sha256(report)
    return report


def verify_receipt(report, *, expected_input_sha256, expected_receipt_sha256):
    if any(type(x) is not str or HEX.fullmatch(x) is None
           for x in (expected_input_sha256, expected_receipt_sha256)):
        raise ValueError("INDEPENDENT_SHA256_ANCHORS_REQUIRED")
    if type(report) is not dict or report.get("schema") != RESULT_SCHEMA or (
        report.get("authorization") != "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE"
    ):
        raise ValueError("UNSUPPORTED_RECEIPT_OR_AUTHORITY")
    if not hmac.compare_digest(str(report.get("receipt_sha256", "")), expected_receipt_sha256):
        raise ValueError("EXTERNAL_RECEIPT_ANCHOR_MISMATCH")
    if not hmac.compare_digest(str(report.get("source_input_sha256", "")), expected_input_sha256):
        raise ValueError("EXTERNAL_INPUT_ANCHOR_MISMATCH")
    raw = {k: v for k, v in report.items() if k != "receipt_sha256"}
    if not hmac.compare_digest(native.sha256(raw), expected_receipt_sha256):
        raise ValueError("RECEIPT_CONTENT_CHANGED")
    rec = report["native_receipt"]
    native.verify_receipt(
        rec, anchored_receipt_sha256=rec["receipt_sha256"],
        anchored_input_sha256=native.sha256(report["native_input"]))
    return True


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_JSON_FIELD")
        out[key] = value
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        raise ValueError("INPUT_OUTPUT_MUST_DIFFER")
    if args.input.is_symlink() or not args.input.is_file() or args.input.stat().st_size > MAX_BYTES:
        raise ValueError("BOUNDED_REGULAR_SYNTHETIC_INPUT_REQUIRED")
    data = json.loads(args.input.read_text("utf-8"), object_pairs_hook=strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    receipt = assess(data)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(receipt, out, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        out.write("\n")
    print(json.dumps({"receipt_sha256": receipt["receipt_sha256"],
                      "authorization": receipt["authorization"]}, sort_keys=True))


if __name__ == "__main__":
    main()
