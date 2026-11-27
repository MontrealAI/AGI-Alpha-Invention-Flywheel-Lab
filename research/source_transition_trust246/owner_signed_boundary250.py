"""P0-250: narrowly scoped owner-locked synthetic HMAC boundary reference.

RESEARCH ONLY: no account access, no source transition, no on-disk keys.
This is not the historical PR40 signer. Any production adoption requires an
independently authenticated old JournalAccount and exclusive writer lease.
"""
import hashlib
import hmac

from owner_wire248 import canonical, externalize_owner_v2, owner_pre_sign_compare

DOMAIN = b"native-source-transition\n"
LOCK_FIELDS = frozenset((
    "id", "account_path", "from_source", "to_source",
    "expected_state_digest", "historical_root", "verifier_files",
    "previous_counter", "last_day", "prior_record_sha256",
    "prior_envelope_sha256", "operating_sha256"
))


def _digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sign_owner_locked(original, *, owner_lock, ephemeral_authority_key):
    """Sign only the exact owner-locked old record via fixed trusted code.

    The lock must have been constructed while auditing and exclusively owning
    the original account; that property CANNOT be proved by this reference.
    Neither a target path nor target Python/callback is accepted or executed.
    """
    if type(original) is not dict or type(owner_lock) is not dict:
        raise ValueError("OWNER_LOCK_AND_ORIGINAL_REQUIRED")
    if set(owner_lock) != LOCK_FIELDS:
        raise ValueError("EXACT_OWNER_LOCK_REQUIRED")
    if type(ephemeral_authority_key) is not bytes or len(ephemeral_authority_key) < 32:
        raise ValueError("EPHEMERAL_SYNTHETIC_KEY_REQUIRED")
    previous = owner_lock["previous_counter"]
    last_day = owner_lock["last_day"]
    if type(previous) is not int or not 0 <= previous < 4:
        raise ValueError("OWNER_COUNTER_BOUND_REQUIRED")
    if type(last_day) is not int or last_day < 0:
        raise ValueError("OWNER_CLOCK_BOUND_REQUIRED")
    if type(original.get("counter")) is not int or original["counter"] != previous + 1:
        raise ValueError("STALE_OR_SKIPPED_OWNER_TRANSITION_COUNTER")
    if type(original.get("day")) is not int or original["day"] < last_day:
        raise ValueError("OWNER_SOURCE_UPGRADE_CLOCK_ROLLBACK")
    for field in ("id", "account_path", "from_source", "to_source",
                  "expected_state_digest", "historical_root", "verifier_files"):
        if canonical(original.get(field)) != canonical(owner_lock[field]):
            raise ValueError("OWNER_LOCK_FIELD_CHANGED:" + field)
    for field in ("prior_record", "prior_envelope", "operating"):
        expected = owner_lock[field + "_sha256"]
        if field not in original:
            if field != "operating" or expected is not None:
                raise ValueError("OWNER_EVIDENCE_FIELD_MISSING:" + field)
            continue
        if type(expected) is not str or len(expected) != 64:
            raise ValueError("OWNER_EVIDENCE_DIGEST_REQUIRED:" + field)
        if not hmac.compare_digest(_digest(original[field]), expected):
            raise ValueError("OWNER_LOCK_EVIDENCE_CHANGED:" + field)
    # All transformations are fixed owner-selected functions, and compare the
    # entire original record before any HMAC. No target code or data codec.
    v2, blobs = externalize_owner_v2(original)
    owner_pre_sign_compare(original, v2, blobs)
    signature = hmac.new(ephemeral_authority_key, DOMAIN + canonical(v2),
                         hashlib.sha256).hexdigest()
    return {"body": v2, "signature": signature}, blobs
