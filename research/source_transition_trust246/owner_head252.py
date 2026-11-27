"""P0-252: cooperative owner-selected synthetic head CAS; NOT native financial authority.

The lease spans the fixed-code P0-250 signing proposal, P0-251 durable
bundle publication and one authenticated synthetic head update. Neither
successor Python nor a second accounting system is imported or executed.
This is not a substitute for the original historical JournalAccount lock.
"""
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import stat
from pathlib import Path

from owner_durable251 import (_DIRECTORY, _NOFOLLOW, _root_fd, publish_bundle,
                              verify_bundle)
from owner_signed_boundary250 import sign_owner_locked
from owner_wire248 import canonical

HEAD_NAME = "owner-head.json"
HEAD_DOMAIN = b"agi-alpha/p0-252-owner-head/v1\n"
HEAD_SCHEMA = "agi-alpha/p0-252-owner-head/v1"
HEAD_LIMIT = 4096
_HEX = frozenset("0123456789abcdef")
_BODY_FIELDS = frozenset(("schema", "id", "account_path", "from_source",
                          "to_source", "counter", "day", "predecessor",
                          "ticket_sha256"))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value):
    return type(value) is str and len(value) == 64 and all(c in _HEX for c in value)


def _unique(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("DUPLICATE_SYNTHETIC_HEAD_FIELD")
        result[name] = value
    return result


def _reject_constant(_):
    raise ValueError("NONFINITE_SYNTHETIC_HEAD")


def _parse_head(raw, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("EPHEMERAL_SYNTHETIC_KEY_REQUIRED")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                         parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("STRICT_SYNTHETIC_HEAD_REQUIRED") from exc
    if type(obj) is not dict or set(obj) != {"body", "signature"} or canonical(obj) != raw:
        raise ValueError("EXACT_CANONICAL_SYNTHETIC_HEAD_REQUIRED")
    body = obj["body"]
    if type(body) is not dict or set(body) != _BODY_FIELDS or body["schema"] != HEAD_SCHEMA:
        raise ValueError("EXACT_SYNTHETIC_HEAD_BODY_REQUIRED")
    if type(body["id"]) is not str or not body["id"] or type(body["account_path"]) is not str or not body["account_path"]:
        raise ValueError("OWNER_ACCOUNT_IDENTITY_REQUIRED")
    if (type(body["counter"]) is not int or not 1 <= body["counter"] <= 4
            or type(body["day"]) is not int or body["day"] < 0
            or (body["predecessor"] is not None and not _is_sha(body["predecessor"]))
            or not _is_sha(body["ticket_sha256"])):
        raise ValueError("OWNER_HEAD_COUNTER_CLOCK_OR_POINTER_INVALID")
    for field in ("from_source", "to_source"):
        source = body[field]
        if type(source) is not dict or not _is_sha(source.get("sha256")):
            raise ValueError("OWNER_HEAD_SOURCE_IDENTITY_REQUIRED")
    expected = hmac.new(key, HEAD_DOMAIN + canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(obj["signature"])):
        raise ValueError("OWNER_SYNTHETIC_HEAD_HMAC_MISMATCH")
    return obj


def _read_head_fd(rootfd, key):
    try:
        fd = os.open(HEAD_NAME, os.O_RDONLY | _NOFOLLOW, dir_fd=rootfd)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_mode & 0o077 or info.st_size <= 0
                or info.st_size > HEAD_LIMIT):
            raise ValueError("PRIVATE_SINGLE_OWNER_HEAD_REQUIRED")
        remaining = info.st_size + 1
        chunks = []
        while remaining:
            part = os.read(fd, min(remaining, 4096))
            if not part:
                break
            chunks.append(part)
            remaining -= len(part)
        raw = b"".join(chunks)
        if len(raw) != info.st_size:
            raise ValueError("OWNER_HEAD_CHANGED_DURING_READ")
        return _parse_head(raw, key)
    finally:
        os.close(fd)


def _head_id(head):
    return _sha(canonical(head))


def _signed_head(body, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("EPHEMERAL_SYNTHETIC_KEY_REQUIRED")
    record = {"body": body, "signature": hmac.new(
        key, HEAD_DOMAIN + canonical(body), hashlib.sha256).hexdigest()}
    raw = canonical(record)
    if len(raw) > HEAD_LIMIT:
        raise ValueError("SYNTHETIC_HEAD_SIZE_BOUND")
    _parse_head(raw, key)
    return record, raw


def _install_head(rootfd, raw):
    temp = ".p0252-head-" + secrets.token_hex(16)
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _NOFOLLOW,
                 0o600, dir_fd=rootfd)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise OSError("SYNTHETIC_HEAD_WRITE_FAILED")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    # Only cooperating P0-252 publishers obey this advisory lease.
    os.replace(temp, HEAD_NAME, src_dir_fd=rootfd, dst_dir_fd=rootfd)
    os.fsync(rootfd)


def _lease_fd(rootfd):
    fd = os.open(".p0252.owner-lease", os.O_RDWR | os.O_CREAT | _NOFOLLOW,
                 0o600, dir_fd=rootfd)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
        os.close(fd)
        raise ValueError("PRIVATE_OWNER_LEASE_REQUIRED")
    return fd


def read_committed_head(root, ephemeral_authority_key, *, original=None):
    """Read the synthetic committed head, never infer authority from a bare bundle."""
    fd = _root_fd(root)
    try:
        head = _read_head_fd(fd, ephemeral_authority_key)
        if head is None:
            return None
        if original is not None:
            body = head["body"]
            if (original.get("account_path") != body["account_path"]
                    or original.get("id") != body["id"]
                    or original.get("counter") != body["counter"]
                    or canonical(original.get("to_source")) != canonical(body["to_source"])):
                raise ValueError("OWNER_HEAD_DOES_NOT_MATCH_ORIGINAL")
            verify_bundle(root, body["ticket_sha256"], original, ephemeral_authority_key)
        return {"head_sha256": _head_id(head), "body": head["body"]}
    finally:
        os.close(fd)


def commit_owner_transition(root, original, owner_lock, ephemeral_authority_key, *,
                            expected_prior_head=None, interrupt=None):
    """Commit one synthetic successor with a cooperative owner-head CAS.

    The old record and lock are independently supplied test fixtures; no real
    JournalAccount or operating file is inspected or authenticated here.
    """
    if expected_prior_head is not None and not _is_sha(expected_prior_head):
        raise ValueError("EXACT_PREDECESSOR_DIGEST_REQUIRED")
    if interrupt not in (None, "after_bundle", "after_head"):
        raise ValueError("REGISTERED_INTERRUPTION_POINT_REQUIRED")
    rootfd = _root_fd(root)
    try:
        lease = _lease_fd(rootfd)
        try:
            fcntl.flock(lease, fcntl.LOCK_EX)
            try:
                head = _read_head_fd(rootfd, ephemeral_authority_key)
                actual_head = _head_id(head) if head is not None else None
                if head is None and expected_prior_head is not None:
                    raise ValueError("MISSING_PREDECESSOR_HEAD")
                if head is not None:
                    current = head["body"]
                    if (original.get("account_path") != current["account_path"]
                            or original.get("id") != current["id"]):
                        raise ValueError("OWNER_ACCOUNT_IDENTITY_CHANGED")
                    if actual_head != expected_prior_head:
                        # A prior successful commit may be acknowledged twice.
                        if current["predecessor"] != expected_prior_head:
                            raise ValueError("STALE_OR_FORKED_OWNER_HEAD")
                        ticket, _ = sign_owner_locked(
                            original, owner_lock=owner_lock,
                            ephemeral_authority_key=ephemeral_authority_key)
                        if _sha(canonical(ticket)) != current["ticket_sha256"]:
                            raise ValueError("CONFLICTING_SUCCESSOR_FROM_SAME_PARENT")
                        verify_bundle(root, current["ticket_sha256"], original,
                                      ephemeral_authority_key)
                        return {"head_sha256": actual_head,
                                "bundle_sha256": current["ticket_sha256"],
                                "counter": current["counter"], "idempotent": True}
                    if (canonical(original.get("from_source")) != canonical(current["to_source"])
                            or type(original.get("counter")) is not int
                            or original["counter"] != current["counter"] + 1
                            or type(original.get("day")) is not int
                            or original["day"] < current["day"]):
                        raise ValueError("NONCONTIGUOUS_OWNER_SOURCE_COUNTER_OR_CLOCK")
                elif expected_prior_head is not None:
                    raise ValueError("MISSING_PREDECESSOR_HEAD")
                # Sign only after source/head/counter preflight under the lease.
                ticket, _ = sign_owner_locked(
                    original, owner_lock=owner_lock,
                    ephemeral_authority_key=ephemeral_authority_key)
                requested_bundle = _sha(canonical(ticket))
                receipt = publish_bundle(
                    root, original, owner_lock, ephemeral_authority_key)
                if receipt["bundle_sha256"] != requested_bundle:
                    raise ValueError("SYNTHETIC_BUNDLE_COMMIT_CHANGED")
                verify_bundle(root, requested_bundle, original, ephemeral_authority_key)
                if interrupt == "after_bundle":
                    raise RuntimeError("SYNTHETIC_CRASH_AFTER_BUNDLE_NO_HEAD")
                body = {"schema": HEAD_SCHEMA, "id": original["id"],
                        "account_path": original["account_path"],
                        "from_source": original["from_source"],
                        "to_source": original["to_source"],
                        "counter": original["counter"], "day": original["day"],
                        "predecessor": expected_prior_head,
                        "ticket_sha256": requested_bundle}
                signed, raw = _signed_head(body, ephemeral_authority_key)
                _install_head(rootfd, raw)
                if interrupt == "after_head":
                    raise RuntimeError("SYNTHETIC_CRASH_AFTER_HEAD_ALREADY_COMMITTED")
                return {"head_sha256": _head_id(signed),
                        "bundle_sha256": requested_bundle,
                        "counter": original["counter"], "idempotent": False}
            finally:
                fcntl.flock(lease, fcntl.LOCK_UN)
        finally:
            os.close(lease)
    finally:
        os.close(rootfd)
