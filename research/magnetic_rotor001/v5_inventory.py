"""Independent, bounded MATLAB v5 directory inventory. No numerical arrays are decoded."""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct
from zipfile import ZipFile
import zlib

from research.magnetic_rotor001 import gate, schema

REPORT_SCHEMA = "agi-alpha/magnetic-mat-independent-directory004/v1"
MAX_MEMBER = 8 * 1024 * 1024
MAX_INFLATED = 16 * 1024 * 1024
MAX_VARIABLES = 256
MAX_DEPTH = 2
MAX_NAME_BYTES = 128
MI_MATRIX = 14
MI_COMPRESSED = 15


class DirectoryError(gate.SourceGateError):
    pass


def _tag(blob: bytes, offset: int, endian: str) -> tuple[int, bytes, int]:
    if offset < 0 or offset + 8 > len(blob):
        raise DirectoryError("MAT_TRUNCATED_ELEMENT_TAG")
    word = struct.unpack_from(endian + "I", blob, offset)[0]
    small_size = word >> 16
    if small_size:
        if small_size > 4:
            raise DirectoryError("MAT_SMALL_TAG_SIZE_INVALID")
        return word & 0xffff, blob[offset + 4:offset + 4 + small_size], offset + 8
    data_type = word
    length = struct.unpack_from(endian + "I", blob, offset + 4)[0]
    padded = (length + 7) // 8 * 8
    end = offset + 8 + padded
    if end > len(blob):
        raise DirectoryError("MAT_ELEMENT_LENGTH_OUT_OF_BOUNDS")
    return data_type, blob[offset + 8:offset + 8 + length], end


def _matrix_metadata(data: bytes, endian: str) -> dict:
    offset = 0
    kind, flags, offset = _tag(data, offset, endian)
    if kind != 6 or len(flags) < 8:
        raise DirectoryError("MAT_ARRAY_FLAGS_INVALID")
    matrix_class_code = struct.unpack_from(endian + "I", flags, 0)[0] & 255
    if matrix_class_code < 1 or matrix_class_code > 17:
        raise DirectoryError("MAT_MATRIX_CLASS_UNRECOGNIZED")
    kind, raw_dims, offset = _tag(data, offset, endian)
    if kind != 5 or not raw_dims or len(raw_dims) % 4 or len(raw_dims) > 128:
        raise DirectoryError("MAT_DIMENSIONS_INVALID")
    dims = [x[0] for x in struct.iter_unpack(endian + "i", raw_dims)]
    if len(dims) < 2 or any(d < 0 or d > 10_000_000 for d in dims):
        raise DirectoryError("MAT_DIMENSIONS_OUT_OF_RANGE")
    kind, raw_name, offset = _tag(data, offset, endian)
    if kind not in (1, 2, 16) or not raw_name or len(raw_name) > MAX_NAME_BYTES:
        raise DirectoryError("MAT_VARIABLE_NAME_INVALID")
    try:
        name = raw_name.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DirectoryError("MAT_VARIABLE_NAME_NOT_UTF8") from exc
    if not name or any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise DirectoryError("MAT_VARIABLE_NAME_CONTROL")
    # The numeric payload beginning at offset is intentionally NOT inspected.
    return {"name": name, "shape": dims, "matrix_class_code": matrix_class_code}


def _bounded_inflate(data: bytes) -> bytes:
    try:
        decomp = zlib.decompressobj()
        out = decomp.decompress(data, MAX_INFLATED + 1)
        if len(out) > MAX_INFLATED or decomp.unconsumed_tail or not decomp.eof or decomp.unused_data:
            raise DirectoryError("MAT_COMPRESSED_STREAM_UNBOUNDED_OR_INVALID")
        out += decomp.flush(MAX_INFLATED + 1 - len(out))
    except (zlib.error, ValueError) as exc:
        raise DirectoryError("MAT_COMPRESSED_STREAM_INVALID") from exc
    if len(out) > MAX_INFLATED or not out:
        raise DirectoryError("MAT_COMPRESSED_OUTPUT_LIMIT_OR_EMPTY")
    return out


def _scan(data: bytes, endian: str, depth: int) -> list[dict]:
    if depth > MAX_DEPTH:
        raise DirectoryError("MAT_COMPRESSION_DEPTH_EXCEEDED")
    if not data or len(data) > MAX_INFLATED:
        raise DirectoryError("MAT_STREAM_SIZE_REJECTED")
    variables: list[dict] = []
    position = 0
    elements = 0
    while position < len(data):
        elements += 1
        if elements > MAX_VARIABLES or len(variables) > MAX_VARIABLES:
            raise DirectoryError("MAT_ELEMENT_COUNT_EXCEEDED")
        kind, payload, nxt = _tag(data, position, endian)
        if nxt <= position:
            raise DirectoryError("MAT_ELEMENT_NOT_PROGRESSING")
        position = nxt
        if kind == MI_MATRIX:
            variables.append(_matrix_metadata(payload, endian))
        elif kind == MI_COMPRESSED:
            variables.extend(_scan(_bounded_inflate(payload), endian, depth + 1))
        else:
            raise DirectoryError("MAT_TOP_LEVEL_TAG_UNSUPPORTED")
        if len(variables) > MAX_VARIABLES:
            raise DirectoryError("MAT_VARIABLE_COUNT_EXCEEDED")
    return variables


