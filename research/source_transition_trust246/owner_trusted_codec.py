"""Pure owner-trusted ticket externalization reference (P0-247, research only).

This module contains no signing authority, account access, filesystem access,
target-source import or arbitrary evaluation. Historical signers must reconstruct
their own ORIGINAL body and compare before signing. NOT a native upgrade.
"""
import hashlib
import json
import math
import re

FIELDS = ("prior_record", "prior_envelope")
DOMAIN = b"agi-alpha/owner-trusted-ticket-blob/v1\n"
MAX_TICKET_BYTES = 16_000_000  # Existing historical owner ticket guard; never raised here.
MAX_BLOB_BYTES = 16_000_000    # Conservative reference bound, not production authorization.
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _plain(value, depth=0):
    """Reject non-JSON Python objects, including custom code-bearing wrappers."""
    if depth > 96:
        raise ValueError("JSON_DEPTH_LIMIT")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("NONFINITE_JSON")
        return
    if type(value) is list:
        for child in value:
            _plain(child, depth + 1)
        return
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise ValueError("STRING_JSON_KEYS_REQUIRED")
            _plain(child, depth + 1)
        return
    raise ValueError("PLAIN_JSON_VALUES_ONLY")


def canonical(value):
    _plain(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("NONFINITE_JSON")


def strict_decode(raw):
    if type(raw) is not bytes or len(raw) > MAX_BLOB_BYTES:
        raise ValueError("BOUNDED_BYTES_REQUIRED")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                         parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as e:
        raise ValueError("STRICT_UTF8_JSON_REQUIRED") from e
    if canonical(obj) != raw:
        raise ValueError("NONCANONICAL_JSON_BLOB")
    return obj


def _hash(field, raw):
    return hashlib.sha256(DOMAIN + field.encode("ascii") + b"\n" + raw).hexdigest()


def _body(body):
    if type(body) is not dict or any(field not in body for field in FIELDS):
        raise ValueError("HISTORICAL_FIELDS_REQUIRED")
    return json.loads(canonical(body))


def externalize_owner_trusted(original):
    """Construct a proposal without executing code or changing original history.

    Returns proposed JSON body and in-memory bytes keyed by content hash.
    No file is written; safe durable CAS staging is a separate owner obligation.
    """
    proposal = _body(original)
    blobs = {}
    for field in FIELDS:
        raw = canonical(proposal[field])
        if len(raw) > MAX_BLOB_BYTES:
            raise ValueError("EXISTING_BLOB_RESOURCE_BOUND")
        ident = _hash(field, raw)
        proposal[field] = {"blob_domain": "owner-trusted-ticket-blob/v1",
                           "field": field, "sha256": ident, "bytes": len(raw)}
        blobs[ident] = raw
    if len(canonical(proposal)) > MAX_TICKET_BYTES:
        raise ValueError("EXISTING_TICKET_RESOURCE_BOUND")
    return proposal, blobs


def recover_and_compare(original, proposal, blobs):
    """A pre-sign data conservation gate, NOT an alternative authority/verifier.

    The old signer supplies original from its own authenticated account; only
    the smaller proposal and blobs may originate from an outside preparer.
    The owner must still apply its existing HMAC, locking and write-ahead logic.
    """
    trusted_original = _body(original)
    candidate = _body(proposal)
    if type(blobs) is not dict or any(type(k) is not str or type(v) is not bytes
                                      for k, v in blobs.items()):
        raise ValueError("PLAIN_BLOB_DICTIONARY_REQUIRED")
    expected = set()
    for field in FIELDS:
        ref = candidate[field]
        if type(ref) is not dict or set(ref) != {"blob_domain", "field", "sha256", "bytes"}:
            raise ValueError("EXACT_BLOB_REFERENCE_REQUIRED")
        if ref["blob_domain"] != "owner-trusted-ticket-blob/v1" or ref["field"] != field:
            raise ValueError("BLOB_DOMAIN_OR_FIELD_CHANGED")
        sha = ref["sha256"]
        if type(sha) is not str or not HEX.fullmatch(sha):
            raise ValueError("CONTENT_DIGEST_FORMAT_REQUIRED")
        n = ref["bytes"]
        if type(n) is not int or n < 0 or n > MAX_BLOB_BYTES:
            raise ValueError("EXISTING_BLOB_RESOURCE_BOUND")
        if sha not in blobs:
            raise ValueError("MISSING_BLOB")
        raw = blobs[sha]
        if len(raw) != n or _hash(field, raw) != sha:
            raise ValueError("BLOB_CONTENT_OR_SIZE_CHANGED")
        candidate[field] = strict_decode(raw)
        expected.add(sha)
    if set(blobs) != expected:
        raise ValueError("UNREFERENCED_BLOB_REFUSED")
    if canonical(candidate) != canonical(trusted_original):
        raise ValueError("ORIGINAL_ACCOUNT_HISTORY_OR_AUTHORITY_CHANGED")
    if len(canonical(proposal)) > MAX_TICKET_BYTES:
        raise ValueError("EXISTING_TICKET_RESOURCE_BOUND")
    return canonical(proposal)
