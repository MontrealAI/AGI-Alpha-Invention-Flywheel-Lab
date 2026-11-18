"""Reproduce the second ZTF cohort using source bytes, SQLite and exact decimal photometry."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
from itertools import product
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import photometry
import reference

D = Decimal
OPEN, CUTOFF, END = map(D, ("2461347.5", "2461354.5", "2461361.5"))
DATE_START, DATE_CUTOFF, DATE_END = ("2026-11-03T00:00:00Z", "2026-11-10T00:00:00Z", "2026-11-17T00:00:00Z")
META_SHA = {
    "alerts-source.json": "a55a4d43d46ea18cec4a838504d6ac7058b753c7f1fae0119ac9a91e65788fcc",
    "holdout-source.json": "e3e82fd193ded81c804c80e01fdfbc35ad88effb958ff73e72b7c3f442292ced",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sources():
    meta = {}
    for name, digest in META_SHA.items():
        data = (HERE / "sources" / name).read_bytes()
        require(sha(data) == digest, f"Changed source descriptor: {name}")
        meta[name] = json.loads(data)
    a, b = meta["alerts-source.json"], meta["holdout-source.json"]
    raw_a = (HERE / "sources/alerts.json").read_bytes()
    raw_b = (HERE / "sources/objects.json").read_bytes()
    require((sha(raw_a), len(raw_a)) == (a["alerts_sha256"], a["raw_bytes"]), "Changed class response")
    require((sha(raw_b), len(raw_b)) == (b["upstream_sha256"], b["upstream_bytes"]), "Changed object response")
    require((a["selection_start_utc"], a["cutoff_utc"], a["max_targets"]) == (DATE_START, DATE_CUTOFF, 6),
            "Selection contract differs from registration")
    require(list(map(D, b["interval_jd"])) == [CUTOFF, END], "Holdout contract differs from registration")
    return a, b, raw_a, raw_b


def jd_ticks(value):
    tick = value * 10**10
    require(tick == tick.to_integral_value(), "Unrepresentable source time")
    return int(tick)


def select_sql(alerts):
    """Use integer Julian-day ticks: apply the cutoff before duplicate resolution and ranking."""
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE alerts(object_id TEXT, tick INTEGER, physical_row INTEGER)")
        db.executemany("INSERT INTO alerts VALUES(?,?,?)", [
            (r["i:objectId"], jd_ticks(r["i:jd"]), i) for i, r in enumerate(alerts)])
        eligible = (jd_ticks(OPEN), jd_ticks(CUTOFF))
        clauses = """WITH eligible AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY object_id ORDER BY tick DESC, physical_row) AS per_id
            FROM alerts WHERE tick >= ? AND tick < ?) """
        selected = db.execute(clauses + "SELECT physical_row FROM eligible WHERE per_id=1 "
                              "ORDER BY tick DESC, object_id LIMIT 6", eligible).fetchall()
        counts = db.execute(clauses + "SELECT COUNT(*),COUNT(DISTINCT object_id) FROM eligible", eligible).fetchone()
    return [alerts[r[0]] for r in selected], counts


def exact_utc(jd):
    # Truncate exact publisher Julian-day fractions to the delivery's milliseconds.
    ms = int((jd - D("2440587.5")) * 86400000)
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ms)


def exact_pairs(epochs, rows, gap):
    positive = {name: [] for name in epochs}
    for row in rows:
        if (row["i:isdiffpos"] in {"t", "1"} and row["i:fid"] in (1, 2, 3) and
                row["i:magpsf"].is_finite() and row["i:sigmapsf"].is_finite() and row["i:sigmapsf"] > 0):
            positive[row["i:objectId"]].append(row)
    accepted = {}
    for name, detections in positive.items():
        gs = [r for r in detections if r["i:fid"] == 1]
        rs = [r for r in detections if r["i:fid"] == 2]
        def rank(pair):
            g, r = pair
            return (abs(g["i:jd"] - r["i:jd"]), g["i:jd"], r["i:jd"], g["i:candid"], r["i:candid"])
        best = min(product(gs, rs), key=rank, default=None)
        if best is None or rank(best)[0] * 1440 > gap:
            continue
        g, r = best
        signed = g["i:magpsf"] - r["i:magpsf"]
        sigma = (g["i:sigmapsf"]**2 + r["i:sigmapsf"]**2).sqrt()
        accepted[name] = (g, r, round(signed, 6), round(sigma, 6), round(rank(best)[0] * 1440, 5))
    return accepted, positive


def verify_pairs(measured, exact):
    members = {row["target_id"] for row in measured}
    require(len(members) == len(measured) and members == set(exact), "Decimal pair identity/count differs")
    for line in measured:
        g, r, color, sigma, separation = exact[line["target_id"]]
        for band, original in (("g", g), ("r", r)):
            require(line[f"{band}_candid"] == str(original["i:candid"]), "Detection identifier differs")
            require((line[f"{band}_jd"], line[f"{band}_diff_mag"], line[f"{band}_error_mag"]) ==
                    tuple(float(original[key]) for key in ("i:jd", "i:magpsf", "i:sigmapsf")),
                    "Publisher photometric values differ")
            time_error = abs(datetime.fromisoformat(line[f"{band}_utc"]) - exact_utc(original["i:jd"]))
            require(time_error <= timedelta(milliseconds=1), "UTC stamp differs by more than its published precision")
        require((line["g_minus_r_diff_mag"], line["formal_error_mag"]) == (float(color), float(sigma)),
                "Signed photometry or propagated uncertainty differs")
        require(abs(D(str(line["separation_minutes"])) - separation) <= D("0.00001"),
                "Gap differs by more than one output tick")


def calculate():
    meta_a, meta_b, raw_a, raw_b = sources()
    alerts = json.loads(raw_a, parse_float=D)
    time_orig = json.loads(raw_b, parse_float=D)
    selected, (n_eligible, n_distinct) = select_sql(alerts)
    names = [row["i:objectId"] for row in selected]
    repaired, selection = reference.select_in_window(json.loads(raw_a), meta_a)
    require(names == [r["id"] for r in repaired] and selection["in_window_rows"] == n_eligible and
            selection["distinct_in_window_targets"] == n_distinct, "Typed receiver differs from SQLite date-first selection")
    for expected, target in zip(selected, repaired):
        require((float(expected["i:jd"]), float(expected["i:ra"]), float(expected["i:dec"])) ==
                (target["alert_jd"], target["ra_deg"], target["dec_deg"]), "Selected epoch or coordinates differ")
    queried = parse_qs(urlparse(meta_b["query"]).query)["objectId"][0].split(",")
    require(sorted(queried) == sorted(names), "Holdout query does not correspond to the independently selected IDs")
    require(len(time_orig) == meta_b["upstream_rows"] and all(r["i:objectId"] in names for r in time_orig),
            "Archive population mismatch")
    obs_exact = [r for r in time_orig if CUTOFF <= r["i:jd"] < END]
    observed = [r for r in json.loads(raw_b) if float(CUTOFF) <= r["i:jd"] < float(END)]
    projected = (json.dumps(observed, indent=2, sort_keys=True) + "\n").encode()
    require(sha(projected) == meta_b["projection_sha256"] and len(observed) == meta_b["retained_rows"],
            "Frozen post-cutoff projection differs")
    require([r["i:candid"] for r in obs_exact] == [r["i:candid"] for r in observed],
            "Exact and native temporal cutoffs differ")
    catalog = {"targets": repaired}
    first_catalog = json.loads((HERE.parent / "catalog.json").read_bytes())
    previous = json.loads((HERE.parent / "public.json").read_bytes())["photometry"]
    overlap = sorted(set(names) & {r["id"] for r in first_catalog["targets"]})
    result = {
        "scope": "second historical public Fink/ZTF cohort; positive difference-image photometry",
        "selection_start_utc": DATE_START, "cutoff_utc": DATE_CUTOFF, "observation_end_utc": DATE_END,
        "alert_rows": len(alerts), "eligible_alert_rows": n_eligible, "distinct_eligible_targets": n_distinct,
        "selection_counts": selection, "targets": len(names), "selected_target_ids": names,
        "overlap_with_first": overlap, "holdout_source_rows": len(time_orig), "holdout_rows": len(observed),
        "source_sha256": {"alerts": meta_a["alerts_sha256"], "object_history": meta_b["upstream_sha256"],
                          "in_window_projection": meta_b["projection_sha256"]},
    }
    for gap in (120, 10):
        answer = photometry.measure(catalog, observed, [float(CUTOFF), float(END)], gap)
        sql = photometry.compare_sql(catalog, observed, [float(CUTOFF), float(END)], answer, gap)
        exact, detections = exact_pairs(names, obs_exact, gap)
        verify_pairs(answer["pairs"], exact)
        require(answer["missing_pair"] == sorted(set(names) - set(exact)), "Withholding disagrees")
        result[f"pairs_{gap}"] = answer["pairs"]
        result[f"no_pair_{gap}"] = answer["missing_pair"]
        result[f"independent_sql_{gap}"] = sql
    result["positive_detections_by_target"] = {k: len(detections[k]) for k in sorted(names)}
    result["positive_detections"] = sum(result["positive_detections_by_target"].values())
    result["targets_with_positive_detections"] = sum(bool(r) for r in detections.values())
    result["first_week_withheld_now_qualifies_120"] = sorted(
        {row["target_id"] for row in result["pairs_120"]} & set(previous["missing_pair"]))
    return result


def csv_bytes(result, gap):
    text = io.StringIO(newline="")
    columns = ["max_gap_minutes", "outcome", "positive_detections", *photometry.FIELDS]
    writer = csv.DictWriter(text, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    pairs = {row["target_id"]: row for row in result[f"pairs_{gap}"]}
    for target in sorted(result["selected_target_ids"]):
        writer.writerow({"max_gap_minutes": gap, "outcome": "measured" if target in pairs else "no_qualifying_pair",
                         "positive_detections": result["positive_detections_by_target"][target],
                         **pairs.get(target, {"target_id": target})})
    return text.getvalue().encode()


def outputs(result):
    payload = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    return {"RESULT.json": payload, **{f"photometry-{gap}m.csv": csv_bytes(result, gap) for gap in (120, 10)}}


def replay():
    result = calculate()
    files = outputs(result)
    for name, data in files.items():
        require((HERE / name).read_bytes() == data, f"Registered recipient differs: {name}")
    return result, files


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, help="Write freshly verified outputs into a new directory")
    args = ap.parse_args()
    result, files = replay()
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            ap.error("Use a new output directory")
        with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
            stage = Path(temp) / "accepted"
            stage.mkdir()
            for name, data in files.items():
                (stage / name).write_bytes(data)
            stage.rename(args.output)
    print(json.dumps({"qualifying_pairs": {str(g):len(result[f"pairs_{g}"]) for g in (120, 10)},
                      "selected": result["targets"], "holdout_rows": result["holdout_rows"],
                      "overlap_with_first": result["overlap_with_first"],
                      "withheld_then_measured": result["first_week_withheld_now_qualifies_120"],
                      "sha256": {k: sha(v) for k, v in files.items()}}))
