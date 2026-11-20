"""Durable, idempotent shadow queue. This module does not deliver messages."""
from contextlib import closing
import json
import sqlite3

from . import core, ingest, triage

SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_drafts (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_decisions (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


def queue(db, drafts, decisions=()):
    inserted = []
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.executescript(SCHEMA)
        for d in decisions:
            conn.execute("INSERT OR IGNORE INTO shadow_decisions VALUES (?, ?, ?, ?)",
                         (d["id"], d["opportunity_id"], d["created_at"], json.dumps(d, sort_keys=True)))
        for d in drafts:
            row = conn.execute(
                "INSERT OR IGNORE INTO shadow_drafts VALUES (?, ?, ?, ?)",
                (d["id"], d["created_at"], d["kind"], d["body"]),
            )
            if row.rowcount:
                inserted.append(d)
    return inserted


def drafts(db):
    with closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return [dict(r) for r in conn.execute("SELECT * FROM shadow_drafts ORDER BY created_at, id")]


def decisions(db):
    with closing(sqlite3.connect(db)) as conn:
        conn.executescript(SCHEMA)
        return [json.loads(r[0]) for r in conn.execute(
            "SELECT payload FROM shadow_decisions ORDER BY created_at, id")]


def run(db, atlas, records, now, *, source_ids=None):
    report = ingest.run(db, source_ids)
    health = report["sources"]
    healthy = bool(health) and all(x["status"] in ("ok", "not_modified") for x in health)
    local = now.astimezone(core.TORONTO)
    candidates = []
    audit = []
    if local.weekday() == 4 and local.hour >= 8:
        candidates.append({"id": "friday:" + local.date().isoformat(),
                           "created_at": now.isoformat(), "kind": "briefing",
                           "body": core.briefing(atlas, records, now, health)})
    for record in records:
        decision = core.assess(record, now)
        state = {"result": decision, "record_digest": core.digest(record),
                 "coverage_degraded": not healthy}
        audit.append({**state, "id": core.digest(state), "opportunity_id": record["id"],
                      "created_at": now.isoformat()})
        if decision["alert"] and healthy:
            identifier = core.digest([record["id"], decision["decision"], record["urgency"]])
            candidates.append({"id": "alert:" + identifier, "created_at": now.isoformat(),
                               "kind": "alert", "body": core.alert_text(record, decision)})
    inserted = queue(db, candidates, audit)
    return {"mode": "shadow", "coverage_degraded": not healthy,
            "new_leads": len(report["new_observations"]), "source_health": health,
            "revisit_leads": triage.route(report["new_observations"], records),
            "queued": inserted, "delivery_attempts": 0}
