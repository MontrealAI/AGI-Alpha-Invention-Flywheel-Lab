# SPDX-License-Identifier: Apache-2.0
"""Member-supplied UTF-8 originals in a private mission revision."""

import hashlib
import re

from .workflows import require


MAX_DOCUMENTS = 8
MAX_BYTES = 96 * 1024
READ = "read_mission_document"
INVALID_NAME = re.compile(r"[/\\:\x00-\x1f\x7f]")
BINARY_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate(documents):
    require(isinstance(documents, list) and len(documents) <= MAX_DOCUMENTS,
            "Choose up to eight UTF-8 documents.", "MISSION_DOCUMENT_LIMIT")
    total = 0
    for row in documents:
        require(isinstance(row, dict) and set(row) == {"name", "text"},
                "Each document needs its name and original text.", "MISSION_DOCUMENT_INPUT")
        name, text = row["name"], row["text"]
        require(isinstance(name, str) and bool(name.strip()) and name not in {".", ".."}
                and len(name.encode("utf-8")) <= 240 and not INVALID_NAME.search(name),
                "Use the original document's filename without a path.", "MISSION_DOCUMENT_INPUT")
        require(isinstance(text, str) and not BINARY_CONTROL.search(text),
                "Document content must be UTF-8 text.", "MISSION_DOCUMENT_INPUT")
        total += len(text.encode("utf-8"))
        require(total <= MAX_BYTES, "Choose up to 96 KiB of UTF-8 documents.", "MISSION_DOCUMENT_LIMIT")
    return documents


def _describe(row, ident):
    raw = row["text"].encode("utf-8")
    return {"id": ident, "name": row["name"], "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def describe(documents, *, preview=False):
    records = []
    for ident, row in enumerate(documents, 1):
        record = _describe(row, ident)
        if preview:
            record["first_excerpt"] = _excerpt(row, 0, 480)
        records.append(record)
    return records


def _excerpt(row, offset, limit):
    raw = row["text"].encode("utf-8")
    require(type(offset) is int and 0 <= offset <= len(raw)
            and (offset == len(raw) or (raw[offset] & 0xC0) != 0x80),
            "Use the next byte offset returned for this document.", "MISSION_DOCUMENT_OFFSET")
    text = raw[offset:offset + limit].decode("utf-8", errors="ignore")
    end = offset + len(text.encode("utf-8"))
    return {"offset": offset, "next_offset": end if end < len(raw) else None, "text": text}


def read(documents, ident, offset):
    require(type(ident) is int and 1 <= ident <= len(documents),
            "Choose one of the documents shared for this revision.", "MISSION_DOCUMENT_AUTHORITY")
    row = documents[ident - 1]
    return {**_describe(row, ident), **_excerpt(row, offset, 2200)}
