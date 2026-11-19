"""Read-only, fail-closed AppleDouble v2 metadata preflight for EIT archive sources.

This does NOT validate the official Zenodo manifest, real .mat variable tables,
all ZIP CRCs, or any physical-property measurements. Original inspector must
perform those checks independently. Does not change owner-source or accounts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import unicodedata
from zipfile import BadZipFile, ZipFile

APPLEDOUBLE_MAGIC = 0x00051607
APPLEDOUBLE_VERSION = 0x00020000
HEADER = struct.Struct(">II16sH")
DESCRIPTOR = struct.Struct(">III")
MAX_METADATA_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 2000
MAX_SIDECARS = 500
MAX_DESCRIPTORS = 64


class Refusal(ValueError):
    """Untrusted source cannot be classified without loss of provenance."""


def safe_name(info):
    name = info.filename
    if (not name or "\\" in name or "\x00" in name or name.startswith("/")
            or (name.endswith("/") and not info.is_dir())):
        raise Refusal("EIT192_UNSAFE_MEMBER_PATH")
    if unicodedata.normalize("NFC", name) != name:
        raise Refusal("EIT192_NONCANONICAL_UNICODE_PATH")
    parts = name.rstrip("/").split("/")
    if any(x in ("", ".", "..") for x in parts):
        raise Refusal("EIT192_UNSAFE_MEMBER_PATH")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise Refusal("EIT192_NONREGULAR_MEMBER")
    return name


def metadata_counterpart(name):
    """Only a ._ name inside the actual __MACOSX root is an eligible sidecar."""
    parts = name.split("/")
    if len(parts) < 2 or parts[0] != "__MACOSX":
        return None
    basename = parts[-1]
    if not basename.startswith("._") or len(basename) <= 2:
        raise Refusal("EIT192_UNRECOGNIZED_METADATA_DIR_MEMBER")
    base = "/".join(parts[1:-1] + [basename[2:]])
    if not base or base.startswith("/") or ".." in PurePosixPath(base).parts:
        raise Refusal("EIT192_INVALID_SIDECAR_COUNTERPART")
    return base


def parse_appledouble(raw):
    """Validate v2 container descriptors without parsing opaque resource data."""
    if len(raw) > MAX_METADATA_BYTES:
        raise Refusal("EIT192_SIDECAR_TOO_LARGE")
    if len(raw) < HEADER.size:
        raise Refusal("EIT192_SIDECAR_HEADER_TRUNCATED")
    magic, version, filler, count = HEADER.unpack_from(raw)
    if magic != APPLEDOUBLE_MAGIC or version != APPLEDOUBLE_VERSION:
        raise Refusal("EIT192_NOT_APPLEDOUBLE_V2")
    if filler != b"\x00" * 16:
        raise Refusal("EIT192_APPLEDOUBLE_FILLER_NONZERO")
    if count < 1 or count > MAX_DESCRIPTORS:
        raise Refusal("EIT192_DESCRIPTOR_COUNT_INVALID")
    table_end = HEADER.size + count * DESCRIPTOR.size
    if len(raw) < table_end:
        raise Refusal("EIT192_DESCRIPTOR_TABLE_TRUNCATED")
    ids = set()
    spans = []
    entries = []
    for index in range(count):
        entry_id, offset, length = DESCRIPTOR.unpack_from(raw, HEADER.size + index * DESCRIPTOR.size)
        if entry_id == 0 or entry_id in ids:
            raise Refusal("EIT192_DUPLICATE_OR_ZERO_ENTRY_ID")
        ids.add(entry_id)
        if offset < table_end or offset > len(raw) or length > len(raw) - offset:
            raise Refusal("EIT192_DESCRIPTOR_OUTSIDE_PAYLOAD")
        if length:
            spans.append((offset, offset + length))
        entries.append({"id": entry_id, "offset": offset, "length": length})
    spans.sort()
    if any(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1)):
        raise Refusal("EIT192_OVERLAPPING_PAYLOADS")
    return entries


def classify_zip(path):
    """Bound sidecar scanning and retain *all* genuine member names unchanged."""
    sidecars = []
    data_names = []
    seen = set()
    all_names = set()
    with ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise Refusal("EIT192_TOO_MANY_ZIP_ENTRIES")
        for info in infos:
            name = safe_name(info)
            if info.is_dir():
                continue
            folded = name.casefold()
            if folded in seen:
                raise Refusal("EIT192_DUPLICATE_CASEFOLDED_MEMBER")
            seen.add(folded)
            all_names.add(name)
            counterpart = metadata_counterpart(name)
            if counterpart is None:
                data_names.append(name)
                continue
            if len(sidecars) >= MAX_SIDECARS:
                raise Refusal("EIT192_TOO_MANY_SIDECARS")
            if info.file_size > MAX_METADATA_BYTES:
                raise Refusal("EIT192_SIDECAR_TOO_LARGE")
            raw = archive.read(info)
            if len(raw) != info.file_size:
                raise Refusal("EIT192_SIDECAR_SIZE_CHANGED")
            sidecars.append({
                "member": name, "intended_counterpart": counterpart,
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "descriptors": parse_appledouble(raw),
            })
    for item in sidecars:
        item["counterpart_present"] = item["intended_counterpart"] in all_names
    return {
        "schema": "agi-alpha/eit-appledouble-sidecar192/v1",
        "scope": "metadata-only; original manifest/ZIP-CRC/MAT parser still required",
        "sidecars": sorted(sidecars, key=lambda x: x["member"]),
        "genuine_members": sorted(data_names),
        "genuine_matlab_candidates": sorted(
            name for name in data_names if name.lower().endswith((".mat", ".m"))
        ),
        "property_reconstructed": False,
        "paid_buyers_or_revenue_observed": False,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def write_once(path, receipt):
    if path.exists() or path.is_symlink():
        raise Refusal("EIT192_RECEIPT_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists() or args.out.is_symlink():
        raise Refusal("EIT192_RECEIPT_EXISTS")
    report = classify_zip(args.archive)
    write_once(args.out, report)
    print(json.dumps({
        "sidecars": len(report["sidecars"]),
        "matlab_candidates": len(report["genuine_matlab_candidates"]),
        "decision": report["decision"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refusal, OSError, BadZipFile) as exc:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "error": str(exc)}, sort_keys=True))
        raise SystemExit(2)
