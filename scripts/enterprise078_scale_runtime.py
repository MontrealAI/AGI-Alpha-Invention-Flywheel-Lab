"""Compose frozen scale science without replacing the current native runtime.

This is source materialization only. It does not open, migrate, reseed or copy
an account, change either experiment, or reclassify a historical failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from enterprise078.runtime import EXPECTED_FREEZE, digest, materialize as materialize_science

SCALE_FREEZE = "50748c34a6ee2b528b78745eb947e191798906b91f1f9abbe26647622cae9dbc"
SUPPORT_HASHES = {
    "enterprise078_scale/FROZEN.json": "0d11013af5cf60afe102cab366a305603f3ad8446bad1f28a68c9fa441467c68",
    "enterprise078_scale/README.md": "3c069a22e12e73bf7a3a7a2a127905b1c58e79113cce580d3a84e46d7e79a875",
    "enterprise078_scale/REGISTRATION.md": "feca3d519e413738340bc49a440baf7f59851bdb0880c44df89bc4c864dc0eef",
}


def regular_bytes(path: Path) -> bytes:
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("REGULAR_SCALE_SOURCE_REQUIRED")
    return path.read_bytes()


def scale_payload(root: Path) -> dict[str, bytes]:
    declaration = regular_bytes(root / "enterprise078_scale/FROZEN.json")
    frozen = json.loads(declaration)
    if frozen.get("sha256") != SCALE_FREEZE or digest(frozen.get("files")) != SCALE_FREEZE:
        raise ValueError("ORIGINAL_SCALE_FREEZE_REQUIRED")
    hashes = {**frozen["files"], **SUPPORT_HASHES}
    payload = {}
    for name, expected in hashes.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "enterprise078_scale":
            raise ValueError("RELATIVE_SCALE_SOURCE_REQUIRED")
        raw = regular_bytes(root / relative)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("FROZEN_SCALE_BYTES_CHANGED:" + name)
        payload[name] = raw
    return payload


def materialize(root: Path, destination: Path) -> dict:
    if any(".." in Path(path).parts for path in (root, destination)):
        raise ValueError("UNALIASED_COMPOSITION_PATH_REQUIRED")
    root, destination = Path(root).absolute(), Path(destination).absolute()
    if any(p.is_symlink() for p in (root, *root.parents, destination, *destination.parents)):
        raise ValueError("UNALIASED_COMPOSITION_PATH_REQUIRED")
    if destination.exists():
        raise ValueError("NEW_SCALE_RUNTIME_REQUIRED")
    if root == destination or root in destination.parents:
        raise ValueError("SCALE_RUNTIME_MUST_BE_OUTSIDE_CHECKOUT")
    payload = scale_payload(root)
    # Validate and write both closures privately; failed materialization leaves
    # no runnable destination, and never changes the checkout or its accounts.
    with tempfile.TemporaryDirectory(prefix=".e078-composition-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "source"
        materialize_science(root, stage)
        for name, raw in payload.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        if destination.exists() or destination.is_symlink():
            raise ValueError("NEW_SCALE_RUNTIME_REQUIRED")
        os.rename(stage, destination)
    return {
        "schema": "enterprise078-scale/isolated-composition/v1",
        "scientific_freeze_sha256": EXPECTED_FREEZE,
        "scale_freeze_sha256": SCALE_FREEZE,
        "scientific_files": 306,
        "scale_files": len(payload),
        "account_state_read_or_copied": False,
        "historical_failures_reclassified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(ROOT, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
