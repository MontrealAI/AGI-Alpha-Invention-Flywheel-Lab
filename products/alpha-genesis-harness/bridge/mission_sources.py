# SPDX-License-Identifier: Apache-2.0
"""Bind operator-acquired source bytes to an offline mission scope."""

from hashlib import sha256
import re
from urllib.parse import urlsplit

from .workflows import NAME, require


FIELDS = {"url", "version", "sha256", "content_type", "text", "acquisition"}
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,250}[a-z0-9])?\Z")
TYPES = {"text/plain", "text/markdown", "application/json", "text/html"}
MAX_SOURCE_BYTES = 64 * 1024
EXCERPT_BYTES = 512


def _label(value, limit):
    return isinstance(value, str) and bool(value.strip()) and value.isprintable() and len(value.encode()) <= limit


def _source_url(value):
    if not _label(value, 2048) or any(char.isspace() for char in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname is not None and HOST.fullmatch(url.hostname) is not None
                and "." in url.hostname and url.port in (None, 443) and not url.username and not url.password
                and not url.fragment and not url.query and bool(url.path))
    except ValueError:
        return False


def _validate(ident, record):
    code = "MISSION_SOURCE_CAPTURE"
    require(isinstance(ident, str) and NAME.fullmatch(ident) and isinstance(record, dict) and set(record) == FIELDS,
            "A source capture needs an approved ID, URL, version, digest, content type, bytes and acquisition record.", code)
    require(_source_url(record["url"]) and _label(record["version"], 240)
            and isinstance(record["content_type"], str) and record["content_type"] in TYPES
            and _label(record["acquisition"], 400), "Invalid source identity, format or acquisition record.", code)
    text = record["text"]
    require(isinstance(text, str) and "\x00" not in text and 0 < len(text.encode()) <= MAX_SOURCE_BYTES
            and isinstance(record["sha256"], str) and DIGEST.fullmatch(record["sha256"]),
            "A source capture needs bounded UTF-8 text and an exact SHA-256 pin.", code)
    require(sha256(text.encode()).hexdigest() == record["sha256"], "Source capture bytes differ from the approved digest.",
            "MISSION_SOURCE_PIN")


def validate_snapshots(snapshots):
    require(isinstance(snapshots, dict) and 0 < len(snapshots) <= 8,
            "Approve between one and eight pinned source captures.", "MISSION_SOURCE_CAPTURE")
    for ident, record in snapshots.items():
        _validate(ident, record)


def describe(snapshots):
    return {ident: {k: v for k, v in record.items() if k != "text"} for ident, record in snapshots.items()}


def pinned_source(snapshots, ident):
    require(isinstance(ident, str) and ident in snapshots,
            "Source ID is outside the operator-approved capture scope.", "MISSION_SOURCE_AUTHORITY")
    record = snapshots[ident]
    _validate(ident, record)
    return {"source_id": ident, **record, "trust": "UNTRUSTED_SOURCE_CONTENT",
            "transport": "OPERATOR_CAPTURE", "network_retrieved_by_executor": False}


def source_excerpt(source, offset):
    raw = source["text"].encode()
    code = "MISSION_SOURCE_OFFSET"
    require(type(offset) is int and 0 <= offset < len(raw) and raw[offset] & 0xc0 != 0x80,
            "Use a returned next byte offset at a UTF-8 character boundary.", code)
    end = min(offset + EXCERPT_BYTES, len(raw))
    while end < len(raw) and raw[end] & 0xc0 == 0x80:
        end -= 1
    return {"source_id": source["source_id"], "byte_offset": offset, "total_bytes": len(raw),
            "next_byte_offset": end if end < len(raw) else None, "text": raw[offset:end].decode()}
