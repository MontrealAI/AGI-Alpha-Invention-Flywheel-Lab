"""Frozen structure-only inspection of ten independently source-bound public MATLAB files."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import numpy
import scipy
from scipy.io import whosmat
from scipy.io.matlab import MatReadError

from research.magnetic_rotor001 import gate

EXPECTED_ZIP_SHA256 = "a5a536b9f279604a3aee1a9caaec134b8586d8b5972cbd9733f465cdbb3d3bc8"
HEIGHT_LABELS = ("0.5", "1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "5.0", "6.0")
PREFIX = "Experiments_force_sensor/data_incre_00_height_"
EXPECTED_MEMBERS = tuple(sorted(f"{PREFIX}{h}.mat" for h in HEIGHT_LABELS))
SCHEMA = "agi-alpha/magnetic-rotor-mat-schema002/v1"


class SchemaError(gate.SourceGateError):
    pass


def inspect_mat_schema(data: bytes, *, require_original: bool = True) -> dict:
    source_report = gate.inspect_source(data, require_published_md5=require_original)
    if require_original and source_report["source_sha256_measured"] != EXPECTED_ZIP_SHA256:
        raise SchemaError("PINNED_ARCHIVE_SHA256_MISMATCH")
    member_names = tuple(sorted(m["name"] for m in source_report["member_metadata_displayed"]))
    if source_report["file_count"] != len(EXPECTED_MEMBERS) or member_names != EXPECTED_MEMBERS:
        raise SchemaError("TEN_FROZEN_HEIGHT_MEMBERS_REQUIRED")
    observations = []
    common = None
    try:
        with ZipFile(BytesIO(data), "r") as zf:
            for name in EXPECTED_MEMBERS:
                # whosmat inspects MATLAB directory metadata, not numeric array values.
                fields = whosmat(BytesIO(zf.read(name)))
                if not fields:
                    raise SchemaError("MAT_NO_VARIABLE_METADATA")
                found = set()
                public_fields = []
                for var, dimensions, kind in fields:
                    if not isinstance(var, str) or not var or var in found:
                        raise SchemaError("MAT_VARIABLE_NAMES_INVALID_OR_DUPLICATED")
                    found.add(var)
                    if not isinstance(kind, str) or not kind:
                        raise SchemaError("MAT_CLASS_MISSING")
                    if not dimensions or any(
                        not isinstance(d, int) or d < 0 or d > 10_000_000
                        for d in dimensions
                    ):
                        raise SchemaError("MAT_DIMENSIONS_REJECTED")
                    public_fields.append({
                        "name": var,
                        "shape": list(dimensions),
                        "matlab_class": kind,
                    })
                common = found if common is None else common.intersection(found)
                label = name.removeprefix(PREFIX).removesuffix(".mat")
                observations.append({
                    "member": name,
                    "height_label_unverified_units": label,
                    "top_level_variables": public_fields,
                })
    except (MatReadError, ValueError, TypeError, IndexError, OSError, NotImplementedError) as exc:
        if isinstance(exc, SchemaError):
            raise
        raise SchemaError("MAT_DIRECTORY_PARSE_FAILED") from exc
    if not common:
        raise SchemaError("NO_SHARED_VARIABLE_ACROSS_TEN_HEIGHTS")
    return {
        "schema": SCHEMA,
        "status": "SCHEMA_GATE_PASS_PHYSICAL_MEASUREMENT_HOLD",
        "source_record": source_report["source_record"],
        "source_archive_sha256": source_report["source_sha256_measured"],
        "source_archive_md5": source_report["source_md5_metadata"],
        "expected_member_count": 10,
        "observed_member_count": len(observations),
        "reported_mat_schemas": observations,
        "common_top_level_variable_names": sorted(common),
        "python_version": sys.version.split()[0],
        "numpy_version": numpy.__version__,
        "scipy_version": scipy.__version__,
        "numeric_arrays_materialized": False,
        "physical_force_values_interpreted": False,
        "height_units_known": False,
        "independent_physical_replicates_qualified": False,
        "physical_hold_slide_accepted": False,
        "commercial_rights": "UNVERIFIED",
        "actual_paid_customers": 0,
        "native_account_opened": False,
        "deployment": "NO_DEPLOY",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    opt = p.parse_args()
    try:
        result = inspect_mat_schema(gate.download_once())
    except (SchemaError, gate.SourceGateError, OSError, TimeoutError, ValueError) as e:
        result = {
            "schema": SCHEMA, "status": "SCHEMA_GATE_FAILED",
            "failure_type": type(e).__name__,
            "reason": str(e)[:160],
            "physical_hold_slide_accepted": False,
            "deployment": "NO_DEPLOY",
        }
    opt.output.mkdir(parents=True, exist_ok=True)
    target = opt.output / "SCHEMA_RESULT.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    print(json.dumps({
        "result": str(target), "status": result["status"],
        "variables_shared": result.get("common_top_level_variable_names"),
        "reason": result.get("reason"),
    }, sort_keys=True))
    return int(result["status"] != "SCHEMA_GATE_PASS_PHYSICAL_MEASUREMENT_HOLD")


if __name__ == "__main__":
    raise SystemExit(main())
