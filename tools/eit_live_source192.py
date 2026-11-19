"""Read-only original chest ZIP metadata/CRC qualification on a pinned Zenodo record.

Not the EIT190 MATLAB inventory, an inverse reconstruction, or a finance action.
The single original source is preregistered in LIVE_SOURCE_PROTOCOL.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile

from tools.eit_zip_metadata192 import (
    Refusal, classify_zip, safe_name, write_once, MAX_ENTRIES,
)

RECORD = "24120439"
TARGET = "AgarChestPhantom.zip"
RECORD_URL = f"https://zenodo.org/api/records/{RECORD}"
ARCHIVE_URL = f"https://zenodo.org/api/records/{RECORD}/files/{TARGET}/content"
MAX_ARCHIVE = 256_000_000
MAX_MEMBER = 250_000_000
MAX_UNCOMPRESSED = 1_500_000_000
HISTORICAL_MEMBER = (
    "__MACOSX/AgarChestPhantom/Data/"
    "._2o2_AgarChestPhantom_Inc_missingPiece_1.mat"
)
HISTORICAL_SHA = "470cc714030fef9d87ff74e55523ac9db3e33f81d1dc84d7bc2606ab5fe79e99"
HISTORICAL_HEADER = "00051607000200004d6163204f532058"


def choose_target(record):
    if not isinstance(record, dict) or str(record.get("id")) != RECORD:
        raise Refusal("EIT192_WRONG_OR_MISSING_ZENODO_RECORD")
    files = record.get("files")
    if isinstance(files, dict):
        entries = files.get("entries")
        if not isinstance(entries, dict) or TARGET not in entries:
            raise Refusal("EIT192_TARGET_ARCHIVE_NOT_LISTED")
        entry = entries[TARGET]
        if not isinstance(entry, dict) or entry.get("key", TARGET) != TARGET:
            raise Refusal("EIT192_TARGET_ARCHIVE_KEY_MISMATCH")
    elif isinstance(files, list):
        hits = [x for x in files if isinstance(x, dict) and x.get("key") == TARGET]
        if len(hits) != 1:
            raise Refusal("EIT192_TARGET_ARCHIVE_COUNT_INVALID")
        entry = hits[0]
    else:
        raise Refusal("EIT192_MANIFEST_FILE_SCHEMA_UNSUPPORTED")
    size, checksum = entry.get("size"), entry.get("checksum")
    if type(size) is not int or not 0 < size <= MAX_ARCHIVE:
        raise Refusal("EIT192_TARGET_SIZE_UNSUPPORTED")
    if not isinstance(checksum, str) or not checksum.startswith("md5:"):
        raise Refusal("EIT192_MANIFEST_CHECKSUM_MISSING")
    md5 = checksum[4:].lower()
    if len(md5) != 32 or any(c not in "0123456789abcdef" for c in md5):
        raise Refusal("EIT192_MANIFEST_MD5_INVALID")
    return size, md5


def read_manifest():
    with urlopen(Request(RECORD_URL, headers={"User-Agent": "AGI-ALPHA-EIT192-source-preflight/1"}),
                 timeout=60) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise Refusal("EIT192_UNSAFE_RECORD_REDIRECT")
        data = response.read(5_000_001)
        if len(data) > 5_000_000:
            raise Refusal("EIT192_RECORD_TOO_LARGE")
    return json.loads(data)


def get_exact_archive(dest, size, md5_from_record):
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    count = 0
    with urlopen(Request(ARCHIVE_URL, headers={"User-Agent": "AGI-ALPHA-EIT192-source-preflight/1"}),
                 timeout=90) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise Refusal("EIT192_UNSAFE_ARCHIVE_REDIRECT")
        with dest.open("xb") as handle:
            while chunk := response.read(1 << 20):
                count += len(chunk)
                if count > size or count > MAX_ARCHIVE:
                    raise Refusal("EIT192_ARCHIVE_EXCEEDS_MANIFEST")
                sha256.update(chunk)
                md5.update(chunk)
                handle.write(chunk)
    if count != size or md5.hexdigest() != md5_from_record:
        raise Refusal("EIT192_ARCHIVE_SIZE_OR_CHECKSUM_MISMATCH")
    return sha256.hexdigest()


def qualify_archive(path, *, historical_member=HISTORICAL_MEMBER,
                    historical_sha=HISTORICAL_SHA, historical_header=HISTORICAL_HEADER):
    """Always scan all entries and CRCs, then apply typed metadata classification."""
    with ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ENTRIES:
            raise Refusal("EIT192_ZIP_ENTRY_COUNT_UNSAFE")
        total = 0
        seen_names = set()
        for info in infos:
            name = safe_name(info)
            if not info.is_dir():
                folded = name.casefold()
                if folded in seen_names:
                    raise Refusal("EIT192_DUPLICATE_CASEFOLDED_MEMBER")
                seen_names.add(folded)
            if info.file_size < 0 or info.file_size > MAX_MEMBER:
                raise Refusal("EIT192_ZIP_MEMBER_SIZE_UNSAFE")
            total += info.file_size
            if total > MAX_UNCOMPRESSED:
                raise Refusal("EIT192_ZIP_TOTAL_UNCOMPRESSED_UNSAFE")
        bad = archive.testzip()
        if bad is not None:
            raise Refusal("EIT192_ZIP_CRC_FAILURE:" + bad)
    report = classify_zip(path)
    historical = [s for s in report["sidecars"] if s["member"] == historical_member]
    if len(historical) != 1:
        raise Refusal("EIT192_HISTORICAL_SIDECAR_ABSENT")
    if historical[0]["sha256"] != historical_sha:
        raise Refusal("EIT192_HISTORICAL_SIDECAR_SHA_CHANGED")
    with ZipFile(path) as archive:
        prefix = archive.read(historical_member)[:16].hex()
    if prefix != historical_header:
        raise Refusal("EIT192_HISTORICAL_SIDECAR_HEADER_CHANGED")
    report.update({
        "full_zip_crc_validated": True,
        "all_original_entry_count": len(infos),
        "all_original_uncompressed_bytes": total,
        "historical_original_failure_member_preserved": {
            "path": historical_member, "sha256": historical_sha, "header16": prefix,
        },
        "source_archive_sha256": None,
        "manifest_verified": False,
        "semantic_matlab_inventory_completed": False,
        "full_physical_property_validation": False,
    })
    return report


def run(output, failure_output):
    if output.exists() or output.is_symlink() or failure_output.exists() or failure_output.is_symlink():
        raise Refusal("EIT192_RECEIPT_EXISTS")
    with tempfile.TemporaryDirectory(prefix="eit192-chest-") as temp:
        metadata = read_manifest()
        size, md5_from_record = choose_target(metadata)
        archive = Path(temp) / TARGET
        sha = get_exact_archive(archive, size, md5_from_record)
        report = qualify_archive(archive)
    report.update({
        "source_archive_sha256": sha,
        "source_archive_bytes": size,
        "source_archive_md5_verified": md5_from_record,
        "source_record": RECORD,
        "source_filename": TARGET,
        "manifest_verified": True,
        "source_retrieval_url": ARCHIVE_URL,
    })
    write_once(output, report)
    return {"decision": "HOLD_NO_DEPLOY_NO_BID", "source_sha256": sha,
            "sidecar_count": len(report["sidecars"]),
            "genuine_matlab_candidates": len(report["genuine_matlab_candidates"])}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--failure-out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        print(json.dumps(run(a.out, a.failure_out), sort_keys=True))
    except (Refusal, OSError, ValueError, TypeError, BadZipFile) as exc:
        failure = {"decision": "FAILED_HOLD_NO_DEPLOY", "error": str(exc),
                   "source_record": RECORD, "source_filename": TARGET,
                   "property_reconstructed": False, "paid_revenue_observed": False}
        if not a.failure_out.exists() and not a.failure_out.is_symlink():
            write_once(a.failure_out, failure)
        print(json.dumps(failure, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
