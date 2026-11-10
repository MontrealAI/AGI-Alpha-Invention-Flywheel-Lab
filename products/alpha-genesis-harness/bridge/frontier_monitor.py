# SPDX-License-Identifier: Apache-2.0
"""Explicitly authorized, source-bound frontier observation; no model inference.

Only the existing public-source transport performs network access. Byte changes
reopen questions in GENESIS NEXT; they never certify a new capability.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .adapters import BridgeError, retrieve_source, strict_json
from .workflows import _atomic, _regular, encoded, require

SHA = re.compile(r"[a-f0-9]{64}\Z")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
MAX_JOBS = 100
HISTORY_LIMIT = 20
SCOPE = "Reported public-source observations only. Retrieval time is not publication time; changed bytes are not a reproduced capability or promotion authority."
_OWNERS = {}
_OWNER_LOCK = threading.RLock()


def stamp(seconds=None):
    return datetime.fromtimestamp(time.time() if seconds is None else seconds, timezone.utc).isoformat()


class FrontierMonitorService:
    """One process owner per private workspace; stored restart consent is explicit."""
    def __init__(self, workflows, genesis_next, *, fetcher=None, clock=time.time):
        self.workflows, self.genesis = workflows, genesis_next
        self.runtime = workflows.runtime
        self.fetcher = retrieve_source if fetcher is None else fetcher
        self.clock = clock
        self.root = workflows.root / "frontier-monitor"
        require(not self.root.is_symlink(), "Frontier workspace cannot be a symlink.", "MONITOR_INTEGRITY")
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.path = self.root / "state.json"
        self.lock = workflows._lock("frontier-monitor")
        self._closed = False
        self._wake = threading.Event()
        self._thread = None
        self._inflight = set()
        with _OWNER_LOCK:
            previous = _OWNERS.get(str(self.root))
            require(previous is None or previous._closed, "Another frontier monitor owns this workspace.", "MONITOR_OWNED")
            _OWNERS[str(self.root)] = self
        try:
            with self.lock:
                if not self.path.exists():
                    self._save({"schema": "genesis-frontier-monitor/v1", "revision": 0, "jobs": [], "removed_count": 0})
                state = self._load()
                changed = False
                for job in state["jobs"]:
                    if job["enabled"] and not job["consent"]["resume_after_restart"]:
                        job["enabled"] = False
                        job["epoch"] += 1
                        job["last_status"] = "PAUSED_AFTER_RESTART"
                        changed = True
                    if job["last_status"] == "POLLING":
                        job["last_status"] = "INTERRUPTED"
                        self._history(job, "INTERRUPTED", "Previous source request has no committed result.")
                        changed = True
                if changed:
                    self._save(state)
                should_resume = any(j["enabled"] and j["consent"]["resume_after_restart"] for j in state["jobs"])
            if should_resume:
                self._ensure_worker()
        except Exception:
            self.close()
            raise

    def _local_only(self):
        config = getattr(self.runtime, "config", {})
        return bool(getattr(self.runtime, "local_only", False) or (isinstance(config, dict) and config.get("local_only") is True))

    def _hosts(self):
        return frozenset(getattr(self.runtime, "source_hosts", ()))

    def _network_allowed(self):
        require(not self._closed, "Frontier monitor is closed.", "MONITOR_CLOSED")
        require(not self._local_only(), "Local-only mode disables external frontier observations.", "LOCAL_ONLY")

    def _url(self, value):
        require(isinstance(value, str) and 0 < len(value) <= 2000 and not any(x in value for x in "\r\n\x00"), "Use a bounded public HTTPS source URL.", "SOURCE_URL")
        try:
            parsed = urlsplit(value)
            safe = (parsed.scheme == "https" and parsed.hostname in self._hosts() and parsed.port in {None, 443}
                    and not parsed.username and not parsed.password and not parsed.fragment)
        except ValueError:
            safe = False
        require(safe, "Use an exact configured HTTPS source host without credentials or fragments.", "SOURCE_URL")
        return value

    def _load(self):
        value = strict_json(_regular(self.path, 4 * 1024 * 1024))
        require(isinstance(value, dict) and set(value) == {"state", "mac"}, "Frontier state envelope is invalid.", "MONITOR_INTEGRITY")
        state = value["state"]
        mac = hmac.new(self.workflows._key, encoded(state), hashlib.sha256).hexdigest()
        require(isinstance(value["mac"], str) and hmac.compare_digest(value["mac"], mac), "Frontier state authentication failed.", "MONITOR_INTEGRITY")
        require(isinstance(state, dict) and state.get("schema") == "genesis-frontier-monitor/v1"
                and isinstance(state.get("jobs"), list) and len(state["jobs"]) <= MAX_JOBS,
                "Frontier inventory is invalid.", "MONITOR_INTEGRITY")
        return state

    def _save(self, state):
        state["revision"] += 1
        body = encoded(state)
        require(len(body) <= 4 * 1024 * 1024, "Frontier state reached its processing envelope.", "MONITOR_SIZE")
        _atomic(self.path, encoded({"state": state, "mac": hmac.new(self.workflows._key, body, hashlib.sha256).hexdigest()}))

    def _view(self, state):
        return {"jobs": copy.deepcopy(state["jobs"]), "revision": state["revision"], "removed_count": state["removed_count"],
                "source_hosts": sorted(self._hosts()), "local_only": self._local_only(),
                "worker_running": bool(self._thread and self._thread.is_alive() and not self._closed), "scope": SCOPE}

    def status(self):
        with self.lock:
            return self._view(self._load())

    @staticmethod
    def _job(state, data):
        require(isinstance(data, dict) and isinstance(data.get("job_id"), str), "Select a frontier monitor job.", "MONITOR_INPUT")
        job = next((j for j in state["jobs"] if j["id"] == data["job_id"]), None)
        require(job is not None, "Frontier monitor job does not exist.", "MONITOR_NOT_FOUND")
        return job

    def _history(self, job, status, message, **details):
        job["history"].append({"at": stamp(self.clock()), "status": status, "message": message, **details})
        if len(job["history"]) > HISTORY_LIMIT:
            job["history_omitted"] += len(job["history"]) - HISTORY_LIMIT
            job["history"] = job["history"][-HISTORY_LIMIT:]

    def add(self, data):
        self._network_allowed()
        require(isinstance(data, dict) and data.get("authorize") is True, "Explicitly authorize public-source observation for this URL and interval.", "MONITOR_CONSENT")
        require(not set(data) - {"url", "title", "capability_ids", "interval_seconds", "authorize", "resume_after_restart"}, "Unsupported frontier monitor fields.", "MONITOR_INPUT")
        url = self._url(data.get("url"))
        title = data.get("title")
        require(isinstance(title, str) and 0 < len(title) <= 300, "Provide a source title of at most 300 characters.", "MONITOR_INPUT")
        ids = data.get("capability_ids", [])
        require(isinstance(ids, list) and 0 < len(ids) <= 100 and all(isinstance(i, str) and IDENT.fullmatch(i) for i in ids), "Associate one or more existing or proposed capability IDs.", "MONITOR_INPUT")
        interval = data.get("interval_seconds", 3600)
        require(type(interval) is int and 60 <= interval <= 31536000, "Choose a polling interval between 60 seconds and one year.", "MONITOR_INPUT")
        resume = data.get("resume_after_restart", False)
        require(type(resume) is bool, "Restart consent must be an explicit boolean.", "MONITOR_CONSENT")
        with self.lock:
            self._network_allowed()
            state = self._load()
            require(len(state["jobs"]) < MAX_JOBS, "This monitor workspace supports at most 100 source jobs.", "MONITOR_SIZE")
            require(not any(j["url"] == url for j in state["jobs"]), "This exact source already has a monitor job.", "MONITOR_DUPLICATE")
            job = {"id": "frontier_" + secrets.token_hex(8), "title": title, "url": url, "capability_ids": sorted(set(ids)),
                   "interval_seconds": interval, "enabled": False, "epoch": 0,
                   "consent": {"authorized": True, "at": stamp(self.clock()), "resume_after_restart": resume,
                               "scope": "Observe this exact public source and reopen associated questions; no inference, spending or promotion."},
                   "next_poll_at": None, "last_sha256": None, "last_replayed_sha256": None, "last_observed_at": None,
                   "last_status": "NEVER_POLLED", "poll_count": 0, "change_count": 0, "failure_count": 0,
                   "history": [], "history_omitted": 0}
            state["jobs"].append(job)
            self._save(state)
            return {"job": copy.deepcopy(job), "state": self._view(state)}

    def poll(self, data, *, _scheduled=False):
        self._network_allowed()
        with self.lock:
            self._network_allowed()
            state = self._load()
            job = self._job(state, data)
            require(not _scheduled or job["enabled"], "Periodic observation was paused before dispatch.", "MONITOR_PAUSED")
            require(job["consent"].get("authorized") is True, "Source observation consent is missing.", "MONITOR_CONSENT")
            self._url(job["url"])
            require(job["id"] not in self._inflight, "This source already has an active request.", "MONITOR_BUSY")
            self._inflight.add(job["id"])
            snapshot = copy.deepcopy(job)
            job["poll_count"] += 1
            job["last_status"] = "POLLING"
            job["next_poll_at"] = self.clock() + job["interval_seconds"]
            self._save(state)
        try:
            try:
                observed = self.fetcher(snapshot["url"], self._hosts(), snapshot["last_sha256"])
                require(isinstance(observed, dict) and observed.get("url") == snapshot["url"] and isinstance(observed.get("sha256"), str)
                        and SHA.fullmatch(observed["sha256"]), "Source transport returned invalid identity evidence.", "MONITOR_SOURCE")
                observed_at = observed.get("retrieved_at")
                require(isinstance(observed_at, str), "Source observation timestamp is missing.", "MONITOR_SOURCE")
                fetched_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                require(fetched_at.tzinfo is not None and fetched_at <= datetime.now(timezone.utc), "Source observation timestamp is invalid.", "MONITOR_SOURCE")
                error_code = None
            except BridgeError as error:
                observed, error_code = None, error.code
            except Exception:
                observed, error_code = None, "SOURCE_FAILURE"
            with self.lock:
                if self._closed:
                    return {"observation": {"status": "DISCARDED", "reason": "Monitor closed after request dispatch."}, "state": self._view(self._load())}
                state = self._load()
                job = next((j for j in state["jobs"] if j["id"] == snapshot["id"]), None)
                if job is None:
                    return {"observation": {"status": "DISCARDED", "reason": "Job removed after request dispatch."}, "state": self._view(state)}
                if job["epoch"] != snapshot["epoch"] or self._local_only():
                    job["last_status"] = "DISCARDED"
                    self._history(job, "DISCARDED", "Stopped or local-only policy changed after dispatch; no replay committed.")
                    self._save(state)
                    return {"observation": {"status": "DISCARDED"}, "state": self._view(state)}
                if error_code:
                    job["last_status"] = "FAILED"
                    job["failure_count"] += 1
                    self._history(job, "FAILED", "Source request failed; earlier successful evidence is unchanged.", error_code=error_code)
                    self._save(state)
                    return {"observation": {"status": "FAILED", "error_code": error_code}, "state": self._view(state)}
                sha = observed["sha256"]
                old_sha = job["last_sha256"]
                classification = "INITIAL_OBSERVATION" if old_sha is None else "UNCHANGED" if old_sha == sha else "CHANGED"
                if classification == "CHANGED":
                    job["change_count"] += 1
                job["last_sha256"], job["last_observed_at"] = sha, observed["retrieved_at"]
                replayed = False
                if sha != job["last_replayed_sha256"]:
                    try:
                        self.genesis.replay({"title": job["title"], "url": job["url"], "observed_at": observed["retrieved_at"],
                            "content_sha256": sha, "capability_ids": job["capability_ids"], "evidence_status": "reported"})
                        job["last_replayed_sha256"] = sha
                        replayed = True
                    except Exception:
                        # Keep fetched identity and retry the pending replay on the
                        # next observation; do not assert successful reactivation.
                        job["failure_count"] += 1
                        self._history(job, "REPLAY_FAILED", "Observed bytes retained; GENESIS reactivation remains pending.", sha256=sha)
                job["last_status"] = classification
                self._history(job, classification, "Public bytes observed; relevance and capability claims require independent verification.",
                              sha256=sha, previous_sha256=old_sha, replayed=replayed)
                self._save(state)
                return {"observation": {"status": classification, "sha256": sha, "previous_sha256": old_sha,
                                        "retrieved_at": observed["retrieved_at"], "replayed": replayed, "scope": SCOPE}, "state": self._view(state)}
        finally:
            with self.lock:
                self._inflight.discard(snapshot["id"])

    def start(self, data):
        self._network_allowed()
        with self.lock:
            self._network_allowed()
            state = self._load()
            job = self._job(state, data)
            require(job["consent"].get("authorized") is True, "Explicit source consent is missing.", "MONITOR_CONSENT")
            self._url(job["url"])
            job["enabled"] = True
            if job["next_poll_at"] is None:
                job["next_poll_at"] = self.clock()
            self._save(state)
        self._ensure_worker()
        self._wake.set()
        return {"job": copy.deepcopy(job), "state": self.status()}

    def stop(self, data):
        with self.lock:
            require(not self._closed, "Frontier monitor is closed.", "MONITOR_CLOSED")
            state = self._load()
            job = self._job(state, data)
            job["enabled"] = False
            job["epoch"] += 1
            job["last_status"] = "PAUSED"
            self._save(state)
            return {"job": copy.deepcopy(job), "state": self._view(state)}

    def remove(self, data):
        with self.lock:
            require(not self._closed, "Frontier monitor is closed.", "MONITOR_CLOSED")
            state = self._load()
            job = self._job(state, data)
            state["jobs"].remove(job)
            state["removed_count"] += 1
            self._save(state)
            return {"removed": job["id"], "state": self._view(state)}

    def _ensure_worker(self):
        with self.lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, name="genesis-frontier-monitor", daemon=True)
                self._thread.start()

    def _loop(self):
        while not self._closed:
            try:
                with self.lock:
                    state = self._load()
                    due = [j["id"] for j in state["jobs"] if j["enabled"] and j["id"] not in self._inflight
                           and j["next_poll_at"] is not None and j["next_poll_at"] <= self.clock()]
                for ident in due:
                    if self._closed:
                        break
                    try:
                        self.poll({"job_id": ident}, _scheduled=True)
                    except BridgeError as error:
                        with self.lock:
                            state = self._load()
                            job = next((j for j in state["jobs"] if j["id"] == ident), None)
                            if job and not self._closed:
                                job["enabled"] = False
                                job["last_status"] = "FAILED"
                                job["failure_count"] += 1
                                self._history(job, "FAILED", "Periodic observation paused by a permission or source boundary.", error_code=error.code)
                                self._save(state)
            except Exception:
                # Integrity/I/O failures terminate background work without
                # inventing a clean state or weakening authentication.
                return
            self._wake.wait(0.5)
            self._wake.clear()

    def close(self):
        with self.lock:
            self._closed = True
        self._wake.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
        with _OWNER_LOCK:
            if _OWNERS.get(str(self.root)) is self:
                _OWNERS.pop(str(self.root), None)
