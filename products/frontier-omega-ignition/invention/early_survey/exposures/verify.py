"""Recover and independently check two public ZTF detections across archive sources."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import sys
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from invention.early_survey import survey
from invention.early_survey.exposures.avro_packet import record
from invention.evolution.alert import json_bytes, julian, stamp

INDEX = "797dc2172e9b4b67732d57c0f0db27434f3f41cbe1af84dfc94f97fb3f64c1a2"
TARGET = "ZTF26acbezdh"
FINAL = "2026-11-17T00:00:00Z"
ISSUE = "2026-10-26T00:00:00Z"
DEADLINE = "2026-10-29T00:00:00Z"
FIDS = {"g": 1, "r": 2}
PACKET_EPOCHS = {"packet-g": D("2461341.7490625"), "packet-r": D("2461341.8897106"),
                 "next-packet": D("2461347.7893171")}


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def inputs(folder, until=None):
    raw = (folder / "index.json").read_bytes()
    require(digest(raw) == INDEX, "acquisition index differs")
    index = json.loads(raw)
    data = {}
    for key, info in index.items():
        if until is not None and (key.startswith("ibe-") or (key == "alerce-force" and until <= PACKET_EPOCHS["packet-r"]) or
                                  (key in PACKET_EPOCHS and PACKET_EPOCHS[key] >= until)):
            continue
        require(info["status"] == 200, "unsuccessful decision-bearing query")
        if "file" in info:
            raw = gzip.decompress((folder / info["file"]).read_bytes())
            require(len(raw) == info["size_bytes"] and digest(raw) == info["sha256"], "source differs: " + key)
        else:
            raw = (folder / info["projection_file"]).read_bytes()
            require(digest(raw) == info["projection_sha256"], "detection projection differs")
        data[key] = raw
    packets = {k: record(data[k]) for k in PACKET_EPOCHS if k in data}
    for key, p in packets.items():
        require(p["objectId"] == TARGET and p["publisher"] == "ZTF (www.ztf.caltech.edu)"
                and p["schemavsn"] == "4.02" and p["candid"] == p["candidate"]["candid"]
                and D(str(p["candidate"]["jd"])) == PACKET_EPOCHS[key],
                "invalid original packet identity: " + key)
        for row in [p["candidate"], *p["fp_hists"], *p["prv_candidates"]]:
            require(row["programid"] == 1, "archive pack contains material outside ZTF public survey program 1")
    return index, data, packets


def archive_access(data):
    rows = {}
    for k, raw in data.items():
        if k.startswith("ibe-"):
            rows[k] = list(csv.DictReader(io.StringIO(raw.decode())))
    historical = rows["ibe-coverage-control"]
    require(historical and all(not v for k, v in rows.items() if k != "ibe-coverage-control"),
            "anonymous image index outcome changed")
    latest = {}
    for band, fid in FIDS.items():
        candidates = [r for r in historical if int(r["fid"]) == fid]
        require(all((int(r["field"]), int(r["rcid"]), int(r["ccdid"]), int(r["qid"])) == (505, 58, 15, 3)
                    for r in candidates), "older image control did not reach the same detector")
        last = max(candidates, key=lambda r: D(r["obsjd"]))
        latest[band] = {k: last[k] for k in ("obsdate", "pid", "expid", "filefracday", "filtercode",
                                              "infobits", "ipac_pub_date")}
    return {"registered_window_rows": sum(len(rows["ibe-" + str(fid) + "-window"]) for fid in FIDS.values()),
            "trigger_control_rows": sum(len(rows["ibe-" + str(fid) + "-trigger"]) for fid in FIDS.values()),
            "historical_footprint_rows": len(historical), "last_returned_by_band": latest,
            "subsequent_index_rows": len(rows["ibe-tail"]), "mosaic_field": 505, "readout_channel": 58,
            "ccd": 15, "quadrant": 3, "science_image_release_days": 60}


def judged(delta, uncertainty, direction):
    if abs(delta) < .2 or abs(delta) < 2 * uncertainty:
        return "not_reproduced"
    return "persisted" if (delta < 0) == (direction == "brightening") else "reversed"


def forced_pair(packets, db_forced, baseline_pid, repeat_pid, fid, refid, until):
    # The repeat's forced history may be transmitted in a *later* packet.
    for key in ("packet-g", "packet-r", "next-packet"):
        pack = packets.get(key)
        if pack is None:
            continue
        carrier = pack["candidate"]
        if D(str(carrier["jd"])) >= until:
            continue
        rows = {r["pid"]: r for r in pack["fp_hists"]}
        if baseline_pid not in rows or repeat_pid not in rows:
            continue
        result = []
        for pid in (baseline_pid, repeat_pid):
            f = rows[pid]
            require((f["programid"], f["field"], f["rcid"], f["fid"], f["rfid"], f["procstatus"])
                    == (1, 505, 58, fid, refid, "0"), "uncertified fixed-position photometry")
            flux, error = f["forcediffimflux"], f["forcediffimfluxunc"]
            require(flux > 0 and error > 0, "signed flux or uncertainty outside this magnitude comparison")
            mag = f["magzpsci"] - 2.5 * math.log10(flux)
            sigma = (2.5 / math.log(10)) * error / flux
            broker = db_forced[pid]
            require(abs(broker["mag"] - mag) < 0.00005 and abs(broker["e_mag"] - sigma) < 0.00005,
                    "published forced magnitude or statistical error disagrees with flux and zero point")
            result.append({"processing_id": str(pid), "jd": f["jd"], "mag": round(mag, 6),
                           "error_mag": round(sigma, 6), "difference_flux_dn": flux, "error_dn": error,
                           "zero_point_mag": f["magzpsci"], "zero_point_rms_mag": f["magzpscirms"],
                           "procstatus": f["procstatus"]})
        delta = result[1]["mag"] - result[0]["mag"]
        sigma = math.hypot(result[0]["error_mag"], result[1]["error_mag"])
        return {"carrier_candid": str(carrier["candid"]), "carrier_utc": stamp(D(str(carrier["jd"]))),
                "baseline": result[0], "witness": result[1], "delta_mag": round(delta, 6),
                "formal_error_mag": round(sigma, 6), "status": judged(delta, sigma, "brightening")}
    return None


def calculate(as_of=None, *, folder=HERE/"sources"):
    as_of = FINAL if as_of is None else as_of
    until = julian(as_of)
    result = {"scope": "public ZTF program 1 archive replay; alternate broker plus original packets",
              "as_of_utc": as_of, "witnesses": {}}
    if until < julian(ISSUE):
        return result
    original = survey.calculate(as_of)
    warm = next(c for c in original["cohorts"] if c["id"] == "early_warm")
    _, raw, packets = inputs(folder, until)
    aggregated = json.loads(raw["alerce-api"])
    all_forced = json.loads(raw.get("alerce-force", b"[]"))
    require(all(x["oid"] == TARGET and x["extra_fields"]["programid"] == 1 for x in all_forced),
            "unqualified source in public forced sequence")
    db_forced = {row["pid"]: row for row in all_forced}
    db = {row["candid"]: row for row in aggregated["detections"]}
    astro = {str(row["i:candid"]): row for row in json.loads(raw["astrometry"])}
    for original_alert in warm["alerts"]:
        band = original_alert["band"]
        require(original_alert["target_id"] == TARGET and original_alert["issued_utc"] == ISSUE
                and original_alert["deadline_utc"] == DEADLINE and original_alert["direction"] == "brightening",
                "frozen Fink mission differs")
        fid = FIDS[band]
        refid = int(original_alert["reference_image"]["rfids"][0])
        require(original_alert["reference_image"]["rfids"] == [str(refid), str(refid)], "three reference IDs differ")
        baseline, trigger = [{**original_alert[tag], "programid": 1, "rfid": refid} for tag in ("baseline", "trigger")]
        position = astro[trigger["candid"]]
        b, t = db[baseline["candid"]], db[trigger["candid"]]
        for z, f in ((b, baseline), (t, trigger)):
            require(z["rfid"] == refid and z["fid"] == fid and abs(z["magpsf"] - f["mag"]) <= 0.00001,
                    "original Fink photometry differs from alternate broker")
        require((position["i:field"], position["i:rcid"], position["i:programid"]) == (505, 58, 1)
                and position["i:ra"] == t["ra"] and position["i:dec"] == t["dec"], "trigger position differs")
        current = {"target_id": TARGET, "band": band, "source": "ALeRCE / ZTF", "issued_utc": ISSUE,
                   "deadline_utc": DEADLINE, "baseline": baseline, "trigger": trigger,
                   "fink_status": original_alert["status"], "status": "awaiting_repeat", "witness": None,
                   "delta_from_baseline_mag": None, "formal_error_mag": None, "aperture": None,
                   "forced_photometry": None}
        result["witnesses"][band] = current
        packet = packets.get("packet-" + band)
        if packet is None:
            continue
        c = packet["candidate"]
        jd = D(str(c["jd"]))
        require(julian(ISSUE) <= jd < julian(DEADLINE) and jd - D(str(trigger["jd"])) >= D(".5"),
                "repeat falls outside the registered notice")
        # The broker stores an MJD derived from a binary-float JD. At submillisecond
        # boundaries use the original alert epoch for this exact candidate.
        aggregate_window = sorted((row for row in db.values() if row["fid"] == fid
                                   and row["rfid"] == refid
                                   and 61339 <= row["mjd"] < 61342 and (jd if row["candid"] == str(c["candid"])
                                   else D(str(row["mjd"])) + D("2400000.5")) < until),
                                  key=lambda row: (row["mjd"], int(row["candid"])))
        require(aggregate_window and aggregate_window[0]["candid"] == str(c["candid"]),
                "ambiguous or missing first alternative-broker witness")
        if "next-packet" in packets:
            history = [z for z in packets["next-packet"]["prv_candidates"]
                       if z["fid"] == fid and z["field"] == 505 and z["rcid"] == 58
                       and julian(ISSUE) <= D(str(z["jd"])) < julian(DEADLINE) and z["candid"] is not None]
            require(len(history) == 1 and history[0]["candid"] == c["candid"], "later packet history differs")
        z = aggregate_window[0]
        require((c["programid"], c["field"], c["rcid"], c["fid"], c["nbad"]) == (1, 505, 58, fid, 0)
                and c["isdiffpos"] == "t" and c["rfid"] == z["rfid"] == refid and c["pid"] == z["pid"]
                and abs(float(jd - D("2400000.5")) - z["mjd"]) < 1e-8
                and abs(c["magpsf"] - z["magpsf"]) < .00001 and abs(c["sigmapsf"] - z["sigmapsf"]) < .000001
                and not z["dubious"] and z["has_stamp"], "original survey packet disagrees with broker witness")
        footprint_distance = 3600 * math.hypot((position["i:ra"] - c["ra"]) * math.cos(math.radians(c["dec"])),
                                               position["i:dec"] - c["dec"])
        require(footprint_distance < 1, "repeat centroid inconsistent with its target")
        mag, error = c["magpsf"], c["sigmapsf"]
        delta, sigma = mag - baseline["mag"], math.hypot(error, baseline["error_mag"])
        aperture_delta = c["magap"] - b["magap"]
        aperture_sigma = math.hypot(c["sigmagap"], b["sigmagap"])
        current.update(status=judged(delta, sigma, original_alert["direction"]),
                       delta_from_baseline_mag=round(delta, 6), formal_error_mag=round(sigma, 6),
                       witness={"candid": str(c["candid"]), "processing_id": str(c["pid"]), "jd": c["jd"],
                                "utc": stamp(jd), "mag": mag, "error_mag": error, "field": c["field"],
                                "rcid": c["rcid"], "rfid": refid, "programid": 1, "ra_deg": c["ra"],
                                "dec_deg": c["dec"], "offset_from_trigger_arcsec": round(footprint_distance, 5),
                                "aperture_mag": c["magap"], "aperture_error_mag": c["sigmagap"],
                                "bad_pixels": c["nbad"], "deep_real_bogus": c["drb"], "limiting_mag": c["diffmaglim"],
                                "zero_point_mag": c["magzpsci"], "zero_point_rms_mag": c["magzpscirms"]},
                       aperture={"delta_from_baseline_mag": round(aperture_delta, 6),
                                 "formal_error_mag": round(aperture_sigma, 6),
                                 "status": judged(aperture_delta, aperture_sigma, original_alert["direction"])},
                       forced_photometry=forced_pair(packets, db_forced, b["pid"], c["pid"], fid, refid, until))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="UTC, right-open for observation times")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="rebuild all final scientific and access findings")
    group.add_argument("--out", type=Path, help="write the dated view to a new file")
    args = parser.parse_args()
    if args.check and args.as_of not in (None, FINAL):
        parser.error("the frozen final observation uses " + FINAL)
    rows = calculate(args.as_of)
    if args.check:
        require(json_bytes(rows) == (HERE/"RESULT.json").read_bytes(), "cross-archive witness changed")
        _, raw, _ = inputs(HERE/"sources")
        require(json_bytes(archive_access(raw)) == (HERE/"ARCHIVE_ACCESS.json").read_bytes(), "image controls changed")
        print(json.dumps({k: v["status"] for k, v in rows["witnesses"].items()}))
    elif args.out:
        with args.out.open("xb") as dest:
            dest.write(json_bytes(rows))
    else:
        sys.stdout.buffer.write(json_bytes(rows))
