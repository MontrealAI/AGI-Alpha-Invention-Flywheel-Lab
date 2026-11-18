"""Direct SQL control and independent source-bound recipient for the difference-light queue."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "invention"
DAY = 86_400_000_000_000
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
JD_EPOCH = Decimal("2440587.5")
DEFAULT_AS_OF = "2026-11-17T00:00:00Z"
STATUSES = ("persisted", "reversed", "not_reproduced", "coverage_gap", "right_censored", "awaiting_repeat")
ACTIONS = {
    "no_trigger": "monitor_archive", "awaiting_repeat": "inspect_next_same_band_detection",
    "persisted": "inspect_subtractions_and_reference_identity", "reversed": "withdraw_review_alert",
    "not_reproduced": "withdraw_review_alert", "coverage_gap": "seek_missing_in_window_data",
    "right_censored": "obtain_remaining_ledger_interval",
}
SOURCES = (
    ("nov01", "2026-11-01T00:00:00Z", "sources", "fink-alerts.json", "fink-holdout.json",
     "5a50023cc996b443ae4d4aea6d599d184f76caea9aa94f5e614e462793e5c250",
     "d8677d608223f3119eb13c5f54d820d4f5f5b064da23cd1d5da310db75d91597"),
    ("nov10", "2026-11-10T00:00:00Z", "next_week/sources", "alerts.json", "objects.json",
     "a55a4d43d46ea18cec4a838504d6ac7058b753c7f1fae0119ac9a91e65788fcc",
     "e3e82fd193ded81c804c80e01fdfbc35ad88effb958ff73e72b7c3f442292ced"),
)


def fail_unless(condition, message):
    if not condition:
        raise ValueError(message)


def from_jd(jd):
    value = (Decimal(jd) - JD_EPOCH) * DAY
    fail_unless(value.is_finite() and value == value.to_integral_value(), "Unrepresentable source timestamp")
    return int(value)


def from_utc(iso):
    instant = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    fail_unless(instant.utcoffset() == timedelta(0), "Use an explicit UTC timezone")
    delta = instant - EPOCH
    return delta.days * DAY + delta.seconds * 1_000_000_000 + delta.microseconds * 1000


def stamp(ns, *, measurement=False):
    if measurement:
        instant = EPOCH + timedelta(milliseconds=ns // 1_000_000)
        return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    instant = EPOCH + timedelta(microseconds=ns // 1000)
    return instant.isoformat().replace("+00:00", "Z")


def signed_change(m0, m1):
    return Decimal(m1) - Decimal(m0)


def large_enough(change, err0, err1, sigmas):
    # Compare squared formal uncertainties. No rounded score or float square root enters a decision.
    return (abs(change) >= Decimal("0.20")
            and change * change >= sigmas**2 * (Decimal(err0)**2 + Decimal(err1)**2))


def trigger_pass(m0, m1, e0, e1, lag_ns):
    delta = signed_change(m0, m1)
    return large_enough(delta, e0, e1, 3) and abs(delta) * DAY >= Decimal("0.10") * lag_ns


def follow_disposition(m0, m1, m2, e0, e2):
    change = signed_change(m0, m2)
    if not large_enough(change, e0, e2, 2):
        return "not_reproduced"
    return "persisted" if change * signed_change(m0, m1) > 0 else "reversed"


def read_pinned(path, digest):
    raw = path.read_bytes()
    fail_unless(hashlib.sha256(raw).hexdigest() == digest, f"Source identity differs: {path.name}")
    return json.loads(raw, parse_float=Decimal)


def roster_for(alerts, start, end, maximum):
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE classes(target TEXT, tick INTEGER)")
        db.executemany("INSERT INTO classes VALUES (?,?)",
                       [(a["i:objectId"], from_jd(a["i:jd"])) for a in alerts])
        return sorted(r[0] for r in db.execute("""
            SELECT target FROM classes WHERE tick>=? AND tick<?
            GROUP BY target ORDER BY max(tick) DESC,target LIMIT ?""", (start, end, maximum)))


def read_cohort(spec, source=SOURCE):
    cohort, start, subdir, alerts, objects, class_hash, history_hash = spec
    directory = source / subdir
    classes = read_pinned(directory / "alerts-source.json", class_hash)
    history = read_pinned(directory / "holdout-source.json", history_hash)
    cls_id = classes["alerts_sha256"]
    obs_id = history["projection_sha256"] if cohort == "nov01" else history["upstream_sha256"]
    class_rows = read_pinned(directory / alerts, cls_id)
    obj_rows = read_pinned(directory / objects, obs_id)
    targets = roster_for(class_rows, from_utc(classes["selection_start_utc"]), from_utc(start),
                         classes["max_targets"])
    fail_unless(all(r["i:objectId"] in targets for r in obj_rows), "Object outside selected target roster")
    hashes = dict(class_response=cls_id, observation_file=obs_id, class_descriptor=class_hash,
                  observation_descriptor=history_hash)
    return targets, obj_rows, hashes


def science_value(value):
    return isinstance(value, (int, Decimal)) and not isinstance(value, bool) and Decimal(value).is_finite()


def witness(row, with_detector=False):
    result = dict(candid=str(row["i:candid"]), jd=float(row["i:jd"]), utc=stamp(from_jd(row["i:jd"]), measurement=True),
                mag=float(row["i:magpsf"]), error_mag=float(row["i:sigmapsf"]))
    if with_detector:
        result.update(field=row["i:field"], rcid=row["i:rcid"])
    return result


def sigma(a, b):
    return (Decimal(a["i:sigmapsf"])**2 + Decimal(b["i:sigmapsf"])**2).sqrt()


def delivered(value):
    return float(round(value, 6))


def pair_details(a, b, references):
    delta = signed_change(a["i:magpsf"], b["i:magpsf"])
    days = Decimal(b["i:jd"]) - Decimal(a["i:jd"])
    err = sigma(a, b)
    gates = dict(change=abs(delta) >= Decimal("0.20"), rate=abs(delta) >= Decimal("0.10") * days,
                 formal_error=delta**2 >= 9 * (Decimal(a["i:sigmapsf"])**2 + Decimal(b["i:sigmapsf"])**2))
    return dict(baseline=witness(a, references), trigger=witness(b, references), delta_mag=delivered(delta),
                gap_days=delivered(days), formal_error_mag=delivered(err), rate_mag_per_day=delivered(delta / days),
                gates=gates)


def strongest_pair(row, by_id, references):
    if row["strongest_issue"] is None:
        return None
    a, b = (by_id[int(row[field])] for field in ("strongest_base", "strongest_current"))
    return dict(issued_utc=stamp(row["strongest_issue"]), **pair_details(a, b, references))


def decide(targets, rows, start_ns, cutoff_ns, *, baseline_lookback_days=0, reference_fields=()):
    """Calculate a seven-day queue. Optional prior days are eligible only as baselines.

    With reference_fields, every matched physical reference field must be present and equal
    for the comparison or repeat. The original registered two cohorts use the empty tuple.
    """
    fail_unless(type(baseline_lookback_days) is int and 0 <= baseline_lookback_days <= 7,
                "Extra baseline history must lie within the seven-day comparison rule")
    fail_unless(cutoff_ns >= start_ns and len(set(targets))==len(targets), "Invalid cutoff or duplicate target")
    fail_unless(reference_fields in ((), ("i:field", "i:rcid")), "Unknown detector stream fields")
    end_ns = start_ns + 7 * DAY
    cutoff = min(cutoff_ns, end_ns)
    by_id, history = {}, []
    source_rows = eligible_count = 0
    for row in rows:
        cid = row["i:candid"]
        fail_unless(type(cid) is int and cid > 0 and cid not in by_id, "Invalid or repeated detection identifier")
        fail_unless(row["i:objectId"] in targets, "Object outside selected target roster")
        by_id[cid] = row
        t = from_jd(row["i:jd"])
        if start_ns <= t < cutoff:
            source_rows += 1
        if t < start_ns - baseline_lookback_days*DAY or t >= cutoff:
            continue
        mag, error, band = row["i:magpsf"], row["i:sigmapsf"], row["i:fid"]
        if (row["i:isdiffpos"] not in ("1", "t") or type(band) is not int or band not in (1, 2)
                or not science_value(mag) or not science_value(error) or error <= 0):
            continue
        ref_values = [row.get(field) for field in reference_fields]
        if reference_fields:
            field, channel = ref_values
            if type(field) is not int or field <= 0 or type(channel) is not int or not 0 <= channel < 64:
                continue
        identity = json.dumps(ref_values)
        history.append((row["i:objectId"], band, str(cid), t, str(mag), str(error), identity))
        eligible_count += t >= start_ns

    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        db.create_function("trigger_pass", 5, trigger_pass, deterministic=True)
        db.create_function("follow_disposition", 5, follow_disposition, deterministic=True)
        db.create_function("change_abs", 2, lambda a, b: str(abs(signed_change(a, b))), deterministic=True)
        db.create_collation("magnitude", lambda a, b: (Decimal(a) > Decimal(b)) - (Decimal(a) < Decimal(b)))
        db.executescript("""
            CREATE TABLE history(target TEXT,band INTEGER,candid TEXT PRIMARY KEY,t INTEGER,mag TEXT,err TEXT,ref TEXT);
            CREATE TABLE nights(t INTEGER PRIMARY KEY);
            CREATE TABLE roster(target TEXT PRIMARY KEY);
            CREATE TABLE bands(band INTEGER PRIMARY KEY);
            INSERT INTO bands VALUES(1),(2);
        """)
        db.executemany("INSERT INTO history VALUES(?,?,?,?,?,?,?)", history)
        db.execute("CREATE TEMPORARY TABLE valid AS SELECT * FROM history WHERE t>=?", (start_ns,))
        db.executemany("INSERT INTO roster VALUES(?)", ((v,) for v in targets))
        db.executemany("INSERT INTO nights VALUES(?)", ((t,) for t in range(start_ns + DAY, cutoff + 1, DAY)))
        decisions = db.execute((HERE / "select.sql").read_text(), dict(day=DAY, cutoff=cutoff, end=end_ns)).fetchall()

    alerts, coverage = [], []
    for row in decisions:
        target, band, status = row["target"], {1: "g", 2: "r"}[row["band"]], row["status"]
        coverage.append(dict(target_id=target, band=band, eligible_detections=row["detections"],
                             comparisons=row["comparisons"], status=status, action=ACTIONS[status],
                             strongest_comparison=strongest_pair(row, by_id, bool(reference_fields))))
        if row["issue"] is None:
            continue
        a, b = (by_id[int(row[s])] for s in ("base_id", "current_id"))
        delta = signed_change(a["i:magpsf"], b["i:magpsf"])
        next_obs = by_id[int(row["next_id"])] if row["next_id"] is not None else None
        alerts.append(dict(target_id=target, band=band, issued_utc=stamp(row["issue"]),
                           deadline_utc=stamp(row["issue"] + 3 * DAY), direction="fading" if delta > 0 else "brightening",
                           **pair_details(a, b, bool(reference_fields)), followup=witness(next_obs, bool(reference_fields)) if next_obs else None,
                           followup_delta_mag=delivered(signed_change(a["i:magpsf"], next_obs["i:magpsf"])) if next_obs else None,
                           followup_formal_error_mag=delivered(sigma(a, next_obs)) if next_obs else None, status=status, action=ACTIONS[status]))
    alerts.sort(key=lambda a: (a["issued_utc"], a["target_id"], a["band"]))
    result = dict(source_rows=source_rows, eligible_rows=eligible_count, alerts=alerts, coverage=coverage)
    if baseline_lookback_days:
        result["eligible_baseline_history_rows"] = len(history) - eligible_count
    return result


def conventional(as_of=None, source=SOURCE):
    instant = from_utc(as_of or DEFAULT_AS_OF)
    cohorts = []
    for spec in SOURCES:
        cohort, start = spec[:2]
        start_ns = from_utc(start)
        if instant < start_ns:
            continue
        targets, rows, hashes = read_cohort(spec, source)
        decisions = decide(targets, rows, start_ns, instant)
        cohorts.append(dict(id=cohort, start_utc=start, end_utc=stamp(start_ns+7*DAY), targets=targets,
                            source_sha256=hashes, **decisions))
    statuses = Counter(a["status"] for c in cohorts for a in c["alerts"])
    overlap = sorted(set(cohorts[0]["targets"]) & set(cohorts[1]["targets"])) if len(cohorts) == 2 else []
    return dict(scope="registered public archive event-time replay", as_of_utc=as_of or DEFAULT_AS_OF,
                cohorts=cohorts, overlap=overlap,
                summary={"alerts": sum(statuses.values()), **{key: statuses[key] for key in STATUSES}})


def require_match(expected, actual, path="result"):
    # Source-bound delivery requires the complete expected content, including follow-up actions.
    if isinstance(expected, dict):
        fail_unless(isinstance(actual, dict), f"Expected object at {path}")
        fail_unless(set(actual) == set(expected), f"Field set differs at {path}")
        for key, value in expected.items():
            fail_unless(key in actual, f"Missing {path}.{key}")
            require_match(value, actual[key], path + "." + key)
    elif isinstance(expected, list):
        fail_unless(isinstance(actual, list) and len(expected) == len(actual), f"Count differs at {path}")
        for i, (want, item) in enumerate(zip(expected, actual)):
            require_match(want, item, f"{path}[{i}]")
    else:
        fail_unless(type(expected) is type(actual) and expected == actual, f"Value differs at {path}")


def verify(product, as_of=None, *, source=SOURCE):
    expected = conventional(as_of, source)
    require_match(expected, product)
    return dict(agrees=True, cohorts=len(expected["cohorts"]), target_band_decisions=sum(
        len(c["coverage"]) for c in expected["cohorts"]), alerts=expected["summary"]["alerts"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="right-open UTC archive cutoff; defaults to the final registered midnight")
    parser.add_argument("--check", type=Path, help="independently verify a candidate delivery")
    parser.add_argument("--out", type=Path, help="write direct SQL delivery to a new JSON file")
    args = parser.parse_args()
    if args.check:
        result = verify(json.loads(args.check.read_bytes()), args.as_of)
    else:
        result = conventional(args.as_of)
    if args.out:
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, allow_nan=False)
            f.write("\n")
    else:
        print(json.dumps(result, indent=2, allow_nan=False))
