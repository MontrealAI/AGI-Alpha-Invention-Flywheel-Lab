"""ALPHA economic engine: persistent, nonfinancial production workcell.

This module does real SQLite work. It does NOT create customers, collect money,
replace JournalAccount, execute arbitrary code, or call a model/API. Retained
index configurations are ordinary reuse, not self-improving intelligence.
Python 3.10+, POSIX. Run with: python -m connected_enterprise.alpha_runtime --help
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import statistics
import tempfile
import time
import uuid

VERSION = "0.1.0"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")
JOBID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
REQUEST_KEYS = {"version", "id", "table", "equals", "range", "measure",
                "discovery", "confirmation", "min_gain", "max_index_bytes"}
STOP = False
LOADED_RUNTIME_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("Duplicate JSON key")
            out[k] = v
        return out
    def bad(x):
        raise ValueError("Nonfinite JSON")
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=bad)


def safe_path(path):
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink path refused")
    return path


def atomic(path, data):
    path = safe_path(path)
    temp = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def quote(name):
    if not isinstance(name, str) or not IDENT.fullmatch(name):
        raise ValueError("Unsupported SQL identifier")
    return '"' + name + '"'


def validate_request(r):
    if not isinstance(r, dict) or set(r) != REQUEST_KEYS:
        raise ValueError("Request fields do not match version 1")
    if type(r["version"]) is not int or r["version"] != 1 or not isinstance(r["id"], str) or not JOBID.fullmatch(r["id"]):
        raise ValueError("Invalid version or job id")
    if not isinstance(r["equals"], list) or not 1 <= len(r["equals"]) <= 3:
        raise ValueError("Workcell supports one to three equality fields")
    cols = r["equals"] + [r["range"], r["measure"]]
    for x in [r["table"]] + cols:
        quote(x)
    if len(set(cols)) != len(cols):
        raise ValueError("Column roles must be distinct")
    for group in ("discovery", "confirmation"):
        probes = r[group]
        if not isinstance(probes, list) or not 1 <= len(probes) <= 64:
            raise ValueError("Each probe set must contain 1..64 cases")
        for p in probes:
            if not isinstance(p, list) or len(p) != len(r["equals"]) + 2:
                raise ValueError("Wrong parameter arity")
            if any(type(x) is not int or not -(2**63) < x < 2**63 for x in p) or p[-2] >= p[-1]:
                raise ValueError("Expected bounded integer parameters and nonempty range")
    if set(map(tuple, r["discovery"])) & set(map(tuple, r["confirmation"])):
        raise ValueError("Discovery and confirmation cases must be disjoint")
    if type(r["min_gain"]) not in (int, float) or not math.isfinite(r["min_gain"]) or r["min_gain"] <= 1:
        raise ValueError("Minimum gain must be finite and greater than one")
    if type(r["max_index_bytes"]) is not int or not 0 <= r["max_index_bytes"] <= 2**40:
        raise ValueError("Invalid declared index storage allowance")
    return r


def read_source(path):
    path = safe_path(path)
    if not path.is_file():
        raise ValueError("Source snapshot missing")
    c = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    c.execute("PRAGMA trusted_schema=OFF")
    return c


def inspect(c, r):
    schema = c.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (r["table"],)).fetchone()
    if not schema or schema[0] != "table" or "VIRTUAL" in schema[1].upper():
        raise ValueError("Ordinary table required")
    columns = {x[1]: x[2].upper() for x in c.execute("PRAGMA table_info(" + quote(r["table"]) + ")")}
    wanted = r["equals"] + [r["range"], r["measure"]]
    if any(x not in columns or columns[x] != "INTEGER" for x in wanted):
        raise ValueError("This workcell requires INTEGER columns")
    if c.execute("SELECT 1 FROM " + quote(r["table"]) + " WHERE " + " OR ".join("typeof(" + quote(x) + ")!='integer'" for x in wanted) + " LIMIT 1").fetchone():
        raise ValueError("NULL or noninteger data outside workcell scope")
    return digest({"table": r["table"], "columns": columns, "equals": r["equals"],
                   "range": r["range"], "measure": r["measure"], "sqlite": sqlite3.sqlite_version})


def query(r):
    where = [quote(x) + "=?" for x in r["equals"]]
    where += [quote(r["range"]) + ">=?", quote(r["range"]) + "<?"]
    return "SELECT COALESCE(SUM(" + quote(r["measure"]) + "),0),COUNT(*) FROM " + quote(r["table"]) + " WHERE " + " AND ".join(where)


def index_sql(r, cols):
    allowed = set(r["equals"] + [r["range"], r["measure"]])
    if not isinstance(cols, list) or not cols or len(set(cols)) != len(cols) or not set(cols) <= allowed:
        raise ValueError("Index outside allowed column grammar")
    name = "alpha_" + digest({"table": r["table"], "columns": cols})[:20]
    return "CREATE INDEX " + quote(name) + " ON " + quote(r["table"]) + " (" + ",".join(quote(x) for x in cols) + ");", "DROP INDEX " + quote(name) + ";"


def candidates(r):
    # Established equality-first covering index is a first-class comparator.
    ordinary = r["equals"] + [r["range"], r["measure"]]
    out = [ordinary]
    for eq in itertools.permutations(r["equals"]):
        out.extend([list(eq) + [r["range"]], list(eq) + [r["range"], r["measure"]]])
    out.extend([[r["range"]] + r["equals"] + [r["measure"]]])
    out.extend([[x] for x in r["equals"] + [r["range"]]])
    return list(dict.fromkeys(tuple(x) for x in out))


def measure(c, sql, probes):
    """SQLite progress callbacks at every VM instruction, plus uninstrumented wall samples."""
    answers, ticks, samples = [], 0, []
    for p in probes:
        steps = [0]
        deadline = time.monotonic() + 30
        def progress():
            steps[0] += 1
            return int(time.monotonic() > deadline)
        c.set_progress_handler(progress, 1)
        try:
            answers.append(list(c.execute(sql, p).fetchone()))
        finally:
            c.set_progress_handler(None, 0)
        ticks += max(steps[0], 1)
        for _ in range(3):
            start = time.perf_counter_ns()
            c.execute(sql, p).fetchone()
            samples.append(time.perf_counter_ns() - start)
    return {"vm_steps": ticks, "median_query_ns": statistics.median(samples),
            "answers": answers, "wall_samples_ns": samples}


@contextlib.contextmanager
def variant(source, r, cols):
    c = sqlite3.connect(":memory:")
    try:
        source.backup(c)
        c.execute("PRAGMA trusted_schema=OFF")
        # Count allocated pages, not file growth: CREATE INDEX can use the
        # source snapshot's freelist without increasing page_count.
        before = (c.execute("PRAGMA page_count").fetchone()[0]
                  - c.execute("PRAGMA freelist_count").fetchone()[0])
        start = time.perf_counter_ns()
        if cols:
            apply_sql, _ = index_sql(r, cols)
            name = "alpha_" + digest({"table": r["table"], "columns": cols})[:20]
            existing = c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,)).fetchone()
            if existing:
                if not existing[0] or existing[0].strip().rstrip(";") != apply_sql.strip().rstrip(";"):
                    raise ValueError("Conflicting preexisting index definition")
                # The exact same owner-applied index is already present:
                # measuring it as a fresh build would fail the entire job.
            else:
                c.execute(apply_sql)
            c.execute("ANALYZE")
        build_ns = time.perf_counter_ns() - start
        after = (c.execute("PRAGMA page_count").fetchone()[0]
                 - c.execute("PRAGMA freelist_count").fetchone()[0])
        size = max(0, (after - before) * c.execute("PRAGMA page_size").fetchone()[0])
        yield c, size, build_ns
    finally:
        c.close()


def solve(source_path, r, retained=None):
    """Finite authored index search, never an assertion of novel invention."""
    from .alpha_verify import reference_answers
    start, cpu = time.perf_counter_ns(), time.process_time_ns()
    sql = query(r)
    traces = []
    with contextlib.closing(read_source(source_path)) as source:
        signature = inspect(source, r)
        expected = reference_answers(source_path, r, r["discovery"] + r["confirmation"])
        with variant(source, r, None) as (base, _, _):
            baseline = measure(base, sql, r["discovery"])
        ordinary = list(candidates(r)[0])
        queue = [ordinary]
        if retained is not None:
            index_sql(r, retained)
            queue = [retained] + ([] if retained == ordinary else [ordinary])
        else:
            queue = [list(x) for x in candidates(r)]
        best = None
        for cols in queue:
            with variant(source, r, cols) as (c, size, build_ns):
                m = measure(c, sql, r["discovery"])
            if m["answers"] != expected[:len(r["discovery"])]:
                raise ValueError("Candidate changed results")
            t = {"columns": cols, "index_bytes": size, "build_ns": build_ns, "discovery": m}
            traces.append(t)
            key = (m["vm_steps"], 0 if cols == ordinary else 1, size, len(cols))
            if size <= r["max_index_bytes"] and (best is None or key < best[0]):
                best = (key, t)
        # Reuse is only a search shortcut after revalidation. On failure, do cold search.
        if retained is not None and (best is None or baseline["vm_steps"] / best[0][0] < r["min_gain"]):
            cold = solve(source_path, r, None)
            cold["reuse_fallback"] = traces
            cold["search_candidates"] += len(traces)
            cold["total_wall_ns"] = time.perf_counter_ns() - start
            cold["total_cpu_ns"] = time.process_time_ns() - cpu
            return cold
        if best is None:
            return {"accepted": False, "reason": "NO_CANDIDATE_WITHIN_STORAGE_ALLOWANCE", "traces": traces,
                    "search_candidates": len(traces), "total_wall_ns": time.perf_counter_ns() - start,
                    "total_cpu_ns": time.process_time_ns() - cpu}
        winner = best[1]
        with variant(source, r, None) as (b, _, _), variant(source, r, winner["columns"]) as (c, _, _), variant(source, r, ordinary) as (o, ordinary_size, _):
            bm = measure(b, sql, r["confirmation"])
            cm = measure(c, sql, r["confirmation"])
            om = measure(o, sql, r["confirmation"])
        correct = cm["answers"] == bm["answers"] == om["answers"] == expected[len(r["discovery"]):]
        gain = bm["vm_steps"] / cm["vm_steps"]
        # No better-than-specialist claim: incumbent quality must at least be matched.
        meets_ordinary = cm["vm_steps"] <= om["vm_steps"] if ordinary_size <= r["max_index_bytes"] else True
        accepted = correct and gain >= r["min_gain"] and meets_ordinary
        apply, rollback = index_sql(r, winner["columns"])
        return {"accepted": accepted, "reason": "VERIFIED" if accepted else "ACCEPTANCE_NOT_MET",
                "signature": signature, "columns": winner["columns"], "apply_sql": apply,
                "rollback_sql": rollback, "query_sql": sql, "index_bytes": winner["index_bytes"],
                "source_sha256": filehash(source_path), "request_sha256": digest(r),
                "baseline": bm, "selected": cm, "ordinary": om,
                "vm_work_reduction_factor": gain, "wall_ratio_observation": bm["median_query_ns"] / max(cm["median_query_ns"], 1),
                "ordinary_work_ratio": om["vm_steps"] / cm["vm_steps"],
                "search_candidates": len(traces), "used_retained_configuration": retained is not None,
                "traces": traces, "total_wall_ns": time.perf_counter_ns() - start,
                "total_cpu_ns": time.process_time_ns() - cpu,
                "economic_status": "NOT_SETTLED", "cash_collected": None,
                "complete_cost_profit": None, "cost_status": "HOST_BILLING_AND_COMMERCIAL_COSTS_UNKNOWN",
                "limitations": ["Conventional index search; no model inference or novel invention claim",
                                "Read workload only; write amplification, deployment and customer acceptance unqualified",
                                "Confirmation probes are owner supplied, not secret or external certification",
                                "Retained configuration is ordinary reuse, not learned general intelligence"]}


class Engine:
    """Single writer, persistent work queue. SQLite here stores work, never money."""
    def __init__(self, root):
        self.root = safe_path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_mode & 0o077:
            raise ValueError("Work directory must be owner-only (0700)")
        for folder in ("inbox", "outbox"):
            p = safe_path(self.root / folder)
            p.mkdir(mode=0o700, exist_ok=True)
        self.dbpath = safe_path(self.root / "work.sqlite")
        with self.db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
              source_hash TEXT NOT NULL, status TEXT NOT NULL, payload TEXT, attempts INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS capabilities(signature TEXT PRIMARY KEY, columns_json TEXT NOT NULL,
              from_job TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, job TEXT NOT NULL, kind TEXT NOT NULL,
              body TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
            """)

    @contextlib.contextmanager
    def db(self):
        c = sqlite3.connect(self.dbpath, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=20000")
        c.execute("PRAGMA synchronous=FULL")
        try:
            with c:
                yield c
        finally:
            c.close()

    @contextlib.contextmanager
    def lock(self):
        import fcntl
        p = safe_path(self.root / "worker.lock")
        with open(p, "a+b") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another worker already owns this work directory") from None
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def event(c, job, kind, body):
        row = c.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous = row[0] if row else "0" * 64
        content = {"job": job, "kind": kind, "body": body, "previous": previous}
        c.execute("INSERT INTO events(job,kind,body,previous,hash) VALUES(?,?,?,?,?)",
                  (job, kind, encoded(body).decode(), previous, digest(content)))

    def submit(self, source_path, request):
        r = validate_request(request)
        source_path = safe_path(source_path)
        target = safe_path(self.root / "inbox" / r["id"])
        if target.exists():
            raise ValueError("Job id already submitted; submissions are immutable")
        temp = self.root / "inbox" / ("." + uuid.uuid4().hex)
        temp.mkdir(mode=0o700)
        try:
            with contextlib.closing(read_source(source_path)) as source, contextlib.closing(sqlite3.connect(temp / "source.sqlite")) as dest:
                inspect(source, r)
                source.backup(dest)
            atomic(temp / "request.json", encoded(r))
            os.rename(temp, target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
        return r["id"]

    def scan(self):
        with self.db() as c:
            for p in sorted((self.root / "inbox").iterdir()):
                if p.name.startswith("."):
                    continue
                safe_path(p)
                if not p.is_dir():
                    continue
                r = validate_request(load(safe_path(p / "request.json")))
                if r["id"] != p.name:
                    raise ValueError("Job directory/id mismatch")
                rh, sh = digest(r), filehash(safe_path(p / "source.sqlite"))
                row = c.execute("SELECT * FROM jobs WHERE id=?", (p.name,)).fetchone()
                if row:
                    if row["request_hash"] != rh or row["source_hash"] != sh:
                        raise ValueError("Previously admitted job changed: " + p.name)
                    continue
                c.execute("INSERT INTO jobs(id,request_hash,source_hash,status) VALUES(?,?,?,?)", (p.name, rh, sh, "QUEUED"))
                self.event(c, p.name, "DISCOVERED", {"request_sha256": rh, "source_sha256": sh})

    def recover(self):
        with self.db() as c:
            for row in c.execute("SELECT id FROM jobs WHERE status='RUNNING'").fetchall():
                c.execute("UPDATE jobs SET status='QUEUED' WHERE id=?", (row[0],))
                self.event(c, row[0], "INTERRUPTED_ATTEMPT", {"lost_attempt_cost": "UNKNOWN", "action": "RETRY_FROM_SNAPSHOT"})

    def deliver(self, job, payload):
        p = safe_path(self.root / "outbox" / job)
        p.mkdir(mode=0o700, exist_ok=True)
        result = payload["result"]
        atomic(p / "receipt.json", encoded(payload))
        if result["accepted"]:
            atomic(p / "apply.sql", (result["apply_sql"] + "\n").encode())
            atomic(p / "rollback.sql", (result["rollback_sql"] + "\n").encode())
        atomic(p / "REPORT.html", report_html(payload).encode())
        with self.db() as c:
            row = c.execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()
            if row[0] != "VERIFIED":
                return
            status = "DELIVERED_AWAITING_SETTLEMENT" if result["accepted"] else "DECLINED"
            c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job))
            self.event(c, job, status, {"receipt_sha256": digest(payload)})
            if result["accepted"]:
                c.execute("INSERT OR REPLACE INTO capabilities VALUES(?,?,?)", (result["signature"], encoded(result["columns"]).decode(), job))
                self.event(c, job, "CAPABILITY_RETAINED", {"kind": "ORDINARY_CONFIGURATION_REUSE", "funding": "NO_EARNED_MONEY_CLAIM"})

    def step(self):
        self.scan()
        with self.db() as c:
            ready = c.execute("SELECT id,payload FROM jobs WHERE status='VERIFIED' ORDER BY id LIMIT 1").fetchone()
        if ready:
            self.deliver(ready["id"], json.loads(ready["payload"]))
            return True
        with self.db() as c:
            row = c.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY id LIMIT 1").fetchone()
            if not row:
                return False
            job = row["id"]
            c.execute("UPDATE jobs SET status='RUNNING',attempts=attempts+1 WHERE id=?", (job,))
            self.event(c, job, "ATTEMPT_STARTED", {"attempt": row["attempts"] + 1})
        try:
            p = self.root / "inbox" / job
            r = validate_request(load(p / "request.json"))
            with contextlib.closing(read_source(p / "source.sqlite")) as source:
                signature = inspect(source, r)
            with self.db() as c:
                old = c.execute("SELECT columns_json,from_job FROM capabilities WHERE signature=?", (signature,)).fetchone()
            result = solve(p / "source.sqlite", r, json.loads(old[0]) if old else None)
            payload = {"version": VERSION, "job": job, "request": r, "result": result,
                       "inherited_from": old[1] if old else None,
                       "source_identity": source_identity(), "sqlite_version": sqlite3.sqlite_version}
            if filehash(p / "source.sqlite") != row["source_hash"] or digest(r) != row["request_hash"]:
                raise ValueError("Inputs changed during production")
            if result["accepted"]:
                from .alpha_verify import verify
                verify(p / "source.sqlite", payload)
            with self.db() as c:
                c.execute("UPDATE jobs SET status='VERIFIED',payload=? WHERE id=?", (encoded(payload).decode(), job))
                self.event(c, job, "TESTED", {"accepted": result["accepted"], "search_candidates": result["search_candidates"]})
        except Exception as e:
            with self.db() as c:
                c.execute("UPDATE jobs SET status='FAILED' WHERE id=?", (job,))
                self.event(c, job, "FAILED", {"type": type(e).__name__, "message": str(e)[:300]})
            return True
        # A delivery I/O failure leaves VERIFIED durable, then stops this worker.
        # Restart republishes the same stored receipt rather than recomputing it.
        self.deliver(job, payload)
        return True

    def run(self, watch=False, poll=1.0):
        with self.lock():
            # Refuse a forged status before recover()/step() can retry and
            # duplicate a previously committed delivery.
            self.reconcile_history()
            self.recover()
            while not STOP:
                worked = self.step()
                if not worked and not watch:
                    break
                if not worked:
                    time.sleep(poll)
        return self.status()

    def status(self):
        with self.db() as c:
            jobs = [dict(x) for x in c.execute("SELECT id,status,attempts FROM jobs ORDER BY id")]
            return {"jobs": jobs, "capabilities": c.execute("SELECT COUNT(*) FROM capabilities").fetchone()[0],
                    "events": c.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                    "commercial_cycle_proven": False, "live_payment_adapter": "NOT_CONNECTED",
                    "real_revenue_evidence": "NONE", "financial_account_created": False}

    def reconcile_history(self):
        """Read-only consistency check: hash chain, legal transitions, all job states.

        Hashes are LOCAL integrity evidence, not an authenticated signature.
        """
        with self.db() as c:
            events = c.execute("SELECT * FROM events ORDER BY seq").fetchall()
            jobs = {j["id"]: j for j in c.execute("SELECT * FROM jobs").fetchall()}
        transitions = {
            "DISCOVERED": (None, "QUEUED"),
            "ATTEMPT_STARTED": ("QUEUED", "RUNNING"),
            "INTERRUPTED_ATTEMPT": ("RUNNING", "QUEUED"),
            "TESTED": ("RUNNING", "VERIFIED"),
            "FAILED": ("RUNNING", "FAILED"),
            "DECLINED": ("VERIFIED", "DECLINED"),
            "DELIVERED_AWAITING_SETTLEMENT": ("VERIFIED", "DELIVERED_AWAITING_SETTLEMENT"),
        }
        states, capabilities, previous = {}, set(), "0" * 64
        for expected_seq, ev in enumerate(events, 1):
            if ev["seq"] != expected_seq:
                raise ValueError("Event history sequence mismatch")
            body = json.loads(ev["body"])
            if not isinstance(body, dict):
                raise ValueError("Event history body mismatch")
            content = {"job": ev["job"], "kind": ev["kind"], "body": body, "previous": previous}
            if ev["previous"] != previous or ev["hash"] != digest(content):
                raise ValueError("Event chain mismatch")
            previous = ev["hash"]
            job, kind = ev["job"], ev["kind"]
            if job not in jobs:
                raise ValueError("Event history references missing job")
            current = states.get(job)
            if kind == "CAPABILITY_RETAINED":
                if current != "DELIVERED_AWAITING_SETTLEMENT" or job in capabilities:
                    raise ValueError("Event history invalid retained capability")
                capabilities.add(job)
                continue
            if kind not in transitions:
                raise ValueError("Event history unknown transition")
            required, successor = transitions[kind]
            if current != required:
                raise ValueError("Event history invalid state transition")
            if kind in ("DECLINED", "DELIVERED_AWAITING_SETTLEMENT"):
                payload = jobs[job]["payload"]
                if not payload or body.get("receipt_sha256") != digest(json.loads(payload)):
                    raise ValueError("Event history delivered receipt mismatch")
            states[job] = successor
        if set(states) != set(jobs):
            raise ValueError("Event history missing job states")
        for job, row in jobs.items():
            if row["status"] != states[job]:
                raise ValueError("Event history / job state mismatch")
            if row["status"] == "DELIVERED_AWAITING_SETTLEMENT" and job not in capabilities:
                raise ValueError("Event history missing retained-capability event")
        checked = [j for j in jobs.values()
                   if j["status"] in ("DELIVERED_AWAITING_SETTLEMENT", "DECLINED")]
        return events, checked, previous

    def audit(self):
        from .alpha_verify import verify
        self.reconcile_history()  # Refuse unsafe history before scanning new inputs.
        self.scan()
        events, jobs, previous = self.reconcile_history()
        for j in jobs:
            payload = json.loads(j["payload"])
            out = self.root / "outbox" / j["id"]
            if encoded(load(out / "receipt.json")) != encoded(payload):
                raise ValueError("Delivered receipt changed")
            if j["status"] == "DELIVERED_AWAITING_SETTLEMENT":
                result = payload["result"]
                if (out / "apply.sql").read_text() != result["apply_sql"] + "\n" or (out / "rollback.sql").read_text() != result["rollback_sql"] + "\n":
                    raise ValueError("SQL artifact changed")
                verify(self.root / "inbox" / j["id"] / "source.sqlite", payload)
        return {"audit": "PASS", "jobs_checked": len(jobs), "events_checked": len(events),
                "chain_tip": previous, "scope": "LOCAL_INTEGRITY_AND_REEXECUTION_NOT_EXTERNAL_CERTIFICATION"}


