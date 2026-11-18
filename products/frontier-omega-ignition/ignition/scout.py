"""Observe named public release feeds and open ordinary, source-bound investigations."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import research
from .store import Conflict, StateError, canonical, clean_mission, digest, strict_json

PUBLICATION = "Published release"


def _brief(document):
    if not isinstance(document, dict) or set(document) != {"mission", "feeds", "max_investigations"}:
        raise StateError("Supply a mission, named publisher feeds and a total investigation budget.")
    mission = clean_mission(document["mission"])
    feeds = document["feeds"]
    budget = document["max_investigations"]
    if (not isinstance(feeds, list) or not feeds or any(type(k) is not str or k not in research.FEEDS for k in feeds)
            or len(set(feeds)) != len(feeds)):
        raise StateError("Select distinct named feeds from the public research allowlist.")
    if type(budget) is not int or budget <= 0:
        raise StateError("max_investigations must be a positive integer.")
    auth, resources = mission["authority"], mission["resources"]
    if auth.get("public_sources") is not True or auth.get("assisted_model") is True:
        raise StateError("Scouting requires public-source authority and supports only local inference.")
    allowed = {"execution_strategy", "max_model_calls", "max_repairs", "assets", "budget"}
    if (resources.get("execution_strategy") != "research" or set(resources) - allowed
            or resources.get("max_model_calls") is None):
        raise StateError("Use a generic research strategy with an explicit per-mission model-call budget.")
    return mission, feeds, budget


def _schema(store):
    with store.connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS scout_profiles (
              name TEXT PRIMARY KEY, brief_sha TEXT NOT NULL, clock TEXT NOT NULL, feeds TEXT NOT NULL, last_poll TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS scout_sources (
              name TEXT NOT NULL, identity TEXT NOT NULL, source TEXT NOT NULL, PRIMARY KEY(name,identity));
            CREATE TABLE IF NOT EXISTS scout_work (
              name TEXT NOT NULL, request TEXT NOT NULL, body TEXT NOT NULL, outcome TEXT,
              PRIMARY KEY(name,request));
        """)


def _source_key(row):
    # Full publisher response digests can change with download counts or a different page order.
    return digest([row["feed"], row["url"], row["version"], row["title"], row["text"], row["published_at"]])


def _drain(controller, name):
    with controller.store.connection() as db:
        pending = db.execute("SELECT request,body FROM scout_work WHERE name=? AND outcome IS NULL ORDER BY rowid",
                             (name,)).fetchall()
    outcomes = []
    for request, raw in pending:
        # Replay the identical snapshot after a crash, including original retrieval dates.
        run_id, version = controller.create(json.loads(raw))
        head = controller.store.get(run_id)
        current = head["version"] == version
        state = head if current else controller.store.get(run_id, version)
        if current and controller.obsolete(state):
            state = controller.view(run_id)
        elif current and state["operation"]["state"] == "active" and state["status"] in {"queued", "running"}:
            try:
                state = controller.advance(run_id, version, pending_only=True)
            except Conflict:
                # An operator or another worker has the mission. Leave the outbox entry for replay.
                continue
        research_result = state.get("research") or {}
        result = {"mission_id": run_id, "version": version, "current_version": head["version"],
                  "status": state["status"], "decision": research_result.get("decision"),
                  "candidates": len(research_result.get("candidates", [])), "error": state.get("error"),
                  "operation_state": state.get("operation", {}).get("state", "active"),
                  "model_attempts": state.get("attempts", 0),
                  "verified_artifact": (state["status"] == "verified" and bool(state.get("artifact"))
                                        and (state.get("evaluation") or {}).get("status") == "pass")}
        with controller.store.connection() as db:
            recorded = db.execute("UPDATE scout_work SET outcome=? WHERE name=? AND request=? AND outcome IS NULL",
                                  (canonical(result), name, request)).rowcount
        if recorded:
            outcomes.append(result)
    return outcomes


