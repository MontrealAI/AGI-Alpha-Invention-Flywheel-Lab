"""Source-bound inventory of the *original* EIT Jacobian and example scripts.

This is not a reconstruction, sensor calibration, buyer service or financial action.
All candidates are inventoried; none is selected post hoc for a favorable fit.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
from zipfile import ZipFile

from research.eit_physical_control183.control import (
    EXPECTED_SHA256, MEMBERS, Refusal, download_exact, parse_member, validate_zip,
)

MAX_FILE = 250_000_000
MAX_DATASET_CELLS = 20_000_000
MAX_CANDIDATES = 100
MAX_SCRIPTS = 200


def candidate_names(archive):
    """Fully deterministic exhaustive inventory from frozen path/extension rules."""
    validate_zip(archive)
    jacobians, scripts = [], []
    for info in archive.infolist():
        if info.is_dir():
            continue
        parts = info.filename.split("/")
        basename = parts[-1].casefold()
        if basename.startswith("j_") and basename.endswith(".mat"):
            jacobians.append(info.filename)
        if basename.endswith(".m") and any(p.casefold() == "examplecodes" for p in parts[:-1]):
            scripts.append(info.filename)
    if not jacobians or not scripts:
        raise Refusal("ORIGINAL_JACOBIAN_OR_EXAMPLE_SCRIPT_MISSING")
    if len(jacobians) > MAX_CANDIDATES or len(scripts) > MAX_SCRIPTS:
        raise Refusal("SOURCE_CANDIDATE_INVENTORY_TOO_LARGE")
    return sorted(jacobians), sorted(scripts)


def dataset_inventory(raw):
    """Inventory all numeric HDF5 arrays without guessing the original row mapping."""
    import h5py
    import numpy as np
    if len(raw) > MAX_FILE:
        raise Refusal("JACOBIAN_MEMBER_TOO_LARGE")
    try:
        h = h5py.File(io.BytesIO(raw), "r")
    except (ValueError, OSError) as exc:
        raise Refusal("ORIGINAL_JACOBIAN_NOT_HDF5") from exc
    datasets = []
    with h:
        def visit(group, prefix=""):
            # Do not resolve external or soft HDF5 links.
            for name in sorted(group.keys()):
                link = group.get(name, getlink=True)
                if not isinstance(link, h5py.HardLink):
                    raise Refusal("HDF5_NONLOCAL_LINK")
                obj = group[name]
                path = prefix + "/" + name
                if isinstance(obj, h5py.Group):
                    visit(obj, path)
                elif isinstance(obj, h5py.Dataset):
                    count = int(obj.size)
                    if count > MAX_DATASET_CELLS:
                        raise Refusal("JACOBIAN_DATASET_TOO_LARGE")
                    dtype = obj.dtype
                    if dtype.kind in "fiucb":
                        arr = np.asarray(obj[()])
                        if not np.isfinite(arr).all():
                            raise Refusal("NONFINITE_JACOBIAN_DATASET")
                        datasets.append({
                            "path": path,
                            "shape": list(obj.shape),
                            "dtype": str(dtype),
                            "cells": count,
                            "has_1264_measurement_dimension": 1264 in obj.shape,
                        })
                    else:
                        datasets.append({
                            "path": path,
                            "shape": list(obj.shape),
                            "dtype": str(dtype),
                            "cells": count,
                            "numeric_supported": False,
                        })
        visit(h)
    if not datasets:
        raise Refusal("ORIGINAL_JACOBIAN_HAS_NO_DATASETS")
    return datasets


def inspect_zip(archive):
    import numpy as np
    jacobians, scripts = candidate_names(archive)
    measurements = []
    for name, expected in MEMBERS.items():
        info = archive.getinfo(name)
        if info.file_size > MAX_FILE:
            raise Refusal("MEASUREMENT_MEMBER_TOO_LARGE")
        raw = archive.read(info)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise Refusal("ORIGINAL_MEASUREMENT_HASH_CHANGED")
        measurements.append(parse_member(raw))
    if not np.array_equal(measurements[0][0], measurements[1][0]):
        raise Refusal("ORIGINAL_EXCITATIONS_UNMATCHED")
    result = []
    for name in jacobians:
        info = archive.getinfo(name)
        if info.file_size > MAX_FILE:
            raise Refusal("JACOBIAN_MEMBER_TOO_LARGE")
        raw = archive.read(info)
        result.append({
            "member": name,
            "original_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "datasets": dataset_inventory(raw),
        })
    examples = []
    for name in scripts:
        info = archive.getinfo(name)
        if info.file_size > MAX_FILE:
            raise Refusal("EXAMPLE_SCRIPT_TOO_LARGE")
        raw = archive.read(info)
        examples.append({"member": name, "original_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return {
        "matched_original_currents": True,
        "original_measurement_member_sha256": dict(MEMBERS),
        "original_jacobian_candidate_count": len(result),
        "original_example_script_count": len(examples),
        "all_original_jacobian_candidates": result,
        "all_original_example_script_hashes": examples,
        "measurement_to_J_mapping_authenticated": False,
        "reconstruction_performed": False,
        "interior_property_identified": False,
        "beneficiary_accepted": False,
        "real_commercial_collections_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def run_archive(path):
    from research.eit_physical_control183.control import EXPECTED_SIZE, EXPECTED_MD5
    raw = path.read_bytes()
    if (len(raw) != EXPECTED_SIZE
            or hashlib.md5(raw).hexdigest() != EXPECTED_MD5
            or hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256):
        raise Refusal("FROZEN_ORIGINAL_SOURCE_HASH_MISMATCH")
    with ZipFile(io.BytesIO(raw)) as archive:
        return inspect_zip(archive)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    dest = Path(args.out)
    if dest.exists() or dest.is_symlink():
        raise Refusal("OUTPUT_ALREADY_EXISTS")
    with tempfile.TemporaryDirectory(prefix="eit185-original-") as tmp:
        archive = Path(tmp) / "original.zip"
        sha = download_exact(archive)
        if sha != EXPECTED_SHA256:
            raise Refusal("FROZEN_ORIGINAL_SOURCE_HASH_MISMATCH")
        result = run_archive(archive)
    receipt = {
        "schema": "eit185-original-jacobian-source-qualification-v1",
        "original_archive_sha256": sha,
        "registered_protocol": "campaign/eit-original-jacobian185/PREREGISTRATION.md",
        **result,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": receipt["decision"], "jacobian_files": result["original_jacobian_candidate_count"],
                      "original_scripts": result["original_example_script_count"], "receipt": str(dest)}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, ValueError, OSError) as exc:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "reason": str(exc)}, sort_keys=True))
        raise SystemExit(2)
