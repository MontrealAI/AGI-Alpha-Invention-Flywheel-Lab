"""Fail-closed, key-free proof of native design041 on *actual* Connected014 release bytes.

This verifier runs from the GitHub checkout to authenticate downloaded public
assets, but native operations and their independent audit must run with the
extracted published source as the working directory. No local account/private
simulation key may be uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_connected014 import checked_members, verify_assets

SCHEMA = "agi-alpha/native-design041-actual-public-release-proof/v1"
REQUIRED = {"connected_enterprise/design_flywheel.py", "tests/test_connected_design_flywheel041.py"}


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(assets: Path, commit: str, source: Path) -> None:
    if source.exists() or source.is_symlink():
        raise FileExistsError("FRESH_EXTRACTED_SOURCE_REQUIRED")
    published = verify_assets(assets, commit)
    with zipfile.ZipFile(assets / "connected014-source.zip") as archive:
        names = checked_members(archive)
        manifest = json.loads(archive.read("SOURCE_MANIFEST.json"))
        if manifest["executing_source"]["sha256"] != published["source_sha256"]:
            raise ValueError("RELEASE_EXECUTING_SOURCE_CHANGED")
        if not REQUIRED <= set(manifest["files"]) or not REQUIRED <= set(names):
            raise ValueError("RELEASE_NATIVE_DESIGN_CLOSURE_MISSING")
        source.mkdir(parents=True)
        archive.extractall(source)
    if _read(source / "SOURCE_MANIFEST.json") != manifest:
        raise ValueError("EXTRACTED_RELEASE_MANIFEST_CHANGED")
    for name in REQUIRED:
        if _hash(source / name) != manifest["files"][name]:
            raise ValueError("EXTRACTED_NATIVE_DESIGN_SOURCE_CHANGED:" + name)
    print(json.dumps({"accepted": True, "actual_public_release": True,
                      "source_commit": commit, "source_sha256": published["source_sha256"],
                      "required_native_files": sorted(REQUIRED)}, sort_keys=True))


def seal(assets: Path, commit: str, source: Path, public_path: Path, receipt: Path, public_copy: Path) -> None:
    published = verify_assets(assets, commit)
    manifest = _read(source / "SOURCE_MANIFEST.json")
    public = _read(public_path)
    expected = published["source_sha256"]
    if (published["source_commit"] != commit
            or manifest["executing_source"]["sha256"] != expected
            or public.get("source_sha256") != expected):
        raise ValueError("PUBLIC_NATIVE_RELEASE_IDENTITY_CHANGED")
    if any(_hash(source / name) != manifest["files"].get(name) for name in REQUIRED):
        raise ValueError("RELEASE_NATIVE_SOURCE_CHANGED_AFTER_EXECUTION")
    if (public.get("confirmed_positive_funded_successor_opportunity") is not True
            or public.get("comparative_advantage_on_one_fresh_seed") is not True
            or public.get("heldout_recommendation", {}).get("challenger_accepted") is not True):
        raise ValueError("FROZEN_EXPOSED_NATIVE_DESIGN_GATE_FAILED")
    if receipt.exists() or public_copy.exists():
        raise FileExistsError("FRESH_PUBLIC_RECEIPT_REQUIRED")
    result = {
        "schema": SCHEMA, "source_commit": commit, "source_sha256": expected,
        "release_source_archive_sha256": _hash(assets / "connected014-source.zip"),
        "native_public_sha256": _hash(public_path),
        "actual_public_release_download": True,
        "executed_bytes": "verified_and_extracted_exact_published_source_archive",
        "native_adversarial_regressions": "passed_as_separate_workflow_step",
        "independent_native_audit": "passed_as_separate_workflow_step",
        "registered_development_seed": 341014, "registered_confirmation_seed": 341015,
        "modeled_matched_profit_delta_microUSD": public["matched_confirmation_profit_delta_microUSD"],
        "modeled_connected_funded_successor": public["confirmed_positive_funded_successor_opportunity"],
        "actual_paid_commerce": False, "causal_new_invention_established": False,
        "original_signed_account_migration": "NOT_EXERCISED",
        "annual_profit_established": False, "whole_episode_real_billing": None,
        "scope": "SOURCE_MATCHED_RELEASED_BYTE_SYNTHETIC_ENGINEERING_REPRODUCTION_ONLY",
    }
    receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    public_copy.write_bytes(public_path.read_bytes())
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("extract", "seal"))
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--public", type=Path)
    p.add_argument("--receipt", type=Path)
    p.add_argument("--public-copy", type=Path)
    a = p.parse_args()
    if a.mode == "extract":
        extract(a.assets, a.source_commit, a.source)
    else:
        if not all((a.public, a.receipt, a.public_copy)):
            p.error("seal requires public, receipt and public-copy")
        seal(a.assets, a.source_commit, a.source, a.public, a.receipt, a.public_copy)


if __name__ == "__main__":
    main()
