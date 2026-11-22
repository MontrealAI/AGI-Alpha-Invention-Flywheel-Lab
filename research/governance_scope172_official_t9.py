"""Frozen OSCAL172 T9: pinned real NIST source, synthetic application mappings.

This only tests *provisional* continuity mechanics. It never authenticates the
hypothetical system's scope or issues a compliance or procurement finding.
"""
from __future__ import annotations

import argparse
import copy
import json
import resource
import time
from pathlib import Path

from products.governance_impact140 import engine as native
from research import governance_oscal171_official_t9 as official
from research import governance_scope172 as continuity

TAG = "synthetic-risk"
SYSTEM = "synthetic-unowned-offline-system"


def assert_true(value, error):
    if not value:
        raise AssertionError(error)


def run(fixture: Path):
    start = time.perf_counter()
    source, source_id = official.load_official_fixture(fixture)
    independent_ids, groups = official.traverse_catalog(source["catalog"])
    assert_true(len(independent_ids) == 91 and groups == 4, "REAL_NIST_STRUCTURE_UNEXPECTED")
    scope = {ident: {"applies_to": [TAG]} for ident in independent_ids}
    systems = [{"id": SYSTEM, "tags": [TAG]}]
    data = {
        "schema": continuity.SCHEMA,
        "before_catalog": source,
        "after_catalog": copy.deepcopy(source),
        "before_scope": scope,
        "before_systems": systems,
        "after_systems": copy.deepcopy(systems),
    }
    data["anchors"] = {
        "catalog_before_sha256": native.sha256(data["before_catalog"]),
        "catalog_after_sha256": native.sha256(data["after_catalog"]),
        "scope_before_sha256": native.sha256(data["before_scope"]),
        "systems_before_sha256": native.sha256(data["before_systems"]),
    }
    unchanged = continuity.propose(data)
    assert_true(unchanged["summary"] == {
        "old_controls": 91, "new_controls": 91,
        "provisional_count": 91, "review_required_count": 0, "retired_count": 0
    }, "UNCHANGED_REAL_SOURCE_NOT_91_PROVISIONAL")
    assert_true(unchanged["authorization"] == "NO_AUTHENTICATED_POLICY_OR_COMPLIANCE_APPROVAL",
                "REAL_SOURCE_FALSE_APPROVAL")

    # This alteration is explicitly synthetic; no revised NIST publication is
    # claimed. The source-publisher version and 90 unaffected controls stay fixed.
    changed_data = copy.deepcopy(data)
    amended = changed_data["after_catalog"]["catalog"]["groups"][0]["controls"][0]["controls"][0]
    assert_true(amended["id"] == "GOVERN_1.1", "PINNED_NIST_CONTROL_PATH_DIFFERENT")
    amended["parts"][0]["prose"] += " [SYNTHETIC CONTROL CHANGE, NOT NIST]"
    changed_data["anchors"]["catalog_after_sha256"] = native.sha256(changed_data["after_catalog"])
    changed = continuity.propose(changed_data)
    assert_true(changed["summary"] == {
        "old_controls": 91, "new_controls": 91,
        "provisional_count": 90, "review_required_count": 1, "retired_count": 0
    }, "CHANGED_CONTROL_MISSED_OR_SCOPE_LEAK")
    assert_true(changed["review_required"][0]["id"] == "GOVERN_1.1" and
                changed["review_required"][0]["proposed_scope"] is None and
                changed["review_required"][0]["reason"] == "CONTROL_OR_CONTEXT_CHANGED",
                "CHANGED_NIST_CONTROL_WRONGLY_APPROVED")
    assert_true("GOVERN_1.1" not in {x["id"] for x in changed["provisional"]},
                "STALE_SCOPE_REUSE")
    assert_true(changed["old_catalog"]["catalog_version"] ==
                changed["new_catalog"]["catalog_version"], "PUBLISHER_VERSION_NOT_FIXED")

    # Both proposed outputs are conventional hash/reuse mechanics. The
    # competent conventional baseline can also copy all 91 identical entries.
    # Counts are operation counts, never measured human hours or cost savings.
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "schema": "agi-alpha/governance-scope172-official-nist-t9/v1",
        "verdict": "PASS_MECHANICAL_PROVISIONAL_SCOPE_ONLY",
        "source": source_id,
        "official_controls": 91,
        "official_groups": groups,
        "synthetic_registered_system_count": 1,
        "synthetic_scope_assignments": len(scope),
        "unchanged_provisional_count": len(unchanged["provisional"]),
        "changed_provisional_count": len(changed["provisional"]),
        "synthetic_review_required_ids": [x["id"] for x in changed["review_required"]],
        "same_publisher_version_in_mutation": True,
        "conventional_hash_copy_may_tie": True,
        "source_issuer_or_reviewer_signature_verified": False,
        "real_policy_scope_authorized": False,
        "official_revision_observed": False,
        "compliance_approved": False,
        "buyer_accepted": None,
        "complete_actual_cost": None,
        "profit_trailing365": None,
        "real_collected_revenue": None,
        "commercial_decision": "NO_BID_NO_DEPLOY",
        "process_self_cpu_seconds": round(usage.ru_utime + usage.ru_stime, 5),
        "elapsed_wall_seconds": round(time.perf_counter() - start, 5),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.fixture.resolve() == args.output.resolve():
        raise ValueError("INPUT_OUTPUT_PATH_COLLISION")
    report = run(args.fixture)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "verdict": report["verdict"], "official_controls": report["official_controls"],
        "provisional_changed": report["changed_provisional_count"],
        "review_required": report["synthetic_review_required_ids"],
        "commercial_decision": report["commercial_decision"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
