#!/usr/bin/env python3
"""Verify or reconstruct the preserved classical raw tree from extracted evidence.

First verify/extract the distribution with evidence.py. In that distribution,
classical/ holds the canonical projection and classical-residuals/ holds every
residual plus PROJECTION.json. The map's original workspace directory names are
historical metadata, never filesystem instructions. This utility checks relative
paths, the complete file partition and every byte identity; it does not rescore
predictions, authenticate an independently altered distribution, explain the
residuals, or prove that all execution costs were recorded.

Reconstruction requires a new directory outside the extracted evidence. It
restores relative file names and bytes, not historical inodes or timestamps.
Residuals remain present: reconstruction does not repair the raw tree's strict
inventory rejection. A failed reconstruction is retained for inspection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def name_check(name):
    require(isinstance(name, str) and name and "\\" not in name
            and ":" not in name and all(ord(c) >= 32 for c in name),
            "Invalid relative file name")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts
            and path.as_posix() == name and name != ".",
            "Unsafe relative file name: " + name)
    return name


def no_symlinks(path):
    """Check ancestors too; resolving a path first would hide a symlink."""
    path = Path(path).expanduser().absolute()
    for parent in reversed((path, *path.parents)):
        try:
            mode = parent.lstat().st_mode
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(mode), "Symlink is not permitted: " + str(parent))
    return path


def read_regular(path):
    path = no_symlinks(path)
    require(stat.S_ISREG(path.lstat().st_mode), "Nonregular input: " + str(path))
    # O_NOFOLLOW also rejects a final-component replacement between checks.
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
        return stream.read()


def content_identity(contents):
    return {"bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}


def identity(row):
    require(isinstance(row, dict) and type(row.get("bytes")) is int and row["bytes"] >= 0
            and isinstance(row.get("sha256"), str) and len(row["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in row["sha256"]),
            "Invalid file identity")
    return {"bytes": row["bytes"], "sha256": row["sha256"]}


def file_paths(names):
    names = list(names)
    require(len(names) == len(set(names)), "Duplicate mapped path")
    paths = set(map(name_check, names))
    for name in paths:
        require(not any(p.as_posix() in paths for p in PurePosixPath(name).parents),
                "File/directory path collision: " + name)
    return paths


def inventory(directory):
    directory = no_symlinks(directory)
    require(directory.is_dir(), "Missing evidence directory: " + str(directory))
    result = {}
    for path in sorted(directory.rglob("*")):
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), "Symlink is not permitted: " + str(path))
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "Nonregular evidence: " + str(path))
        if stat.S_ISREG(mode):
            name = name_check(path.relative_to(directory).as_posix())
            result[name] = content_identity(read_regular(path))
    return result


def tree_hash(rows):
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify(evidence, reconstruct=None):
    evidence = no_symlinks(evidence)
    projected, residuals = evidence / "classical", evidence / "classical-residuals"
    map_path = residuals / "PROJECTION.json"
    map_bytes = read_regular(map_path)
    mapping = json.loads(map_bytes, object_pairs_hook=unique_object)
    require(mapping["schema"] == "learning-to-build/observed-evidence-projection/v1"
            and mapping["status"] == "COMPLETE_BYTE_PRESERVING_PROJECTION",
            "Unsupported projection map")
    require(mapping["numerical_edits"] is False and mapping["cost_exclusions"] is False
            and mapping["source_bytes_unchanged_during_projection"] is True,
            "Map does not declare a byte-preserving projection")
    observed = {name_check(name): identity(row)
                for name, row in mapping["observed_raw_files"].items()}
    after = {name_check(name): identity(row)
             for name, row in mapping["post_copy_raw_files"].items()}
    require(observed == after, "Observed pre/post raw content identities differ")
    file_paths(observed)
    included, excluded = mapping["inclusion_mapping"], mapping["residual_mapping"]
    require(isinstance(included, list) and isinstance(excluded, list), "Mapping must contain lists")
    raw_paths = file_paths(row["raw_path"] for row in included + excluded)
    canonical_paths = file_paths(row["projected_path"] for row in included)
    residual_paths = file_paths(row["preserved_path"] for row in excluded)
    require(raw_paths == set(observed), "Mapping is not a complete raw-path partition")
    require("PROJECTION.json" not in residual_paths, "Residual mapping collides with its map")
    for key, count in (("raw_file_count", len(raw_paths)),
                       ("projected_file_count", len(canonical_paths)),
                       ("residual_file_count", len(residual_paths))):
        require(type(mapping[key]) is int and mapping[key] == count, "File count differs: " + key)
    canonical_files, residual_files = inventory(projected), inventory(residuals)
    require(set(canonical_files) == canonical_paths, "Canonical file inventory differs from map")
    require(set(residual_files) == residual_paths | {"PROJECTION.json"},
            "Residual file inventory differs from map")
    require(residual_files["PROJECTION.json"] == content_identity(map_bytes),
            "Projection map changed during verification")
    sources = {}
    for row in included:
        raw, name = row["raw_path"], row["projected_path"]
        require(identity(row) == observed[raw] == canonical_files[name],
                "Canonical byte identity differs: " + raw)
        sources[raw] = projected / name
    for row in excluded:
        raw, name = row["raw_path"], row["preserved_path"]
        counterpart = name_check(row["canonical_counterpart"])
        require(counterpart in canonical_files, "Missing canonical counterpart: " + counterpart)
        require(identity(row) == observed[raw] == residual_files[name] == canonical_files[counterpart],
                "Residual/counterpart byte identity differs: " + raw)
        sources[raw] = residuals / name
    require(tree_hash(observed) == mapping["raw_content_tree_sha256"], "Raw content tree digest differs")
    require(tree_hash(canonical_files) == mapping["projection_content_tree_sha256"],
            "Canonical content tree digest differs")

    destination = None
    if reconstruct is not None:
        destination = no_symlinks(reconstruct)
        require(not destination.exists(), "Reconstruction requires a new destination")
        require(not destination.resolve().is_relative_to(evidence.resolve()),
                "Reconstruction destination must be outside extracted evidence")
        destination.mkdir(parents=True, exist_ok=False)
        for name in sorted(sources):
            contents = read_regular(sources[name])
            require(content_identity(contents) == observed[name], "Source changed before copying: " + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            no_symlinks(target)
            with target.open("xb") as stream:
                stream.write(contents)
        require(inventory(destination) == observed, "Reconstructed raw tree differs")
    require(inventory(projected) == canonical_files and inventory(residuals) == residual_files,
            "Source inventory or bytes changed during verification/reconstruction")
    return {
        "schema": "learning-to-build/projection-verification/v1", "status": "VERIFIED",
        "mapping_sha256": content_identity(map_bytes)["sha256"],
        "raw_files": len(raw_paths), "canonical_files": len(canonical_paths),
        "retained_residual_files": len(residual_paths),
        "raw_content_tree_sha256": tree_hash(observed),
        "canonical_content_tree_sha256": tree_hash(canonical_files),
        "source_entry_and_exit_content_identical": True,
        "reconstructed_to": str(destination) if destination is not None else None,
        "reconstructed_bytes": sum(row["bytes"] for row in observed.values()) if destination is not None else 0,
        "scope": "Complete relative-file partition and byte identities only; historical filesystem metadata is not recreated.",
        "scientific_acceptance_checked": False, "raw_strict_inventory_acceptance_checked": False,
        "residual_origin": "UNKNOWN; equal bytes do not establish how the residuals were produced.",
        "cost_completeness_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path, help="Verified extracted evidence directory")
    parser.add_argument("--reconstruct", type=Path, help="New raw-tree directory outside the extracted evidence")
    args = parser.parse_args()
    started, cpu = time.perf_counter(), time.process_time()
    try:
        result = verify(args.evidence, args.reconstruct)
        exit_code = 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        result = {"schema": "learning-to-build/projection-verification/v1", "status": "REJECTED",
                  "error": type(error).__name__ + ": " + str(error),
                  "scientific_acceptance_checked": False, "cost_completeness_verified": False}
        exit_code = 1
    result.update(verifier_source_sha256=content_identity(Path(__file__).read_bytes())["sha256"],
                  actual_cpu_seconds=time.process_time() - cpu,
                  actual_wall_seconds=time.perf_counter() - started)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
