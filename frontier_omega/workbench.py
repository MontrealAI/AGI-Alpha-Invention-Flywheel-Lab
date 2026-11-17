"""Private FRONTIER Ω inventory workbench, reusing Reservoir and release radar.

A local research workspace: never a buyer, payment authority, or profit ledger.
Python 3.10+, POSIX. No third-party runtime packages or model API required.
"""
from __future__ import annotations

import argparse
import base64
import re
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import sqlite3
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .core import (Reservoir, COSTS, canonical, parse, sha, identifier, day,
                   load_file, validate_problem, validate_frontier, validate_trial)
from . import releases

STAGES = ("BLOCKED", "RETEST", "TESTING", "PILOT_REVIEW", "ARCHIVED")
TASK_STATES = ("PENDING", "RUNNING", "DONE", "DISMISSED")
ASSETS = Path(__file__).parent
MAX_REQUEST = 2_000_000


def text(value, maximum=4000):
    if type(value) is not str or len(value) > maximum:
        raise ValueError("BOUNDED_TEXT_REQUIRED")
    return value.strip()


def money(value):
    """Nullable USD decimal string -> exact integer microUSD, never float."""
    if value is None or value == "":
        return None
    if type(value) is not str or len(value) > 40:
        raise ValueError("DECIMAL_USD_STRING_REQUIRED")
    try:
        d = Decimal(value)
        if not d.is_finite() or d < 0:
            raise ValueError("NONNEGATIVE_USD_WITH_AT_MOST_SIX_DECIMALS")
        tup = d.as_tuple()
        if tup.exponent < -6 or tup.exponent > 60 or len(tup.digits) > 72:
            raise ValueError("BOUNDED_EXACT_USD_SCALAR_REQUIRED")
        # Work directly on digits: Decimal context precision must not round money.
        coefficient = int("".join(map(str, tup.digits)))
        return coefficient * 10 ** (tup.exponent + 6)
    except InvalidOperation:
        raise ValueError("INVALID_USD_AMOUNT") from None


def economics(value):
    """Conservative/optimistic scenario contribution, NOT an economic crossing."""
    fields = {"price", "costs", "loss", "probability_bps", "basis"}
    if type(value) is not dict or set(value) != fields:
        raise ValueError("EXACT_SCENARIO_FIELDS_REQUIRED")
    if type(value["costs"]) is not dict or set(value["costs"]) != set(COSTS):
        raise ValueError("TEN_COMPLETE_COST_CATEGORIES_REQUIRED")
    def pair(a):
        if type(a) is not list or len(a) != 2:
            raise ValueError("LOW_HIGH_PAIR_REQUIRED")
        lo, hi = map(money, a)
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("LOW_EXCEEDS_HIGH")
        return lo, hi
    price, loss = pair(value["price"]), pair(value["loss"])
    costs = [pair(value["costs"][k]) for k in COSTS]
    probs = value["probability_bps"]
    if (type(probs) is not list or len(probs) != 2 or
        any(v is not None and (type(v) is not int or not 0 <= v <= 10000) for v in probs)):
        raise ValueError("PROBABILITY_BASIS_POINTS_REQUIRED")
    if None not in probs and probs[0] > probs[1]:
        raise ValueError("LOW_EXCEEDS_HIGH")
    text(value["basis"])
    known = all(v is not None for p in [price, loss, probs] + costs for v in p)
    if known and not value["basis"].strip():
        raise ValueError("ESTIMATE_BASIS_REQUIRED")
    return {"status": "ESTIMATED" if known else "UNKNOWN", "currency": "USD",
            "low_microUSD_x10000": price[0] * probs[0] - 10000 * (sum(c[1] for c in costs) + loss[1]) if known else None,
            "high_microUSD_x10000": price[1] * probs[1] - 10000 * (sum(c[0] for c in costs) + loss[0]) if known else None,
            "actual_profit": None, "execution_authorized": False}


