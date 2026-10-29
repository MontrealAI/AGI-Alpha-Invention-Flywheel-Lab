"""Materialize the exact frozen cycle-001 closure beside newer experiments."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = "c487e4741aa9d6f1a0928bc73d399d8a247b62e4"
MANIFEST = "campaign/cycle-001/CLOSURE.json"
EDITION = "campaign/cycle-001/EDITION_SHA256.json"
PINS = {MANIFEST: "a06a4f7630184b54205173e1f271e6af7ae5396687fd64deb575ae4de13b3252",
        EDITION: "e968d63bd2c4b22d635216f8d2df5b80a92db253cdfe3982c5cbbaf5b639f920",
        "reproduce.py": "1e812332d6b8ed91d38970ae07fffde0cca0047730a1a8e3d5c9665f7de254e3",
        "research/pglib_opf_case14_ieee.m": "bd5c568621de65e4b0922317010868bc7fa94173807faa10ea8fdbbe77c28106",
        "research/pglib_opf_case30_ieee.m": "cae3290639d989731d32428aacf30c0b918bc91db73bc54791f3aa62d3f76c70"}


def _safe(root, name):
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("LEGACY_PATH_SCOPE")
    path = root / relative
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root.parent):
        raise ValueError("LEGACY_SYMLINK_REFUSED " + name)
    return path


def _read(root, name, expected):
    path = _safe(root, name)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() == expected:
        return raw, "current-tree"
    if name == ".github/workflows/campaign.yml":
        found = subprocess.run(["git", "-C", str(root), "show", BASE + ":" + name],
                               capture_output=True, timeout=10, check=False)
        if found.returncode == 0 and hashlib.sha256(found.stdout).hexdigest() == expected:
            return found.stdout, "frozen-git-object/" + BASE
    raise ValueError("LEGACY_IDENTITY_MISMATCH " + name)


def materialize(root: Path, destination: Path):
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    raw_closure, _ = _read(root, MANIFEST, PINS[MANIFEST])
    raw_edition, _ = _read(root, EDITION, PINS[EDITION])
    closure, edition = json.loads(raw_closure), json.loads(raw_edition)
    expected = dict(edition)
    for name, value in {**closure, **PINS}.items():
        if name in expected and expected[name] != value:
            raise ValueError("LEGACY_MANIFEST_DISAGREEMENT " + name)
        expected[name] = value
    allowed_python = {name for name in closure if name.endswith(".py")} | {"reproduce.py"}
    if {name for name in expected if name.endswith(".py")} != allowed_python:
        raise ValueError("LEGACY_EXECUTABLE_SET_MISMATCH")
    pending, provenance = {}, {}
    for name, expected_hash in sorted(expected.items()):
        raw, origin = _read(root, name, expected_hash)
        pending[name] = raw
        provenance[name] = {"sha256": expected_hash, "origin": origin}
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in pending.items():
        target = _safe(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    receipt = {"schema": "lab/frozen-legacy-snapshot/v1", "baseline_commit": BASE,
               "closure_sha256": PINS[MANIFEST], "edition_sha256": PINS[EDITION],
               "files": provenance, "python_source_set": sorted(allowed_python),
               "scope": "Exact frozen legacy source and edition evidence; no new experiment source copied",
               "legacy_interruption_marker_defect": "PRESERVED_NOT_REPAIRED"}
    with (destination / "LEGACY_SNAPSHOT.json").open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = materialize(args.root, args.output)
    print(json.dumps({"files": len(result["files"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
