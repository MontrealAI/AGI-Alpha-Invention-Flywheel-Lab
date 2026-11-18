"""Deliver source-linked difference-photometry measurements from a frozen Fink interval."""
import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ["target_id", "g_candid", "r_candid", "g_jd", "r_jd", "g_utc", "r_utc",
          "g_diff_mag", "r_diff_mag", "g_error_mag", "r_error_mag", "separation_minutes",
          "g_minus_r_diff_mag", "formal_error_mag"]


def stamp(jd):
    instant = datetime.fromtimestamp((jd - 2440587.5) * 86400, timezone.utc)
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def format_pair(name, g, r):
    return {"target_id": name, "g_candid": str(g["i:candid"]), "r_candid": str(r["i:candid"]),
            "g_jd": g["i:jd"], "r_jd": r["i:jd"],
            "g_utc": stamp(g["i:jd"]), "r_utc": stamp(r["i:jd"]),
            "g_diff_mag": g["i:magpsf"], "r_diff_mag": r["i:magpsf"],
            "g_error_mag": g["i:sigmapsf"], "r_error_mag": r["i:sigmapsf"],
            "separation_minutes": round(abs(g["i:jd"]-r["i:jd"])*1440, 5),
            "g_minus_r_diff_mag": round(g["i:magpsf"]-r["i:magpsf"], 6),
            "formal_error_mag": round(math.hypot(g["i:sigmapsf"], r["i:sigmapsf"]), 6)}


