"""Compute the product-stage decisions in a frozen evidence ledger with SQLite."""

import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import resource
import sqlite3
import sys
import time


SCHEMA = "frontier/evidence-truth-v1"
UTC_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
STAGE_ROLE = (
    ("public_offer", "manufacturer_offer"),
    ("public_offer", "authorized_supplier_offer"),
    ("software_support", "first_party_release"),
    ("machine_operation", "observed_machine_run"),
    ("fulfilled_order", "observed_fulfillment"),
)

DDL = """
CREATE TABLE stage_role (
    stage TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (stage, role)
) WITHOUT ROWID;

CREATE TABLE source (
    source_id TEXT PRIMARY KEY,
    published_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE decision (
    case_id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    stage TEXT NOT NULL,
    as_of TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE required_scope (
    case_id TEXT NOT NULL REFERENCES decision (case_id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (case_id, key)
) WITHOUT ROWID;

CREATE TABLE evidence (
    case_id TEXT NOT NULL REFERENCES decision (case_id),
    record_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source (source_id),
    role TEXT NOT NULL,
    verified_by TEXT NOT NULL,
    PRIMARY KEY (case_id, record_id)
) WITHOUT ROWID;

CREATE TABLE evidence_scope (
    case_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (case_id, record_id, key),
    FOREIGN KEY (case_id, record_id) REFERENCES evidence (case_id, record_id)
) WITHOUT ROWID;
"""

ASSESS = """
WITH classified AS (
    SELECT
        e.case_id,
        e.record_id,
        e.source_id,
        e.verified_by,
        CASE
            WHEN e.verified_by > d.as_of THEN 'AFTER_CUTOFF'
            WHEN EXISTS (
                SELECT 1
                FROM required_scope AS q
                WHERE q.case_id = e.case_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM evidence_scope AS s
                      WHERE s.case_id = e.case_id
                        AND s.record_id = e.record_id
                        AND s.key = q.key
                        AND s.value = q.value
                  )
            ) THEN 'SCOPE_MISMATCH'
            WHEN a.role IS NULL THEN 'INSUFFICIENT_EVIDENCE_ROLE'
        END AS exclusion
    FROM evidence AS e
    JOIN decision AS d ON d.case_id = e.case_id
    LEFT JOIN stage_role AS a ON a.stage = d.stage AND a.role = e.role
),
ranked AS (
    SELECT
        *,
        CASE WHEN exclusion IS NULL THEN
            ROW_NUMBER() OVER (
                PARTITION BY case_id, (exclusion IS NULL)
                ORDER BY verified_by, record_id, source_id
            )
        END AS witness_rank
    FROM classified
)
SELECT
    d.case_id,
    d.stage,
    r.record_id,
    r.source_id,
    r.verified_by,
    r.exclusion,
    r.witness_rank
FROM decision AS d
LEFT JOIN ranked AS r ON r.case_id = d.case_id
ORDER BY d.position, r.record_id, r.source_id
"""


def require_object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_array(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def timestamp(value, label):
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError(f"{label} must have the format YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid UTC timestamp") from error
    return value


def field_text(item, key, label):
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}.{key} must be a nonempty string")
    return value


def scope_rows(scope):
    for key, value in scope.items():
        yield key, json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def load_sources(database, items):
    dates = {}
    for index, value in enumerate(require_array(items, "sources")):
        label = f"sources[{index}]"
        source = require_object(value, label)
        source_id = field_text(source, "id", label)
        if source_id in dates:
            raise ValueError(f"duplicate source ID {source_id!r}")
        dates[source_id] = timestamp(source.get("published_at"), f"{label}.published_at")
    database.executemany("INSERT INTO source VALUES (?, ?)", dates.items())
    return dates


