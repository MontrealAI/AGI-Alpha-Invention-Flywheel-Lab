"""Evaluator-controlled cases, exact oracle, and two complete incumbent methods."""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
import random
import re
import sqlite3
import time

from common import LEGACY, decode, encode, load_module, measure, require, sha

DECIMAL = re.compile(r"[0-9]{1,30}(?:\.[0-9]{1,30})?\Z")
FIELDS = {"id", "published", "facts", "metric", "upper_metric", "load", "submission_id", "system"}


def decimal_key(value):
    left, _, right = value.partition(".")
    return f"{left:0>30}{right:0<30}"


def admitted(document, registration):
    source, design = registration["source"], registration["comparison"]
    require(isinstance(document, dict) and document.get("schema") ==
            "frontier-omega-alpha/endpoint-observations-v1", "MALFORMED_SOURCE")
    require(document.get("source") == source["url"] and
            document.get("source_sha256") == source["upstream_sha256"], "UNAUTHENTICATED_SOURCE")
    require(document.get("generated_at") == source["retrieved_at"], "STALE_OR_UNREGISTERED_SOURCE")
    records = document.get("rows")
    require(isinstance(records, list) and records, "MISSING_SOURCE_ROWS")
    models = set(design["development_models"] + design["confirmation_models"])
    identities, rows = set(), []
    for record in records:
        require(isinstance(record, dict) and FIELDS <= record.keys(), "MALFORMED_RECORD")
        ident, fields = record["id"], record["facts"]
        require(isinstance(ident, str) and ident and isinstance(fields, dict), "MALFORMED_RECORD")
        require(ident not in identities, "CONTRADICTORY_SOURCE_IDENTITY")
        identities.add(ident)
        require(isinstance(fields.get("model"), str), "MALFORMED_RECORD")
        if fields["model"] not in models or any(fields.get(k) != v for k, v in design["required_facts"].items()):
            continue
        scope = fields | {key: record[key] for key in ("submission_id", "system")}
        require(all(isinstance(scope.get(key), str) and scope[key] for key in design["scope_keys"]),
                "INCOMPLETE_CONFIGURATION")
        day, rate, first, load = (record[k] for k in ("published", "metric", "upper_metric", "load"))
        require(all(value is not None for value in (day, rate, first, load)), "INCOMPLETE_MEASUREMENT")
        require(isinstance(day, str) and date.fromisoformat(day).isoformat() == day and
                type(load) is int and 0 < load < 2**63 and
                all(isinstance(value, str) and DECIMAL.fullmatch(value) for value in (rate, first)),
                "MALFORMED_MEASUREMENT")
        if day <= source["cutoff"]:
            rows.append({"id": ident, "scope": [scope[k] for k in design["scope_keys"]],
                         "day": day, "rate": rate, "first": first, "load": load})
    require(rows, "MISSING_ELIGIBLE_EVIDENCE")
    return rows


def authenticated(raw, registration):
    require(sha(raw) == registration["source"]["normalized_sha256"], "SOURCE_DIGEST_MISMATCH")
    return admitted(decode(raw), registration)


def result(load, ids):
    if load is None:
        return {"decision": "ABSTAIN", "reason": "NO_QUALIFYING_OBSERVATION"}
    return {"decision": "OBSERVED_LOAD", "load": load, "witnesses": sorted(ids)}


def oracle(rows, query):
    floor, ceiling = Decimal(query["floor"]), Decimal(query["ceiling"])
    feasible = defaultdict(list)
    for row in rows:
        if (row["scope"] == query["scope"] and row["day"] <= query["as_of"] and
                floor <= Decimal(row["rate"]) and Decimal(row["first"]) <= ceiling):
            feasible[row["load"]].append(row["id"])
    highest = max(feasible, default=None)
    return result(highest, feasible.get(highest, []))


