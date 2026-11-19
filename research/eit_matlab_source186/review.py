"""Original MATLAB source-line inventory: no execution, no property reconstruction."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile
from research.eit_physical_control183.control import (
    EXPECTED_SHA256, Refusal, download_exact, validate_zip,
)
from research.eit_jacobian185.original_source import candidate_names, run_archive

SAMPLE_BASENAME = "Example_CylinderPhantom_LinearDifferenceImaging.m"
SAMPLE_SHA = "48cac4535c4239b538a98b23e3088bc2bf3e4200291fb2946bf0156cb99209f9"
SAMPLE_BYTES = 1910
JACOBIAN_SHA = "9f8f10443fd3a19d72a1011d31321eb14b0767d5987e93d9601bf64f5e2c50f8"
PROBES = {
    "jacobian": ("j", "jacobian"),
    "voltage": ("voltage", "voltages", "voltages_matrix"),
    "current": ("current", "currents", "currents_matrix"),
    "difference": ("difference", "diff", "baseline", "reference"),
    "regularization": ("regularization", "tikhonov", "lambda", "alpha", "svd"),
    "reshape_or_order": ("reshape", "permute", "transpose", "vectorize"),
    "mesh": ("mesh", "nodes", "elements", "plotmesh"),
    "units": ("units", "units_info", "conversion", "scale"),
}

def source_line_index(raw: bytes, expected_sha: str, expected_size: int):
    if not isinstance(raw, bytes) or len(raw) > 4096 or len(raw) != expected_size:
        raise Refusal("SAMPLE_SIZE_CHANGED_OR_OVER_LIMIT")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise Refusal("SAMPLE_SHA256_CHANGED")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise Refusal("NONASCII_OR_UNDECODABLE_SAMPLE") from exc
    if not 1 <= len(lines) <= 200:
        raise Refusal("INVALID_SAMPLE_LINE_COUNT")
    entries = []
    for n, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("%"):
            continue
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", line)
        if not tokens:
            continue
        words = list(dict.fromkeys(x.lower() for x in tokens))
        indicators = sorted(label for label, probes in PROBES.items()
                            if any(p in word for word in words for p in probes))
        entries.append({
            "line": n,
            "line_sha256": hashlib.sha256(line.encode("ascii")).hexdigest(),
            "identifier_count": len(words),
            "first_identifiers": words[:12],
            "identifiers_truncated": len(words) > 12,
            "lexical_indicators_only": indicators,
        })
    if not entries:
        raise Refusal("NO_CODE_BEARING_LINES")
    return {
        "script_sha256": expected_sha,
        "script_size": len(raw),
        "physical_line_count": len(lines),
        "code_bearing_line_count": len(entries),
        "source_line_index": entries,
        "lexical_indicator_line_counts": {
            label: sum(label in e["lexical_indicators_only"] for e in entries)
            for label in PROBES
        },
        "original_matlab_not_executed": True,
        "semantic_measurement_row_mapping_authenticated": False,
        "property_reconstruction_performed": False,
        "sensor_repeatability_established": False,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }

def inspect_archive(path: Path):
    # Existing EIT185 source controls reverify original ZIP, both measured
    # members/currents and all source Jacobian candidates before source review.
    original = run_archive(path)
    jacobians = [x for x in original["all_original_jacobian_candidates"]
                 if x["member"].rsplit("/", 1)[-1] == "J_AgarCylinderPhantom.mat"]
    if len(jacobians) != 1 or jacobians[0]["sha256"] != JACOBIAN_SHA:
        raise Refusal("ORIGINAL_JACOBIAN_CHANGED")
    if not any(row["shape"] == [1264, 1197] for row in jacobians[0]["datasets"]):
        raise Refusal("ORIGINAL_JACOBIAN_SHAPE_CHANGED")
    with ZipFile(path) as archive:
        validate_zip(archive)
        _, scripts = candidate_names(archive)
        choices = [p for p in scripts if p.rsplit("/", 1)[-1] == SAMPLE_BASENAME]
        if len(choices) != 1:
            raise Refusal("SCRIPT_MISSING_OR_AMBIGUOUS")
        info = archive.getinfo(choices[0])
        if info.file_size != SAMPLE_BYTES:
            raise Refusal("SAMPLE_SIZE_CHANGED_OR_OVER_LIMIT")
        review = source_line_index(archive.read(info), SAMPLE_SHA, SAMPLE_BYTES)
    return {
        "schema": "agi-alpha/eit186-original-matlab-source-review/v1",
        "registered_protocol": "campaign/eit-matlab-source186/PREREGISTRATION.md",
        "original_archive_sha256": EXPECTED_SHA256,
        "original_jacobian_sha256": JACOBIAN_SHA,
        "jacobian_shape": [1264, 1197],
        "matched_original_currents": original["matched_original_currents"],
        "original_script_member": choices[0],
        **review,
        "unresolved_mapping": "Script syntax, source numerical row order, units and full MATLAB execution not independently authenticated",
        "beneficiary_accepted": False,
        "commercial_revenue_collected_usd": None,
        "native_financial_account_accessed": False,
        "actual_host_model_billing_usd": None,
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    destination = Path(parser.parse_args(argv).out)
    if destination.exists() or destination.is_symlink():
        raise Refusal("OUTPUT_MUST_BE_CREATE_ONLY")
    with tempfile.TemporaryDirectory(prefix="eit186-script-") as d:
        original_zip = Path(d) / "source.zip"
        if download_exact(original_zip) != EXPECTED_SHA256:
            raise Refusal("FROZEN_SOURCE_CHANGED")
        result = inspect_archive(original_zip)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({"decision": result["decision"], "script_sha256": result["script_sha256"],
                      "code_bearing_lines": result["code_bearing_line_count"],
                      "mapping_authenticated": False}, sort_keys=True))

if __name__ == "__main__":
    try:
        main()
    except (Refusal, ValueError, OSError) as error:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "reason": str(error)}))
        raise SystemExit(2)
