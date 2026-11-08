"""Read-only, bounded external experimental-source verification (no scientific inference)."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import md5, sha256
import io
import json
from pathlib import Path, PurePosixPath
import stat
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

SOURCE_URL = "https://zenodo.org/records/18487116/files/Experiments_force_sensor.zip?download=1"
EXPECTED_MD5 = "28897fb33b1915a0c9317629b9951759"
MAX_TRANSFER = 8 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
MAX_MEMBERS = 1000
MAX_RATIO = 1000.0
SHOW_MEMBERS = 120
SCHEMA = "agi-alpha/magnetic-rotor-source001/v1"


class SourceGateError(ValueError):
    pass


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or not (
            parsed.hostname == "zenodo.org" or
            (parsed.hostname or "").endswith(".zenodo.org")
        ):
            raise SourceGateError("UNAPPROVED_DOWNLOAD_REDIRECT")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_once() -> bytes:
    """Single HTTP transaction. No retries, environment credentials or alternate source."""
    opener = build_opener(RestrictedRedirect())
    request = Request(SOURCE_URL, headers={"User-Agent": "AGI-ALPHA-source-gate001/1.0"})
    with opener.open(request, timeout=60) as response:
        final_url = urlparse(response.geturl())
        if final_url.scheme != "https" or not (
            final_url.hostname == "zenodo.org" or
            (final_url.hostname or "").endswith(".zenodo.org")
        ):
            raise SourceGateError("UNAPPROVED_FINAL_HOST")
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) > MAX_TRANSFER:
            raise SourceGateError("SOURCE_EXCEEDS_TRANSFER_LIMIT")
        chunks = []
        size = 0
        while True:
            chunk = response.read(min(65536, MAX_TRANSFER + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_TRANSFER:
                raise SourceGateError("SOURCE_EXCEEDS_TRANSFER_LIMIT")
            chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise SourceGateError("EMPTY_SOURCE")
    return data


def _safe_name(name: str) -> str:
    if not name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise SourceGateError("UNSAFE_ZIP_MEMBER_NAME")
    if "\\" in name or name.startswith("/") or ":" in name:
        raise SourceGateError("UNSAFE_ZIP_MEMBER_NAME")
    parts = PurePosixPath(name).parts
    if not parts or any(part in (".", "..") for part in name.split("/")) or any(part == "" for part in name.split("/")[:-1]):
        raise SourceGateError("UNSAFE_ZIP_MEMBER_NAME")
    return "/".join(parts)


def inspect_source(data: bytes, *, require_published_md5: bool = True) -> dict:
    if not isinstance(data, bytes) or len(data) > MAX_TRANSFER or not data:
        raise SourceGateError("SOURCE_SIZE_OR_TYPE_REJECTED")
    digest = md5(data).hexdigest()  # PUBLISHED ZENODO MD5, not cryptographic authority
    if require_published_md5 and digest != EXPECTED_MD5:
        raise SourceGateError("PUBLISHED_SOURCE_MD5_MISMATCH")
    summary = []
    total = 0
    file_count = 0
    nested_archives = 0
    names = set()
    extensions = Counter()
    try:
        with zipfile.ZipFile(io.BytesIO(data), mode="r") as zf:
            members = zf.infolist()
            if not members or len(members) > MAX_MEMBERS:
                raise SourceGateError("ZIP_MEMBER_COUNT_REJECTED")
            for info in members:
                safe = _safe_name(info.filename)
                identity = safe.casefold()
                if identity in names:
                    raise SourceGateError("DUPLICATE_ZIP_MEMBER")
                names.add(identity)
                mode = info.external_attr >> 16
                if stat.S_IFMT(mode) == stat.S_IFLNK:
                    raise SourceGateError("ZIP_SYMLINK_REJECTED")
                if info.flag_bits & 1:
                    raise SourceGateError("ZIP_ENCRYPTED_REJECTED")
                if info.is_dir():
                    continue
                if info.file_size < 0 or info.compress_size < 0:
                    raise SourceGateError("ZIP_INVALID_SIZE")
                if info.file_size > MAX_EXPANDED - total:
                    raise SourceGateError("ZIP_TOTAL_EXPANSION_REJECTED")
                if info.file_size / max(info.compress_size, 1) > MAX_RATIO:
                    raise SourceGateError("ZIP_MEMBER_RATIO_REJECTED")
                total += info.file_size
                file_count += 1
                extension = PurePosixPath(safe).suffix.lower() or "(none)"
                extensions[extension] += 1
                if extension in (".zip", ".7z", ".rar", ".tar", ".gz"):
                    nested_archives += 1
                # Check decompression, advertised size and CRC without extraction to disk.
                read_size = 0
                with zf.open(info, "r") as fh:
                    while True:
                        chunk = fh.read(min(65536, info.file_size - read_size + 1))
                        if not chunk:
                            break
                        read_size += len(chunk)
                        if read_size > info.file_size:
                            raise SourceGateError("ZIP_MEMBER_EXPANSION_REJECTED")
                if read_size != info.file_size:
                    raise SourceGateError("ZIP_MEMBER_SIZE_MISMATCH")
                summary.append({
                    "name": safe, "extension": extension,
                    "bytes": info.file_size, "crc32": f"{info.CRC:08x}"
                })
    except (zipfile.BadZipFile, RuntimeError, EOFError) as e:
        raise SourceGateError("ZIP_CORRUPT_OR_UNREADABLE") from e
    if file_count < 1:
        raise SourceGateError("ZIP_NO_FILES")
    summary.sort(key=lambda e: e["name"])
    return {
        "schema": SCHEMA,
        "status": "SOURCE_ACCESS_GATE_PASS_PHYSICAL_UTILITY_HOLD",
        "source_record": "https://doi.org/10.5281/zenodo.18487116",
        "source_file": "Experiments_force_sensor.zip",
        "source_md5_metadata": digest,
        "source_sha256_measured": sha256(data).hexdigest(),
        "compressed_bytes": len(data),
        "decompressed_bytes_checked": total,
        "file_count": file_count,
        "extension_counts": dict(sorted(extensions.items())),
        "opaque_nested_archive_count": nested_archives,
        "member_metadata_displayed": summary[:SHOW_MEMBERS],
        "member_metadata_displayed_count": min(len(summary), SHOW_MEMBERS),
        "no_material_bytes_redistributed": True,
        "rights_for_commercial_use": "UNVERIFIED",
        "force_curve_interpreted": False,
        "physical_hold_slide_accepted": False,
        "buyer_demand": "UNKNOWN",
        "real_earnings": 0,
        "native_financial_account_opened": False,
        "deployment": "NO_DEPLOY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    try:
        result = inspect_source(download_once())
    except (SourceGateError, OSError, TimeoutError, ValueError, zipfile.LargeZipFile) as error:
        result = {
            "schema": SCHEMA, "status": "SOURCE_ACCESS_GATE_FAILED",
            "error_type": type(error).__name__,
            "reason": str(error)[:160],
            "physical_hold_slide_accepted": False,
            "deployment": "NO_DEPLOY",
        }
    options.output.mkdir(parents=True, exist_ok=True)
    destination = options.output / "SOURCE_GATE_RESULT.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    print(json.dumps({
        "result": str(destination),
        "status": result["status"],
        "files": result.get("file_count"),
        "sha256": result.get("source_sha256_measured"),
        "reason": result.get("reason"),
    }, sort_keys=True))
    return 0 if result["status"] == "SOURCE_ACCESS_GATE_PASS_PHYSICAL_UTILITY_HOLD" else 1


if __name__ == "__main__":
    raise SystemExit(main())