def choose_cases(rows, registration, seed):
    """Called only after the constructor is gone and the immutable plan is checked."""
    design = registration["comparison"]["case_design"]
    generator = random.Random(int.from_bytes(seed, "big"))
    cases = []
    for kind in design["types"]:
        distinct = {}
        for row in rows:
            floor, ceiling, day = row["rate"], row["first"], registration["source"]["cutoff"]
            if kind == "faster-throughput-floor":
                floor = format(Decimal(floor) + Decimal("0.000001"), "f")
            elif kind == "earlier-cutoff":
                day = (date.fromisoformat(row["day"]) - timedelta(days=1)).isoformat()
            elif kind == "unattainable-ceiling":
                ceiling = "0"
            query = {"kind": kind, "scope": row["scope"], "as_of": day, "floor": floor, "ceiling": ceiling}
            distinct[encode(query)] = query
        population = [distinct[key] for key in sorted(distinct)]
        cases.extend(generator.sample(population, design["queries_per_type"]))
    generator.shuffle(cases)
    return cases


def capsule_groups(capsule):
    return {tuple(group["scope"]): group["points"] for group in capsule["groups"]}


def certify(rows, capsule):
    """Check complete coverage, retained values, and strict load dominance independently."""
    original = {row["id"]: row for row in rows}
    kept, scopes = {}, set()
    require(isinstance(capsule, dict) and set(capsule) == {"groups", "covered"} and
            isinstance(capsule["groups"], list) and isinstance(capsule["covered"], dict), "INVALID_CERTIFICATE")
    for group in capsule["groups"]:
        scope = tuple(group["scope"])
        require(scope not in scopes and group["points"], "INVALID_CERTIFICATE_SCOPE")
        scopes.add(scope)
        for point in group["points"]:
            ident, day, rate, first, load = point
            row = original.get(ident)
            require(row is not None and ident not in kept and tuple(row["scope"]) == scope and
                    (day, rate, first, load) == (row["day"], row["rate"], row["first"], row["load"]) and
                    type(load) is int, "CERTIFICATE_CHANGED_WITNESS")
            kept[ident] = row
    covered = capsule["covered"]
    require(not (kept.keys() & covered.keys()) and (kept.keys() | covered.keys()) == original.keys(),
            "CERTIFICATE_INCOMPLETE_COVERAGE")
    for ident, witness in covered.items():
        row, better = original[ident], kept.get(witness)
        require(better is not None and better["scope"] == row["scope"] and better["load"] > row["load"] and
                better["day"] <= row["day"] and Decimal(better["rate"]) >= Decimal(row["rate"]) and
                Decimal(better["first"]) <= Decimal(row["first"]), "CERTIFICATE_INVALID_DOMINANCE")
    return {"admitted_rows": len(original), "retained_witnesses": len(kept),
            "dominated_witnesses": len(covered), "configurations": len(scopes)}


def from_capsule(groups, query):
    floor, ceiling, day = query["floor"], query["ceiling"], query["as_of"]
    floor, ceiling = decimal_key(floor), decimal_key(ceiling)
    high, witnesses = None, []
    for ident, published, rate, first, load in groups.get(tuple(query["scope"]), []):
        if published <= day and decimal_key(rate) >= floor and decimal_key(first) <= ceiling:
            if high is None or load > high:
                high, witnesses = load, [ident]
            elif load == high:
                witnesses.append(ident)
    return result(high, witnesses)