def blank_profile():
    return {"stage": "BLOCKED", "priority": 2, "value_hypothesis": "",
            "unlock_condition": "", "buyer_pathway": "", "next_review": None,
            "note": "", "economics": {"price": [None, None],
            "costs": {k: [None, None] for k in COSTS}, "loss": [None, None],
            "probability_bps": [None, None], "basis": ""}}


def profile_valid(body):
    if type(body) is not dict or set(body) != set(blank_profile()):
        raise ValueError("EXACT_PROFILE_FIELDS_REQUIRED")
    if body["stage"] not in STAGES or type(body["priority"]) is not int or not 1 <= body["priority"] <= 3:
        raise ValueError("INVALID_RESEARCH_STAGE_OR_PRIORITY")
    for k in ("value_hypothesis", "unlock_condition", "buyer_pathway", "note"):
        text(body[k])
    if body["next_review"] is not None:
        day(body["next_review"])
    economics(body["economics"])
    return body


def task_valid(body):
    if (type(body) is not dict or set(body) != {"status", "note"}
        or body["status"] not in TASK_STATES):
        raise ValueError("EXACT_RETEST_STATUS_REQUIRED")
    text(body["note"])
    if body["status"] in ("DONE", "DISMISSED") and not body["note"].strip():
        raise ValueError("RETEST_DISPOSITION_NEEDS_EVIDENCE_OR_REASON")
    return body


def storage_preflight(root):
    root = Path(os.path.abspath(root))
    for p in (root, *root.parents):
        if p.is_symlink():
            raise ValueError("SYMLINK_STORAGE_REFUSED")
    for name in ("frontier.sqlite", "frontier.sqlite-wal", "frontier.sqlite-shm",
                 "frontier.sqlite-journal", "frontier.lock", "inbox", "processed", "rejected"):
        p = root / name
        if p.is_symlink() or (p.is_file() and p.stat().st_nlink != 1):
            raise ValueError("LINKED_STORAGE_REFUSED")
    return root