def load_cases(database, items, source_dates):
    stages = {stage for stage, _ in STAGE_ROLE}
    case_ids = set()
    for index, value in enumerate(require_array(items, "cases")):
        label = f"cases[{index}]"
        case = require_object(value, label)
        if field_text(case, "kind", label) != "product_stage":
            continue

        case_id = field_text(case, "id", label)
        if case_id in case_ids:
            raise ValueError(f"duplicate product-stage case ID {case_id!r}")
        case_ids.add(case_id)
        stage = field_text(case, "stage", label)
        if stage not in stages:
            raise ValueError(f"{label}.stage is not recognized")
        as_of = timestamp(case.get("as_of"), f"{label}.as_of")
        scope = require_object(case.get("scope"), f"{label}.scope")
        field_text(scope, "product", f"{label}.scope")
        field_text(scope, "feature", f"{label}.scope")

        database.execute("INSERT INTO decision VALUES (?, ?, ?, ?)", (case_id, index, stage, as_of))
        database.executemany(
            "INSERT INTO required_scope VALUES (?, ?, ?)",
            ((case_id, key, scope_value) for key, scope_value in scope_rows(scope)),
        )

        evidence_rows = []
        evidence_scope_rows = []
        record_ids = set()
        for record_index, value in enumerate(require_array(case.get("records"), f"{label}.records")):
            record_label = f"{label}.records[{record_index}]"
            record = require_object(value, record_label)
            record_id = field_text(record, "id", record_label)
            if record_id in record_ids:
                raise ValueError(f"duplicate record ID {record_id!r} in case {case_id!r}")
            record_ids.add(record_id)
            source_id = field_text(record, "source", record_label)
            if source_id not in source_dates:
                raise ValueError(f"{record_label} refers to unknown source {source_id!r}")
            verified_by = timestamp(record.get("verified_by"), f"{record_label}.verified_by")
            if source_dates[source_id] > verified_by:
                raise ValueError(f"{record_label} is verified before its source was published")
            role = field_text(record, "role", record_label)
            record_scope = require_object(record.get("scope"), f"{record_label}.scope")

            evidence_rows.append((case_id, record_id, source_id, role, verified_by))
            evidence_scope_rows.extend(
                (case_id, record_id, key, scope_value)
                for key, scope_value in scope_rows(record_scope)
            )

        database.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)", evidence_rows)
        database.executemany("INSERT INTO evidence_scope VALUES (?, ?, ?, ?)", evidence_scope_rows)


def compare(payload):
    payload = require_object(payload, "input")
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"input.schema must be {SCHEMA!r}")

    decisions = {}
    with closing(sqlite3.connect(":memory:")) as database:
        database.execute("PRAGMA foreign_keys = ON")
        database.executescript(DDL)
        database.executemany("INSERT INTO stage_role VALUES (?, ?)", STAGE_ROLE)
        source_dates = load_sources(database, payload.get("sources"))
        load_cases(database, payload.get("cases"), source_dates)

        for case_id, stage, record_id, source_id, verified_by, exclusion, rank in database.execute(ASSESS):
            if case_id not in decisions:
                decisions[case_id] = {
                    "id": case_id,
                    "stage": stage,
                    "verdict": "ABSTAIN_UNESTABLISHED",
                    "first_verified_by": None,
                    "witness": None,
                    "source": None,
                    "excluded": {},
                    "onset_established": False,
                    "continuity_established": False,
                }
            decision = decisions[case_id]
            if exclusion is not None:
                decision["excluded"][record_id] = exclusion
            elif rank == 1:
                decision.update(
                    verdict="DOCUMENTED_BY_CUTOFF",
                    first_verified_by=verified_by,
                    witness=record_id,
                    source=source_id,
                )
    return list(decisions.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="frozen evidence-ledger JSON")
    parser.add_argument("--metrics", action="store_true", help="write process measurements to stderr")
    args = parser.parse_args()

    started_wall = time.perf_counter_ns()
    started_cpu = time.process_time_ns()
    try:
        frozen = args.input.read_bytes()
        decisions = compare(json.loads(frozen))
        serialized = (json.dumps(decisions, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    except (OSError, ValueError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")

    sys.stdout.buffer.write(serialized)
    sys.stdout.buffer.flush()
    if args.metrics:
        measurements = {
            "request_wall_ns": time.perf_counter_ns() - started_wall,
            "request_cpu_ns": time.process_time_ns() - started_cpu,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "input_sha256": hashlib.sha256(frozen).hexdigest(),
            "output_sha256": hashlib.sha256(serialized).hexdigest(),
            "sqlite_version": sqlite3.sqlite_version,
        }
        print(json.dumps(measurements, sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    main()
