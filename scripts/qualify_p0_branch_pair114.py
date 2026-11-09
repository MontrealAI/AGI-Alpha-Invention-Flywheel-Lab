#!/usr/bin/env python3
"""Read-only pinned P0 owner/main pair witness; never opens an Account."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from tools.p0_source_guard import inspect, load_registry

MAIN = "ada84f88d0c852609087fdc838c071917c8a02b8"
TRANSITION = "ced6c1cb004887dcdafaea59a2976020be649f8e"
SCHEMAS = (
    "genesis-commitment001/native-services/v1",
    "public-portfolio-20261102/native-services/v2",
    "flexibility063/native-services/v1",
    "production060/native-services/v1",
    "inventory061/native-services/v1",
)


def sha(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("REGULAR_PUBLIC_SOURCE_REQUIRED:" + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(main: Path, transition: Path) -> dict:
    main = main.absolute()
    transition = transition.absolute()
    a, aroutes = load_registry(main)
    b, broutes = load_registry(transition)
    cases = []
    for name, composed in (("unchanged_main", main), ("unchanged_transition", transition)):
        result = inspect(main, transition, composed)
        cases.append({"case": name, "source_root_role": name,
                      "preflight": result, "registered_incomplete": not result["registry_complete"]})
    outcome = {
        "schema": "agi-alpha/p0-pinned-branch-pair114/v1",
        "scope": "PUBLIC_SOURCE_ONLY_NO_ACCOUNT_NO_SEMANTIC_MIGRATION",
        "protocol": "campaign/p0-branch-pair114/PROTOCOL.md",
        "main_commit": MAIN,
        "transition_commit": TRANSITION,
        "main_finance_source_sha256": sha(main / "connected_enterprise/finance.py"),
        "transition_finance_source_sha256": sha(transition / "connected_enterprise/finance.py"),
        "main_declared_finance_paths": len(a["SOURCE_PATHS"]),
        "transition_declared_finance_paths": len(b["SOURCE_PATHS"]),
        "main_active_manifest_routes": sorted(aroutes),
        "transition_active_manifest_routes": sorted(broutes),
        "registered_required_main_routes": list(SCHEMAS),
        "cases": cases,
        "original_signed_state_or_writer_observed": False,
        "original_financial_migration_qualified": False,
        "real_commerce_or_T365_qualified": False,
        "next": "Owner-held semantic source composition and authenticated nonempty original-account queue continuation; independent native/released audit.",
    }
    outcome["registered_expected_negative_witness"] = (
        set(SCHEMAS).issubset(aroutes)
        and all(case["registered_incomplete"] for case in cases)
        and not set(SCHEMAS).issubset(broutes)
        and any(c["preflight"]["missing_main_manifest_routes"] for c in cases)
    )
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-root", required=True, type=Path)
    parser.add_argument("--transition-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError("CREATE_ONLY_RECEIPT_REQUIRED")
    result = assess(args.main_root, args.transition_root)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"registered_expected_negative_witness": result["registered_expected_negative_witness"],
                      "cases": [{"case": x["case"],
                                 "registry_complete": x["preflight"]["registry_complete"],
                                 "missing_financial_paths": len(x["preflight"]["missing_main_or_transition_financial_paths"]),
                                 "missing_main_routes": x["preflight"]["missing_main_manifest_routes"]}
                                for x in result["cases"]]}, sort_keys=True))
    return 0 if result["registered_expected_negative_witness"] else 1


if __name__ == "__main__":
    sys.exit(main())
