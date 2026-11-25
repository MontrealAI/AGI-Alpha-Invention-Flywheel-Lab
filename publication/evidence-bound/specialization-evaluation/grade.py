#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Grade the frozen specialist against independent protected exact outcomes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import resource
import sqlite3
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from reference import calculate


REGISTRATION_SHA256 = "98700874dc394b0fcb8557d56ac28b220c4efe5697c7b8c2c11698e4cb00e213"
CANDIDATE_SHA256 = "a02bc2e1065c67a492a9d9cb3ee4ee79035ebe51796671c9d72dc54ec01bf6b9"
SQL = """
WITH ranked AS (
 SELECT id, updated, ROW_NUMBER() OVER(PARTITION BY id ORDER BY updated DESC) AS seq FROM events
), latest AS (
 SELECT id, updated FROM ranked WHERE seq = 1
), unique_states AS (
 SELECT DISTINCT e.id, CASE WHEN e.lon = 180 THEN -180 ELSE e.lon END AS point, e.lat, e.mag, e.incident
 FROM events e JOIN latest l ON l.id = e.id AND l.updated = e.updated
), counted AS (
 SELECT s.*, COUNT(*) OVER(PARTITION BY s.id) AS variants FROM unique_states s
), cap(west, east, south, north, minimum, first_ms, last_ms) AS (
 VALUES (?, ?, ?, ?, ?, ?, ?)
)
SELECT id, CASE WHEN variants > 1 THEN 'conflicting' ELSE 'included' END
FROM counted CROSS JOIN cap
WHERE variants > 1 OR (
 lat BETWEEN south AND north AND mag >= minimum AND first_ms <= incident AND incident < last_ms
 AND (
  (west <= east AND (point BETWEEN west AND east OR (point = -180 AND east = 180)))
  OR (west > east AND (point >= west OR point <= east))
 )
) GROUP BY id ORDER BY id;
"""


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def sqlite_ordinary(case):
    keys = ("west", "east", "south", "north", "min_magnitude", "start_ms", "end_ms")
    bounds = [case["bounds"][key] for key in keys]
    params = [float(value) if index < 5 else value for index, value in enumerate(bounds)]
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE events (id TEXT, lon REAL, lat REAL, mag REAL, incident INTEGER, updated INTEGER)")
        db.executemany("INSERT INTO events VALUES (?,?,?,?,?,?)", [
            tuple(row[key] for key in ("id", "lon", "lat", "mag", "time_ms", "updated_ms")) for row in case["records"]])
        results = {"included": [], "conflicting": []}
        for name, label in db.execute(SQL, params):
            results[label].append(name)
        return results
    finally:
        db.close()


def cli(script, source):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    began = perf_counter_ns()
    out = subprocess.run([sys.executable, "-B", str(script), str(source)], capture_output=True, check=False, timeout=8)
    elapsed = perf_counter_ns() - began
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = round((after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime) * 1e9)
    if out.returncode:
        return {"error": out.stderr.decode(errors="replace")[:300], "return_code": out.returncode}, elapsed, cpu
    try:
        result = json.loads(out.stdout)
    except (ValueError, UnicodeError):
        result = {"error": "INVALID_JSON"}
    return result, elapsed, cpu


def score(panels, arm):
    entries = [panel["arms"][arm] for panel in panels]
    timing = [item for value in entries for item in value["wall_ns"]]
    cpu = [item for value in entries for item in value["child_cpu_ns"]]
    strata = {}
    for panel in panels:
        label = panel["family"]
        row = strata.setdefault(label, {"passed": 0, "total": 0})
        row["passed"] += panel["arms"][arm]["exact"]
        row["total"] += 1
    return {"exact_cases": sum(value["exact"] for value in entries), "total_cases": len(panels),
            "false_positive_ids": sum(len(set(value["predictions"].get("included", [])) - set(panel["expected"]["included"]))
                                      for value, panel in zip(entries, panels, strict=True)),
            "median_wall_ns": median(timing), "median_child_cpu_ns": median(cpu) if cpu else None, "strata": strata}


def grade(data, candidate, factory):
    registration = data / "REGISTRATION.json"
    assert sha(registration) == REGISTRATION_SHA256
    assert sha(candidate) == CANDIDATE_SHA256
    frozen = json.loads(registration.read_bytes())["frozen"]
    for name, expected in frozen.items():
        path = factory / name if name.endswith(".py") else data / name
        assert sha(path) == expected, name
    cases = [json.loads(line) for line in (data / "CASES.jsonl").read_bytes().splitlines()]
    oracle = json.loads((data / "ORACLE.json").read_bytes())
    assert oracle == {case["id"]: calculate(case["input"]) for case in cases}
    assert len(cases) == 40
    panels = []
    with TemporaryDirectory() as temp:
        source = Path(temp) / "case.json"
        for index, case in enumerate(cases):
            source.write_text(json.dumps(case["input"], separators=(",", ":")))
            arm_names = ("candidate", "exact_oracle", "ordinary_sqlite")
            panel = {key: case[key] for key in ("id", "family")}
            panel.update(expected=oracle[case["id"]], arms={arm: {} for arm in arm_names})
            for repeat in range(2):
                order = arm_names if (repeat + index) % 2 else arm_names[::-1]
                for arm in order:
                    if arm == "ordinary_sqlite":
                        began = perf_counter_ns()
                        prediction = sqlite_ordinary(case["input"])
                        elapsed, cpu = perf_counter_ns() - began, None
                    else:
                        script = candidate if arm == "candidate" else factory / "reference.py"
                        prediction, elapsed, cpu = cli(script, source)
                    slot = panel["arms"][arm]
                    slot.setdefault("predictions", prediction)
                    assert prediction == slot["predictions"], "NONREPEATABLE_" + arm
                    slot["exact"] = prediction == panel["expected"]
                    slot.setdefault("wall_ns", []).append(elapsed)
                    if cpu is not None:
                        slot.setdefault("child_cpu_ns", []).append(cpu)
                    else:
                        slot["child_cpu_ns"] = []
            panels.append(panel)
    assert sha(candidate) == CANDIDATE_SHA256, "candidate changed during evaluation"
    scored = {arm: score(panels, arm) for arm in arm_names}
    return {"schema": "frontier/independent-geospatial-holdout-result/v1", "reg_sha256": REGISTRATION_SHA256,
            "candidate_sha256": CANDIDATE_SHA256, "grade_source_sha256": sha(Path(__file__)),
            "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "scores": scored,
            "observed_scope": "Two exact cold CLI invocations per panel per executable. Ordinary SQLite is a warmed in-process approximate comparator.",
            "decision": "GO_SCOPED" if scored["candidate"]["exact_cases"] == 40 and scored["candidate"]["false_positive_ids"] == 0 else "NO_GO",
            "panels": panels}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = grade(args.data.resolve(), args.candidate.resolve(), Path(__file__).resolve().parent)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("decision", "scores")}, sort_keys=True))