def validate_gap(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("gap must be a finite, nonnegative number of minutes")


def measure(catalog, observed, interval, max_gap_minutes=120):
    validate_gap(max_gap_minutes)
    known = {t["id"] for t in catalog["targets"]}
    detections = defaultdict(list)
    seen = set()
    for row in observed:
        key = row["i:candid"]
        if key in seen:
            raise ValueError("repeated observation identifier")
        seen.add(key)
        name = row["i:objectId"]
        if name not in known or not interval[0] <= row["i:jd"] < interval[1]:
            raise ValueError("observation outside registered cohort/window")
        if (row["i:isdiffpos"] in ("t", "1") and row["i:fid"] in (1, 2, 3)
                and math.isfinite(row["i:magpsf"]) and math.isfinite(row["i:sigmapsf"])
                and row["i:sigmapsf"] > 0):
            detections[name].append(row)
    pairs, first = [], []
    for name in sorted(known):
        rows = detections[name]
        if rows:
            earliest = min(rows, key=lambda r: (r["i:jd"], r["i:candid"]))
            first.append({"target_id": name, "utc": stamp(earliest["i:jd"]),
                          "candid": str(earliest["i:candid"]), "band": {1:"g",2:"r",3:"i"}[earliest["i:fid"]],
                          "difference_mag": earliest["i:magpsf"], "formal_error_mag": earliest["i:sigmapsf"]})
        g_band = [r for r in rows if r["i:fid"] == 1]
        r_band = [r for r in rows if r["i:fid"] == 2]
        options = [(abs(g["i:jd"]-r["i:jd"]), g["i:jd"], r["i:jd"],
                    g["i:candid"], r["i:candid"], g, r)
                   for g, r in product(g_band, r_band)
                   if abs(g["i:jd"]-r["i:jd"])*1440 <= max_gap_minutes]
        if options:
            *_, g, r = min(options, key=lambda option: option[:5])
            pairs.append(format_pair(name, g, r))
    return {"max_gap_minutes": max_gap_minutes, "public_rows": len(observed), "targets": len(known), "first_detections": first,
            "pairs": pairs, "missing_pair": sorted(known - {r["target_id"] for r in pairs})}


def compare_sql(catalog, observed, interval, product_result, max_gap_minutes=120):
    validate_gap(max_gap_minutes)
    # A conventional row-number window on a two-band self join, without the producer's filter,
    # pair formatter, UTC conversion, or selection function. Integer ZTF subtraction-detection identifiers remain exact.
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE target(name TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO target VALUES (?)", [(t["id"],) for t in catalog["targets"]])
        db.execute("CREATE TABLE obs(name TEXT, candid INTEGER PRIMARY KEY, jd REAL, fid INTEGER, "
                   "mag REAL, err REAL, sign TEXT)")
        columns = ("i:objectId", "i:candid", "i:jd", "i:fid", "i:magpsf", "i:sigmapsf", "i:isdiffpos")
        db.executemany("INSERT INTO obs VALUES (?,?,?,?,?,?,?)",
                       [tuple(row[c] for c in columns) for row in observed])
        db.create_function("quad", 2, lambda a,b: (a*a + b*b)**0.5)
        cte = """WITH keep AS (
           SELECT o.* FROM obs AS o JOIN target USING(name) WHERE sign IN ('1','t')
           AND fid IN (1,2,3) AND jd >= ? AND jd < ? AND err > 0 AND err < 1e308
           AND abs(mag) < 1e308) """
        first = db.execute(cte + """SELECT name, CAST(candid AS TEXT),fid,mag,err, strftime('%Y-%m-%dT%H:%M:%fZ', jd) FROM
            (SELECT *, ROW_NUMBER() OVER (PARTITION BY name ORDER BY jd,candid) AS rank FROM keep)
            WHERE rank=1 ORDER BY name""", interval).fetchall()
        candidates = db.execute(cte + """, pairs AS (
            SELECT g.name, g.candid a, r.candid b, g.jd gj, r.jd rj, g.mag gm, r.mag rm, g.err ge, r.err re,
            g.mag-r.mag color, quad(g.err,r.err) sigma,
            abs(g.jd-r.jd)*1440 gap,
            ROW_NUMBER() OVER (PARTITION BY g.name ORDER BY abs(g.jd-r.jd),g.jd,r.jd,g.candid,r.candid) AS rank
            FROM keep g JOIN keep r ON g.name=r.name WHERE g.fid=1 AND r.fid=2 AND abs(g.jd-r.jd)*1440<=?)
            SELECT name, CAST(a AS TEXT), CAST(b AS TEXT), gj,rj,gm,rm,ge,re,color,sigma,gap,
                   strftime('%Y-%m-%dT%H:%M:%fZ', gj), strftime('%Y-%m-%dT%H:%M:%fZ', rj) FROM pairs
            WHERE rank=1 ORDER BY name""", [*interval, max_gap_minutes]).fetchall()
    finally:
        db.close()
    first_rows = product_result["first_detections"]
    pair_rows = product_result["pairs"]
    if len(first_rows) != len(first) or len(pair_rows) != len(candidates):
        raise ValueError("SQL disagrees with archive product counts")

    def same_time(a, b):
        # SQLite rounds to the nearest millisecond; Python's milliseconds display truncates.
        return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) <= 0.001

    for item, (name, candid, fid, mag, err, utc) in zip(first_rows, first):
        if ((item["target_id"], item["candid"], item["band"], item["difference_mag"], item["formal_error_mag"])
                != (name, candid, {1: "g", 2: "r", 3: "i"}[fid], mag, err) or not same_time(item["utc"], utc)):
            raise ValueError("SQL disagrees with a detection")
    for item, row in zip(pair_rows, candidates):
        name,g,r,gj,rj,gm,rm,ge,re,color,sigma,gap,g_utc,r_utc = row
        expected = (name,g,r,gj,rj,gm,rm,ge,re,round(color,6),round(sigma,6),round(gap,5))
        keys = ("target_id", "g_candid", "r_candid", "g_jd", "r_jd", "g_diff_mag", "r_diff_mag",
                "g_error_mag", "r_error_mag", "g_minus_r_diff_mag", "formal_error_mag", "separation_minutes")
        if (tuple(item[k] for k in keys) != expected or not same_time(item["g_utc"], g_utc)
                or not same_time(item["r_utc"], r_utc)):
            raise ValueError("SQL disagrees with a photometric pair, error or time window")
    missing = sorted({t["id"] for t in catalog["targets"]} - {r[0] for r in candidates})
    if (product_result["max_gap_minutes"] != max_gap_minutes or missing != product_result["missing_pair"]
            or product_result["public_rows"] != len(observed)
            or product_result["targets"] != len(catalog["targets"])):
        raise ValueError("archive-product scope differs")
    return {"agrees": True, "accepted_pairs": len(candidates), "with_detections": len(first)}


def evaluate(max_gap_minutes=120, catalog_path=ROOT/"catalog.json", observed_path=ROOT/"sources/fink-holdout.json",
             source_path=ROOT/"sources/holdout-source.json"):
    import hashlib
    catalog = json.loads(catalog_path.read_text())
    raw = observed_path.read_bytes()
    source = json.loads(source_path.read_text())
    if source["projection_sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("observations differ from source descriptor")
    observed = json.loads(raw)
    interval = source["interval_jd"]
    if (len(interval) != 2 or not all(type(x) in (float,int) and math.isfinite(x) for x in interval)
            or interval[0] >= interval[1] or source["retained_rows"] != len(observed)):
        raise ValueError("invalid source interval or observed row count")
    result = measure(catalog, observed, interval, max_gap_minutes)
    result["direct_sql"] = compare_sql(catalog, observed, interval, result, max_gap_minutes)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="new CSV path")
    parser.add_argument("--max-gap-minutes", type=float, default=120, help="largest allowed g/r separation")
    parser.add_argument("--catalog", type=Path, default=ROOT/"catalog.json")
    parser.add_argument("--observations", type=Path, default=ROOT/"sources/fink-holdout.json")
    parser.add_argument("--source", type=Path, default=ROOT/"sources/holdout-source.json",
                        help="observational interval and identity for the supplied measurements")
    args = parser.parse_args()
    result = evaluate(args.max_gap_minutes,args.catalog,args.observations,args.source)
    with args.out.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(result["pairs"])
    print(json.dumps(result["direct_sql"]))
