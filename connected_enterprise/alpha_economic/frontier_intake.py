"""Durable, private, nonfinancial intake watcher for buyer-signed frontier work.

The worker watches only locally authorized, signed JSON envelopes. It does not
crawl leads, contact customers, accept a checkout notification as revenue, or
create artificial demand. The ALPHA engine independently controls payments.
"""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import hashlib
import math
import os
from pathlib import Path
import stat
import time

from .core import read, safe
from .frontier_bridge import submit_qualified


class QualifiedInbox:
    def __init__(self, engine, reservoir):
        self.engine, self.reservoir = engine, reservoir
        self.root = safe(engine.root / "frontier-intake")
        self.root.mkdir(exist_ok=True, mode=0o700)
        if self.root.stat().st_mode & 0o077:
            raise ValueError("PRIVATE_QUALIFIED_INBOX_REQUIRED")
        self.inbox, self.processed, self.rejected = (
            self.root / "inbox", self.root / "processed", self.root / "rejected")
        for directory in (self.inbox, self.processed, self.rejected):
            directory.mkdir(exist_ok=True, mode=0o700)
            if directory.stat().st_mode & 0o077:
                raise ValueError("PRIVATE_QUALIFIED_INBOX_REQUIRED")

    @contextmanager
    def lock(self):
        path = safe(self.root / "intake.lock")
        with open(path, "a+b") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("QUALIFIED_INTAKE_WORKER_ALREADY_RUNNING") from None
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _archive(self, path, directory):
        path = safe(path)
        # Stable content hash avoids collisions across reusing a filename;
        # second receipt is idempotent on the ALPHA job id.
        raw = path.read_bytes()
        target = safe(directory / (hashlib.sha256(raw).hexdigest() + ".json"))
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError("ARCHIVED_BUYER_PAYLOAD_CONFLICT")
            path.unlink()
        else:
            os.rename(path, target)
        return target

    def scan(self, now=None):
        """One pass. Deferred opportunity remains in place until qualified."""
        receipts = []
        for candidate in sorted(self.inbox.iterdir()):
            if not candidate.name.endswith(".json") or candidate.name.startswith("."):
                continue
            # Symlinks/hardlinks and shared writable contents cannot be admitted.
            if candidate.is_symlink() or not candidate.is_file():
                receipts.append({"file": candidate.name, "status": "REFUSED_UNSAFE_FILE"})
                continue
            st = candidate.stat()
            if st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > 2_000_000:
                receipts.append({"file": candidate.name, "status": "REFUSED_UNSAFE_FILE"})
                continue
            try:
                bundle = read(candidate)
                receipt = submit_qualified(
                    self.engine, self.reservoir, bundle, now=now)
            except ValueError as exc:
                reason = str(exc)
                if reason == "MATCHED_REPORTED_CROSSING_REQUIRED":
                    receipts.append({"file": candidate.name,
                                     "status": "DEFERRED_NOT_YET_QUALIFIED"})
                    continue
                # A failed preflight cannot create a job; keep evidence private
                # for review rather than permanently deleting buyer material.
                target = self._archive(candidate, self.rejected)
                receipts.append({"file": candidate.name, "status": "REJECTED",
                                 "reason": reason[:120], "archive_sha256": target.stem})
                continue
            except (PermissionError, TypeError, KeyError) as exc:
                target = self._archive(candidate, self.rejected)
                receipts.append({"file": candidate.name, "status": "REJECTED",
                                 "reason": type(exc).__name__, "archive_sha256": target.stem})
                continue
            # Never archive as successful before submit_qualified returned.
            target = self._archive(candidate, self.processed)
            receipts.append({"file": candidate.name, "status": "ORDER_ADMITTED_NOT_PAID",
                             "job": receipt["job"], "archive_sha256": target.stem})
        return receipts

    def watch(self, *, interval=5.0, cycles=None, stopped=lambda: False):
        if (type(interval) not in (int, float) or not math.isfinite(interval)
            or interval < 0.05 or
            (cycles is not None and (type(cycles) is not int or cycles < 1))):
            raise ValueError("POSITIVE_BOUNDED_WATCH_INTERVAL_REQUIRED")
        ticks, processed = 0, []
        with self.lock():
            while not stopped() and (cycles is None or ticks < cycles):
                processed.extend(self.scan())
                ticks += 1
                if cycles is None or ticks < cycles:
                    time.sleep(interval)
        return {"cycles": ticks, "receipts": processed,
                "financial_authority_added": False,
                "real_payment_verified": False}
