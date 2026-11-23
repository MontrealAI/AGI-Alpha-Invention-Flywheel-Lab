"""P0-251: synthetic, owner-selected, crash-before-publish v2-CAS transport.

Research only: NO native account, original signing key, live writer lease,
source upgrade, owner-controlled history read, or general-purpose file store.
Use with ephemeral synthetic HMAC keys and private owner-selected POSIX dirs.
Never execute successor or ticket-supplied Python.
"""
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import stat
from pathlib import Path

from owner_signed_boundary250 import DOMAIN, sign_owner_locked
from owner_wire248 import (MAX_BLOB_BYTES, MAX_BUNDLE_BYTES, MAX_BUNDLE_FILES,
                           MAX_TICKET_BYTES, canonical, owner_pre_sign_compare)

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_SHA = set("0123456789abcdef")


def _root_fd(root):
    """Select a preexisting, private, non-symlinked owner root."""
    if not isinstance(root, (str, Path)):
        raise ValueError("OWNER_SELECTED_DIRECTORY_REQUIRED")
    fd = os.open(os.fspath(root), os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        os.close(fd)
        raise ValueError("PRIVATE_OWNER_DIRECTORY_REQUIRED")
    return fd


def _write_once(fd, name, raw):
    if type(raw) is not bytes or not raw:
        raise ValueError("NONEMPTY_CANONICAL_BYTES_REQUIRED")
    f = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                0o600, dir_fd=fd)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(f, view)
            if n <= 0:
                raise OSError("FAILED_DURABLE_BLOB_WRITE")
            view = view[n:]
        os.fsync(f)
    finally:
        os.close(f)


def _read_regular(fd, name, bound):
    f = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=fd)
    try:
        info = os.fstat(f)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size <= 0 or info.st_size > bound):
            raise ValueError("BOUND_SINGLE_REGULAR_FILE_REQUIRED")
        with os.fdopen(os.dup(f), "rb", closefd=True) as stream:
            raw = stream.read(bound + 1)
        if len(raw) != info.st_size:
            raise ValueError("FILE_CHANGED_OR_BOUNDED_READ_FAILED")
        return raw
    finally:
        os.close(f)


def _decode_ticket(raw):
    def unique_pairs(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("DUPLICATE_TICKET_FIELD")
            out[k] = v
        return out
    def no_constants(_):
        raise ValueError("NONFINITE_TICKET")
    try:
        ticket = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                            parse_constant=no_constants)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("STRICT_SIGNED_TICKET_REQUIRED") from exc
    if type(ticket) is not dict or set(ticket) != {"body", "signature"} or canonical(ticket) != raw:
        raise ValueError("EXACT_CANONICAL_TICKET_REQUIRED")
    return ticket


def _check_name(sha):
    if type(sha) is not str or len(sha) != 64 or any(c not in _SHA for c in sha):
        raise ValueError("EXACT_SHA256_BLOB_NAME_REQUIRED")


