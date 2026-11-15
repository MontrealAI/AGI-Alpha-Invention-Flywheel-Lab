"""T9: exact public NIST AI RMF OSCAL catalog against the unchanged OSCAL171 adapter.

Prospectively frozen in campaign/governance-oscal171/OFFICIAL_NIST_T9_PROTOCOL.md.
This is research interoperability verification, not policy authenticity or approval.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import resource
import time
from pathlib import Path

from products.governance_impact140 import engine as native
from research import governance_oscal171 as bridge

SOURCE_REPO = "usnistgov/oscal-content"
SOURCE_TAG = "v1.6.0"
SOURCE_PATH = "nist.gov/AI100-1/ver1/json/NIST_AI-RMF_v1_catalog-min.json"
SOURCE_GIT_BLOB_SHA1 = "1f625a618448cec41f8f7fa8ea50bbaf7751bb82"
SYNTHETIC_SYSTEM = "NIST-RMF-synthetic-offline-system"
TAG = "nist-ai-rmf"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical_sha(obj):
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def traverse_catalog(catalog):
    """Independent structural enumeration; do not call bridge.extract_catalog here."""
    controls = []
    seen = set()
    group_count = 0

    def walk_controls(rows):
        for control in rows:
            require(type(control) is dict and type(control.get("id")) is str,
                    "INVALID_OFFICIAL_CONTROL")
            ident = control["id"]
            require(ident not in seen, "DUPLICATE_OFFICIAL_IDENT")
            seen.add(ident)
            controls.append(ident)
            walk_controls(control.get("controls", []))

    def walk_groups(rows):
        nonlocal group_count
        for group in rows:
            ident = group["id"]
            require(ident not in seen, "DUPLICATE_OFFICIAL_GROUP")
            seen.add(ident)
            group_count += 1
            walk_controls(group.get("controls", []))
            walk_groups(group.get("groups", []))

    walk_controls(catalog.get("controls", []))
    walk_groups(catalog.get("groups", []))
    return controls, group_count


def load_official_fixture(path):
    require(path.is_file() and not path.is_symlink(), "OFFICIAL_REGULAR_FILE_REQUIRED")
    raw = path.read_bytes()
    require(0 < len(raw) <= bridge.MAX_BYTES, "OFFICIAL_SOURCE_OUT_OF_BOUNDS")
    git_payload = b"blob " + str(len(raw)).encode("ascii") + b"\\0" + raw
    git_blob = hashlib.sha1(git_payload).hexdigest()
    require(git_blob == SOURCE_GIT_BLOB_SHA1, "PINNED_GIT_BLOB_CHANGED")
    source = json.loads(raw.decode("utf-8"), object_pairs_hook=bridge.strict_object,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    return source, {"source_repo": SOURCE_REPO, "source_tag": SOURCE_TAG,
                    "source_path": SOURCE_PATH, "git_blob_sha1": git_blob,
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "raw_bytes": len(raw)}


def run(fixture):
    start = time.perf_counter()
    catalog, provenance = load_official_fixture(fixture)
    doc = catalog["catalog"]
    require(doc["metadata"]["oscal-version"] == "v1.2.3", "UNEXPECTED_OFFICIAL_OSCAL_VERSION")
    controls_independent, groups = traverse_catalog(doc)
    require(len(controls_independent) == 91 and len(set(controls_independent)) == 91,
            "OFFICIAL_CONTROL_COUNT_CHANGED")
    require(len(doc.get("groups", [])) == 4 and groups == 4, "OFFICIAL_GROUP_COUNT_CHANGED")
    parsed, metadata = bridge.extract_catalog(catalog)
    require(set(parsed) == set(controls_independent) and metadata["control_count"] == 91,
            "OFFICIAL_IMPORT_DROPPED_CONTROL")

    scope = {ident: {"applies_to": [TAG]} for ident in controls_independent}
    base = {"schema": bridge.SCHEMA, "before_catalog": catalog,
            "after_catalog": copy.deepcopy(catalog),
            "systems": [{"id": SYNTHETIC_SYSTEM, "tags": [TAG]}],
            "before_scope": copy.deepcopy(scope), "after_scope": copy.deepcopy(scope),
            "evidence": []}
    original = bridge.assess(base)
    native_original = original["native_receipt"]
    require(len(native_original["findings"]) == 91, "INCOMPLETE_NATIVE_FINDINGS")
    require(not native_original["changes"] and not native_original["impacted_systems"],
            "UNCHANGED_OFFICIAL_CATALOG_PRODUCED_CHANGES")
    require(all(f["review_status"] == "pending_authorized_independent_review"
                for f in native_original["findings"]), "AUTO_APPROVAL_FORBIDDEN")
    require(original["authorization"] == "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE"
            and original["complete_actual_cost"] is None
            and original["real_customer_accepted"] is None, "UNSUPPORTED_AUTHORITY_OR_COMMERCE")
    require(native_original == native.assess(original["native_input"]), "NATIVE_PARITY_FAILED")

    synthetic = copy.deepcopy(base)
    target = synthetic["after_catalog"]["catalog"]["groups"][0]["controls"][0]["controls"][0]
    require(target["id"] == "GOVERN_1.1", "PINNED_LEAF_PATH_CHANGED")
    target["parts"][0]["prose"] += " [SYNTHETIC NON-NIST ADVERSARIAL REVISION]"
    require(synthetic["after_catalog"]["catalog"]["metadata"]["version"]
            == synthetic["before_catalog"]["catalog"]["metadata"]["version"],
            "SYNTHETIC_METADATA_CHANGED")
    changed = bridge.assess(synthetic)
    b = {x["id"]: x["version"] for x in changed["before_controls"]}
    a = {x["id"]: x["version"] for x in changed["after_controls"]}
    changed_ids = sorted(ident for ident in b if b[ident] != a[ident])
    require(changed_ids == ["GOVERN_1.1"], "CONTENT_REVISION_SPILLED_OR_MISSED")
    require(changed["native_receipt"]["impacted_systems"] == [SYNTHETIC_SYSTEM],
            "SYNTHETIC_IMPACT_NOT_DETECTED")
    require(len(changed["native_receipt"]["changes"]) == 1,
            "SYNTHETIC_NATIVE_CHANGE_COUNT_INVALID")
    require(changed["native_receipt"] == native.assess(changed["native_input"]),
            "SYNTHETIC_NATIVE_PARITY_FAILED")

    # Independent recomputation of anchors from JSON, not from producer-provided hashes.
    for input_data, report in ((base, original), (synthetic, changed)):
        independent_input_sha = canonical_sha(input_data)
        independent_receipt_sha = canonical_sha({k: v for k, v in report.items()
                                                if k != "receipt_sha256"})
        require(bridge.verify_receipt(report, expected_input_sha256=independent_input_sha,
                                      expected_receipt_sha256=independent_receipt_sha),
                "EXTERNAL_ANCHOR_RECOMPUTATION_FAILED")
    tampered = copy.deepcopy(changed)
    tampered["after"]["control_count"] = 0
    try:
        bridge.verify_receipt(tampered, expected_input_sha256=canonical_sha(synthetic),
                              expected_receipt_sha256=changed["receipt_sha256"])
    except ValueError:
        pass
    else:
        raise AssertionError("TAMPER_ACCEPTED")

    missing_scope = copy.deepcopy(base)
    missing_scope["after_scope"].pop("GOVERN_1.1")
    try:
        bridge.assess(missing_scope)
    except ValueError as exc:
        require("EVERY_OSCAL_CONTROL_NEEDS_EXPLICIT_SCOPE" in str(exc),
                "WRONG_MISSING_SCOPE_REFUSAL")
    else:
        raise AssertionError("MISSING_SCOPE_ACCEPTED")

    cpu = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "schema": "agi-alpha/oscal171-official-nist-t9-result/v1",
        "verdict": "PASS_ENGINEERING_SOURCE_COMPATIBILITY_ONLY",
        "fixture": provenance,
        "original_protocol": "campaign/governance-oscal171/PROTOCOL.md",
        "additive_protocol": "campaign/governance-oscal171/OFFICIAL_NIST_T9_PROTOCOL.md",
        "external_model": "NIST AI RMF 1.0, official OSCAL v1.2.3 catalog (NIST v1.6.0)",
        "controls": len(controls_independent), "groups": groups,
        "synthetic_registered_systems": 1,
        "identical_input_native_findings": len(native_original["findings"]),
        "identical_input_changes": len(native_original["changes"]),
        "synthetic_nonstandard_mutation_ids": changed_ids,
        "synthetic_affected_systems": changed["native_receipt"]["impacted_systems"],
        "complete_actual_cost": None, "real_buyer_acceptance": None,
        "authentic_publisher_signature_verified": False,
        "full_oscal_schema_conformance": False,
        "procurement_eligible": None, "earned_revenue_usd": None,
        "trailing_365_profit_usd": None,
        "resource_self_cpu_seconds": round(cpu.ru_utime + cpu.ru_stime, 4),
        "elapsed_wall_seconds": round(time.perf_counter() - start, 4),
        "claims": "Source-ingest and fail-closed semantics only; no compliance approval or differentiated profitability",
        "commercial_decision": "NO_BID_NO_DEPLOY",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(args.fixture.resolve() != args.output.resolve(), "INPUT_OUTPUT_PATH_COLLISION")
    receipt = run(args.fixture)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(receipt, out, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        out.write("\\n")
    print(json.dumps({"verdict": receipt["verdict"], "controls": receipt["controls"],
                      "source_sha256": receipt["fixture"]["raw_sha256"],
                      "commercial_decision": receipt["commercial_decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