def poll(controller, document, name, *, investigate_initial=False, fetch=None, clock=None):
    mission, feeds, budget = _brief(document)
    if controller.assisted or not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise StateError("Use a private observer ID and an unassisted local controller.")
    controller._check_time(mission)
    store = controller.store
    now = clock or (lambda: datetime.now(timezone.utc))
    _schema(store)
    brief_hash = digest([mission, feeds, budget])
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO scout_profiles VALUES(?,?,?,?,'{}')", (name, brief_hash, "", "[]"))
        pinned, prev = db.execute("SELECT brief_sha,clock FROM scout_profiles WHERE name=?", (name,)).fetchone()
        if pinned != brief_hash:
            raise Conflict("Observer brief, authority or budget changed. Use a new private observer ID.")
    started = now().astimezone(timezone.utc)
    if prev and started < datetime.fromisoformat(prev):
        raise Conflict("Observer UTC clock regressed relative to the durable checkpoint.")
    resumed = _drain(controller, name)
    capture = research.discover_sources(mission, feeds=feeds, fetch=fetch, as_of=started)
    stamp = now().astimezone(timezone.utc)
    if stamp < started:
        raise Conflict("Observer UTC clock regressed during retrieval.")
    # Validate source chronology, URLs and excerpt digests through the same parser as the mission.
    sources = capture["sources"]
    research._signals(sources, stamp)
    valid_current = [s for s in sources if s["role"] == PUBLICATION]
    cutoff = stamp.date() - timedelta(days=35)
    fresh, baseline = [], []
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        stored_clock, initialized = db.execute("SELECT clock,feeds FROM scout_profiles WHERE name=?",(name,)).fetchone()
        if stored_clock and started < datetime.fromisoformat(stored_clock):
            raise Conflict("A newer observation already committed. Retry with the current UTC clock.")
        known_feeds = set(json.loads(initialized))
        for row in valid_current:
            key = _source_key(row)
            inserted = db.execute("INSERT OR IGNORE INTO scout_sources VALUES(?,?,?)",
                                  (name, key, canonical(row))).rowcount
            published = research._now(row["published_at"]).date()
            if inserted and cutoff < published <= stamp.date():
                if row["feed"] in known_feeds or investigate_initial:
                    fresh.append(row)
                else:
                    baseline.append(row)
        count = db.execute("SELECT COUNT(*) FROM scout_work WHERE name=?", (name,)).fetchone()[0]
        status = "observed_unchanged" if valid_current else "source_unavailable"
        if any(row["feed"] not in known_feeds for row in valid_current):
            status = "baseline_recorded"
        if fresh:
            if count >= budget:
                status = "budget_exhausted"
            else:
                # The child's immutable source snapshot is already acquired. Narrow its public grant
                # to avoid a second acquisition or a different inferred destination.
                child = dict(mission, authority=dict(mission["authority"], public_sources=False))
                seen_feeds = {row["feed"] for row in fresh}
                context = [row for row in sources if row["feed"] in seen_feeds and row["role"] != PUBLICATION]
                request = "scout-" + digest([name, brief_hash, sorted(_source_key(row) for row in fresh)])
                body = {"mission": child, "sources": fresh + context, "request_id": request}
                db.execute("INSERT INTO scout_work(name,request,body) VALUES(?,?,?)", (name, request, canonical(body)))
                count += 1
                status = "investigation_registered"
        report = {"observer": name, "polled_at": stamp.isoformat(), "status": status, "feeds": feeds,
                  "observed": [{"url": r["url"], "version": r["version"], "published_at": r["published_at"],
                                "retrieved_at": r["retrieved_at"], "identity": _source_key(r)} for r in valid_current],
                  "comparison_sources": [{"url": r["url"], "version": r["version"], "event_at": r["event_at"],
                                          "retrieved_at": r["retrieved_at"], "source_response_sha256": r["source_response_sha256"]}
                                         for r in sources if r["role"] != PUBLICATION],
                  "new_release_records": len(fresh), "initial_baseline_records": len(baseline),
                  "investigations_reserved": count, "budget": budget, "failures": capture["failures"],
                  "evidence_scope": "Publisher records. Capability, economic advantage and payment require separate evidence."}
        known_feeds.update(row["feed"] for row in valid_current)
        db.execute("UPDATE scout_profiles SET clock=?,feeds=?,last_poll=? WHERE name=?",
                   (stamp.isoformat(), canonical(sorted(known_feeds)), canonical(report), name))
    report["missions"] = resumed + _drain(controller, name)
    return report


def register_cli(sub):
    parser = sub.add_parser("scout", help="observe public releases and start local frontier investigations")
    parser.add_argument("brief", type=Path)
    parser.add_argument("--id", required=True, help="durable observer ID within this private workspace")
    parser.add_argument("--investigate-initial", action="store_true", help="open a mission for recent first-seen releases")
    parser.add_argument("--follow", action="store_true", help="repeat in the foreground until interrupted")
    parser.add_argument("--interval", type=int, default=900, help="seconds between completed foreground observations")


def dispatch_cli(args, controller):
    if args.interval <= 0:
        raise StateError("The foreground poll interval must be positive.")
    brief = strict_json(args.brief.read_bytes())
    while True:
        result = poll(controller, brief, args.id, investigate_initial=args.investigate_initial)
        if not args.follow or result["investigations_reserved"] >= result["budget"]:
            return result
        print(json.dumps(result, ensure_ascii=False), flush=True)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return {"observer": args.id, "status": "foreground_stopped", "last_poll": result["polled_at"]}
