"""Independently replay a bounded *public-byte* citation packet, offline.

This does not certify official authorship, browser-visible HTML, legal interpretation,
buyer consent, native account balances or commercial profit. No HTTP or credentials.
The two hash pins are external to the supplied packet and came from an already
exposed hosted public-source observation, NOT an issuer signature.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys

from research import regulatory_citation097 as original

SCHEMA = "agi-alpha/regulatory-offline-replay098/v1"
TRUSTED = {
    "tbs-directive-2025": {
        "url": "https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592",
        "bytes": 69865,
        "sha256": "225f990673205a49cee216fb8fc124909e8eb917559e3e258a8dd7fb7c35a0e3",
    },
    "ssc-challenge-2026": {
        "url": "https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/"
               "artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance",
        "bytes": 63094,
        "sha256": "dbc717a8898ae6694a1c3bf3cb44c82d5849d8e430b0a35e08a655b0019f6550",
    },
}
LIMITS = {
    "official_issuer_signature": False,
    "full_browser_visibility": False,
    "semantic_or_legal_assessment": False,
    "rights_or_buyer_acceptance": False,
    "real_paid_commerce": False,
    "complete_cost_profit": False,
    "trailing365_usd3b": False,
}
PACKET_MAX_BYTES = 128 * 1024


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def _nonfinite(_value):
    raise ValueError("NONFINITE_JSON")


def _read_regular(path, maximum):
    """Read one regular file via one no-follow descriptor with identity checks.

    The named final component must stay the same regular inode across the
    finite read. This defends against final-component pre-open/post-open
    substitution, not hostile mutable *parent* directories or post-return
    path mutation; exact external SHA256 pins remain the content authority.
    """
    path = Path(path)
    initial = path.lstat()  # path identity before the descriptor acquisition
    if not stat.S_ISREG(initial.st_mode):
        raise ValueError("NOT_A_REGULAR_INPUT_FILE")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise ValueError("POSIX_SAFE_OPEN_UNAVAILABLE")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino)):
            raise ValueError("INPUT_CHANGED_BEFORE_READ")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            blob = handle.read(maximum + 1)
        final = path.lstat()
        if (not stat.S_ISREG(final.st_mode)
                or (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino)):
            raise ValueError("INPUT_CHANGED_DURING_READ")
    finally:
        os.close(fd)
    if not blob or len(blob) > maximum:
        raise ValueError("INVALID_INPUT_SIZE")
    return blob


def _parse_packet(path):
    data = _read_regular(path, PACKET_MAX_BYTES)
    return json.loads(data.decode("utf-8", "strict"),
                      object_pairs_hook=_unique_pairs, parse_constant=_nonfinite)


def verify_offline(sources_dir, packet_path, *, trusted=None):
    """Verify using independent pins, not hashes from the untrusted packet.

    trusted exists for completely synthetic, preregistered unit fixtures only.
    The public CLI always uses hardcoded original public-observation pins.
    """
    trust = TRUSTED if trusted is None else trusted
    if not isinstance(trust, dict) or set(trust) != set(original.ALLOWED):
        raise ValueError("MISSING_EXTERNAL_PINS")
    path = Path(sources_dir)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("INVALID_SOURCE_DIRECTORY")
    names = {item.name for item in path.iterdir()}
    expected_names = {key + ".html" for key in original.ALLOWED}
    if names != expected_names:
        raise ValueError("INCOMPLETE_OR_EXTRA_SOURCE_SET")
    if Path(packet_path).is_symlink():
        raise ValueError("NOT_A_REGULAR_INPUT_FILE")
    observed = _parse_packet(packet_path)
    docs = {}
    for ident, (url, _version) in original.ALLOWED.items():
        record = trust.get(ident)
        if not isinstance(record, dict) or set(record) != {"url", "bytes", "sha256"}:
            raise ValueError("MISSING_EXTERNAL_PINS")
        if record["url"] != url or type(record["bytes"]) is not int or record["bytes"] <= 0:
            raise ValueError("INVALID_EXTERNAL_PIN")
        digest = record["sha256"]
        if (not isinstance(digest, str) or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)):
            raise ValueError("INVALID_EXTERNAL_PIN")
        blob = _read_regular(path / (ident + ".html"), original.MAX_BYTES)
        if len(blob) != record["bytes"] or sha256(blob).hexdigest() != digest:
            raise ValueError("PINNED_BYTES_MISMATCH")
        docs[ident] = original.document(ident, url, blob)
    claims = [original.make_claim(code, docs[ident], anchor, stop, quote)
              for code, ident, anchor, stop, quote in original.CLAIMS]
    original.verify_packet(observed, docs, claims)
    return {
        "schema": SCHEMA,
        "accepted": True,
        "trusted_observation": "EXPOSED_GITHUB_PUBLIC_BYTE_HASHES_NOT_ISSUER_SIGNATURE",
        "packet_sha256": observed["packet_sha256"],
        "source_sha256": {ident: docs[ident]["sha256"] for ident in sorted(docs)},
        "accepted_claim_count": len(claims),
        "limitations": LIMITS,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify",))
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.sources_dir.is_absolute() or not args.packet.is_absolute() or not args.output.is_absolute():
        parser.error("absolute paths required")
    if args.output.exists() or args.output.is_symlink():
        parser.error("refuse to overwrite prior receipt")
    try:
        result = verify_offline(args.sources_dir, args.packet)
        status = 0
    except (ValueError, TypeError, OSError, UnicodeError, json.JSONDecodeError):
        # No untrusted file paths, raw text, source excerpts or exception content
        # appear in the output. This is an intentionally bounded refusal receipt.
        result = {"schema": SCHEMA, "accepted": False,
                  "error": "OFFLINE_REPLAY_REJECTED", "limitations": LIMITS}
        status = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