def build_sqlite(path, rows):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE points (id TEXT PRIMARY KEY, scope TEXT, day TEXT,
                   rate_key TEXT, first_key TEXT, load INTEGER)""")
        db.executemany("INSERT INTO points VALUES (?, ?, ?, ?, ?, ?)", [
            (r["id"], encode(r["scope"]).decode(), r["day"], decimal_key(r["rate"]),
             decimal_key(r["first"]), r["load"]) for r in rows
        ])
        db.execute("CREATE INDEX points_scope_load ON points(scope, load DESC, id, day, rate_key, first_key)")


def from_sqlite(db, query):
    criteria = "scope = ? AND day <= ? AND rate_key >= ? AND first_key <= ?"
    bindings = (encode(query["scope"]).decode(), query["as_of"], decimal_key(query["floor"]),
                decimal_key(query["ceiling"]))
    maximum = db.execute(f"SELECT load FROM points WHERE {criteria} ORDER BY load DESC LIMIT 1", bindings).fetchone()
    if maximum is None:
        return result(None, [])
    witnesses = db.execute(f"SELECT id FROM points WHERE {criteria} AND load = ? ORDER BY id",
                           (*bindings, maximum[0]))
    return result(maximum[0], [ident for ident, in witnesses])


def legacy_adapter(rows, scope_keys):
    legacy = load_module("frozen_endpoint_decision", LEGACY)
    frozen_rows = [{"id": row["id"], "facts": dict(zip(scope_keys, row["scope"], strict=True)),
                    "published": row["day"], "metric": row["rate"], "upper_metric": row["first"],
                    "objective": str(row["load"])} for row in rows]
    loads = {row["id"]: row["load"] for row in rows}

    def legacy_query(query):
        checked = legacy.evaluate(frozen_rows, dict(zip(scope_keys, query["scope"], strict=True)),
                                  query["as_of"], query["floor"], query["ceiling"])
        winners = checked["winners"]
        return result(loads[winners[0]] if winners else None, winners)

    return legacy_query, len(encode(frozen_rows))


def compare(rows, cases, capsule, state, registration):
    costs = {}
    with measure(costs, "independent_oracle"):
        answers = [oracle(rows, case) for case in cases]
    db_path = state / "incumbent.sqlite"
    with measure(costs, "sqlite_materialization"):
        db_path.unlink(missing_ok=True)
        build_sqlite(db_path, rows)
    with measure(costs, "existing_materialization"):
        legacy, legacy_bytes = legacy_adapter(rows, registration["comparison"]["scope_keys"])
    with measure(costs, "capsule_open"):
        groups = capsule_groups(capsule)
    with measure(costs, "sqlite_open"):
        connection = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    with closing(connection):
        connection.execute("PRAGMA query_only=ON")
        using_index = connection.execute(
            "EXPLAIN QUERY PLAN SELECT load FROM points WHERE scope=? ORDER BY load DESC LIMIT 1", ("",)
        ).fetchone()[3]
        require("points_scope_load" in using_index, "BASELINE_INDEX_NOT_USED")
        arms = {"indexed_sqlite": lambda query: from_sqlite(connection, query), "existing_instrument": legacy,
                "detached_capsule": lambda query: from_capsule(groups, query)}
        timings, observations, failure_witnesses = defaultdict(list), defaultdict(list), []
        names = list(arms)
        for i, (case, expected) in enumerate(zip(cases, answers, strict=True)):
            for name in names[i % len(names):] + names[:i % len(names)]:
                wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                actual = arms[name](case)
                timings[name].append((time.perf_counter_ns() - wall, time.process_time_ns() - cpu))
                observations[name].append(actual)
                if actual != expected:
                    failure_witnesses.append({"method": name, "case_index": i, "case": case,
                                              "expected": expected, "actual": actual})
    metrics = {}
    for name, values in observations.items():
        wall, cpu = zip(*timings[name])
        metrics[name] = {"correct": sum(a == b for a, b in zip(values, answers, strict=True)),
                         "decisions": dict(Counter(v["decision"] for v in values)), "cases": len(values),
                         "query_wall_ns": sum(wall), "query_process_cpu_ns": sum(cpu),
                         "p90_query_wall_ns": sorted(wall)[(9 * len(wall) + 9) // 10 - 1]}
    return {"methods": metrics, "costs": costs, "expected_decisions": dict(Counter(a["decision"] for a in answers)),
            "stored_bytes": {"indexed_sqlite": db_path.stat().st_size, "existing_projection": legacy_bytes,
                             "capsule": len(encode(capsule))}, "exact_sqlite_index": using_index,
            "failure_count": len(failure_witnesses)}, {"answers": answers, "failure_witnesses": failure_witnesses}
