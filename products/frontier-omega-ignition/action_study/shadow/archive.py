"""Two separately implemented adjudications of the six public event-clock cutoffs."""
import gzip
import hashlib
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import fieldkit as kit
from evolution_trials import broker_control as direct
from invention.early_survey.exposures.avro_packet import record

PRODUCT = Path(__file__).resolve().parents[2]
EXPOSURES = PRODUCT / "invention/early_survey/exposures"
BROKER = PRODUCT / "evolution_trials"
SLOTS = ("2026-10-27T00:00:00Z", "2026-10-28T07:00:00Z", "2026-10-29T00:00:00Z")
TARGET = "ZTF26acbezdh"
TAP = BROKER / "broker_sources/alerce-window.vot"
ANCHORS = {
    "g": ("3579392285815015017", "3584356425815015004"),
    "r": ("3580268845815015008", "3584382785815015006"),
}
WITNESS_FILES = {"3587249065815015015": "g.avro.gz", "3587389715815015003": "r.avro.gz"}
MJDEPOCH = datetime(1858, 11, 17, tzinfo=timezone.utc)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mjd(stamp):
    return (kit.utc(stamp) - MJDEPOCH).total_seconds() / 86400


def pins():
    return kit.load(BROKER / "BROKER_CONTROL.json")["source_sha256"]


def raw_packet(candid, expected):
    label = str(candid)
    path = (EXPOSURES / "sources" / WITNESS_FILES[label] if label in WITNESS_FILES
            else BROKER / "broker_sources" / (label + ".avro.gz"))
    raw = gzip.decompress(path.read_bytes())
    kit.check(sha(raw) == expected["packets"][label], "Original packet bytes differ from the archived receipt")
    return raw


def index(expected):
    data = TAP.read_bytes()
    kit.check(sha(data) == expected["index"], "TAP bytes differ from the archived receipt")
    notice = direct.notice_from_file()
    rows, acquired = direct.index_rows(data, notice)
    kit.check(set(map(str, rows)) == set(expected["packets"]), "Packet inventory differs from bounded TAP response")
    return notice, rows, acquired


def plan_and_cases():
    plan = {
        "mode": "historical_rehearsal", "currency": "CAD", "cost_horizon": "one registered six-slot rehearsal",
        "objective": "Deliver the first source-qualified repeat decision for each October notice by each event cutoff.",
        "roster_rule": "Both #451 notices on a single known transient at the three registered rehearsal cutoffs.",
        "end_rule": "Close after six opportunities per route; preserve every missing or incorrect response.",
        "allowed_sources": "Retained Fink notice, bounded ALeRCE index, original ZTF packets and source-linked supporting evidence.",
        "clock_basis": "Right-open exposure UTC. Live broker or observer availability at these dates is unknown.",
        "grading_rule": "Independent original-packet selection in SQL; signed PSF delta and formal sigma within 1e-5 mag.",
        "incumbent": "No participating beneficiary or observed fully human workflow in the retrospective rehearsal.",
        "operator_budget": "Offline standard-library tools; no external observing, outreach, charges or deployment.",
        "source_access": "All arms may read the same source set; each decision uses the event-time prefix at its cutoff.",
        "assignment_rule": "All arms receive every case; preserve temporal order of linked cutoffs. Blind reviewer codes independently.",
    }
    expected = pins()
    _, indexed, _ = index(expected)
    fink = PRODUCT / "invention/early_survey/RESULT.json"
    projection = EXPOSURES / "sources/detections.json"
    # This is an identity fence for the shared source set. A hash reveals no future measurement.
    manifest = {"notice_file_sha256": sha(fink.read_bytes()), "tap_sha256": expected["index"],
                "alerce_projection_sha256": sha(projection.read_bytes()),
                "exposure_index_sha256": sha((EXPOSURES / "sources/index.json").read_bytes())}
    cases = []
    for cutoff in SLOTS:
        for band in ANCHORS:
            case_id = cutoff[5:10].replace("-", "") + "-" + band
            prefix = {str(k): expected["packets"][str(k)] for k, v in indexed.items() if v[0] < mjd(cutoff)}
            source_set = {"object": TARGET, "band": band, "event_cutoff_exclusive": cutoff,
                          "manifest": manifest, "original_packets_in_prefix": prefix}
            cases.append({"case_id": case_id, "cluster": TARGET, "band": band, "cutoff_utc": cutoff,
                          "source_set_sha256": kit.digest(source_set), "available_utc": None,
                          "question": (f"At {cutoff} (exclusive exposure time), should the {band}-band {TARGET} "
                                       f"notice be delivered? Baseline {ANCHORS[band][0]}, trigger {ANCHORS[band][1]}. "
                                       "Use the earliest qualified same-reference repeat and original ZTF packet. "
                                       "Supply candidate, anchors, reference, packet SHA-256, signed PSF difference, "
                                       "formal uncertainty in mag and persistence finding, or leave the notice open.")})
    return plan, cases


