"""Run the matched successor comparison on a frozen ledger of hardware evidence."""

from argparse import ArgumentParser
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from statistics import median
import sys
from time import perf_counter_ns, process_time_ns

from ..endpoint_study import decision, reference

HERE = Path(__file__).resolve().parent
S1 = HERE.parent / "endpoint_study"
S1_REVISION = "d1cc2651546341e0f48cc5b114337337c3558a7e"
S1_HASHES = {
    "decision.py": "fb0796f64ece515a2d600d6ae4357d4f0f195bfe27d497e117e386b8c72e5fe0",
    "reference.py": "a024b214cbef2ab45a15cffb60912d29d12425f92d9d5c0d364ced36693d525c",
}
DAYS = (
    "2026-09-28", "2026-09-29", "2026-10-05", "2026-10-20", "2026-10-21", "2026-11-23",
)
ROLES = (
    "announcement", "orderable", "documented-specification", "tracking-reported",
    "receipt-reported", "firmware-support-declared", "independent-application", "economic-feasibility",
)


def adapt(sources):
    return [
        {"id": f"{source['id']}/{role}", "published": source["published"],
         "facts": {"role": role}, "metric": "1", "objective": "1"}
        for source in sources for role in source["roles"]
    ]


def selected_sources(result):
    return [key.split("/", 1)[0] for key in result["winners"]]


def retained(sources):
    rows = adapt(sources)
    return {day: {role: selected_sources(decision.evaluate(rows, {"role": role}, day, "1"))
                  for role in ROLES} for day in DAYS}


def ordinary_reuse(sources):
    rows = adapt(sources)
    return {day: {role: selected_sources(reference.evaluate_many(rows, {"role": role}, day, ["1"])[0])
                  for role in ROLES} for day in DAYS}


def direct_sql(sources):
    result = {day: {role: [] for role in ROLES} for day in DAYS}
    with closing(sqlite3.connect(":memory:")) as db:
        query = """
            WITH observations AS (
                SELECT json_extract(value, '$.id') AS source_id,
                       json_extract(value, '$.published') AS documented,
                       json_extract(value, '$.roles') AS role_list
                FROM json_each(:sources)
            )
            SELECT scopes.value, labels.value, observations.source_id
            FROM observations, json_each(observations.role_list) AS claims,
                 json_each(:days) AS scopes, json_each(:roles) AS labels
            WHERE observations.documented <= scopes.value AND claims.value = labels.value
            ORDER BY observations.source_id
        """
        for day, role, ident in db.execute(query, {
            "sources": json.dumps(sources), "days": json.dumps(DAYS), "roles": json.dumps(ROLES),
        }):
            result[day][role].append(ident)
    return result


def run(measure=False):
    if any(sha256((S1 / name).read_bytes()).hexdigest() != expected for name, expected in S1_HASHES.items()):
        raise ValueError("The frozen S1 comparison source has changed")
    content = (HERE / "observations.json").read_bytes()
    sources = json.loads(content)["sources"]
    if len({source["id"] for source in sources}) != len(sources):
        raise ValueError("Duplicate source identity")
    arms = (retained, ordinary_reuse, direct_sql)
    baseline = direct_sql(sources)
    if any(arm(sources) != baseline for arm in arms[:-1]):
        raise ValueError("Successor arms disagree")
    dated = {source["id"]: source["published"] for source in sources}
    receipt = {
        "schema": "frontier-omega-alpha/alpha-1-milestone-receipt-v1",
        "frozen_s1_commit": S1_REVISION,
        "s1_files_sha256": S1_HASHES,
        "observations_sha256": sha256(content).hexdigest(),
        "matched_cells": len(DAYS) * len(ROLES),
        "arms": [arm.__name__ for arm in arms],
        "established_firsts_in_observed_record": {
            role: min((dated[key] for key in keys), default=None)
            for role, keys in baseline[DAYS[-1]].items()
        },
        "witnesses_by_cutoff": baseline,
        "causal_inventor_improvement_established": False,
        "economic_advantage_established": False,
        "production_authority": False,
    }
    if measure:
        print(json.dumps(timings(arms, sources), sort_keys=True), file=sys.stderr)
    return receipt


def timings(arms, sources):
    results = {arm.__name__: [] for arm in arms}
    for rep in range(21):
        offset = rep % len(arms)
        for arm in arms[offset:] + arms[:offset]:
            wall, cpu = perf_counter_ns(), process_time_ns()
            arm(sources)
            results[arm.__name__].append((perf_counter_ns() - wall, process_time_ns() - cpu))
    return {"repetitions": 21, "median_ns": {
        name: {"wall": median(wall for wall, _ in runs), "cpu": median(cpu for _, cpu in runs)}
        for name, runs in results.items()
    }, "scope": "Adapter and decision only; common evidence acquisition and authoring excluded."}


def checked_receipt():
    result = run()
    if result != json.loads((HERE / "receipt.json").read_bytes()):
        raise ValueError("Hardware evidence differs from the registered replay")
    return result


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--measure", action="store_true")
    args = parser.parse_args()
    result = run(args.measure)
    if args.check and result != json.loads((HERE / "receipt.json").read_bytes()):
        raise SystemExit("Hardware evidence differs from the registered replay")
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True))
