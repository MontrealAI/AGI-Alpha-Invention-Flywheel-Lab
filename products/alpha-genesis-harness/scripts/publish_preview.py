#!/usr/bin/env python3
"""Publish the allowlisted public browser assets; never bridge config or user data.

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Vincent Boucher
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ASSETS = ("index.html", "app.js", "engine.js", "styles.css", "workshop.js")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision):
        raise ValueError("Exact source revision required")
    repository = Path(__file__).resolve().parents[3]
    payload = {}
    for name in ASSETS:
        source_path = "products/alpha-genesis-harness/app/" + name
        mode = subprocess.check_output(["git", "-C", str(repository), "ls-tree", args.source_revision, "--", source_path], text=True)
        if not mode.startswith(("100644 blob ", "100755 blob ")):
            raise ValueError("Ordinary committed app file required: " + name)
        payload[name] = subprocess.check_output(["git", "-C", str(repository), "cat-file", "blob", args.source_revision + ":" + source_path])
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": "alpha-genesis-harness-public-preview/v1", "source_revision": args.source_revision,
                "status": "release-candidate", "files": {}}
    for name, data in payload.items():
        (args.output / name).write_bytes(data)
        manifest["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (args.output / "preview-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