def conventional(band, cutoff):
    expected = pins()
    notice, rows, _ = index(expected)
    prefix = {k: v for k, v in rows.items() if v[0] < mjd(cutoff)}
    packets = {k: direct.packet_candidate(raw_packet(k, expected), notice.target) for k in prefix}
    row = direct.adjudicate(notice, prefix, packets, kit.utc(cutoff))["bands"][band]
    if "witness" not in row:
        return {"action": "keep_open"}
    witness = row["witness"]["candid"]
    return {"action": "deliver", "measurement": {
        "witness": witness, "reference": str(row["reference"]["rfid"]),
        "baseline": row["baseline"]["candid"], "trigger": row["trigger"]["candid"],
        "packet_sha256": expected["packets"][witness], "direction": row["status"], "unit": "mag",
        "delta_mag": row["signed_delta_mag"], "sigma_mag": row["quadrature_error_mag"]}}


def engine(band, cutoff):
    from action_study.desk import case
    receipt = case({"profile": "ztf-persistence", "scope": {"band": band, "as_of": cutoff, "clock": "event"},
                    "sources": ["fink", "alerce"]})
    outcome = receipt["decision"]
    if outcome["state"] in {"pending", "incomplete", "unavailable"}:
        return {"action": "keep_open"}
    if outcome["state"] != "observed":
        return {"action": "review"}
    rows = [s for a in receipt["attempts"] if a["state"] == "observed" for s in a["evidence"]]
    kit.check(len(rows) == 1, "Need the integrated source-linked witness")
    r = rows[0]
    witness = r["record_id"]
    links = []
    for s in r["sources"]:
        url = urlsplit(s["url"])
        if (url.scheme, url.netloc, url.path) == ("https", "avro.alerce.online", "/get_avro"):
            if parse_qs(url.query) == {"oid": [TARGET], "candid": [witness]}:
                links.append(s)
    kit.check(len(links) == 1, "Witness requires exactly one matching original packet acquisition")
    raw_hash = links[0]["sha256"]
    kit.check(isinstance(raw_hash, str) and kit.SHA.fullmatch(raw_hash), "Missing packet digest in integrated evidence")
    return {"action": "deliver", "measurement": {
        "witness": witness, "baseline": r["baseline"]["candid"], "trigger": r["trigger"]["candid"],
        "reference": str(r["rfid"]), "direction": outcome["finding"], "unit": "mag",
        "delta_mag": r["delta_from_baseline_mag"], "sigma_mag": r["formal_error_mag"], "packet_sha256": raw_hash}}


