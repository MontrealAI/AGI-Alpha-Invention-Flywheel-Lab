"""Private workspace credentials. Only SHA-256 digests of random capabilities persist."""
import contextlib
import hashlib
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

from .store import StateError

WORKSPACE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
INVITE_TTL = 86400
SESSION_TTL = 7 * 86400
DAILY_ADMISSIONS = 20


def private_dir(path):
    path = Path(path).expanduser()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise StateError("Private directory must be user-owned, mode 0700 and not a symlink")
    return path.resolve()


def workspace_name(name):
    if not isinstance(name, str) or WORKSPACE.fullmatch(name) is None:
        raise StateError("Use a lowercase workspace alias of 1 through 48 letters, numbers or hyphens")
    return name


def token_hash(raw):
    if not isinstance(raw, str) or TOKEN.fullmatch(raw) is None:
        return ""
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


class Access:
    def __init__(self, root, environment):
        if environment not in {"production", "staging"}:
            raise StateError("Explicitly select staging or production")
        self.root = private_dir(root)
        self.workspaces = private_dir(self.root / "workspaces")
        self.path = self.root / "access.sqlite3"
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS setting (id INTEGER PRIMARY KEY CHECK(id=1), env TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS invitations (token TEXT PRIMARY KEY, workspace TEXT NOT NULL,
                    expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, workspace TEXT NOT NULL,
                    expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace (alias TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS admissions (workspace TEXT NOT NULL, day INTEGER NOT NULL,
                    request TEXT NOT NULL, PRIMARY KEY(workspace,day,request));
                CREATE TABLE IF NOT EXISTS audit (sequence INTEGER PRIMARY KEY, at INTEGER NOT NULL,
                    action TEXT NOT NULL, workspace TEXT);
            """)
            db.execute("INSERT OR IGNORE INTO setting VALUES (1, ?)", (environment,))
            if db.execute("SELECT env FROM setting WHERE id=1").fetchone()[0] != environment:
                raise StateError("This state directory belongs to a different environment")

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def record(db, now, action, tenant):
        db.execute("INSERT INTO audit(at,action,workspace) VALUES(?,?,?)", (now, action, tenant))

    def issue(self, alias):
        alias = workspace_name(alias)
        raw = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO workspace VALUES (?)", (alias,))
            db.execute("DELETE FROM invitations WHERE workspace=? OR expires<=?", (alias, now))
            db.execute("INSERT INTO invitations VALUES (?,?,?)", (token_hash(raw), alias, now + INVITE_TTL))
            self.record(db, now, "invite-issued", alias)
        return raw

    def exchange(self, raw):
        digest = token_hash(raw)
        if not digest:
            return None
        now, session = int(time.time()), secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT workspace FROM invitations WHERE token=? AND expires>?", (digest, now)).fetchone()
            if not row:
                return None
            db.execute("DELETE FROM invitations WHERE token=?", (digest,))
            db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (token_hash(session), row[0], now + SESSION_TTL))
            self.record(db, now, "session-created", row[0])
        return session

    def principal(self, raw):
        digest = token_hash(raw)
        if digest:
            with self.connection() as db:
                row = db.execute("SELECT workspace FROM sessions WHERE token=? AND expires>?",
                                 (digest, int(time.time()))).fetchone()
                return row[0] if row else None
        return None

    def logout(self, raw):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT workspace FROM sessions WHERE token=?", (token_hash(raw),)).fetchone()
            if row:
                db.execute("DELETE FROM sessions WHERE token=?", (token_hash(raw),))
                self.record(db, int(time.time()), "session-closed", row[0])

    def revoke(self, alias):
        workspace_name(alias)
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE workspace=?", (alias,))
            db.execute("DELETE FROM invitations WHERE workspace=?", (alias,))
            self.record(db, int(time.time()), "access-revoked", alias)

    def tenants(self):
        with self.connection() as db:
            return [r[0] for r in db.execute("SELECT alias FROM workspace ORDER BY alias")]

    def admit(self, alias, request):
        if not isinstance(request, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,120}", request):
            raise StateError("Supply a stable request identifier")
        now = int(time.time())
        day = now // 86400
        digest = hashlib.sha256(request.encode()).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM admissions WHERE day<?", (day-1,))
            if db.execute("SELECT 1 FROM admissions WHERE workspace=? AND day=? AND request=?",
                          (alias, day, digest)).fetchone():
                return
            used = db.execute("SELECT COUNT(*) FROM admissions WHERE workspace=? AND day=?", (alias, day)).fetchone()[0]
            if used >= DAILY_ADMISSIONS:
                raise StateError("Daily workspace admission limit reached; existing missions remain accessible")
            db.execute("INSERT INTO admissions VALUES (?,?,?)", (alias, day, digest))
            self.record(db, now, "mission-request-admitted", alias)
