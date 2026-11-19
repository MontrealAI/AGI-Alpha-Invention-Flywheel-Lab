"""EIT189 stage-one source witness for the authors' complete conventional estimator.

Read exact public bytes, never execute the MATLAB original. This intentionally
does *not* claim a faithful reconstruction until every source expression,
mesh dataset, and measurement-index mapping is independently supported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

from research.eit_physical_control183.control import (
    EXPECTED_SHA256, MEMBERS, Refusal, download_exact, validate_zip,
)
from research.eit_jacobian185.original_source import (
    candidate_names, run_archive,
)
from research.eit_matlab_source186.review import (
    SAMPLE_BASENAME, SAMPLE_SHA, SAMPLE_BYTES, JACOBIAN_SHA, source_line_index,
)

MAX_SCRIPT_LINES = 200
MAX_MESH_CANDIDATES = 30


def source_expression_witness(raw: bytes):
    """Return a deterministic verified code-line index, without evaluating code."""
    index = source_line_index(raw, SAMPLE_SHA, SAMPLE_BYTES)
    lines = raw.decode("ascii").splitlines()
    if (len(lines) != 65 or index["code_bearing_line_count"] != 29 or
            len(lines) > MAX_SCRIPT_LINES):
        raise Refusal("EIT189_ORIGINAL_SCRIPT_LINE_BOUND_CHANGED")
    if len(index["source_line_index"]) != 29:
        raise Refusal("EIT189_ORIGINAL_CODE_LINE_COUNT_CHANGED")
    # Deterministic content-bearing witnesses; only input read, never exec/eval.
    witnesses = []
    for item in index["source_line_index"]:
        line_no = item["line"]
        source = lines[line_no - 1]
        if hashlib.sha256(source.encode("ascii")).hexdigest() != item["line_sha256"]:
            raise Refusal("EIT189_SOURCE_INDEX_INCONSISTENT")
        witnesses.append({
            "line": line_no,
            "sha256": item["line_sha256"],
            "indicators": item["lexical_indicators_only"],
            "source": source,
        })
    # Original authors encode covariance regularization through Gamma, IGe,
    # and IGs, rather than necessarily naming a scalar ridge lambda. The
    # actual source estimator line, already SHA-verified in EIT187, is the
    # correct semantic gate; no guessed penalty is substituted.
    expected_estimator = (
        "f232324c3110215a0e27062c584088bcfb631cf8da802eef33945d58fff19a52"
    )
    if hashlib.sha256(lines[57].encode("ascii")).hexdigest() != expected_estimator:
        raise Refusal("EIT189_ORIGINAL_COVARIANCE_ESTIMATOR_CHANGED")
    return witnesses


def inspect_original(archive_path: Path):
    original = run_archive(archive_path)  # Full immutable zip/member/J inventory.
    if not original["matched_original_currents"]:
        raise Refusal("EIT189_ORIGINAL_CURRENTS_UNMATCHED")
    jacobians = [
        x for x in original["all_original_jacobian_candidates"]
        if x["member"].rsplit("/", 1)[-1] == "J_AgarCylinderPhantom.mat"
    ]
    if (len(jacobians) != 1 or jacobians[0]["sha256"] != JACOBIAN_SHA or
            not any(d.get("shape") == [1264, 1197] for d in jacobians[0]["datasets"])):
        raise Refusal("EIT189_ORIGINAL_J_MISSING_CHANGED_OR_AMBIGUOUS")

    with ZipFile(archive_path) as z:
        validate_zip(z)
        _, scripts = candidate_names(z)
        hits = [name for name in scripts
                if name.rsplit("/", 1)[-1] == SAMPLE_BASENAME]
        if len(hits) != 1:
            raise Refusal("EIT189_EXACT_AUTHOR_SCRIPT_MISSING_OR_AMBIGUOUS")
        entry = z.getinfo(hits[0])
        if entry.file_size != SAMPLE_BYTES:
            raise Refusal("EIT189_AUTHOR_SCRIPT_LENGTH_CHANGED")
        raw = z.read(entry)
        witnesses = source_expression_witness(raw)
        meshes = sorted([
            {"name": i.filename, "bytes": i.file_size,
             "member_sha256": hashlib.sha256(z.read(i)).hexdigest()}
            for i in z.infolist()
            if not i.is_dir()
            and i.filename.rsplit("/", 1)[-1].lower().startswith("mesh_")
            and i.filename.lower().endswith(".mat")
        ], key=lambda x: x["name"])
        if len(meshes) > MAX_MESH_CANDIDATES:
            raise Refusal("EIT189_EXCESS_MESH_CANDIDATES")
        if not meshes:
            raise Refusal("EIT189_ORIGINAL_MESH_ABSENT")
    if not any("mesh" in x["indicators"] for x in witnesses):
        raise Refusal("EIT189_NO_MESH_REFERENCE_IN_AUTHOR_SCRIPT")
    return {
        "schema": "agi-alpha/eit189-frozen-original-source-semantics/v1",
        "protocol": "campaign/eit-original-authors189/PREREGISTRATION.md",
        "archive_sha256": EXPECTED_SHA256,
        "jacobian_sha256": JACOBIAN_SHA,
        "original_matlab_sha256": SAMPLE_SHA,
        "measured_member_sha256": dict(MEMBERS),
        "measurement_count": 1264,
        "original_jacobian_shape": [1264, 1197],
        "code_bearing_lines": witnesses,
        "all_mesh_candidates": meshes,
        "source_to_hdf5_row_order_authenticated": False,
        "full_author_inverse_reconstructed": False,
        "property_truth_known": False,
        "physical_repeatability_calibrated": False,
        "commercial_payments_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def write_fresh(path: Path, witness: dict):
    """A create-only receipt; never overwrite a previous failed/source record."""
    if path.exists() or path.is_symlink():
        raise Refusal("EIT189_OUTPUT_MUST_BE_FRESH")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8") as f:
        json.dump(witness, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    dest = Path(parser.parse_args(argv).out)
    if dest.exists() or dest.is_symlink():
        raise Refusal("EIT189_OUTPUT_MUST_BE_FRESH")
    with tempfile.TemporaryDirectory(prefix="eit189-original-public-") as d:
        archive = Path(d) / "source.zip"
        if download_exact(archive) != EXPECTED_SHA256:
            raise Refusal("EIT189_ORIGINAL_ZIP_CHANGED")
        report = inspect_original(archive)
    write_fresh(dest, report)
    print(json.dumps({
        "source_verified": True,
        "source_SHA256": report["original_matlab_sha256"],
        "code_line_count": len(report["code_bearing_lines"]),
        "mesh_file_count": len(report["all_mesh_candidates"]),
        "full_inverse_performed": False,
        "decision": report["decision"],
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, TypeError, ValueError) as error:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY",
                          "reason": str(error)}, sort_keys=True))
        raise SystemExit(2)
