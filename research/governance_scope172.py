"""Conservative OSCAL control-to-system scope continuity *proposal*, never an approval.

A source/content anchor is not a signature, authenticated reviewer or proof of
policy applicability. The output does not call native finance or change a control.
"""
from __future__ import annotations

import argparse
import copy
import hmac
import json
import re
from pathlib import Path

from products.governance_impact140 import engine as native
from research import governance_oscal171 as oscal

SCHEMA = "agi-alpha/governance-scope-continuity172/input-v1"
RESULT_SCHEMA = "agi-alpha/governance-scope-continuity172/result-v1"
HEX = re.compile(r"[0-9a-f]{64}\\Z")
MAX_BYTES = 2_000_000
ANCHORS = (
    "catalog_before_sha256", "catalog_after_sha256",
    "scope_before_sha256", "systems_before_sha256",
)


def _systems(rows):
    if type(rows) is not list or not rows:
        raise ValueError("NONEMPTY_REGISTERED_SYSTEMS_REQUIRED")
    # Use the unchanged canonical governance verifier's system schema and
    # uniqueness rules rather than inventing a weaker alternate validator.
    native._indexed(rows, "system")
    return rows


def _anchor(anchor, observed, label):
    if type(anchor) is not str or HEX.fullmatch(anchor) is None:
        raise ValueError("LOWERCASE_SHA256_ANCHOR_REQUIRED_" + label)
    if not hmac.compare_digest(anchor, native.sha256(observed)):
        raise ValueError("EXTERNAL_SOURCE_ANCHOR_MISMATCH_" + label)


def propose(data):
    if type(data) is not dict or set(data) != {
        "schema", "before_catalog", "after_catalog", "before_systems",
        "after_systems", "before_scope", "anchors"
    } or data["schema"] != SCHEMA:
        raise ValueError("EXACT_SOURCE_CONTINUITY_INPUT_REQUIRED")
    anchors = data["anchors"]
    if type(anchors) is not dict or set(anchors) != set(ANCHORS):
        raise ValueError("FOUR_EXTERNAL_SOURCE_ANCHORS_REQUIRED")
    for label, source in (
        ("catalog_before_sha256", data["before_catalog"]),
        ("catalog_after_sha256", data["after_catalog"]),
        ("scope_before_sha256", data["before_scope"]),
        ("systems_before_sha256", data["before_systems"]),
    ):
        _anchor(anchors[label], source, label)

    prior_systems = _systems(data["before_systems"])
    target_systems = _systems(data["after_systems"])
    old, bmeta = oscal.extract_catalog(data["before_catalog"])
    new, ameta = oscal.extract_catalog(data["after_catalog"])
    # The same importer that backs the canonical impact140 assessment must
    # validate EVERY old explicit decision, even if its control is retired.
    oscal.explicit_requirements(old, data["before_scope"], prior_systems)

    inventory_unchanged = native.sha256(prior_systems) == native.sha256(target_systems)
    provisional, required, retired = [], [], []
    for ident in sorted(new):
        ancestor = old.get(ident)
        if inventory_unchanged and ancestor is not None and (
            ancestor["semantic_sha256"] == new[ident]["semantic_sha256"]
        ):
            provisional.append({
                "id": ident,
                "scope": copy.deepcopy(data["before_scope"][ident]),
                "source_semantic_sha256": new[ident]["semantic_sha256"],
                "status": "PROVISIONAL_CONTINUITY_NOT_REVIEW_APPROVAL",
            })
        else:
            why = ("SYSTEM_INVENTORY_CHANGED" if not inventory_unchanged else
                   "CONTROL_ADDED" if ancestor is None else
                   "CONTROL_OR_CONTEXT_CHANGED")
            required.append({"id": ident, "reason": why,
                             "status": "EXPLICIT_NEW_SCOPE_REVIEW_REQUIRED",
                             "proposed_scope": None})
    for ident in sorted(set(old) - set(new)):
        retired.append({"id": ident, "last_semantic_sha256": old[ident]["semantic_sha256"],
                        "status": "HISTORICAL_RETIRED_NOT_APPLIED"})

    result = {
        "schema": RESULT_SCHEMA,
        "old_catalog": bmeta,
        "new_catalog": ameta,
        "source_input_sha256": native.sha256(data),
        "external_anchor_values": copy.deepcopy(anchors),
        "same_registered_system_inventory": inventory_unchanged,
        "provisional": provisional,
        "review_required": required,
        "retired": retired,
        "summary": {
            "old_controls": len(old), "new_controls": len(new),
            "provisional_count": len(provisional),
            "review_required_count": len(required), "retired_count": len(retired),
        },
        "authorization": "NO_AUTHENTICATED_POLICY_OR_COMPLIANCE_APPROVAL",
        "actual_customer_acceptance": None,
        "complete_actual_cost": None,
        "actual_revenue": None,
        "trailing_365_profit": None,
        "native_financial_account_modified": False,
    }
    result["receipt_sha256"] = native.sha256(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        raise ValueError("INPUT_OUTPUT_PATH_COLLISION")
    if args.input.is_symlink() or not args.input.is_file() or args.input.stat().st_size > MAX_BYTES:
        raise ValueError("BOUNDED_REGULAR_SOURCE_INPUT_REQUIRED")
    data = json.loads(args.input.read_text("utf-8"),
                      object_pairs_hook=oscal.strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    result = propose(data)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"receipt_sha256": result["receipt_sha256"],
                      "provisional": len(result["provisional"]),
                      "review_required": len(result["review_required"]),
                      "authorization": result["authorization"]}, sort_keys=True))


if __name__ == "__main__":
    main()
