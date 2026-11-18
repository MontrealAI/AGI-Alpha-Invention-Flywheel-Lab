"""Local durable mission revisions. SQLite transactions own the state, never the model."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .economics import validate_case
from .routing import validate_options

PRODUCT = Path(__file__).resolve().parents[1]


class StateError(ValueError):
    """Bad input or stale client state."""


class Conflict(StateError):
    """A revision or idempotency key no longer matches."""


class Missing(StateError):
    """The requested private mission does not exist in this workspace."""


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def strict_json(data):
    def unique(pairs):
        mapping = {}
        for key, value in pairs:
            if key in mapping:
                raise StateError("Duplicate JSON key")
            mapping[key] = value
        return mapping
    def invalid(_):
        raise StateError("Non-finite number")
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def runtime_source():
    # Hash the trusted computation, including the checker and portable recipient path.
    # Editing a stylesheet or command-line help does not change an accepted calculation.
    paths = [PRODUCT / "ignition" / f"{n}.py" for n in
             ("construction","evaluation","delivery","portable","provider","research","controller","store","economics","model_schema","routing","development","pairing_specialist","endpoint_specialist","followup_specialist","change_specialist","fixed_delivery","change_recipient","evidence_specialist","scroll_specialist","quantum_specialist")]
    paths += [PRODUCT / "discovery_field" / name for name in ("protocol.py", "catalog.json")]
    paths += [PRODUCT / "discovery_field" / "decision_study" / name
              for name in ("private_sources.py", "evaluate.py", "missions.json", "sources.json", "publisher_observations.json")]
    bridge = PRODUCT.parent / "alpha-genesis-harness" / "bridge"
    paths += [bridge / name for name in ("__init__.py", "adapters.py", "output_schema.py", "streaming.py")]
    return digest({"python": [sys.implementation.name, *sys.version_info[:3]],
                   "files": {str(p.relative_to(PRODUCT.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(paths)}})


def clean_mission(mission):
    if not isinstance(mission, dict):
        raise StateError("mission must be an object")
    allowed = {"purpose", "beneficiary", "requirements", "authority", "resources", "time", "construction_spec"}
    if set(mission) - allowed:
        raise StateError("Unknown mission fields")
    purpose = mission.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 12000:
        raise StateError("Provide a purpose of 1–12000 characters")
    result = dict(mission, purpose=purpose.strip())
    beneficiary = result.setdefault("beneficiary", "")
    requirements = result.setdefault("requirements", [])
    if not isinstance(beneficiary, str) or not isinstance(requirements, list) or any(
            not isinstance(r, str) or not r.strip() for r in requirements):
        raise StateError("Invalid beneficiary or requirements")
    for field in ("authority", "resources", "time", "construction_spec"):
        if not isinstance(result.setdefault(field, {}), dict):
            raise StateError(f"{field} must be an object")
    try:
        validate_options(result["resources"])
    except ValueError as exc:
        raise StateError(str(exc)) from exc
    if "commercial_case" in result["resources"]:
        validate_case(result["resources"]["commercial_case"])
    auth = result["authority"]
    if set(auth) - {"local_model", "assisted_model", "public_sources", "allow_program_reuse"} or any(type(v) is not bool for v in auth.values()):
        raise StateError("Unsupported permission or non-boolean permission value")
    if "public_repositories" in result["resources"]:
        from .research import validate_public_repositories
        urls = validate_public_repositories(result["resources"]["public_repositories"])
        if urls and auth.get("public_sources") is not True:
            raise StateError("Public repository acquisition requires the mission's public_sources permission")
        result["resources"] = dict(result["resources"],public_repositories=urls)
    spec = result["construction_spec"]
    if spec and spec.get("purpose") != result["purpose"]:
        raise StateError("Construction specification must bind the exact mission purpose")
    return result


def event(state, stage, message, status=None):
    state["stage"] = stage
    if status:
        state["status"] = status
    state["events"].append({"stage": stage, "at": timestamp(), "message": message})


def initial_operation():
    return {"state": "active", "sequence": 0, "history": []}


def require_active(operation):
    if operation["state"] != "active":
        raise Conflict(f"Mission is {operation['state']} by operator control")


class Store:
    def __init__(self, directory):
        self.root = Path(directory).expanduser()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink() or (os.name == "posix" and
                (self.root.stat().st_mode & 0o077 or self.root.stat().st_uid != os.getuid())):
            raise StateError("Use a private, user-owned state directory (mode 0700)")
        self.db = self.root / "missions.sqlite3"
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS revisions (
                  id TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(id, version));
                CREATE TABLE IF NOT EXISTS requests (
                  key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL);
            """)

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.db, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, body, provider, runtime, *, run_id=None, base=None, inherited=None, specialist_source=None, source_sequence=None):
        if not isinstance(body, dict) or set(body) - {"mission", "sources", "request_id", "version"}:
            raise StateError("Unexpected mission request")
        key = body.get("request_id")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,120}", key):
            raise StateError("A stable request_id of 8–120 letters, digits, underscores or hyphens is required")
        mission = clean_mission(body.get("mission"))
        sources = body.get("sources", [])
        if not isinstance(sources, list) or len(sources) > 64 or any(not isinstance(s, dict) for s in sources):
            raise StateError("sources must be an array of up to 64 evidence records")
        if len(canonical([mission, sources]).encode()) > 2_000_000:
            raise StateError("Mission and source snapshot exceed transport limit")
        fp = digest([run_id, base, mission, sources, inherited])
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if run_id is not None:
                require_active(self._get(db, run_id)["operation"])
            if inherited:
                source = self._get(db, inherited["source_id"])
                require_active(source["operation"])
                if source["version"] != inherited["source_version"]:
                    raise Conflict("Source mission was amended")
                if source_sequence is not None and source["operation"]["sequence"] != source_sequence:
                    raise Conflict("Operator control changed during reuse")
            previous = db.execute("SELECT fingerprint,id,version FROM requests WHERE key=?", (key,)).fetchone()
            if previous:
                if previous[0] != fp:
                    raise Conflict("request_id was used with different inputs")
                return previous[1:]
            if run_id is None:
                run_id = uuid.uuid4().hex
                version = 1
            else:
                head = self._get(db, run_id)
                if type(base) is not int or head["version"] != base:
                    raise Conflict("Mission changed. Refresh before amending")
                version = base + 1
            state = dict(id=run_id, version=version, mission=mission, sources=sources, provider=provider,
                         runtime=runtime, input_sha256=digest([mission, sources]), status="queued", stage="intake",
                         operation=initial_operation(), events=[], calls={}, exchanges={}, source_result=None, research=None, contract=None,
                         routing=None, construction_attempts=[],
                         proposed_contract=None, contract_sha256=None, artifact=None, evaluation=None,
                         handoff=None, error=None, inherited=inherited, created_at=timestamp())
            if {"pairing_lab", "endpoint_lab", "followup", "change_desk", "evidence_action", "scroll_normalization", "quantum_multiplier"} & mission["resources"].keys():
                state["specialist_source"] = specialist_source
            event(state, "intake", "Mission and permission snapshot saved")
            db.execute("INSERT INTO revisions VALUES(?,?,?)", (run_id,version,canonical(state)))
            db.execute("INSERT INTO requests VALUES(?,?,?,?)", (key,fp,run_id,version))
            return run_id, version

    @staticmethod
    def _get(db, run_id, version=None):
        if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise Missing("Unknown mission")
        if version is None:
            row = db.execute("SELECT data FROM revisions WHERE id=? ORDER BY version DESC LIMIT 1", (run_id,)).fetchone()
        else:
            row = db.execute("SELECT data FROM revisions WHERE id=? AND version=?", (run_id,version)).fetchone()
        if row is None:
            raise Missing("Unknown mission")
        state = json.loads(row[0])
        state.setdefault("operation", initial_operation())
        return state

    def get(self, run_id, version=None):
        with self.connection() as db:
            return self._get(db, run_id, version)

    def set_operation(self, run_id, version, action, reason="", *, expected_sequence=None):
        target_states = {"pause": "paused", "resume": "active", "stop": "stopped"}
        if not isinstance(action, str) or action not in target_states:
            raise StateError("Choose pause, resume or stop")
        if not isinstance(reason, str) or len(reason) > 2000:
            raise StateError("Operator reason must be text of up to 2000 characters")
        if expected_sequence is not None and (type(expected_sequence) is not int or expected_sequence < 0):
            raise StateError("Expected control sequence must be a nonnegative integer")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._get(db, run_id)
            if type(version) is not int or state["version"] != version:
                raise Conflict("Stale mission version")
            control = state["operation"]
            if expected_sequence is not None and expected_sequence != control["sequence"]:
                raise Conflict("Operator control changed. Refresh before acting")
            target = target_states[action]
            if control["state"] == target:
                return state
            if control["state"] == "stopped":
                raise Conflict("A stopped mission cannot be restarted")
            control["sequence"] += 1
            control["state"] = target
            control["history"].append({"action": action, "state": target, "at": timestamp(),
                                       "sequence": control["sequence"], "reason": reason.strip()})
            db.execute("UPDATE revisions SET data=? WHERE id=? AND version=?", (canonical(state), run_id, version))
            return state

    def assert_operating(self, state):
        current = self.get(state["id"])
        if current["version"] != state["version"]:
            raise Conflict("Mission was amended")
        require_active(current["operation"])
        if current["operation"]["sequence"] != state["operation"]["sequence"]:
            raise Conflict("Operator control changed during this operation")

    def save(self, state, *, completed_call=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            head = self._get(db, state["id"])
            if state["version"] != head["version"]:
                raise Conflict("This work was superseded by a new mission revision")
            control = head["operation"]
            interrupted = (control["state"] != "active" or control["sequence"] != state["operation"]["sequence"])
            if interrupted:
                if not completed_call:
                    raise Conflict("Operator control changed. Work halted at its checkpoint")
                # The previously authorized call has already returned. Preserve its
                # receipt in the same revision without restoring any worker state.
                head["calls"].update(state["calls"])
                head["unsuccessful_calls"] = state.get("unsuccessful_calls", [])
                state = head
            else:
                state["operation"] = control
            db.execute("UPDATE revisions SET data=? WHERE id=? AND version=?",
                       (canonical(state),state["id"],state["version"]))
        if interrupted:
            raise Conflict("Operator control changed during the call. Its receipt was retained")

    def history(self, run_id):
        with self.connection() as db:
            self._get(db, run_id)
            states = [json.loads(row[0]) for row in db.execute(
                "SELECT data FROM revisions WHERE id=? ORDER BY version", (run_id,))]
            for state in states:
                state.setdefault("operation", initial_operation())
            return states

    def inventory(self):
        """Private operator summary; this read grants no reuse authority."""
        with self.connection() as db:
            rows = db.execute("""SELECT r.data FROM revisions r
                              JOIN (SELECT id, MAX(version) version FROM revisions GROUP BY id) h
                              ON r.id=h.id AND r.version=h.version ORDER BY r.rowid DESC""")
            for (raw,) in rows:
                state = json.loads(raw)
                report = state["research"] or {}
                yield {"id": state["id"], "version": state["version"], "purpose": state["mission"]["purpose"],
                       "observed_status": state["status"], "operation_state": state.get("operation", {}).get("state", "active"),
                       "recorded_at": state["events"][-1]["at"],
                       "decision": report.get("decision"), "frontier": report.get("frontier"),
                       "obstruction": state["error"] or report.get("decision_reason"),
                       "candidates": [{"title":c["title"], "obstruction":c["obstruction"], "test":c["test"]}
                                      for c in report.get("candidates", [])]}

    @contextlib.contextmanager
    def work_lock(self, run_id, revision=None):
        """An OS-released SQLite write lock per run spans expensive inference, never other missions."""
        self.get(run_id)
        if revision is not None and (type(revision) is not int or revision < 1):
            raise Conflict("Invalid mission revision")
        label = "delivery" if revision is None else str(revision)
        guard = sqlite3.connect(self.root / f"{run_id}.{label}.lock", timeout=0)
        try:
            try:
                guard.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                raise Conflict("A worker already owns this mission") from exc
            yield
        finally:
            guard.close()
