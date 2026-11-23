#!/usr/bin/env python3
"""Adjudicate bounded public ZTF witness acquisition and broker failure replays."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import product
import json
from pathlib import Path
import re
import sqlite3
import struct
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "autonomous_endpoint"))
from common import ROOT, SANDBOX, atomic, checked, clock, encode, load_module, measure, read, require, sha
from cycle import exclusive_state, signature, verify

REGISTRATION = HERE / "registration.json"
COLUMNS = "i:objectId,i:candid,i:jd,i:fid,i:magpsf,i:sigmapsf,i:isdiffpos"
OBJECT = re.compile(r"ZTF[0-9]{2}[a-z]{7}\Z")
TICKS = 10**11
DAY = 86400
JD_OFFSET = Decimal("2400000.5")
HALF_SECOND = Decimal("0.1")
SANDBOX_HASH = "103e2a8828a7aaf31faac475fb48ccbba1a685b4f64191dae4f6fbe8a9b6c7c8"


def jd(day):
    return Decimal((date.fromisoformat(day) - date(1970, 1, 1)).days) + Decimal("2440587.5")


def exact_json(raw):
    def unique(pairs):
        item = dict(pairs)
        require(len(item) == len(pairs), "DUPLICATE_SOURCE_FIELD")
        return item

    def invalid(_):
        raise ValueError("NONFINITE_SOURCE_NUMBER")

    return json.loads(raw, parse_float=Decimal, object_pairs_hook=unique, parse_constant=invalid)


def public_query(url, budget):
    wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
    response = {"url": url, "started_utc": clock(), "status": None, "sha256": None, "bytes": 0}
    try:
        with urlopen(Request(url, headers={"Accept": "application/json", "User-Agent": "MONTREAL.AI archive research replay"}),
                     timeout=budget["request_timeout_seconds"]) as result:
            response["status"] = result.status
            require(urlparse(result.geturl()).netloc == urlparse(url).netloc, "UNREGISTERED_SOURCE_REDIRECT")
            raw = result.read(budget["max_reply_bytes"] + 1)
        response.update({"sha256": sha(raw), "bytes": len(raw)})
        require(len(raw) <= budget["max_reply_bytes"], "SOURCE_SIZE_EXCEEDED")
        document = exact_json(raw)
        require(isinstance(document, list), "MALFORMED_SOURCE")
        return document, response
    except HTTPError as error:
        response.update({"status": error.code, "fault": "HTTP_ERROR"})
    except (URLError, OSError, ValueError) as error:
        response["fault"] = type(error).__name__
    finally:
        response.update({"wall_ns": time.perf_counter_ns() - wall, "thread_cpu_ns": time.thread_time_ns() - cpu})
    return [], response


def select(records, start, stop, excluded, limit):
    latest = {}
    for row in records:
        require(isinstance(row, dict), "MALFORMED_ROSTER")
        ident, tick = row["i:objectId"], Decimal(row["i:jd"])
        require(isinstance(ident, str) and OBJECT.fullmatch(ident) and tick.is_finite(), "MALFORMED_ROSTER")
        if start <= tick < stop and ident not in excluded:
            latest[ident] = max(latest.get(ident, tick), tick)
    return sorted(latest, key=lambda target: (-latest[target], target))[:limit]


def project(records, provider, ids, start, stop):
    points, conflicts, invalid = {}, set(), 0
    for row in records:
        try:
            if provider == "fink":
                target, ident, when, band, mag, sigma, sign = (row[key] for key in COLUMNS.split(","))
                positive = sign in ("t", "1", 1)
            else:
                target = ids[0]
                require(row.get("tid", "ztf") == "ztf" and row.get("oid", target) == target,
                        "ALTERNATE_OBJECT_IDENTITY_MISMATCH")
                ident, band, mjd, mag, sigma, sign = (row[k] for k in
                    ("candid", "fid", "mjd", "magpsf", "sigmapsf", "isdiffpos"))
                when, positive = Decimal(mjd) + JD_OFFSET, sign == 1
            if band not in (1, 2) or not positive:
                continue
            when, mag, sigma = Decimal(when), Decimal(mag), Decimal(sigma)
            require(target in ids and type(band) is int and str(ident).isdigit() and all(
                    v.is_finite() for v in (when, mag, sigma)) and sigma > 0, "MALFORMED_OBSERVATION")
            if not start <= when < stop:
                continue
            point = {"target": target, "id": str(ident), "band": band, "jd": str(when), "mag": str(mag),
                     "sigma": str(sigma), "provider": provider}
            key = (target, str(ident))
            if key in points and points[key] != point:
                conflicts.add(key)
            points[key] = point
        except (KeyError, TypeError, ValueError, InvalidOperation):
            invalid += 1
    return [p for key, p in points.items() if key not in conflicts], invalid, len(conflicts)


def equivalence(left, right, seconds):
    try:
        return (left["target"], left["id"], left["band"]) == (right["target"], right["id"], right["band"]) and all(
            struct.pack(">f", float(left[k])) == struct.pack(">f", float(right[k])) for k in ("mag", "sigma")) and abs(
                Decimal(left["jd"]) - Decimal(right["jd"])) * DAY <= seconds
    except (OverflowError, ValueError):
        return False


def acquire(ids, start, stop, registration, *, primary=True, alternate=True):
    providers, budget = registration["providers"], registration["budget"]
    fink_url = providers["primary"] + "?" + urlencode({"objectId": ",".join(ids), "columns": COLUMNS,
                                                         "output-format": "json"})
    def pull(target):
        return public_query(providers["alternate"].format(object=target), budget)

    begin = time.perf_counter_ns()
    fink, alerce, traces = [], [], {"primary": [], "alternate": []}
    if ids and primary:
        wire, trace = public_query(fink_url, budget)
        fink, invalid, conflicts = project(wire, "fink", ids, start, stop)
        traces["primary"].append(trace | {"invalid": invalid, "conflicts": conflicts, "retained": len(fink)})
    if ids and alternate:
        alt_begin = time.perf_counter_ns()
        with ThreadPoolExecutor(max_workers=budget["alternate_parallelism"]) as pool:
            for target, (wire, trace) in zip(ids, pool.map(pull, ids), strict=True):
                points, invalid, conflicts = project(wire, "alerce", [target], start, stop)
                alerce.extend(points)
                traces["alternate"].append(trace | {"invalid": invalid, "conflicts": conflicts, "retained": len(points)})
        traces["alternate_batch_wall_ns"] = time.perf_counter_ns() - alt_begin
    return fink, alerce, traces | {"acquisition_wall_ns": time.perf_counter_ns() - begin}


def points_for_arm(primary, secondary, seconds):
    by_key = defaultdict(list)
    for point in primary + secondary:
        by_key[(point["target"], point["id"])].append(point)
    admitted, conflicts = [], 0
    for group in by_key.values():
        if any(not equivalence(group[0], other, seconds) for other in group[1:]):
            conflicts += 1
        else:
            admitted.append(group[0])
    return admitted, conflicts


def witness(left, right):
    a, b = Decimal(left["jd"]), Decimal(right["jd"])
    return {"g": left, "r": right, "gap_seconds": str(abs(a - b) * DAY),
            "difference_mag": str(Decimal(left["mag"]) - Decimal(right["mag"])),
            "formal_sigma_mag": str((Decimal(left["sigma"])**2 + Decimal(right["sigma"])**2).sqrt())}


def certificate(rows, target, start, stop, limit, tolerance):
    relevant = [r for r in rows if r["target"] == target]
    choices = []
    for left, right in product((r for r in relevant if r["band"] == 1), (r for r in relevant if r["band"] == 2)):
        dates = [Decimal(left["jd"]), Decimal(right["jd"])]
        margin = sum((tolerance for point in (left, right) if point["provider"] == "alerce"), Decimal(0))
        if left["id"] != right["id"] and min(dates) >= start + margin/DAY and max(dates) < stop - margin/DAY:
            gap = abs(dates[0] - dates[1]) * DAY
            if gap + margin <= limit:
                choices.append((gap, dates[0], dates[1], left["id"], right["id"], left, right))
    if not choices:
        return None
    *_, left, right = min(choices)
    return witness(left, right)


def indexed(rows, target, start, stop, limit, tolerance):
    def tick(value):
        return int((Decimal(value) * TICKS).to_integral_value())

    with sqlite3.connect(":memory:") as database:
        database.execute("CREATE TABLE exposure (id TEXT PRIMARY KEY, target TEXT, band INTEGER, epoch INTEGER, error INTEGER)")
        database.executemany("INSERT INTO exposure VALUES(?,?,?,?,?)", [(r["id"], r["target"], r["band"], tick(r["jd"]),
                             int(tolerance * TICKS / DAY) + 1 if r["provider"] == "alerce" else 0) for r in rows])
        database.execute("CREATE INDEX target_band ON exposure(target,band,epoch,id)")
        row = database.execute("""
            SELECT a.id,b.id FROM exposure a JOIN exposure b ON a.target=b.target
            WHERE a.target=? AND a.band=1 AND b.band=2 AND a.id<>b.id
              AND min(a.epoch,b.epoch)>=?+a.error+b.error AND max(a.epoch,b.epoch)<?-a.error-b.error
              AND abs(a.epoch-b.epoch)+a.error+b.error<=?
            ORDER BY abs(a.epoch-b.epoch),a.epoch,b.epoch,a.id,b.id LIMIT 1
            """, (target, tick(start), tick(stop), int(limit * TICKS / DAY))).fetchone()
    values = {p["id"]: p for p in rows}
    return witness(values[row[0]], values[row[1]]) if row is not None else None


def accepted(pair, by_id, start, stop, limit, tolerance):
    if pair is None:
        return False
    a, b = pair["g"], pair["r"]
    if any((p["target"], p["id"]) not in by_id or not equivalence(p, by_id[(p["target"], p["id"])], tolerance)
           for p in (a, b)):
        return False
    a, b = (by_id[(p["target"], p["id"])] for p in (a, b))
    x, y = Decimal(a["jd"]), Decimal(b["jd"])
    return a["target"] == b["target"] and a["id"] != b["id"] and a["band"] == 1 and b["band"] == 2 and (
        start <= min(x, y) <= max(x, y) < stop and abs(x-y)*DAY <= limit)


def score(payload, registration):
    costs = {}
    targets, primary, alternate = (payload[k] for k in ("targets", "primary", "alternate"))
    start, stop = jd(payload["start"]), jd(payload["stop"])
    limit = Decimal(registration["contract"]["max_gap_minutes"]) * 60
    tolerance = Decimal(str(registration["contract"]["max_observed_provider_time_disagreement_seconds"]))
    held = {(p["target"], p["id"]): p for p in primary}
    joined, conflicts = points_for_arm(primary, alternate, tolerance)
    fragment = [p for p in primary if p["band"] == 1]
    fragment_alt = [p for p in alternate if p["band"] == 2]
    combined, fragmented_conflicts = points_for_arm(fragment, fragment_alt, tolerance)
    adaptive = payload["route"] == "combine-calibrated-brokers"
    arms = {"healthy_primary_sql": (indexed, primary), "ordinary_alternate_sql": (indexed, alternate),
            "proposed_alternate_witness": (certificate, alternate if adaptive else []),
            "combined_source_sql": (indexed, joined), "proposed_healthy_witness": (certificate, joined if adaptive else primary),
            "fragmented_single_broker_sql": (indexed, fragment), "fragmented_join_sql": (indexed, combined),
            "proposed_fragmented_witness": (certificate, combined if adaptive else fragment)}
    outcomes = {}
    for name, (solver, points) in arms.items():
        with measure(costs, name):
            decisions = {}
            for target in targets:
                pair = solver(points, target, start, stop, limit, tolerance)
                status = "ABSTAIN" if pair is None else ("ACCEPTED" if accepted(pair, held, start, stop, limit, tolerance)
                                                        else "REJECTED_WITNESS")
                decisions[target] = {"state": status, "witness": pair}
            outcomes[name] = {"counts": dict(Counter(r["state"] for r in decisions.values())), "decisions": decisions}
    returning_pairs = {name: set(target for target, r in results["decisions"].items() if r["state"] == "ACCEPTED")
                       for name, results in outcomes.items()}
    with measure(costs, "coverage_and_controls"):
        if primary:
            example = primary[0]
            conflict = example | {"mag": str(Decimal(example["mag"]) + 1), "provider": "alerce"}
            conflict_rows, n_conflicts = points_for_arm([example], [conflict], tolerance)
            require(n_conflicts == 1 and not conflict_rows, "CONTRADICTORY_EXPOSURE_NOT_WITHHELD")
        cutoff_input = {"i:objectId": "ZTF26abcdefg", "i:jd": str(stop)}
        require(not select([cutoff_input], start, stop, set(), 6), "OUTSIDE_CUTOFF_ACCEPTED")
        require(indexed([], "ZTF26abcdefg", start, stop, limit, tolerance) is None, "MISSING_SOURCE_ACCEPTED")
    with measure(costs, "boundary_controls"):
        target = "ZTF26abcdefg"
        g = {"target": target, "id": "1", "band": 1, "jd": str(start+Decimal("0.5")),
             "mag": "20", "sigma": "0.1", "provider": "fink"}
        near = g | {"id": "2", "band": 2, "jd": str(start+Decimal("0.58333"))}
        far = near | {"jd": str(start+Decimal("0.58334"))}
        require(all(solver([g, near], target, start, stop, limit, tolerance) for solver in (certificate, indexed)),
                "IN_BOUND_WITNESS_WITHHELD")
        require(all(solver([g, far], target, start, stop, limit, tolerance) is None for solver in (certificate, indexed)),
                "FALSE_BOUNDARY_WITNESS_ACCEPTED")
        malformed, invalid, _ = project([{}], "fink", [target], start, stop)
        require(not malformed and invalid == 1, "MALFORMED_DETECTION_ACCEPTED")
    return {"arms": outcomes, "costs": costs, "join_conflicts": conflicts, "fragmented_conflicts": fragmented_conflicts,
            "outage_discriminator": {"more_accepted_than_single_primary_fragment": len(
                returning_pairs["proposed_fragmented_witness"] - returning_pairs["fragmented_single_broker_sql"]),
                "more_accepted_than_competent_sql_join": len(
                returning_pairs["proposed_fragmented_witness"] - returning_pairs["fragmented_join_sql"]),
                "more_accepted_than_ordinary_alternate": len(
                returning_pairs["proposed_alternate_witness"] - returning_pairs["ordinary_alternate_sql"])} ,
            "controls": {"cutoff": True, "source_missing": True, "conflict": bool(primary),
                         "malformed_detection": True, "both_sides_of_gap_boundary": True}}


def source_identity():
    return {name: sha((HERE / name).read_bytes()) for name in ("registration.json", "replay.py", "constructor.py")}


def frozen_plan(state, registration):
    marker = state / "freeze.json"
    identity = source_identity()
    if marker.exists():
        existing = read(marker)
        require(existing["identity"] == identity, "FROZEN_PROTOCOL_CHANGED")
        return existing
    costs = {}
    with measure(costs, "development_acquire"):
        prior = registration["prior"]
        source = checked(["git", "-C", str(ROOT), "show", f"{prior['commit']}:{prior['path']}/sources/objects.json"])
        require(sha(source) == registration["development"]["primary_blob_sha256"], "DEVELOPMENT_SOURCE_CHANGED")
        report = checked(["git", "-C", str(ROOT), "show", f"{prior['commit']}:{prior['path']}/sources/holdout-source.json"])
        from urllib.parse import parse_qs
        ids = parse_qs(urlparse(json.loads(report)["query"]).query)["objectId"][0].split(",")
        start, stop = (jd(registration["development"][k]) for k in ("start", "stop"))
        fink, invalid, conflict = project(exact_json(source), "fink", ids, start, stop)
        require(not invalid and not conflict, "DEVELOPMENT_SOURCE_CONFLICT")
        _, alternative, trace = acquire(ids, start, stop, registration, primary=False)
    reference = {(p["target"], p["id"]): p for p in fink}
    matched = [p for p in alternative if (p["target"], p["id"]) in reference]
    conflicts = [p for p in matched if not equivalence(p, reference[(p["target"], p["id"])], HALF_SECOND)]
    with measure(costs, "construction"):
        require(sha(SANDBOX.read_bytes()) == SANDBOX_HASH, "EXACT_SANDBOX_REQUIRED")
        sandbox = load_module("photometry_pinned_sandbox", SANDBOX)
        receipt = sandbox.run(HERE / "constructor.py", "construct", {"matched_exposures": len(matched),
                              "conflicts": len(conflicts)}, identity["constructor.py"])
        require(receipt["state"] == "COMPLETE", "CONSTRUCTOR_FAILED")
        plan = receipt["worker"]["result"]
        require(plan["route"] in {"combine-calibrated-brokers", "primary-only"}, "INVALID_CONSTRUCTION")
    frozen = {"identity": identity, "plan": plan, "development_targets": ids, "costs": costs,
              "development_acquisition": trace, "frozen_at": clock(), "constructor_confinement": receipt["worker"]["confinement"]}
    atomic(marker, frozen)
    return frozen


def run(state, destination):
    require(not destination.resolve().is_relative_to(state.resolve()), "EXPORT_OUTSIDE_EVALUATOR_STATE_REQUIRED")
    with exclusive_state(state):
        registration = read(REGISTRATION)
        freeze = frozen_plan(state, registration)
        excluded, replay, costs = set(freeze["development_targets"]), [], {}
        for spec in registration["confirmation"]:
            saved = state / (spec["name"] + ".json")
            if not saved.exists():
                url = registration["providers"]["roster"] + "?" + urlencode({"class": "SLSN candidate",
                      "n": registration["budget"]["max_roster_alerts"], "startdate": spec["select_start"],
                      "stopdate": spec["select_stop"], "columns": "i:objectId,i:jd", "output-format": "json"})
                raw, trace = public_query(url, registration["budget"])
                targets = select(raw, jd(spec["select_start"]), jd(spec["select_stop"]), excluded,
                                 registration["budget"]["max_targets"])
                primary, alternate, requests = acquire(targets, jd(spec["start"]), jd(spec["stop"]), registration)
                atomic(saved, spec | {"targets": targets, "primary": primary, "alternate": alternate, "roster": trace,
                       "requests": requests, "route": freeze["plan"]["route"], "freeze_sha256": sha(encode(freeze)),
                       "case_selection_utc": trace["started_utc"]})
            data = read(saved)
            require(data["freeze_sha256"] == sha(encode(freeze)) and not (set(data["targets"]) & excluded),
                    "CUSTODY_OR_COHORT_CHANGED")
            excluded.update(data["targets"])
            with measure(costs, spec["name"]):
                replay.append({"observations": data, "scientific_result": score(data, registration)})
        require(freeze["identity"] == source_identity(), "FROZEN_EVALUATOR_CHANGED")
        verdict = {"schema": "frontier-omega-alpha/photometry-resilience-receipt-v1", "completed_utc": clock(),
                   "freeze": freeze, "verification_costs": costs, "campaigns": replay,
                   "authorization": "public scientific archive research", "endpoint_operational_adoption": "ABSTAIN",
                   "endpoint_incumbent": "indexed-sqlite", "complete_operating_cost": None, "productive_s1": False,
                   "s2": "UNPROVEN", "constructor_improvement": "UNPROVEN", "learning_rule_improvement": "UNPROVEN",
                   "custody": "confined constructor and separate evaluator role on same administrative host",
                   "routine_human_operation": 0}
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic(destination, signature(state, verdict))


def audit(path, expected_key=None):
    receipt = verify(path, expected_key)["receipt"]
    require(receipt["freeze"]["identity"] == source_identity(), "REPLAY_IMPLEMENTATION_CHANGED")
    registration = read(REGISTRATION)
    for campaign in receipt["campaigns"]:
        fresh = score(campaign["observations"], registration)
        expected = campaign["scientific_result"]
        require({k: v for k, v in fresh.items() if k != "costs"} == {k: v for k, v in expected.items() if k != "costs"},
                "INDEPENDENT_REPLAY_MISMATCH")
    return {"signature_valid": True, "campaigns_replayed": len(receipt["campaigns"]),
            "targets": sum(len(r["observations"]["targets"]) for r in receipt["campaigns"])}


def main():
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    live = commands.add_parser("run")
    live.add_argument("--state", type=Path, required=True)
    live.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("audit")
    check.add_argument("receipt", type=Path)
    check.add_argument("--key-sha256")
    args = parser.parse_args()
    if args.command == "run":
        run(args.state, args.output)
    else:
        print(encode(audit(args.receipt, args.key_sha256)).decode(), end="")


if __name__ == "__main__":
    main()