class Workbench:
    def __init__(self, root, config=None, *, network=False, fetch=None):
        self.reservoir = Reservoir(storage_preflight(root))
        self.config = releases.validate_config(config) if config is not None else None
        self.network, self.fetch = bool(network), fetch
        self.guard = threading.RLock()
        self.last_poll = None
        with self.reservoir.tx() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS workbench_history(
                kind TEXT NOT NULL,target TEXT NOT NULL,revision INTEGER NOT NULL,
                body TEXT NOT NULL,hash TEXT NOT NULL,updated_at TEXT NOT NULL,
                PRIMARY KEY(kind,target,revision))""")
        self.audit()

    def _latest(self, c, kind, target):
        row = c.execute("SELECT * FROM workbench_history WHERE kind=? AND target=? ORDER BY revision DESC LIMIT 1",
                        (kind, target)).fetchone()
        if row:
            body = parse(row["body"])
            if sha(body) != row["hash"]:
                raise ValueError("WORKBENCH_HISTORY_INTEGRITY_FAILED")
            return {"revision": row["revision"], "body": body, "updated_at": row["updated_at"]}
        return {"revision": 0, "body": blank_profile() if kind == "profile" else {"status": "PENDING", "note": ""}, "updated_at": None}

    def _append(self, c, kind, target, body, expected):
        if kind not in ("profile", "task"):
            raise ValueError("INVALID_NOTE_KIND")
        table = "problems" if kind == "profile" else "triggers"
        if not c.execute("SELECT 1 FROM " + table + " WHERE id=?", (target,)).fetchone():
            raise ValueError("UNKNOWN_NOTE_TARGET")
        (profile_valid if kind == "profile" else task_valid)(body)
        old = self._latest(c, kind, target)
        if type(expected) is not int or old["revision"] != expected:
            raise ValueError("REVISION_CONFLICT_RELOAD_BEFORE_SAVING")
        if old["body"] == body:
            return old
        stamp = datetime.now(timezone.utc).isoformat()
        c.execute("INSERT INTO workbench_history VALUES(?,?,?,?,?,?)",
                  (kind, target, expected + 1, canonical(body).decode(), sha(body), stamp))
        return {"revision": expected + 1, "body": body, "updated_at": stamp}

    def save(self, kind, target, body, expected):
        with self.guard, self.reservoir.tx() as c:
            return self._append(c, kind, target, body, expected)

    def add(self, problem):
        with self.guard:
            return self.reservoir.add(validate_problem(problem))

    def audit(self):
        with self.guard:
            report = self.reservoir.audit()
            with self.reservoir.tx() as c:
                rows = c.execute("SELECT * FROM workbench_history ORDER BY kind,target,revision").fetchall()
                seen = {}
                for r in rows:
                    b = parse(r["body"])
                    k = (r["kind"], r["target"])
                    if r["revision"] != seen.get(k, 0) + 1 or sha(b) != r["hash"]:
                        raise ValueError("WORKBENCH_HISTORY_INTEGRITY_FAILED")
                    if r["kind"] not in ("profile", "task"):
                        raise ValueError("INVALID_NOTE_KIND")
                    (profile_valid if r["kind"] == "profile" else task_valid)(b)
                    table = "problems" if r["kind"] == "profile" else "triggers"
                    if not c.execute("SELECT 1 FROM " + table + " WHERE id=?", (r["target"],)).fetchone():
                        raise ValueError("ORPHANED_NOTE")
                    seen[k] = r["revision"]
            return {**report, "profile_history_records": len(rows)}

    def state(self):
        with self.guard:
            report = self.reservoir.report()
            fronts = {r["id"]: r for r in self.reservoir.rows("frontiers")}
            with self.reservoir.tx() as c:
                for p in report["inventory"]:
                    p["profile"] = self._latest(c, "profile", p["id"])
                    p["scenario"] = economics(p["profile"]["body"]["economics"])
                    p["test_count"] = c.execute("SELECT count(*) FROM trials WHERE problem_id=?", (p["id"],)).fetchone()[0]
                for task in report["retest_signals"]:
                    task["triage"] = self._latest(c, "task", task["id"])
                    task["frontier_title"] = fronts[task["frontier_id"]]["title"]
                    task["observed_on"] = fronts[task["frontier_id"]]["observed_on"]
            report["inventory"].sort(key=lambda p: (p["profile"]["body"]["priority"], p["title"]))
            report["frontiers"] = list(fronts.values())
            report["radar"] = {"network_enabled": self.network, "sources": self.config, "last_poll": self.last_poll}
            report["cost_categories"] = list(COSTS)
            report["ranking_basis"] = "Operator priority, then title; not validated market value."
            return report

    def check_sources(self):
        if not self.network or self.config is None:
            raise PermissionError("NETWORK_DISABLED_START_WITH_MONITOR_AND_SOURCES")
        with self.guard:
            result = releases.poll(self.reservoir, self.config, fetch=self.fetch)
            self.last_poll = {"checked_at": datetime.now(timezone.utc).isoformat(), **result}
            return self.last_poll

    def export(self):
        with self.guard:
            self.audit()
            with self.reservoir.tx() as c:
                keys = c.execute("SELECT DISTINCT kind,target FROM workbench_history ORDER BY kind,target").fetchall()
                notes = [{"kind": k["kind"], "target": k["target"], "body": self._latest(c, k["kind"], k["target"])["body"]} for k in keys]
            return {"schema": "frontier-omega/workbench-snapshot/v1",
                    "seed": {"schema": "frontier-omega/seed/v1", "problems": self.reservoir.rows("problems"),
                             "frontiers": self.reservoir.rows("frontiers")},
                    "trials": self.reservoir.rows("trials"), "notes": notes,
                    "privacy": "MAY_CONTAIN_PRIVATE_CUSTOMER_INFORMATION"}

    def import_snapshot(self, data):
        """Validate then import atomically; any conflict rolls back every record."""
        if type(data) is not dict:
            raise ValueError("SNAPSHOT_OBJECT_REQUIRED")
        if data.get("schema") == "frontier-omega/seed/v1":
            if set(data) != {"schema", "problems", "frontiers"}:
                raise ValueError("EXACT_SEED_FIELDS_REQUIRED")
            seed, trials, notes = data, [], []
        else:
            if (set(data) != {"schema", "seed", "trials", "notes", "privacy"} or
                data["schema"] != "frontier-omega/workbench-snapshot/v1"):
                raise ValueError("EXACT_SNAPSHOT_SCHEMA_REQUIRED")
            seed, trials, notes = data["seed"], data["trials"], data["notes"]
            if type(seed) is not dict or set(seed) != {"schema", "problems", "frontiers"} or seed["schema"] != "frontier-omega/seed/v1":
                raise ValueError("EXACT_SEED_FIELDS_REQUIRED")
        if any(type(v) is not list for v in (seed["problems"], seed["frontiers"], trials, notes)):
            raise ValueError("RECORD_LISTS_REQUIRED")
        for v in seed["problems"]: validate_problem(v)
        for v in seed["frontiers"]: validate_frontier(v)
        for v in trials: validate_trial(v)
        for n in notes:
            if type(n) is not dict or set(n) != {"kind", "target", "body"} or n["kind"] not in ("profile", "task"):
                raise ValueError("INVALID_IMPORTED_NOTE")
            (profile_valid if n["kind"] == "profile" else task_valid)(n["body"])
        with self.guard, self.reservoir.tx() as c:
            added = 0
            for table, vals in (("problems", seed["problems"]), ("frontiers", seed["frontiers"]), ("trials", trials)):
                for v in vals:
                    added += self.reservoir._insert(c, table, v)
            problems = [parse(r[0]) for r in c.execute("SELECT body FROM problems")]
            fronts = [parse(r[0]) for r in c.execute("SELECT body FROM frontiers")]
            for p in problems:
                for f in fronts:
                    self.reservoir._schedule(c, p, f)
            for n in notes:
                old = self._latest(c, n["kind"], n["target"])
                if old["revision"] and old["body"] != n["body"]:
                    raise ValueError("IMPORT_CONFLICT_KEEP_EXISTING_NOTES")
                self._append(c, n["kind"], n["target"], n["body"], old["revision"])
        return {"added_records": added, "financial_effects": 0}


def make_server(workbench, token, port=0):
    if type(token) is not str or len(token) < 32:
        raise ValueError("STRONG_SESSION_TOKEN_REQUIRED")
    page = (ASSETS / "workbench.html").read_bytes()
    scripts = re.findall(rb"<script>(.*?)</script>", page, re.S)
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s).digest()).decode() + "'" for s in scripts)
    csp = "default-src 'none'; style-src 'unsafe-inline'; script-src " + hashes + "; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def _reply(self, code, obj, content="application/json; charset=utf-8"):
            raw = obj if type(obj) is bytes else canonical(obj)
            self.send_response(code)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(raw)
        def _same_host(self):
            expected = "127.0.0.1:" + str(self.server.server_port)
            return self.headers.get("Host") == expected
        def _authorized(self):
            origin = self.headers.get("Origin")
            if not self._same_host() or origin not in (None, "http://127.0.0.1:" + str(self.server.server_port)):
                return False
            auth = self.headers.get("Authorization", "")
            return hmac.compare_digest(auth, "Bearer " + token)
        def do_GET(self):
            if not self._same_host(): return self._reply(403, {"error": "HOST_REFUSED"})
            if self.path == "/": return self._reply(200, page, "text/html; charset=utf-8")
            if not self._authorized(): return self._reply(401, {"error": "AUTH_REQUIRED"})
            try:
                if self.path == "/api/state": return self._reply(200, workbench.state())
                if self.path == "/api/export": return self._reply(200, workbench.export())
                return self._reply(404, {"error": "NOT_FOUND"})
            except (ValueError, KeyError, TypeError, sqlite3.Error):
                return self._reply(409, {"error": "STATE_REQUIRES_OPERATOR_REVIEW"})
        def do_POST(self):
            if not self._authorized(): return self._reply(401, {"error": "AUTH_REQUIRED"})
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if (not 0 <= size <= MAX_REQUEST or self.headers.get("Transfer-Encoding") is not None
                    or self.headers.get_content_type() != "application/json"):
                    raise ValueError("BOUNDED_JSON_BODY_REQUIRED")
                raw = self.rfile.read(size)
                if len(raw) != size: raise ValueError("TRUNCATED_REQUEST")
                data = parse(raw)
                if self.path == "/api/problem": result = workbench.add(data)
                elif self.path in ("/api/profile", "/api/task"):
                    if type(data) is not dict or set(data) != {"target", "body", "expected_revision"}:
                        raise ValueError("EXACT_EDIT_ENVELOPE_REQUIRED")
                    result = workbench.save(self.path.rsplit("/", 1)[1], data["target"], data["body"], data["expected_revision"])
                elif self.path == "/api/import": result = workbench.import_snapshot(data)
                elif self.path == "/api/poll":
                    if data != {}: raise ValueError("EMPTY_REQUEST_REQUIRED")
                    result = workbench.check_sources()
                elif self.path == "/api/audit":
                    if data != {}: raise ValueError("EMPTY_REQUEST_REQUIRED")
                    result = workbench.audit()
                elif self.path == "/api/compare":
                    if type(data) is not dict or set(data) != {"problem", "before", "after"}:
                        raise ValueError("EXACT_COMPARISON_FIELDS_REQUIRED")
                    with workbench.guard:
                        workbench.audit()
                        result = workbench.reservoir.compare(data["problem"], data["before"], data["after"])
                else: return self._reply(404, {"error": "NOT_FOUND"})
                return self._reply(200, result)
            except PermissionError as exc:
                return self._reply(403, {"error": str(exc)})
            except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                return self._reply(400, {"error": str(exc)[:160]})
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("./frontier-private"))
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--seed", type=Path, action="append", default=[])
    p.add_argument("--sources", type=Path)
    p.add_argument("--monitor", action="store_true", help="Enable approved GitHub metadata reads")
    p.add_argument("--interval", type=int, default=3600)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    if not 0 <= args.port <= 65535 or args.interval < 300:
        p.error("Use a valid port and at least 300 seconds between metadata checks.")
    if args.monitor and not args.sources: p.error("--monitor requires --sources")
    cfg = load_file(args.sources) if args.sources else None
    bench = Workbench(args.root, cfg, network=args.monitor)
    for seed in args.seed: bench.import_snapshot(load_file(seed))
    token = secrets.token_urlsafe(32)
    server = make_server(bench, token, args.port)
    stop = threading.Event()
    def monitor():
        while not stop.is_set():
            try:
                with bench.guard:
                    bench.reservoir.ingest_inbox()
                if args.monitor: bench.check_sources()
            except Exception as exc:
                # Keep the UI alive, but expose a failure rather than claim a scan.
                bench.last_poll = {"status": "ERROR", "error_type": type(exc).__name__}
            stop.wait(args.interval if args.monitor else 5)
    def finish(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, finish)
    signal.signal(signal.SIGTERM, finish)
    with bench.reservoir.lock():
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port) + "/#" + token
        print("FRONTIER Ω — private inventory workbench\n" + url, flush=True)
        print("Network radar: " + ("approved release metadata only" if args.monitor else "off"), flush=True)
        if not args.no_browser:
            import webbrowser
            webbrowser.open(url)
        try: server.serve_forever(poll_interval=.2)
        finally:
            stop.set()
            server.server_close()
            thread.join(timeout=20)


if __name__ == "__main__":
    main()
