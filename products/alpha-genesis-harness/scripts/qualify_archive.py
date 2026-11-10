#!/usr/bin/env python3
"""Verify an externally identified HARNESS archive and operate its extracted bytes.

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Vincent Boucher
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import tempfile
import time
import zipfile

from package_release import MAX_ARCHIVE, verify_snapshot


def qualify(archive: Path, expected_sha256: str, expected_revision: str, output: Path) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("An externally supplied SHA-256 is required")
    if not re.fullmatch(r"[a-f0-9]{40}", expected_revision):
        raise ValueError("An exact externally supplied source revision is required")
    with archive.open('rb') as stream:
        data = stream.read(MAX_ARCHIVE)
        if len(data) >= MAX_ARCHIVE or stream.read(1):
            raise ValueError('Archive exceeds the processing envelope')
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Archive differs from the externally supplied SHA-256")
    integrity = verify_snapshot(data, expected_sha256=expected_sha256, expected_source_revision=expected_revision)
    if integrity["source_revision"] != expected_revision or not integrity.get("source_claim_matches_commit") or integrity.get("build_mode") != "source-bound":
        raise ValueError("Archive is not bound to the requested committed source")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "alpha-genesis-harness-downloaded-operation/v1", "verdict": "INVALID",
               "archive_sha256": expected_sha256, "source_revision": expected_revision,
               "operations": [], "scope": "Extracted-byte automated operation on this host; not cross-platform, authenticated-provider or commercial qualification.",
               "actual_inference_cost": "No provider requests", "actual_host_cost": "Unknown"}
    start = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="harness-clean-") as folder:
            # verify() rejects traversal, aliases, symlinks, oversize and unlisted members.
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                bundle.extractall(folder)
            roots = list(Path(folder).iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise ValueError("Expected one extracted product directory")
            product = roots[0]
            tests = sorted(str(p.relative_to(product)) for p in (product / "tests").glob("*.test.cjs"))
            if not tests:
                raise ValueError("Archive contains no executable engine acceptance suite")
            commands = [["node", "--test", *tests],
                        ["python3", "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_bridge.py", "-v"]]
            if not (product / "tests/test_bridge.py").is_file():
                raise ValueError("Archive contains no provider fixture regression suite")
            for index, command in enumerate(commands, 1):
                phase = time.monotonic()
                # Extracted tests never inherit GitHub tokens or caller credentials.
                environment = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
                process = subprocess.run(command, cwd=product, env=environment, capture_output=True, text=True)
                (output / f"operation-{index}.stdout.txt").write_text(process.stdout, encoding="utf-8")
                (output / f"operation-{index}.stderr.txt").write_text(process.stderr, encoding="utf-8")
                receipt["operations"].append({"command": command, "returncode": process.returncode,
                                              "wall_seconds": round(time.monotonic()-phase, 6)})
                if process.returncode:
                    raise ValueError(f"Extracted operation {index} failed; preserved logs identify the failure")
            receipt["verdict"] = "PASSED IN SCOPE"
    except BaseException as exc:
        receipt["error"] = str(exc)
        raise
    finally:
        receipt["wall_seconds"] = round(time.monotonic()-start, 6)
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt["child_cpu_seconds"] = round(usage.ru_utime + usage.ru_stime, 6)
        (output / "QUALIFICATION.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(qualify(args.archive, args.expected_sha256, args.expected_source_revision, args.output), indent=2))


if __name__ == "__main__":
    main()
