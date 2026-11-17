"""FRONTIER Ω: durable demand-first opportunity radar. Standard library, no financial authority.

A reported capability release is not measured task performance; a scenario crossing
is not a customer, a verified purchase order, earnings, or a spend instruction.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from urllib.parse import urlsplit

VERSION = "frontier-omega/v1"
PROBLEM_SCHEMA = "frontier-omega/problem/v1"
FRONTIER_SCHEMA = "frontier-omega/capability/v1"
TRIAL_SCHEMA = "frontier-omega/trial/v1"
SEED_SCHEMA = "frontier-omega/seed/v1"
ID = re.compile(r"[a-z][a-z0-9-]{2,95}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
COSTS = ("acquisition", "research", "construction", "verification", "delivery",
         "support", "maintenance", "payment_fees", "tax_provision", "failure_recovery")
PROBLEM_FIELDS = {"schema", "id", "title", "beneficiary", "outcome", "acceptance",
                  "blocker", "tags", "demand", "alternatives", "source_urls", "next_test"}
FRONTIER_FIELDS = {"schema", "id", "title", "observed_on", "description", "tags",
                   "source_urls", "availability"}
TRIAL_FIELDS = {"schema", "id", "problem_id", "frontier_id", "run_on",
                "terms_sha256", "acceptance_sha256", "protocol_sha256",
                "evidence_sha256", "scope", "passed", "independent_check",
                "price_microUSD", "acceptance_probability_bps", "costs_microUSD",
                "expected_loss_microUSD", "alternative"}
SCOPE = "READ_ONLY_OPPORTUNITY_INTELLIGENCE_NO_PAYMENT_OR_EXECUTION_AUTHORITY"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def parse(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    if len(data) > 2_000_000:
        raise ValueError("RECORD_TOO_LARGE")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("NONFINITE_JSON")
    result = json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)
    canonical(result)
    return result


def exact(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError("EXACT_SCHEMA_FIELDS_REQUIRED")


def title(value):
    if type(value) is not str or not 3 <= len(value) <= 1600 or not value.strip():
        raise ValueError("NONEMPTY_BOUNDED_TEXT_REQUIRED")
    return value


def identifier(value):
    if type(value) is not str or not ID.fullmatch(value):
        raise ValueError("INVALID_IDENTIFIER")
    return value


def tags(value):
    if type(value) is not list or not value or len(value) != len(set(map(str, value))):
        raise ValueError("DISTINCT_TAGS_REQUIRED")
    if len(value) > 64 or any(type(x) is not str or not ID.fullmatch(x) for x in value):
        raise ValueError("INVALID_TAG")
    return value


def sources(value):
    if type(value) is not list or not value or len(value) > 24 or len(value) != len(set(map(str, value))):
        raise ValueError("PUBLIC_SOURCE_URL_REQUIRED")
    for url in value:
        if type(url) is not str or len(url) > 2048:
            raise ValueError("INVALID_SOURCE_URL")
        p = urlsplit(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment:
            raise ValueError("PUBLIC_HTTPS_SOURCE_REQUIRED")
    return value


def day(value):
    if type(value) is not str or len(value) != 10 or date.fromisoformat(value).isoformat() != value:
        raise ValueError("ISO_DAY_REQUIRED")
    return value


def nonnegative(value):
    if type(value) is not int or value < 0:
        raise ValueError("NONNEGATIVE_EXACT_INTEGER_REQUIRED")
    return value


def validate_problem(obj):
    exact(obj, PROBLEM_FIELDS)
    if obj["schema"] != PROBLEM_SCHEMA:
        raise ValueError("PROBLEM_SCHEMA_VERSION")
    identifier(obj["id"])
    for k in ("title", "beneficiary", "outcome", "acceptance", "blocker", "next_test"):
        title(obj[k])
    tags(obj["tags"])
    sources(obj["source_urls"])
    exact(obj["demand"], {"status", "basis", "ceiling_microUSD",
                          "deadline", "terms_sha256", "consent_verification"})
    if obj["demand"]["status"] not in ("HYPOTHESIS", "PUBLIC_SIGNAL", "CUSTOMER_REPORTED_UNVERIFIED"):
        raise ValueError("UNSUPPORTED_DEMAND_EVIDENCE")
    title(obj["demand"]["basis"])
    if obj["demand"]["consent_verification"] != "NOT_VERIFIED":
        raise ValueError("PURCHASE_CONSENT_CANNOT_BE_ASSERTED_BY_JSON")
    if obj["demand"]["ceiling_microUSD"] is not None:
        nonnegative(obj["demand"]["ceiling_microUSD"])
    if obj["demand"]["deadline"] is not None:
        day(obj["demand"]["deadline"])
    if obj["demand"]["terms_sha256"] is not None:
        if type(obj["demand"]["terms_sha256"]) is not str or not SHA.fullmatch(obj["demand"]["terms_sha256"]):
            raise ValueError("DECLARED_TERMS_HASH_REQUIRED")
    if obj["demand"]["status"] in ("HYPOTHESIS", "PUBLIC_SIGNAL"):
        if any(obj["demand"][k] is not None for k in ("ceiling_microUSD", "deadline", "terms_sha256")):
            raise ValueError("PUBLIC_SIGNAL_CANNOT_IMPERSONATE_BUYER_TERMS")
    if type(obj["alternatives"]) is not list or len(obj["alternatives"]) < 2:
        raise ValueError("COMPETENT_ALTERNATIVES_AND_NO_PURCHASE_REQUIRED")
    names = set()
    for alt in obj["alternatives"]:
        exact(alt, {"name", "route", "unknowns"})
        for field in alt:
            title(alt[field])
        if alt["name"] in names:
            raise ValueError("DUPLICATE_ALTERNATIVE")
        names.add(alt["name"])
    if "No purchase" not in names:
        raise ValueError("NO_PURCHASE_COMPARATOR_REQUIRED")
    canonical(obj)
    return obj


def validate_frontier(obj):
    exact(obj, FRONTIER_FIELDS)
    if obj["schema"] != FRONTIER_SCHEMA:
        raise ValueError("FRONTIER_SCHEMA_VERSION")
    identifier(obj["id"])
    for k in ("title", "description"):
        title(obj[k])
    day(obj["observed_on"])
    tags(obj["tags"])
    sources(obj["source_urls"])
    if obj["availability"] not in ("REPORTED", "AVAILABLE_NOT_REPRODUCED", "OPERATOR_REPORTED_REPRODUCTION"):
        raise ValueError("FRONTIER_REPORT_IS_NOT_VERIFIED_BENCHMARK")
    canonical(obj)
    return obj


def validate_trial(obj):
    exact(obj, TRIAL_FIELDS)
    if obj["schema"] != TRIAL_SCHEMA:
        raise ValueError("TRIAL_SCHEMA_VERSION")
    for k in ("id", "problem_id", "frontier_id"):
        identifier(obj[k])
    day(obj["run_on"])
    for k in ("terms_sha256", "acceptance_sha256", "protocol_sha256", "evidence_sha256"):
        if type(obj[k]) is not str or not SHA.fullmatch(obj[k]):
            raise ValueError("SHA256_EVIDENCE_IDENTITY_REQUIRED")
    if obj["scope"] not in ("AUTHORED_SCENARIO", "OPERATOR_REPORTED_UNVERIFIED"):
        raise ValueError("NO_UNVERIFIED_CLAIM_OF_INDEPENDENT_CERTIFICATION")
    if type(obj["passed"]) is not bool or type(obj["independent_check"]) is not bool:
        raise ValueError("EXPLICIT_PASS_AND_CHECK_REQUIRED")
    nonnegative(obj["price_microUSD"])
    nonnegative(obj["expected_loss_microUSD"])
    if type(obj["acceptance_probability_bps"]) is not int or not 0 <= obj["acceptance_probability_bps"] <= 10000:
        raise ValueError("PROBABILITY_BASIS_POINTS_REQUIRED")
    exact(obj["costs_microUSD"], set(COSTS))
    for v in obj["costs_microUSD"].values():
        nonnegative(v)
    exact(obj["alternative"], {"name", "qualified", "complete_cost_microUSD"})
    title(obj["alternative"]["name"])
    if type(obj["alternative"]["qualified"]) is not bool:
        raise ValueError("STRONG_ALTERNATIVE_QUALIFICATION_REQUIRED")
    if obj["alternative"]["complete_cost_microUSD"] is not None:
        nonnegative(obj["alternative"]["complete_cost_microUSD"])
    canonical(obj)
    return obj


def regular_file(path):
    path = Path(os.path.abspath(path))
    if any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError("SYMLINK_PATH_REFUSED")
    if not path.is_file():
        raise ValueError("REGULAR_FILE_REQUIRED")
    details = path.stat()
    if details.st_nlink != 1 or details.st_size > 2_000_000 or not stat.S_ISREG(details.st_mode):
        raise ValueError("UNSAFE_INPUT_FILE")
    return path


def load_file(path):
    return parse(regular_file(path).read_bytes())


class Reservoir:
    """A durable, private, nonfinancial index with immutable source records."""
    def __init__(self, root):
        self.root = Path(os.path.abspath(root))
        if any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ValueError("SYMLINK_ROOT_REFUSED")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_mode & 0o077:
            raise ValueError("OPPORTUNITY_DATA_MUST_BE_PRIVATE_0700")
        for name in ("inbox", "processed", "rejected"):
            (self.root / name).mkdir(exist_ok=True, mode=0o700)
        self.path = self.root / "frontier.sqlite"
        with self.tx() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS problems(
              id TEXT PRIMARY KEY,body TEXT NOT NULL,hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS frontiers(
              id TEXT PRIMARY KEY,body TEXT NOT NULL,hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS trials(
              id TEXT PRIMARY KEY,problem_id TEXT NOT NULL,frontier_id TEXT NOT NULL,
              body TEXT NOT NULL,hash TEXT NOT NULL,
              FOREIGN KEY(problem_id) REFERENCES problems(id),
              FOREIGN KEY(frontier_id) REFERENCES frontiers(id));
            CREATE UNIQUE INDEX IF NOT EXISTS frozen_comparison_arm
              ON trials(problem_id,frontier_id,
                json_extract(body,'$.terms_sha256'),
                json_extract(body,'$.acceptance_sha256'),
                json_extract(body,'$.protocol_sha256'));
            CREATE TABLE IF NOT EXISTS triggers(
              id TEXT PRIMARY KEY,problem_id TEXT NOT NULL,frontier_id TEXT NOT NULL,
              problem_hash TEXT NOT NULL,frontier_hash TEXT NOT NULL,
              body TEXT NOT NULL,hash TEXT NOT NULL);
            """)

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=20000")
        c.execute("PRAGMA synchronous=FULL")
        try:
            with c:
                yield c
        finally:
            c.close()

    @contextmanager
    def lock(self):
        with open(self.root / "frontier.lock", "a+b") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("ANOTHER_FRONTIER_WORKER_IS_RUNNING") from None
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _insert(c, table, obj):
        record = canonical(obj).decode("utf-8")
        digest = sha(obj)
        old = c.execute("SELECT hash FROM " + table + " WHERE id=?", (obj["id"],)).fetchone()
        if old:
            if old["hash"] != digest:
                raise ValueError("IMMUTABLE_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT")
            return False
        if table == "trials":
            c.execute("INSERT INTO trials VALUES(?,?,?,?,?)",
                      (obj["id"], obj["problem_id"], obj["frontier_id"], record, digest))
        else:
            c.execute("INSERT INTO " + table + " VALUES(?,?,?)", (obj["id"], record, digest))
        return True

    @staticmethod
    def _schedule(c, problem, frontier):
        if not set(problem["tags"]).intersection(frontier["tags"]):
            return False
        ph, fh = sha(problem), sha(frontier)
        ident = sha({"problem": problem["id"], "frontier": frontier["id"],
                     "problem_hash": ph, "frontier_hash": fh})
        payload = {"id": ident, "problem_id": problem["id"], "frontier_id": frontier["id"],
                   "reason": "CAPABILITY_TAG_MATCH_REQUIRES_TARGETED_RETEST",
                   "decision": "INVESTIGATE_ONLY", "execution_authorized": False,
                   "customer_payment_established": False}
        c.execute("INSERT OR IGNORE INTO triggers VALUES(?,?,?,?,?,?,?)",
                  (ident, problem["id"], frontier["id"], ph, fh,
                   canonical(payload).decode("utf-8"), sha(payload)))
        return c.execute("SELECT changes()").fetchone()[0] == 1

    def add(self, value):
        schema = value.get("schema") if type(value) is dict else None
        if schema == PROBLEM_SCHEMA:
            obj, table = validate_problem(value), "problems"
        elif schema == FRONTIER_SCHEMA:
            obj, table = validate_frontier(value), "frontiers"
        elif schema == TRIAL_SCHEMA:
            obj, table = validate_trial(value), "trials"
        else:
            raise ValueError("UNKNOWN_FRONTIER_RECORD_SCHEMA")
        with self.tx() as c:
            if table == "trials":
                if not c.execute("SELECT 1 FROM problems WHERE id=?", (obj["problem_id"],)).fetchone():
                    raise ValueError("UNKNOWN_PROBLEM")
                if not c.execute("SELECT 1 FROM frontiers WHERE id=?", (obj["frontier_id"],)).fetchone():
                    raise ValueError("UNKNOWN_FRONTIER")
            fresh = self._insert(c, table, obj)
            count = 0
            if fresh and table in ("problems", "frontiers"):
                other = "frontiers" if table == "problems" else "problems"
                for row in c.execute("SELECT body FROM " + other).fetchall():
                    v = parse(row["body"])
                    count += self._schedule(c, obj if table == "problems" else v,
                                             obj if table == "frontiers" else v)
        return {"id": obj["id"], "kind": table, "added": fresh,
                "retests_queued": count, "financial_effects": 0}

    def seed(self, data):
        exact(data, {"schema", "problems", "frontiers"})
        if data["schema"] != SEED_SCHEMA or type(data["problems"]) is not list or type(data["frontiers"]) is not list:
            raise ValueError("EXACT_SEED_SCHEMA_REQUIRED")
        counts = {"problems_added": 0, "frontiers_added": 0, "retests_queued": 0}
        for key, name in (("problems", "problems_added"), ("frontiers", "frontiers_added")):
            for obj in data[key]:
                receipt = self.add(obj)
                counts[name] += int(receipt["added"])
                counts["retests_queued"] += receipt["retests_queued"]
        return counts

    def rows(self, table):
        if table not in ("problems", "frontiers", "trials", "triggers"):
            raise ValueError("UNKNOWN_TABLE")
        with self.tx() as c:
            return [parse(r["body"]) for r in c.execute(
                "SELECT body FROM " + table + " ORDER BY id").fetchall()]

    @staticmethod
    def _value(trial):
        """Exact numerator in microUSD * 10,000 (no floating point)."""
        costs = sum(trial["costs_microUSD"].values()) + trial["expected_loss_microUSD"]
        expected = trial["price_microUSD"] * trial["acceptance_probability_bps"] - 10000 * costs
        # Failure to pass the held-out task is not a commercial deliverable.
        return min(expected, 0) if not trial["passed"] else expected

    def compare(self, problem_id, before_id, after_id):
        problems = {p["id"]: p for p in self.rows("problems")}
        events = {e["id"]: e for e in self.rows("frontiers")}
        if problem_id not in problems or before_id not in events or after_id not in events:
            raise ValueError("UNKNOWN_COMPARISON_ID")
        if events[before_id]["observed_on"] >= events[after_id]["observed_on"]:
            raise ValueError("STRICT_HISTORICAL_FRONTIER_ORDER_REQUIRED")
        arms = [t for t in self.rows("trials") if t["problem_id"] == problem_id
                and t["frontier_id"] in (before_id, after_id)]
        pairs = []
        for old in (t for t in arms if t["frontier_id"] == before_id):
            # A replay may happen much later, but never before its cited
            # capability was observable. Preserve invalid historic rows;
            # exclude them from economic crossing evidence.
            if old["run_on"] < events[before_id]["observed_on"]:
                continue
            for new in (t for t in arms if t["frontier_id"] == after_id):
                if new["run_on"] < events[after_id]["observed_on"]:
                    continue
                # Price uplift or a switch between authored/operator scope
                # is not a capability gain under fixed voluntary terms.
                keys = ("terms_sha256", "acceptance_sha256", "protocol_sha256",
                        "price_microUSD", "scope")
                if all(old[k] == new[k] for k in keys):
                    pairs.append((old, new))
        if not pairs:
            return {"problem_id": problem_id, "before": before_id, "after": after_id,
                    "verdict": "MATCHED_HISTORICAL_AND_NEW_TEST_REQUIRED",
                    "economic_crossing_established": False,
                    "workorder_authorized": False}
        if len(pairs) != 1:
            return {"problem_id": problem_id, "before": before_id, "after": after_id,
                    "verdict": "AMBIGUOUS_MULTIPLE_MATCHED_COMPARISONS",
                    "economic_crossing_established": False, "workorder_authorized": False}
        old, new = pairs[0]
        a, b = self._value(old), self._value(new)
        crossing = a <= 0 < b and new["passed"] and new["independent_check"]
        demand = problems[problem_id]["demand"]
        ceiling_exceeded = (demand["ceiling_microUSD"] is not None and
                            new["price_microUSD"] > demand["ceiling_microUSD"])
        if ceiling_exceeded:
            crossing = False
        # Caller-supplied claims and scenario numbers are not independently
        # audited and cannot establish actual demand, profit or novel frontier.
        return {"problem_id": problem_id, "before": before_id, "after": after_id,
                "trial_ids": [old["id"], new["id"]],
                "matched_terms_and_protocol": True,
                "before_margin_numerator": a, "after_margin_numerator": b,
                "reported_crossing": crossing,
                "verdict": ("REPORTED_BUYER_CEILING_EXCEEDED" if ceiling_exceeded else
                            "REPORTED_CROSSING_UNVERIFIED" if crossing else
                            "NO_POSITIVE_MATCHED_CROSSING"),
                "economic_crossing_established": False,
                "workorder_authorized": False,
                "demand_status": problems[problem_id]["demand"]["status"],
                "current_strong_alternative_qualified": new["alternative"]["qualified"],
                "actual_customer_acceptance": "NOT_VERIFIED",
                "complete_actual_costs": "NOT_VERIFIED",
                "next_action": "INDEPENDENT_REPLAY_AND_CUSTOMER_QUALIFICATION" if crossing
                               else "RETAIN_BLOCKER_AND_MONITOR"}

    def report(self):
        problems, events, trials, triggers = (self.rows(x) for x in
                                              ("problems", "frontiers", "trials", "triggers"))
        by_problem = {p["id"]: [] for p in problems}
        for tr in triggers:
            by_problem[tr["problem_id"]].append(tr["frontier_id"])
        return {"schema": VERSION, "scope": SCOPE,
                "counts": {"problems": len(problems), "capability_observations": len(events),
                           "reported_trials": len(trials), "retest_signals": len(triggers)},
                "inventory": [{**p, "retest_frontiers": sorted(set(by_problem[p["id"]])),
                               "commercial_status": "NOT_CUSTOMER_QUALIFIED",
                               "economic_value_verified": False}
                              for p in problems],
                "retest_signals": triggers,
                "claims": {"actual_customers": "NOT_ESTABLISHED",
                           "earned_revenue": "NOT_MEASURED",
                           "frontier_crossings": "NOT_INDEPENDENTLY_VERIFIED",
                           "financial_authority": "NONE"}}

    def audit(self):
        counts = {}
        for table in ("problems", "frontiers", "trials", "triggers"):
            with self.tx() as c:
                records = c.execute("SELECT * FROM " + table + " ORDER BY id").fetchall()
            for row in records:
                value = parse(row["body"])
                if type(value) is not dict or value.get("id") != row["id"] or sha(value) != row["hash"]:
                    raise ValueError("RESERVOIR_RECORD_INTEGRITY_FAILED")
                if table == "problems":
                    validate_problem(value)
                elif table == "frontiers":
                    validate_frontier(value)
                elif table == "trials":
                    validate_trial(value)
                elif table == "triggers":
                    if (value["problem_id"] != row["problem_id"] or
                        value["frontier_id"] != row["frontier_id"] or
                        value["execution_authorized"] is not False or
                        value["customer_payment_established"] is not False):
                        raise ValueError("UNAUTHORIZED_TRIGGER_MUTATION")
            counts[table] = len(records)
        problems = {p["id"]: p for p in self.rows("problems")}
        frontiers = {e["id"]: e for e in self.rows("frontiers")}
        for trial in self.rows("trials"):
            if trial["problem_id"] not in problems or trial["frontier_id"] not in frontiers:
                raise ValueError("BROKEN_TRIAL_RELATION")
        stored = {x["id"]: x for x in self._trigger_rows()}
        for row in self.rows("triggers"):
            if row["problem_id"] not in problems or row["frontier_id"] not in frontiers:
                raise ValueError("BROKEN_TRIGGER_SOURCE_BINDING")
            p, e = problems[row["problem_id"]], frontiers[row["frontier_id"]]
            bound = stored.get(row["id"])
            ph, fh = sha(p), sha(e)
            expected_id = sha({"problem": p["id"], "frontier": e["id"],
                               "problem_hash": ph, "frontier_hash": fh})
            if (bound is None or row["id"] != expected_id or
                ph != bound["problem_hash"] or fh != bound["frontier_hash"] or
                not set(p["tags"]).intersection(e["tags"])):
                raise ValueError("BROKEN_TRIGGER_SOURCE_BINDING")
        return {"audit": "PASS", "counts": counts, "financial_authority": "NONE",
                "scope": "LOCAL_HASH_INTEGRITY_NOT_EXTERNAL_CERTIFICATION"}

    def _trigger_rows(self):
        with self.tx() as c:
            return [dict(r) for r in c.execute("SELECT * FROM triggers").fetchall()]

    def ingest_inbox(self):
        receipts = []
        for path in sorted((self.root / "inbox").iterdir()):
            if path.name.startswith(".") or path.suffix != ".json":
                continue
            try:
                result = self.add(load_file(path))
                dest = self.root / "processed" / (hashlib.sha256(path.name.encode()).hexdigest()[:12]
                                                 + "-" + path.name)
                if dest.exists():
                    raise ValueError("INGEST_ARCHIVE_NAME_COLLISION")
                os.rename(path, dest)
                receipts.append({"file": path.name, **result})
            except (ValueError, OSError, KeyError, sqlite3.IntegrityError) as exc:
                dest = self.root / "rejected" / (hashlib.sha256(path.name.encode()).hexdigest()[:12]
                                                + "-" + path.name)
                if not dest.exists() and path.exists() and not path.is_symlink():
                    os.rename(path, dest)
                receipts.append({"file": path.name, "rejected": type(exc).__name__,
                                 "error": str(exc)[:160]})
        return receipts

    def watch(self, interval=5.0, cycles=None, stopped=lambda: False):
        import math
        if type(interval) not in (int, float) or not math.isfinite(interval) or interval < 0.05:
            raise ValueError("POSITIVE_FINITE_INTERVAL_REQUIRED")
        with self.lock():
            n = 0
            receipts = []
            while not stopped() and (cycles is None or n < cycles):
                receipts.extend(self.ingest_inbox())
                n += 1
                if cycles is None or n < cycles:
                    time.sleep(interval)
        return {"cycles": n, "receipts": receipts, "status": self.report()["counts"]}