def inventory_mat_v5(raw: bytes) -> list[dict]:
    if not isinstance(raw, bytes) or len(raw) < 136 or len(raw) > MAX_MEMBER:
        raise DirectoryError("MAT_FILE_SIZE_REJECTED")
    if not raw.startswith(b"MATLAB 5"):
        raise DirectoryError("MAT_NOT_V5_HEADER")
    endian_flag = raw[126:128]
    if endian_flag == b"IM" and raw[124:126] == b"\x00\x01":
        endian = "<"
    elif endian_flag == b"MI" and raw[124:126] == b"\x01\x00":
        endian = ">"
    else:
        raise DirectoryError("MAT_V5_ENDIAN_OR_VERSION_INVALID")
    variables = _scan(raw[128:], endian, 0)
    if not variables:
        raise DirectoryError("MAT_NO_TOP_LEVEL_VARIABLES")
    names = [v["name"] for v in variables]
    if len(set(names)) != len(names):
        raise DirectoryError("MAT_DUPLICATED_TOP_LEVEL_VARIABLE")
    return variables


def inspect_original_archive(data: bytes, *, require_original: bool = True) -> dict:
    base = gate.inspect_source(data, require_published_md5=require_original)
    if require_original and base["source_sha256_measured"] != schema.EXPECTED_ZIP_SHA256:
        raise DirectoryError("PINNED_ARCHIVE_SHA256_MISMATCH")
    names = sorted(m["name"] for m in base["member_metadata_displayed"])
    if base["file_count"] != 10 or names != list(schema.EXPECTED_MEMBERS):
        raise DirectoryError("ORIGINAL_TEN_MEMBERS_REQUIRED")
    records = []
    with ZipFile(BytesIO(data)) as zf:
        for name in schema.EXPECTED_MEMBERS:
            member = zf.read(name)
            record = {
                "member": name,
                "height_label_units_unverified": name.removeprefix(schema.PREFIX).removesuffix(".mat"),
                "source_member_sha256": sha256(member).hexdigest(),
                "metadata_status": "ERROR",
                "error_code": None,
                "top_level_variables": [],
            }
            try:
                record["top_level_variables"] = inventory_mat_v5(member)
                record["metadata_status"] = "READABLE"
            except DirectoryError as exc:
                record["error_code"] = str(exc)
            records.append(record)
    failures = [r["member"] for r in records if r["metadata_status"] != "READABLE"]
    sets = [set(v["name"] for v in r["top_level_variables"]) for r in records]
    common = sorted(set.intersection(*sets)) if sets and not failures else []
    passed = not failures and bool(common)
    return {
        "schema": REPORT_SCHEMA,
        "status": "INDEPENDENT_DIRECTORY_PASS_PHYSICAL_HOLD" if passed else "INDEPENDENT_DIRECTORY_FAILED",
        "source_archive_sha256": base["source_sha256_measured"],
        "source_archive_md5": base["source_md5_metadata"],
        "expected_member_count": 10,
        "inspected_member_count": len(records),
        "failed_member_count": len(failures),
        "all_ten_common_names": common,
        "records": records,
        "unmodified_scipy_schema002_status": "FAILED",
        "matlab_numeric_arrays_interpreted": False,
        "actual_physical_observations_interpreted": False,
        "external_commercial_rights": "UNVERIFIED",
        "observed_buyers": 0,
        "native_account_opened": False,
        "deployment": "NO_DEPLOY"
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inspect_original_archive(gate.download_once())
    except (gate.SourceGateError, OSError, ValueError, TimeoutError) as exc:
        result = {
            "schema": REPORT_SCHEMA, "status": "INDEPENDENT_DIRECTORY_FAILED",
            "error_type": type(exc).__name__,
            "error_code": str(exc)[:120],
            "unmodified_scipy_schema002_status": "FAILED",
            "actual_physical_observations_interpreted": False,
            "deployment": "NO_DEPLOY"
        }
    args.output.mkdir(parents=True, exist_ok=True)
    dest = args.output / "MAT_V5_DIRECTORY_RESULT.json"
    dest.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({
        "status": result["status"], "read": result.get("inspected_member_count"),
        "failed": result.get("failed_member_count"),
        "source_sha256": result.get("source_archive_sha256"),
    }, sort_keys=True))
    return int(result["status"] != "INDEPENDENT_DIRECTORY_PASS_PHYSICAL_HOLD")


if __name__ == "__main__":
    raise SystemExit(main())
