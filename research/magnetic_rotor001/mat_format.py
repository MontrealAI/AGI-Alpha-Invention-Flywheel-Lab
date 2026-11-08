"""Bounded header-only forensic classification; never upgrades failed schema002."""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from scipy.io import whosmat
import scipy

from research.magnetic_rotor001 import gate, schema

HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
SCHEMA = "agi-alpha/magnetic-mat-format-diagnostic003/v1"


def classify_error(e: Exception) -> str:
    name = type(e).__name__
    if name not in ("ValueError", "TypeError", "IndexError", "OSError",
                    "NotImplementedError", "MatReadError", "MatReadWarning",
                    "UnknownMatFileType", "OverflowError"):
        return "UNCLASSIFIED_READER_EXCEPTION"
    return name


def diagnostic(data: bytes, *, require_original: bool = True) -> dict:
    base = gate.inspect_source(data, require_published_md5=require_original)
    if require_original and base["source_sha256_measured"] != schema.EXPECTED_ZIP_SHA256:
        raise schema.SchemaError("PINNED_ARCHIVE_SHA256_MISMATCH")
    if base["file_count"] != len(schema.EXPECTED_MEMBERS):
        raise schema.SchemaError("EXPECTED_MEMBER_COUNT_CHANGED")
    if sorted(v["name"] for v in base["member_metadata_displayed"]) != list(schema.EXPECTED_MEMBERS):
        raise schema.SchemaError("EXPECTED_MEMBER_NAMES_CHANGED")
    records = []
    with ZipFile(BytesIO(data)) as zf:
        for name in schema.EXPECTED_MEMBERS:
            raw = zf.read(name)
            info = {
                "name": name,
                "member_size": len(raw),
                "member_sha256": sha256(raw).hexdigest(),
                "first_eight_bytes_hex": raw[:8].hex(),
                "mat_header_124_127_hex_if_present": raw[124:128].hex() if len(raw) >= 128 else None,
                "hdf5_signature_at_offset0": raw[:8] == HDF5_MAGIC,
                "hdf5_signature_at_offset512": raw[512:520] == HDF5_MAGIC,
                "reader_result": "UNKNOWN",
                "reader_error_type": None,
                "reader_top_level_count": None,
            }
            try:
                fields = whosmat(BytesIO(raw))
                info["reader_result"] = "METADATA_SUCCESS"
                info["reader_top_level_count"] = len(fields)
            except Exception as e:
                # Classification-only; source schema002's strict reject behavior is unchanged.
                info["reader_result"] = "METADATA_ERROR"
                info["reader_error_type"] = classify_error(e)
            records.append(info)
    errors = sum(m["reader_result"] == "METADATA_ERROR" for m in records)
    return {
        "schema": SCHEMA,
        "status": "MAT_FORMAT_DIAGNOSTIC_COMPLETE_SCHEMA002_STILL_FAILED",
        "member_count": len(records),
        "reader_error_count": errors,
        "source_archive_sha256": base["source_sha256_measured"],
        "source_metadata_md5": base["source_md5_metadata"],
        "scipy_version": scipy.__version__,
        "records": records,
        "original_schema002_failure_preserved": True,
        "numeric_arrays_materialized": False,
        "physical_force_interpreted": False,
        "commercial_rights": "UNVERIFIED",
        "deployment": "NO_DEPLOY"
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    o = p.parse_args()
    try:
        result = diagnostic(gate.download_once())
    except (gate.SourceGateError, schema.SchemaError, OSError, ValueError, TimeoutError) as e:
        result = {
            "schema": SCHEMA,
            "status": "MAT_FORMAT_DIAGNOSTIC_FAILED",
            "error_type": type(e).__name__,
            "reason": str(e)[:120],
            "original_schema002_failure_preserved": True,
            "deployment": "NO_DEPLOY",
        }
    o.output.mkdir(parents=True, exist_ok=True)
    dest = o.output / "MAT_FORMAT_DIAGNOSTIC.json"
    dest.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "reader_errors": result.get("reader_error_count"),
        "members": result.get("member_count"),
        "result": str(dest),
    }, sort_keys=True))
    return int(result["status"] != "MAT_FORMAT_DIAGNOSTIC_COMPLETE_SCHEMA002_STILL_FAILED")


if __name__ == "__main__":
    raise SystemExit(main())