def verify_bundle(root, bundle_sha256, original, ephemeral_authority_key):
    """Verify published bytes using an independently supplied owner original/key.

    This is not a native account audit or writer-lease verification.
    """
    _check_name(bundle_sha256)
    if type(ephemeral_authority_key) is not bytes or len(ephemeral_authority_key) < 32:
        raise ValueError("EPHEMERAL_SYNTHETIC_KEY_REQUIRED")
    rootfd = _root_fd(root)
    try:
        subfd = os.open("bundle-" + bundle_sha256,
                        os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=rootfd)
        try:
            if os.fstat(subfd).st_mode & 0o077:
                raise ValueError("PRIVATE_BUNDLE_REQUIRED")
            ticket_raw = _read_regular(subfd, "ticket.json", MAX_TICKET_BYTES)
            if hashlib.sha256(ticket_raw).hexdigest() != bundle_sha256:
                raise ValueError("PUBLISHED_TICKET_DIGEST_MISMATCH")
            ticket = _decode_ticket(ticket_raw)
            refs = ticket["body"].get("evidence")
            if type(refs) is not dict:
                raise ValueError("OWNER_EVIDENCE_REQUIRED")
            names = {v.get("sha256") for v in refs.values() if type(v) is dict}
            if len(names) != len(refs) or len(names) > MAX_BUNDLE_FILES:
                raise ValueError("EXACT_BLOB_NAMES_REQUIRED")
            for name in names:
                _check_name(name)
            if set(os.listdir(subfd)) != names | {"ticket.json"}:
                raise ValueError("EXACT_IMMUTABLE_FILE_SET_REQUIRED")
            blobs = {name: _read_regular(subfd, name, MAX_BLOB_BYTES)
                     for name in sorted(names)}
            if sum(map(len, blobs.values())) > MAX_BUNDLE_BYTES:
                raise ValueError("OWNER_BLOB_TOTAL_BOUND")
            owner_pre_sign_compare(original, ticket["body"], blobs)
            expected = hmac.new(ephemeral_authority_key,
                                DOMAIN + canonical(ticket["body"]), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(ticket["signature"]), expected):
                raise ValueError("OWNER_SYNTHETIC_HMAC_MISMATCH")
            return {"bundle_sha256": bundle_sha256, "file_count": len(blobs) + 1,
                    "total_bytes": sum(map(len, blobs.values())) + len(ticket_raw),
                    "owner_original_verified": True, "synthetic_hmac_verified": True}
        finally:
            os.close(subfd)
    finally:
        os.close(rootfd)


def publish_bundle(root, original, owner_lock, ephemeral_authority_key, *,
                   interrupt_before_publish=False):
    """Private owner-selected transport, with an atomic visibility boundary.

    A prepublication failure leaves a .pending orphan for operator diagnosis.
    Never treats it as committed and never mutates/rolls back old account state.
    """
    ticket, blobs = sign_owner_locked(
        original, owner_lock=owner_lock,
        ephemeral_authority_key=ephemeral_authority_key)
    owner_pre_sign_compare(original, ticket["body"], blobs)
    ticket_raw = canonical(ticket)
    if len(ticket_raw) > MAX_TICKET_BYTES:
        raise ValueError("HISTORICAL_TICKET_BOUND")
    bundle = hashlib.sha256(ticket_raw).hexdigest()
    destination = "bundle-" + bundle
    rootfd = _root_fd(root)
    try:
        lockfd = os.open(".p0251.owner-lock", os.O_RDWR | os.O_CREAT | _NOFOLLOW,
                         0o600, dir_fd=rootfd)
        try:
            info = os.fstat(lockfd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
                raise ValueError("OWNER_LOCK_FILE_UNSAFE")
            fcntl.flock(lockfd, fcntl.LOCK_EX)
            try:
                try:
                    os.stat(destination, dir_fd=rootfd, follow_symlinks=False)
                    existing = True
                except FileNotFoundError:
                    existing = False
                if existing:
                    return verify_bundle(root, bundle, original, ephemeral_authority_key)
                stage = ".pending-" + secrets.token_hex(16)
                os.mkdir(stage, 0o700, dir_fd=rootfd)
                stagefd = os.open(stage, os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                                  dir_fd=rootfd)
                try:
                    _write_once(stagefd, "ticket.json", ticket_raw)
                    for name, raw in sorted(blobs.items()):
                        _check_name(name)
                        _write_once(stagefd, name, raw)
                    os.fsync(stagefd)
                finally:
                    os.close(stagefd)
                if interrupt_before_publish:
                    raise RuntimeError("SYNTHETIC_INTERRUPTED_BEFORE_ATOMIC_PUBLICATION")
                os.rename(stage, destination, src_dir_fd=rootfd, dst_dir_fd=rootfd)
                os.fsync(rootfd)
                return verify_bundle(root, bundle, original, ephemeral_authority_key)
            finally:
                fcntl.flock(lockfd, fcntl.LOCK_UN)
        finally:
            os.close(lockfd)
    finally:
        os.close(rootfd)
