#!/usr/bin/env python3
"""Reconstruct exact frozen public code; this never recreates account authority.

Only source files named by SOURCE.json are materialized. Historical uncommitted
development differences are retained in small byte-preserved override records.
Use this with an existing authenticated account only after all source hashes
match; a public financial export cannot reconstruct its missing private key.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--record", type=Path, required=True, help="Directory containing SOURCE.json")
    p.add_argument("--output", type=Path, required=True, help="Fresh source directory")
    p.add_argument("--base-commit", help="Explicit override; otherwise use the recorded public commit")
    args = p.parse_args()
    record = json.loads((args.record / "SOURCE.json").read_text())
    overrides_path = args.record / "SOURCE_OVERRIDES.json"
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {"files": {}}
    commit = args.base_commit or overrides.get("base_commit") or record.get("git_commit")
    if not commit:
        raise ValueError("RECORDED_PUBLIC_SOURCE_COMMIT_REQUIRED")
    if overrides.get("source_sha256", record["sha256"]) != record["sha256"]:
        raise ValueError("OVERRIDE_SOURCE_MISMATCH")
    canonical = json.dumps(record["files"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest() != record["sha256"]:
        raise ValueError("SOURCE_MANIFEST_DIGEST_MISMATCH")
    args.output.mkdir(parents=True, exist_ok=False)
    for rel, sha in record["files"].items():
        name = Path(rel)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError("RELATIVE_SOURCE_FILE_REQUIRED")
        if rel in overrides["files"]:
            raw = base64.b64decode(overrides["files"][rel], validate=True)
        else:
            raw = subprocess.run(["git", "show", commit + ":" + rel], cwd=args.repo,
                                 check=True, capture_output=True).stdout
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("EXACT_SOURCE_BYTES_REQUIRED:" + rel)
        target = args.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    print(json.dumps({"accepted": True, "source_sha256": record["sha256"],
                      "files": len(record["files"]), "private_account_authority_created": False}))


if __name__ == "__main__":
    main()