def sql_reference(cases):
    expected = pins()
    _, indexed, _ = index(expected)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE det(id TEXT PRIMARY KEY, jd REAL, fid INTEGER, field INTEGER, rcid INTEGER, ref INTEGER,
                   mag REAL, err REAL, program INTEGER, sign TEXT, bad INTEGER, raw_sha TEXT)""")
    for cid, (epoch, filter_id, ref_id, pipeline) in indexed.items():
        raw = raw_packet(cid, expected)
        top = record(raw)
        r = top["candidate"]
        kit.check(top["objectId"] == TARGET and top["candid"] == r["candid"] == cid
                  and abs(r["jd"] - 2400000.5 - epoch) < 1e-8
                  and (r["fid"], r["rfid"], r["pid"]) == (filter_id, ref_id, pipeline),
                  "Packet conflicts with TAP source identity")
        kit.check(all(math.isfinite(r[x]) for x in ("magpsf", "sigmapsf", "jd")), "Nonfinite original measurement")
        db.execute("INSERT INTO det VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (str(cid), r["jd"], r["fid"], r["field"], r["rcid"], r["rfid"], r["magpsf"], r["sigmapsf"],
                    r["programid"], r["isdiffpos"], r["nbad"], sha(raw)))
    for band, (bid, tid) in ANCHORS.items():
        b, t = (db.execute("SELECT * FROM det WHERE id=?", (i,)).fetchone() for i in (bid, tid))
        kit.check(all(b[k] == t[k] for k in ("field", "rcid", "ref", "fid")) and t["fid"] == {"g": 1, "r": 2}[band]
                  and all(r["sign"] in ("t", "1") and r["err"] > 0 and r["program"] == 1 for r in (b, t)),
                  "Published trigger and baseline must meet the same stream and quality rules")
        span = t["jd"] - b["jd"]
        kit.check(0.5 <= span <= 7 and 2461338.5 <= t["jd"] < 2461339.5 and
                  abs(t["mag"] - b["mag"]) >= max(0.2, 0.1 * span, 3 * math.hypot(t["err"], b["err"])),
                  "Original anchors do not reproduce the qualifying notice")
    query = """
        SELECT w.*, b.id AS base, b.mag AS bmag, b.err AS berr, t.id AS trig, t.mag AS tmag
        FROM det w JOIN det b ON b.id=:base JOIN det t ON t.id=:trig
        WHERE w.fid=b.fid AND b.fid=t.fid AND w.fid=:fid
          AND w.field=b.field AND b.field=t.field AND w.rcid=b.rcid AND b.rcid=t.rcid
          AND w.ref=b.ref AND b.ref=t.ref AND w.bad=0
          AND w.program=1 AND b.program=1 AND t.program=1
          AND w.sign IN ('t','1') AND b.sign IN ('t','1') AND t.sign IN ('t','1')
          AND w.err>0 AND b.err>0 AND t.err>0 AND w.jd>=t.jd+0.5
          AND w.jd>=:issue AND w.jd<:stop AND w.jd<:deadline
        ORDER BY w.jd, CAST(w.id AS INTEGER) LIMIT 1"""
    answers = {}
    try:
        for c in cases:
            band = c["band"]
            baseline, trigger = ANCHORS[band]
            params = {"base": baseline, "trig": trigger, "fid": {"g": 1, "r": 2}[band], "issue": 2461339.5,
                      "deadline": 2461342.5, "stop": 2400000.5 + mjd(c["cutoff_utc"])}
            r = db.execute(query, params).fetchone()
            ans = {"action": "keep_open"}
            if r is not None:
                delta, sigma = r["mag"] - r["bmag"], math.hypot(r["err"], r["berr"])
                finding = "not_reproduced"
                if abs(delta) >= max(0.2, 2 * sigma):
                    finding = "persisted" if delta * (r["tmag"] - r["bmag"]) > 0 else "reversed"
                ans = {"action": "deliver", "measurement": {
                    "witness": r["id"], "baseline": r["base"], "trigger": r["trig"], "reference": str(r["ref"]),
                    "direction": finding, "unit": "mag", "delta_mag": delta, "sigma_mag": sigma, "packet_sha256": r["raw_sha"]}}
            answers[c["case_id"]] = dict(ans, reference_sha256=kit.digest({
                "source_set": c["source_set_sha256"], "query": query, "params": params, "answer": ans}))
    finally:
        db.close()
    return answers
