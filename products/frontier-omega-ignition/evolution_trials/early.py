"""Conventional source-to-queue route for the October Fink population. No producer imports."""
import argparse
from collections import Counter
from contextlib import closing
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .verify import decide, fail_unless, from_utc, read_pinned, require_match, roster_for
else:
    from verify import decide, fail_unless, from_utc, read_pinned, require_match, roster_for

HERE = Path(__file__).resolve().parent
SOURCES = HERE.parent / "invention/early_survey/sources"
OBS_INDEX = "80829974c96cfae41ff587d5fad038229d05e50ae04ec99d80accd01c5b6fe7e"
REF_INDEX = "e5740fff884ba87a3779b373e2ed09e58d37fcd177c467e2c0ae22037c057ddb"
SELECT_FROM, START, END = "2026-10-18T00:00:00Z", "2026-10-25T00:00:00Z", "2026-11-01T00:00:00Z"


def rows_for(folder, entry):
    raw = gzip.decompress((folder / entry["file"]).read_bytes())
    fail_unless(entry["status"] == 200 and hashlib.sha256(raw).hexdigest() == entry["sha256"]
                and len(raw) == entry["bytes"], "Acquired public response identity differs")
    rows = json.loads(raw, parse_float=Decimal)
    fail_unless(type(rows) is list and len(rows) == entry["rows"], "Response row count differs")
    return rows


def all_objects(folder, entries, roster):
    all_rows, requested = [], []
    for entry in entries:
        names = parse_qs(urlsplit(entry["url"]).query)["objectId"][0].split(",")
        fetched = rows_for(folder, entry)
        fail_unless(all(r["i:objectId"] in names for r in fetched), "Unexpected target in response")
        all_rows.extend(fetched)
        requested.extend(names)
    fail_unless(sorted(requested) == roster and len({r["i:candid"] for r in all_rows}) == len(all_rows),
                "Object coverage or identity differs")
    return all_rows


def broker_value(row, key):
    value = row.get(key)
    return float(value) if type(value) in (int, Decimal) and Decimal(value).is_finite() else None


def lookup(db, alert):
    stages = [alert[name] for name in ("baseline", "trigger", "followup") if alert[name] is not None]
    rows = []
    for stage in stages:
        data = db.execute("""
            SELECT m.target,m.field,m.channel,m.rate,m.error,m.lag,m.upper_flag,
                   r.target AS ref_target,r.field AS ref_field,r.channel AS ref_channel,r.reference
              FROM measures m LEFT JOIN refs r USING(candid) WHERE m.candid=?
        """, (stage["candid"],)).fetchone()
        fail_unless(data is not None, "Missing source for a delivered measurement")
        if data["ref_target"] is not None:
            fail_unless((data["target"], data["field"], data["channel"]) ==
                        (data["ref_target"], data["ref_field"], data["ref_channel"]), "Reference linkage differs")
        rows.append(data)
    images = [r["reference"] for r in rows]
    ref_status = "unknown" if None in images else ("matched" if len(set(images)) == 1 else "changed")
    alert["reference_image"] = {"status": ref_status, "rfids": images}
    trigger = rows[1]
    alert["broker_at_trigger"] = dict(rate_mag_per_day=trigger["rate"], sigma_mag_per_day=trigger["error"],
                                      gap_days=trigger["lag"], from_upper=json.loads(trigger["upper_flag"]))


def direct(as_of=END, *, folder=SOURCES):
    cutoff = from_utc(as_of)
    result = dict(scope="paired historical early-supernova candidate archive study", as_of_utc=as_of,
                  cohorts=[], summary={})
    if cutoff < from_utc(START):
        return result
    manifest = read_pinned(folder / "index.json", OBS_INDEX)
    ref_manifest = read_pinned(folder / "reference-index.json", REF_INDEX)
    roster = roster_for(rows_for(folder, manifest["requests"][0]), from_utc(SELECT_FROM), from_utc(START), 36)
    fail_unless(roster == manifest["selected_targets"], "Reselected class roster differs")
    objects = all_objects(folder, manifest["requests"][1:], roster)
    references = all_objects(folder, ref_manifest, roster)
    public = [r for r in objects if type(r["i:programid"]) is int and r["i:programid"] == 1]
    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE measures(candid TEXT PRIMARY KEY,target TEXT,field INTEGER,channel INTEGER,
                                  rate REAL,error REAL,lag REAL,upper_flag TEXT);
            CREATE TABLE refs(candid TEXT PRIMARY KEY,target TEXT,field INTEGER,channel INTEGER,reference TEXT);
        """)
        db.executemany("INSERT INTO measures VALUES (?,?,?,?,?,?,?,?)",
                       ((str(r["i:candid"]), r["i:objectId"], r["i:field"], r["i:rcid"],
                         broker_value(r, "d:mag_rate"), broker_value(r, "d:sigma_rate"), broker_value(r, "d:delta_time"),
                         json.dumps(r.get("d:from_upper"))) for r in public))
        db.executemany("INSERT INTO refs VALUES (?,?,?,?,?)",
                       ((str(r["i:candid"]), r["i:objectId"], r["i:field"], r["i:rcid"],
                         str(r["i:rfid"]) if type(r.get("i:rfid")) is int and r["i:rfid"] > 0 else None) for r in references))
        for key, days in (("early_cold", 0), ("early_warm", 7)):
            group = decide(roster, public, from_utc(START), cutoff, baseline_lookback_days=days,
                           reference_fields=("i:field", "i:rcid"))
            for alert in group["alerts"]:
                lookup(db, alert)
            group.update(id=key, start_utc=START, end_utc=END, targets=roster,
                         source_sha256={"archive_index": OBS_INDEX, "reference_index": REF_INDEX})
            result["cohorts"].append(group)
            result["summary"][key] = dict(comparisons=sum(row["comparisons"] for row in group["coverage"]),
                                          alerts=len(group["alerts"]), **Counter(row["status"] for row in group["alerts"]))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", default=END, help="exclusive UTC event-time boundary")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--out", type=Path, help="write a full source-linked result to a fresh file")
    group.add_argument("--check", type=Path, help="verify the complete producer result from public source responses")
    args = p.parse_args()
    observed = direct(args.as_of)
    if args.check:
        require_match(observed, json.loads(args.check.read_bytes()))
        print(json.dumps(observed["summary"]))
    elif args.out:
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(observed, stream, indent=2, allow_nan=False)
            stream.write("\n")
    else:
        print(json.dumps(observed, indent=2, allow_nan=False))
