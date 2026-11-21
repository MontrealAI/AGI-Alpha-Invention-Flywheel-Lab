#!/usr/bin/env python3
"""FIRSTCASH210: narrow pinned-public-source byte witness, not a truth oracle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

SCHEMA = "firstcash210/pinned-source-byte-witness/v1"
CASE = "montrealai-firstcash206-public-admission"
REPO = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
COMMIT = "7f299640e9ad311b79b71850a9e0370aeb2984d9"
SOURCE_PATH = "campaign/unseen-first-cash-206/ADMISSION.md"
SOURCE_URL = f"https://github.com/{REPO}/blob/{COMMIT}/{SOURCE_PATH}"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{SOURCE_PATH}"
EXPECTED_BLOB = "184291fa360326fe3cb44b213b74053ba486817a"
MAX_BYTES = 262144
FILENAMES = ("WITNESS.json", "SOURCE.md")
FIELDS = {
    "schema", "case_id", "source_url", "raw_url", "source_commit",
    "source_path", "expected_git_blob", "observed_git_blob",
    "source_sha256", "source_bytes", "observed_at_utc", "scope",
}


class Refusal(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal("REDIRECT_REFUSED")


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") +
                        b"\x00" + data).hexdigest()


def unique_json(data: bytes) -> dict:
    def no_dupes(pairs):
        obj = {}
        for key, val in pairs:
            if key in obj:
                raise Refusal("DUPLICATE_JSON_KEY")
            obj[key] = val
        return obj
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=no_dupes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal("INVALID_JSON") from exc
    if not isinstance(result, dict):
        raise Refusal("WITNESS_NOT_OBJECT")
    return result


def validate_source_url(url: str) -> str:
    if not isinstance(url, str):
        raise Refusal("INVALID_SOURCE_URL")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "github.com" or
            parts.username or parts.password or parts.port or
            parts.query or parts.fragment or parts.path.startswith("//")):
        raise Refusal("UNSAFE_SOURCE_URL")
    match = re.fullmatch(
        r"/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/([0-9a-f]{40})/"
        r"([A-Za-z0-9_./-]+)", parts.path
    )
    if not match or ".." in match.group(2).split("/"):
        raise Refusal("UNPINNED_OR_UNSUPPORTED_SOURCE")
    if url != SOURCE_URL or match.group(1) != COMMIT or match.group(2) != SOURCE_PATH:
        raise Refusal("UNREGISTERED_SOURCE")
    return RAW_URL


def fetch_public_source(url: str = SOURCE_URL, opener=None) -> bytes:
    raw_url = validate_source_url(url)
    request = Request(raw_url, headers={"Accept": "text/plain",
                                       "User-Agent": "MontrealAI-FIRSTCASH210/1"})
    opener = opener or build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=12) as response:
            if response.status != 200 or response.geturl() != raw_url:
                raise Refusal("UNEXPECTED_HTTP_SOURCE")
            stated = response.headers.get("Content-Length")
            if stated is not None and int(stated) > MAX_BYTES:
                raise Refusal("OVERSIZE_SOURCE")
            data = response.read(MAX_BYTES + 1)
    except Refusal:
        raise
    except Exception as exc:
        raise Refusal("FETCH_FAILED") from exc
    if not data or len(data) > MAX_BYTES:
        raise Refusal("EMPTY_OR_OVERSIZE_SOURCE")
    if git_blob(data) != EXPECTED_BLOB:
        raise Refusal("PINNED_GIT_BLOB_MISMATCH")
    return data


def make_witness(data: bytes, at_utc: str) -> dict:
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise Refusal("EMPTY_OR_OVERSIZE_SOURCE")
    if git_blob(data) != EXPECTED_BLOB:
        raise Refusal("PINNED_GIT_BLOB_MISMATCH")
    if not isinstance(at_utc, str) or not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", at_utc):
        raise Refusal("BAD_OBSERVATION_TIME")
    return {
        "schema": SCHEMA, "case_id": CASE, "source_url": SOURCE_URL,
        "raw_url": RAW_URL, "source_commit": COMMIT, "source_path": SOURCE_PATH,
        "expected_git_blob": EXPECTED_BLOB, "observed_git_blob": git_blob(data),
        "source_sha256": digest(data), "source_bytes": len(data),
        "observed_at_utc": at_utc,
        "scope": "PUBLIC_PINNED_SOURCE_BYTES_ONLY_NOT_INDEPENDENT_FACT_OR_COMMERCE",
    }


def safe_file(path: Path) -> bytes:
    if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise Refusal("UNSAFE_OR_MISSING_FILE")
    if path.stat().st_size > MAX_BYTES:
        raise Refusal("OVERSIZE_FILE")
    return path.read_bytes()


def create_bundle(output: Path, data: bytes, at_utc: str) -> dict:
    witness = make_witness(data, at_utc)
    if output.exists() or output.is_symlink():
        raise Refusal("OUTPUT_MUST_NOT_EXIST")
    output.mkdir(parents=True, exist_ok=False)
    (output / "SOURCE.md").write_bytes(data)
    (output / "WITNESS.json").write_bytes(canonical(witness))
    return witness


def verify_bundle(output: Path) -> dict:
    # Local byte audit: does not independently re-fetch or certify source truth.
    raw = safe_file(output / "WITNESS.json")
    witness = unique_json(raw)
    if set(witness) != FIELDS or raw != canonical(witness):
        raise Refusal("NONCANONICAL_WITNESS")
    data = safe_file(output / "SOURCE.md")
    expected = make_witness(data, witness.get("observed_at_utc"))
    if witness != expected:
        raise Refusal("WITNESS_REPLAY_MISMATCH")
    return {"accepted": True, "scope": expected["scope"],
            "git_blob": expected["observed_git_blob"],
            "source_sha256": expected["source_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            data = fetch_public_source()
            instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = create_bundle(args.output, data, instant)
            print(json.dumps({"accepted": True, "source_bytes": result["source_bytes"],
                              "source_sha256": result["source_sha256"],
                              "scope": result["scope"]}, sort_keys=True))
        else:
            print(json.dumps(verify_bundle(args.output), sort_keys=True))
    except Refusal as exc:
        parser.exit(2, f"FIRSTCASH210_REFUSED: {exc}\n")


if __name__ == "__main__":
    main()