def source_identity():
    from .alpha_verify import LOADED_VERIFY_HASH
    current = {p.name: filehash(p) for p in (Path(__file__), Path(__file__).with_name("alpha_verify.py"))}
    if current != {"alpha_runtime.py": LOADED_RUNTIME_HASH, "alpha_verify.py": LOADED_VERIFY_HASH}:
        raise ValueError("Loaded execution source differs from disk; restart and requalify")
    return current


def report_html(payload):
    r = payload["result"]
    status = "Verified production output" if r["accepted"] else "No qualifying improvement"
    gain = f'{r.get("vm_work_reduction_factor", 1):,.1f}×'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ALPHA | Production receipt</title><style>body{background:#0d1020;color:#e9e9ee;font:17px/1.6 system-ui;max-width:1040px;margin:auto;padding:5vw}small{color:#aaa5ca;letter-spacing:.15em}h1{font-size:clamp(36px,6vw,64px);line-height:1.1}h2{color:#d8c28d}article{border:1px solid #34374a;border-radius:18px;padding:28px;margin:24px 0}strong{color:#e8d3a3}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.metric{font-size:48px;color:#e8d3a3}footer{color:#b2b4c4}</style><small>MONTREAL.AI / ALPHA ECONOMIC ENGINE / 0.1</small><h1>Useful work.<br>Inspectable evidence.</h1><p>''' + html.escape(status + " · " + payload["job"]) + '''</p><article><div class="metric">''' + gain + '''</div><p>Measured reduction in SQLite virtual-machine work versus the submitted database, on the declared confirmation probes. Not production savings, money earned, or superiority to a database specialist.</p></article><article><h2>Earn is a separate gate.</h2><p><strong>No customer payment or profitable economic cycle is established.</strong> This receipt records local computation. It does not authorize a database change, contract, purchase or fund transfer.</p></article><article><h2>Complete production receipt</h2><pre>''' + html.escape(json.dumps(payload, indent=2)) + '''</pre></article><footer>Known-method search · Independent Python result checker · Reversible SQL artifact · Owner-controlled local execution</footer></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--database", type=Path, required=True)
    s.add_argument("--request", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--watch", action="store_true")
    run.add_argument("--poll", type=float, default=1.0)
    sub.add_parser("status")
    sub.add_parser("audit")
    args = p.parse_args()
    engine = Engine(args.root)
    if args.cmd == "submit":
        result = {"submitted": engine.submit(args.database, load(args.request))}
    elif args.cmd == "run":
        if not math.isfinite(args.poll) or args.poll < 0.05:
            p.error("--poll must be finite and >=0.05 seconds")
        def stop(*_):
            global STOP
            STOP = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        result = engine.run(args.watch, args.poll)
    elif args.cmd == "audit":
        with engine.lock():
            result = engine.audit()
    else:
        result = engine.status()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
