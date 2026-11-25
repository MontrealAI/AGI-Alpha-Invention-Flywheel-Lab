"""Acquire an exact range from a pinned, public Hugging Face GGUF release."""

import argparse
from datetime import datetime, UTC
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

from gguf_preflight import raw_digest


MAX_SOURCE_BYTES = 20_000_000
REGISTRATION = Path(__file__).with_name("REGISTRATION.json")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
FILE_SHA = re.compile("[a-f0-9]{64}\\Z")
FILE_NAME = re.compile(r"[A-Za-z0-9_.-]+\.gguf\Z")
REVISION = re.compile("[a-f0-9]{40}\\Z")


def vendor_observation(raw_headers, source, start, end):
    replies = []
    for block in raw_headers.split(b"\r\n\r\n"):
        lines = block.decode("latin-1").splitlines()
        if not lines or not lines[0].startswith("HTTP/"):
            continue
        code = int(lines.pop(0).split()[1])
        header_fields = {}
        for line in lines:
            name, _, value = line.partition(":")
            header_fields[name.casefold()] = value.strip()
        replies.append((code, header_fields))
    if not replies:
        raise ValueError("no HTTPS reply observed")
    code, headers = replies[-1]
    expected = f"bytes {start}-{end}/{source['size_bytes']}"
    if code != 206 or headers.get("content-range") != expected:
        raise ValueError("unexpected final range")
    pins = [reply for _, reply in replies if reply.get("x-repo-commit") is not None]
    if len(pins) != 1:
        raise ValueError("no unique publisher identity header")
    pin = pins[0]
    if (
        pin.get("x-repo-commit") != source["revision"]
        or pin.get("x-linked-etag", "").strip('"') != source["registry_linked_sha256"]
        or pin.get("x-linked-size") != str(source["size_bytes"])
    ):
        raise ValueError("linked object differs from exact public publisher metadata")
    return {
        "http_status": code, "content_range": expected, "status_chain": [status for status, _ in replies],
        "source_etag": headers.get("etag"), "source_date_utc": headers.get("date"),
        "publisher_revision": pin["x-repo-commit"],
        "publisher_linked_digest": pin["x-linked-etag"].strip('"'),
    }


def fetch(source, start, end, destination):
    if (
        REPOSITORY.fullmatch(source["repository"]) is None
        or FILE_SHA.fullmatch(source["registry_linked_sha256"]) is None
        or FILE_NAME.fullmatch(source["filename"]) is None
        or REVISION.fullmatch(source["revision"]) is None
        or not 0 <= start <= end < min(MAX_SOURCE_BYTES, source["size_bytes"])
    ):
        raise ValueError("range and identity must fit the registered public object")
    url = f"https://huggingface.co/{source['repository']}/resolve/{source['revision']}/{source['filename']}"
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as folder:
        headers = Path(folder) / "headers"
        payload = Path(folder) / "payload"
        response = subprocess.run([
            "curl", "--location", "--max-redirs", "2", "--silent", "--show-error", "--fail",
            "--max-time", "50", "--proto", "=https", "--proto-redir", "=https", "--max-filesize",
            str(end - start + 1), "--range", f"{start}-{end}", "--dump-header", str(headers), "--output",
            str(payload), url,
        ], capture_output=True)
        if response.returncode:
            raise RuntimeError(f"range acquisition failed (curl {response.returncode})")
        result = vendor_observation(headers.read_bytes(), source, start, end)
        raw = payload.read_bytes()
    if len(raw) != end - start + 1:
        raise ValueError("observed response body doesn't match requested byte count")
    with destination.open("xb") as target:
        target.write(raw)
    return {
        "url": url, "response_body_bytes": len(raw), "response_sha256": raw_digest(raw),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "recorded_at_utc": datetime.now(UTC).isoformat(), **result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("first", "repeat"))
    parser.add_argument("first_byte", type=int)
    parser.add_argument("last_byte", type=int)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    case = json.loads(REGISTRATION.read_bytes())["sources"][args.case]
    print(json.dumps(fetch(case, args.first_byte, args.last_byte, args.destination)))
