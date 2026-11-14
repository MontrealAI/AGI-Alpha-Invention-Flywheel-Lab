"""Non-operational P0 design fixture: cross-process prepare arbitration only.

Does not authorize financial source transitions, verify HMAC, or operate accounts.
A real integration MUST interlock every native writer and use owner-held authority.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path

INTENT = "PREPARE_INTENT.json"
PREPARED = "PREPARE_RESULT.json"
LOCK = ".prepare.lock"
MAX_BYTES = 1_000_000


class Refusal(ValueError):
    """Fail-closed control-plane refusal, not an account validation verdict."""


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _safe_root(path):
    root = Path(os.path.abspath(path))
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise Refusal("REGULAR_EXISTING_GATE_DIRECTORY_REQUIRED")
    return root


def _read(root, name):
    p = root / name
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Refusal("REFUSE_NONREGULAR_RECORD") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
            raise Refusal("REFUSE_NONREGULAR_OR_UNBOUNDED_RECORD")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise Refusal("REFUSE_UNBOUNDED_RECORD")
        value = json.loads(raw)
        if not isinstance(value, dict) or _bytes(value) + b"\n" != raw:
            raise Refusal("REFUSE_NONCANONICAL_RECORD")
        return value
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise Refusal("REFUSE_CORRUPT_RECORD") from exc
    finally:
        os.close(fd)


def _create(root, name, value):
    raw = _bytes(value) + b"\n"
    if len(raw) > MAX_BYTES:
        raise Refusal("REFUSE_UNBOUNDED_RECORD")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(root / name, flags, 0o600)
    except FileExistsError as exc:
        raise Refusal("IMMUTABLE_PREPARE_RECORD_ALREADY_EXISTS") from exc
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)
    dirfd = os.open(root, os.O_DIRECTORY | os.O_RDONLY | os.O_CLOEXEC)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)


def prepare_once(directory, request, *, observed_checkpoint, authorization_callback):
    """Demonstrate *one* durable prepared request; intentionally no reset/advance.

    request: {id:str, expected_checkpoint_sha256:64 lowercase hex,
              target_source_sha256:64 lowercase hex}.
    observed_checkpoint(): observed source checkpoint digest (mockable in fixture;
       real implementation must authenticate it under the same account writer lease).
    authorization_callback(request): external owner-authorized operation (mock only here).

    This routine DOES NOT safely integrate with an existing financial engine. Its
    standalone lock is not recognized by the production engine or signer. Never
    substitute this for native HMAC/JournalAccount checks or call it as a CLI.
    """
    if (not isinstance(request, dict) or set(request) != {
            "id", "expected_checkpoint_sha256", "target_source_sha256"}
        or type(request["id"]) is not str or not 1 <= len(request["id"]) <= 128
        or not all(c.isalnum() or c in "-_" for c in request["id"])
        or any(type(request[k]) is not str or len(request[k]) != 64
               or any(c not in "0123456789abcdef" for c in request[k])
               for k in ("expected_checkpoint_sha256", "target_source_sha256"))):
        raise Refusal("EXACT_PREPARE_REQUEST_REQUIRED")
    root = _safe_root(directory)
    lockfd = os.open(root / LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(lockfd).st_mode):
            raise Refusal("REGULAR_WRITER_LOCK_REQUIRED")
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        intent = _read(root, INTENT)
        prepared = _read(root, PREPARED)
        if prepared is not None and intent is None:
            raise Refusal("ORPHAN_PREPARED_RECORD_REFUSED")
        if intent is not None:
            if set(intent) != {"schema", "request", "request_sha256"} or intent["schema"] != "transition156/intent/v1" or _sha(intent["request"]) != intent["request_sha256"]:
                raise Refusal("CORRUPT_PREPARE_INTENT_REFUSED")
            if intent["request"] != request:
                raise Refusal("DIFFERENT_PENDING_REQUEST_REFUSED")
            if prepared is None:
                raise Refusal("INCOMPLETE_PREPARE_REQUIRES_OWNER_RECOVERY")
            if (set(prepared) != {"schema", "request_sha256", "receipt", "receipt_sha256"}
                or prepared["schema"] != "transition156/prepared/v1"
                or prepared["request_sha256"] != intent["request_sha256"]
                or _sha(prepared["receipt"]) != prepared["receipt_sha256"]):
                raise Refusal("CORRUPT_PREPARED_RECORD_REFUSED")
            return prepared["receipt"]
        if prepared is not None:
            raise Refusal("ORPHAN_PREPARED_RECORD_REFUSED")
        if observed_checkpoint() != request["expected_checkpoint_sha256"]:
            raise Refusal("STALE_PREPARE_CHECKPOINT_REFUSED")
        intent = {"schema": "transition156/intent/v1", "request": request,
                  "request_sha256": _sha(request)}
        # Create-only prior to external authorization: a crash freezes the
        # intent and requires owner-controlled reconciliation, not a re-sign.
        _create(root, INTENT, intent)
        receipt = authorization_callback(request)
        if not isinstance(receipt, dict):
            raise Refusal("EXACT_AUTHORIZATION_RESULT_REQUIRED")
        prepared = {"schema": "transition156/prepared/v1",
                    "request_sha256": intent["request_sha256"],
                    "receipt": receipt, "receipt_sha256": _sha(receipt)}
        _create(root, PREPARED, prepared)
        return receipt
    finally:
        fcntl.flock(lockfd, fcntl.LOCK_UN)
        os.close(lockfd)
