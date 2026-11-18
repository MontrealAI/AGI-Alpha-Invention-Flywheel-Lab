#!/usr/bin/env python3
"""Independently adjudicate the October 26 notices from ALeRCE's ZTF packets.

Run with --check for an offline proof, or --live to time fresh read-only queries.
Both modes use only Python's standard library.
"""

import argparse
import base64
import gzip
import hashlib
import io
import json
import math
import re
import struct
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EARLY = HERE.parent / "invention" / "early_survey"
SOURCES = HERE / "broker_sources"
MJD_ZERO = 2400000.5
MJD_EPOCH = datetime(1858, 11, 17, tzinfo=timezone.utc)
BANDS = {"g": 1, "r": 2}
ROLES = ("baseline", "trigger")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def utc(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(stamp.tzinfo is not None, "An explicit UTC offset is required")
    return stamp.astimezone(timezone.utc)


@dataclass
class Notice:
    target: str
    issued: str
    deadline: str
    bands: dict

    def __post_init__(self):
        need(re.fullmatch(r"ZTF\d{2}[a-z]{7}", self.target), "Expected a ZTF object ID")
        start, end = utc(self.issued), utc(self.deadline)
        need(start.time().isoformat() == "00:00:00", "The registered issue time is UTC midnight")
        self.start_mjd = (start - MJD_EPOCH).days
        self.stop_mjd = (end - MJD_EPOCH).total_seconds() / 86400
        need(self.start_mjd < self.stop_mjd <= self.start_mjd + 3, "Specify a window of up to three days")
        need(0 < len(self.bands) and self.bands.keys() <= BANDS.keys(), "Choose g, r or both")
        ids = []
        for band, pair in self.bands.items():
            need(pair.keys() == set(ROLES), f"Expected baseline and trigger for {band}")
            for role in ROLES:
                anchor = pair[role]
                if not isinstance(anchor, dict):
                    anchor = pair[role] = {"candid": str(anchor)}
                cid = str(anchor["candid"])
                need(re.fullmatch(r"[1-9]\d*", cid) and int(cid) < 2**63, "Invalid candidate ID")
                anchor["candid"] = cid
                ids.append(cid)
        need(len(set(ids)) == len(ids), "Duplicate anchor IDs")


def notice_from_file(path=None):
    if path:
        n = json.loads(path.read_bytes())
        return Notice(n["target"], n["issue_utc"], n["deadline_utc"], n["bands"])
    target, issued = "ZTF26acbezdh", "2026-10-26T00:00:00Z"
    bands = {}
    for cohort in json.loads((EARLY / "RESULT.json").read_bytes())["cohorts"]:
        for notice in cohort["alerts"]:
            if (notice["target_id"], notice["issued_utc"]) == (target, issued):
                band = notice["band"]
                need(band not in bands, "Duplicate issued notice")
                bands[band] = {role: notice[role] for role in ROLES}
    need(bands.keys() == BANDS.keys(), "Expected both published bands")
    return Notice(target, issued, "2026-10-29T00:00:00Z", bands)


def selection_query(notice):
    chosen = [band for band in BANDS if band in notice.bands]
    ids = ",".join(notice.bands[b][r]["candid"] for b in chosen for r in ROLES)
    filters = ",".join(str(BANDS[b]) for b in chosen)
    return (
        "SELECT d.oid, d.candid, d.mjd, d.fid, d.rfid, d.pid FROM ztf.detection AS d "
        f"WHERE d.oid='{notice.target}' AND d.fid IN ({filters}) "
        f"AND ((d.mjd>={notice.start_mjd} AND d.mjd<{format(notice.stop_mjd, '.15g')}) "
        f"OR d.candid IN ({ids})) ORDER BY d.mjd, d.candid"
    )


def index_rows(data, notice):
    xml = ET.fromstring(data)
    info = xml.findall(".//{*}INFO")
    statuses = [x.get("value") for x in info if x.get("name") == "QUERY_STATUS"]
    need(statuses == ["OK"], "Bounded TAP query failed or overflowed")
    need(any(x.get("name") == "query" and x.get("value") == selection_query(notice) for x in info),
         "Changed TAP query")
    as_of = next((x.get("value") for x in info if x.get("name") == "request_date"), None)
    need(as_of, "Missing TAP retrieval date")
    fields = [(f.get("name"), f.get("datatype")) for f in xml.findall(".//{*}FIELD")]
    need(fields == [("oid", "char"), ("candid", "long"), ("mjd", "double"), ("fid", "int"),
                    ("rfid", "long"), ("pid", "long")], "Unexpected TAP response schema")
    stream = xml.find(".//{*}BINARY/{*}STREAM")
    need(stream is not None and stream.get("encoding") == "base64", "Missing VOTable binary data")
    source = io.BytesIO(base64.b64decode("".join(stream.text.split()), validate=True))
    columns = struct.Struct(">qdiqq")
    nulls = {field.get("name"): int(values.get("null")) for field in xml.findall(".//{*}FIELD")
             if (values := field.find("{*}VALUES")) is not None and values.get("null") is not None}
    rows = {}
    while length := source.read(4):
        name = source.read(struct.unpack(">I", length)[0]).decode()
        candid, mjd, fid, rfid, pid = columns.unpack(source.read(columns.size))
        need(name == notice.target and candid not in rows, "Unexpected target or duplicate detection")
        rows[candid] = (mjd, fid, None if rfid == nulls.get("rfid") else rfid,
                        None if pid == nulls.get("pid") else pid)
    return rows, utc(as_of)


# Project the top-level candidate from a one-record ZTF Avro container.
# Only the metadata map and the schema's primitive, union and record fields are needed.
def avro_long(source):
    value = 0
    for shift in range(0, 70, 7):
        byte = source.read(1)
        need(byte, "Truncated Avro integer")
        value |= (byte[0] & 127) << shift
        if byte[0] < 128:
            return (value >> 1) ^ -(value & 1)
    raise ValueError("Avro integer exceeds 64 bits")


def avro_bytes(source):
    size = avro_long(source)
    need(size >= 0, "Invalid Avro length")
    body = source.read(size)
    need(len(body) == size, "Truncated Avro body")
    return body


def avro_value(source, kind):
    if isinstance(kind, list):
        index = avro_long(source)
        need(0 <= index < len(kind), "Invalid Avro union index")
        return avro_value(source, kind[index])
    if isinstance(kind, dict) and kind["type"] == "record":
        return {f["name"]: avro_value(source, f["type"]) for f in kind["fields"]}
    if kind in ("int", "long"):
        return avro_long(source)
    if kind == "string":
        return avro_bytes(source).decode()
    if kind == "null":
        return None
    fmt = {"float": "<f", "double": "<d"}[kind]
    return struct.unpack(fmt, source.read(struct.calcsize(fmt)))[0]


def packet_candidate(body, target):
    container = io.BytesIO(body)
    need(container.read(4) == b"Obj\x01", "Expected an Avro container")
    metadata = {}
    while count := avro_long(container):
        if count < 0:
            count = -count
            avro_long(container)  # Length of this metadata block in bytes.
        for _ in range(count):
            key = avro_bytes(container)
            metadata[key] = avro_bytes(container)
    sync = container.read(16)
    codec = metadata.get(b"avro.codec", b"null")
    need(codec in (b"null", b"deflate") and avro_long(container) == 1,
         "Expected one ZTF alert using the null or deflate codec")
    payload = avro_bytes(container)
    row = io.BytesIO(zlib.decompress(payload, -15) if codec == b"deflate" else payload)
    need(container.read(16) == sync and not container.read(1), "Invalid Avro sync marker")
    top = {}
    for field in json.loads(metadata[b"avro.schema"])["fields"]:
        top[field["name"]] = avro_value(row, field["type"])
        if field["name"] == "candidate":
            candidate = top["candidate"]
            need(top["objectId"] == target and top["candid"] == candidate["candid"], "Alert identity mismatch")
            return candidate
    raise ValueError("Missing candidate in ZTF alert")


def eligible(row):
    mag, err = row["magpsf"], row["sigmapsf"]
    return (row["programid"] == 1 and row["isdiffpos"] in ("t", "1")
            and row.get("field") is not None and row.get("rcid") is not None and row.get("rfid") is not None
            and mag is not None and math.isfinite(mag) and err is not None and math.isfinite(err) and err > 0)


def describe(row):
    utc = datetime.fromtimestamp((row["jd"] - 2440587.5) * 86400, timezone.utc)
    return {"candid": str(row["candid"]), "jd": row["jd"], "utc": utc.isoformat(timespec="milliseconds"),
            "magpsf": row["magpsf"], "sigmapsf": row["sigmapsf"]}


def adjudicate(notice, indexed, packets, as_of):
    need(indexed.keys() == packets.keys(), "Every indexed detection requires its original packet")
    for candid, (mjd, fid, rfid, pid) in indexed.items():
        row = packets[candid]
        need(mjd <= (as_of - MJD_EPOCH).total_seconds() / 86400, "An indexed observation postdates the receipt")
        need(abs(row["jd"] - MJD_ZERO - mjd) < 1e-8 and (row["fid"], row.get("rfid"), row.get("pid")) == (fid, rfid, pid),
             "TAP row and original ZTF packet disagree")
    bands = {}
    for band, issued in notice.bands.items():
        fid = BANDS[band]
        need(all(int(issued[r]["candid"]) in packets for r in ROLES), "Notice anchor absent from broker evidence")
        base, trigger = (packets[int(issued[r]["candid"])] for r in ROLES)
        for role, row in zip(ROLES, (base, trigger)):
            given = issued[role]
            need(eligible(row) and row["fid"] == fid, "Notice anchor fails public detection eligibility")
            for key in ("jd", "field", "rcid"):
                need(key not in given or given[key] == row[key], f"Anchor {key} differs from notice")
            for key, raw, tol in (("mag", "magpsf", 1e-6), ("error_mag", "sigmapsf", 1e-8)):
                need(key not in given or abs(row[raw] - given[key]) < tol, "Anchor photometry differs")
        reference_keys = ("field", "rcid", "fid", "rfid")
        reference = {key: base[key] for key in reference_keys}
        need(all(trigger[k] == v for k, v in reference.items()), "Trigger reference differs from baseline")
        trigger_change = trigger["magpsf"] - base["magpsf"]
        lag = trigger["jd"] - base["jd"]
        need(notice.start_mjd - 1 <= trigger["jd"] - MJD_ZERO < notice.start_mjd and 0.5 <= lag <= 7
             and abs(trigger_change) >= max(0.2, 0.1 * lag,
             3 * math.hypot(base["sigmapsf"], trigger["sigmapsf"])), "Issued anchor pair fails the trigger rule")
        window = [row for row in packets.values() if row["fid"] == fid
                  and notice.start_mjd <= row["jd"] - MJD_ZERO < notice.stop_mjd]
        matches = [row for row in window if eligible(row) and row["jd"] >= trigger["jd"] + 0.5
                   and all(row[k] == v for k, v in reference.items())]
        missing = "coverage_gap" if notice.stop_mjd == notice.start_mjd + 3 else "right_censored"
        result = {"baseline": describe(base), "trigger": describe(trigger), "reference": reference,
                  "trigger_delta_mag": trigger_change, "indexed_in_window": len(window),
                  "eligible_in_window": len(matches), "status": missing if as_of >= utc(notice.deadline) else "awaiting_repeat"}
        if matches:
            witness = min(matches, key=lambda row: (row["jd"], row["candid"]))
            delta = witness["magpsf"] - base["magpsf"]
            sigma = math.hypot(base["sigmapsf"], witness["sigmapsf"])
            status = "not_reproduced"
            if abs(delta) >= max(0.2, 2 * sigma):
                status = "persisted" if delta * trigger_change > 0 else "reversed"
            stack_keys = ("jdstartref", "jdendref", "nframesref")
            stack = {key: base.get(key) for key in stack_keys}
            same_stack = all(v is not None and row.get(k) == v for row in (trigger, witness) for k, v in stack.items())
            result.update(witness=describe(witness), status=status, signed_delta_mag=delta,
                          quadrature_error_mag=sigma, signed_formal_units=delta / sigma,
                          registered_threshold_mag=max(0.2, 2 * sigma), reference_stack=stack,
                          same_reference_stack=same_stack, programid=witness["programid"],
                          isdiffpos=witness["isdiffpos"], days_after_issue=witness["jd"] - MJD_ZERO - notice.start_mjd)
            if "mag" in issued["baseline"]:
                result["signed_delta_with_issued_baseline_mag"] = witness["magpsf"] - issued["baseline"]["mag"]
        bands[band] = result
    return {"target": notice.target, "issue_utc": notice.issued, "deadline_utc": notice.deadline, "bands": bands}


def get(url):
    wall, cpu = time.perf_counter(), time.thread_time()
    started = datetime.now(timezone.utc).isoformat()
    request = urllib.request.Request(url, headers={"User-Agent": "archival-astronomy-control/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read()
        receipt = {"url": url, "started_utc": started, "http": response.status, "http_date": response.headers["Date"],
                   "server_request_id": response.headers.get("X-Request-ID"), "bytes": len(body), "sha256": digest(body)}
    receipt.update(wall_s=time.perf_counter() - wall, thread_cpu_s=time.thread_time() - cpu)
    return body, receipt


def index_url(notice):
    return "https://tap.alerce.online/tap/sync?" + urllib.parse.urlencode(
        dict(REQUEST="doQuery", LANG="ADQL", FORMAT="votable", MAXREC=1000, QUERY=selection_query(notice)))


def packet_url(target, candid):
    return "https://avro.alerce.online/get_avro?" + urllib.parse.urlencode(dict(oid=target, candid=candid))


def local_packet(directory, candid):
    files = [directory / f"{candid}.avro", directory / f"{candid}.avro.gz"]
    matches = [p for p in files if p.is_file()]
    need(len(matches) == 1, f"Missing or ambiguous packet for indexed detection {candid}")
    path = matches[0]
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == ".gz" else data


def replay(notice, live=False, index_path=None, packet_dir=None):
    wall, cpu = time.perf_counter(), time.process_time()
    requests = []
    if live:
        index, receipt = get(index_url(notice))
        requests.append(receipt)
    else:
        index = (index_path or SOURCES / "alerce-window.vot").read_bytes()
    indexed, as_of = index_rows(index, notice)
    if live:
        urls = [packet_url(notice.target, c) for c in indexed]
        with ThreadPoolExecutor(max_workers=6) as pool:
            fetched = list(pool.map(get, urls))
        bodies = [body for body, _ in fetched]
        requests.extend(receipt for _, receipt in fetched)
    elif packet_dir:
        bodies = [local_packet(packet_dir, c) for c in indexed]
    else:
        shared = EARLY / "exposures" / "sources"
        files = [*sorted(SOURCES.glob("*.avro.gz")), shared / "g.avro.gz", shared / "r.avro.gz"]
        bodies = [gzip.decompress(path.read_bytes()) for path in files]
    packets, hashes = {}, {}
    for body in bodies:
        row = packet_candidate(body, notice.target)
        candid = row["candid"]
        need(candid not in packets, "Duplicate original packet")
        packets[candid], hashes[str(candid)] = row, digest(body)
    result = adjudicate(notice, indexed, packets, as_of)
    return {"result": result, "source_sha256": {"index": digest(index), "packets": hashes},
            "wall_s": time.perf_counter() - wall, "process_cpu_s": time.process_time() - cpu, "requests": requests}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'A notice JSON supplies target, issue_utc, deadline_utc and bands, for example '
        '{"r":{"baseline":"123","trigger":"456"}} for bands. Use --queries to print the TAP URL, '
        'then --queries --index FILE to obtain every required packet URL. Store each returned packet '
        'as CANDID.avro or CANDID.avro.gz. Missing indexed packets leave the result unresolved.'))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify the frozen decisions and all source identities")
    mode.add_argument("--live", action="store_true", help="run fresh public queries and output timings")
    mode.add_argument("--queries", action="store_true", help="print read-only URLs without accessing the network")
    parser.add_argument("--notice", type=Path, help="use a supplied notice JSON")
    parser.add_argument("--index", type=Path, help="read the complete bounded TAP VOTable response")
    parser.add_argument("--packets", type=Path, help="read CANDID.avro or CANDID.avro.gz files from this directory")
    args = parser.parse_args()
    try:
        case = notice_from_file(args.notice)
        if args.queries:
            ids = index_rows(args.index.read_bytes(), case)[0] if args.index else [
                anchor["candid"] for band in case.bands.values() for anchor in band.values()]
            print(json.dumps({"index_url": index_url(case),
                              "packet_urls": [packet_url(case.target, cid) for cid in ids]}, indent=2))
        else:
            need(not args.check or not any((args.notice, args.index, args.packets)), "--check uses the published inputs")
            need(not args.live or not any((args.index, args.packets)), "--live uses fresh broker inputs")
            need(not args.notice or args.live or (args.index and args.packets),
                 "Offline use of a new notice requires --index and --packets")
            report = replay(case, args.live, args.index, args.packets)
            if args.check:
                published = json.loads((HERE / "BROKER_CONTROL.json").read_bytes())
                for key in ("result", "source_sha256"):
                    need(report[key] == published[key], f"Frozen {key} differs")
                print("Verified both registered bands against the bounded TAP response and six original ZTF packets.")
            else:
                print(json.dumps(report, indent=2))
    except (KeyError, OSError, ValueError, struct.error, ET.ParseError) as error:
        parser.exit(1, f"Unresolved evidence: {error}\n")
