#!/usr/bin/env python3
"""Registered public experiment for direct-origin historical temperature extraction."""
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns, thread_time_ns
from urllib.parse import urlencode

from point import forecast_at

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "autonomous_endpoint"))
from common import atomic, clock, encode, measure, read, require, sha
from cycle import exclusive_state, signature, verify

REGISTRATION = HERE / "registration.json"


def transfer(url, cap, interval=None):
    with TemporaryDirectory() as scratch:
        headers, body = Path(scratch) / "headers", Path(scratch) / "payload"
        command = ["curl", "-fsS", "--max-time", "25", "--max-filesize", str(cap), "-D", str(headers), "-o", str(body)]
        if interval:
            command += ["-r", f"{interval[0]}-{interval[1]}"]
        start = perf_counter_ns()
        result = subprocess.run(command+[url], capture_output=True, check=False)
        wall = perf_counter_ns()-start
        payload = body.read_bytes() if body.is_file() else b""
        h = headers.read_text(errors="replace").splitlines() if headers.is_file() else []
        status, values = None, {}
        for item in h:
            if item.startswith("HTTP/"):
                status, values = int(item.split()[1]), {}
            elif ":" in item:
                field, value = item.split(":", 1)
                values[field.lower()] = value.strip()
        trace = {"url": url, "wall_ns": wall, "http_status": status, "curl_exit": result.returncode,
                 "body_bytes": len(payload), "sha256": sha(payload) if payload else None,
                 "etag": values.get("etag"), "content_range": values.get("content-range")}
        if result.returncode or (interval and (status != 206 or len(payload) != interval[1]-interval[0]+1 or
                not (trace["content_range"] or "").startswith(f"bytes {interval[0]}-{interval[1]}/"))) or (
                interval is None and status != 200):
            return b"", trace | {"rejected_transport": True}
        return payload, trace


def fetch_index(origin, spec):
    base = f"{origin}/gfs.{spec['day']}/{spec['cycle']}/atmos/gfs.t{spec['cycle']}z.pgrb2.0p25.f024"
    index, trace = transfer(base+".idx", 100000)
    if not index:
        return base, None, None, trace
    rows = [line.split(":") for line in index.decode().splitlines()]
    pos = [i for i, row in enumerate(rows) if row[2:6] == [f"d={spec['day']}{spec['cycle']}",
           "TMP", "2 m above ground", "24 hour fcst"]]
    require(len(pos) == 1 and pos[0]+1 < len(rows), "REGISTERED_FIELD_MISSING_FROM_INDEX")
    off = int(rows[pos[0]][1])
    complete = int(rows[pos[0]+1][1])-off
    require(off > 0 and complete > 0, "FIELD_INDEX_BOUNDS_INVALID")
    return base, off, complete, trace


def reference_at(payload, spec):
    import eccodes
    physical = eccodes.codes_new_from_message(payload)
    try:
        get = lambda key: eccodes.codes_get(physical, key)
        require(get("centre") == "kwbc" and get("dataDate") == int(spec["day"]) and
                get("dataTime") == int(spec["cycle"])*100 and get("shortName") == "2t" and get("level") == 2 and
                get("forecastTime") == 24 and get("gridType") == "regular_ll" and get("edition") == 2,
                "INDEPENDENT_FIELD_METADATA_DISAGREES")
        point, = eccodes.codes_grib_find_nearest(physical, spec["latitude"], spec["longitude"])
        require(abs(point["lat"]-spec["latitude"]) <= 1e-7 and
                abs((point["lon"]-spec["longitude"]+180)%360-180) <= 1e-7, "INDEPENDENT_REFERENCE_USED_DIFFERENT_CELL")
        return {"temperature_k": float(point["value"]), "index": int(point["index"]),
                "packing_type": str(get("packingType")), "reference_decoder": f"ecCodes {eccodes.codes_get_api_version()}"}
    finally:
        eccodes.codes_release(physical)


def point_service(origin, spec):
    name = f"{spec['day'][:4]}/{spec['day']}/gfs.0p25.{spec['day']}{spec['cycle']}.f024.grib2"
    field = "Temperature_height_above_ground"
    params = {"var": field, "latitude": spec["latitude"], "longitude": spec["longitude"], "vertCoord": 2,
              "accept": "csv"}
    output, trace = transfer(f"{origin}/{name}?{urlencode(params)}", 65536)
    if not output:
        return {"source": trace, "disposition": "POINT_SERVICE_UNAVAILABLE"}
    started, cpu = perf_counter_ns(), thread_time_ns()
    try:
        records = list(csv.DictReader(StringIO(output.decode())))
        require(len(records) == 1, "POINT_SERVICE_CASE_COUNT_CHANGED")
        row = records[0]
        latitude = float(row['latitude[unit="degrees_north"]'])
        longitude = float(row['longitude[unit="degrees_east"]'])
        require(abs(latitude-spec["latitude"]) < 1e-7 and abs((longitude-spec["longitude"]+180)%360-180) < 1e-7,
                "POINT_SERVICE_GRID_MISMATCH")
        time = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
        expected = datetime.strptime(spec["day"]+spec["cycle"], "%Y%m%d%H").replace(tzinfo=timezone.utc)+timedelta(hours=24)
        require(time == expected, "POINT_SERVICE_FORECAST_VALIDITY_CHANGED")
        result = float(row[f'{field}[unit="K"]'])
        return {"source": trace, "disposition": "AVAILABLE", "temperature_k": result,
                "decode_wall_ns": perf_counter_ns()-started, "decode_thread_cpu_ns": thread_time_ns()-cpu,
                "reference_valid_time_utc": expected.isoformat(), "requested_height_m": 2,
                "height_confirmation": "Explicit NCSS vertical coordinate and comparison to independently decoded 2 m message"}
    except (OSError, TypeError, ValueError, KeyError) as error:
        message = str(error)
        return {"source": trace, "disposition": message if isinstance(error, ValueError) and message.isupper()
                else f"POINT_SERVICE_UNREADABLE_{type(error).__name__}", "decode_wall_ns": perf_counter_ns()-started,
                "decode_thread_cpu_ns": thread_time_ns()-cpu}


def direct_decode(base, offset, total, limit, spec, decoder):
    span = min(limit, total)
    payload, source = transfer(base, span, (offset, offset+span-1))
    if not payload or not source["etag"]:
        return {"source": source, "disposition": "ARCHIVE_RANGE_UNAVAILABLE"}
    start, cpu = perf_counter_ns(), thread_time_ns()
    try:
        result = decoder(payload, spec)
        return result | {"source": source, "disposition": "AVAILABLE", "decode_wall_ns": perf_counter_ns()-start,
                         "decode_thread_cpu_ns": thread_time_ns()-cpu}
    except (OSError, TypeError, ValueError, RuntimeError, KeyError, ImportError) as error:
        message = str(error)
        return {"source": source, "disposition": message if isinstance(error, ValueError) and message.isupper()
                else f"DECODING_{type(error).__name__}", "decode_wall_ns": perf_counter_ns()-start,
                "decode_thread_cpu_ns": thread_time_ns()-cpu}


def trial(spec, registration):
    contract = registration["test_contract"]
    base, offset, total, index = fetch_index(registration["origin"], spec)
    service = point_service(registration["independent_point_service"], spec)
    if offset is None or total > contract["maximum_full_field_bytes"]:
        return {"case": spec, "index": index, "point_service": service, "candidate": {"disposition": "FIELD_INDEX_UNAVAILABLE"},
                "reference": {"disposition": "FIELD_INDEX_UNAVAILABLE"}}
    candidate = direct_decode(base, offset, total, contract["candidate_max_prefix_bytes"], spec,
                              lambda payload, selected: forecast_at(payload, total, selected))
    reference = direct_decode(base, offset, total, total, spec, reference_at)
    return {"case": spec, "index": index, "point_service": service, "candidate": candidate, "reference": reference}


def accepted(row, contract):
    candidate, reference, point_service = (row[k] for k in ("candidate", "reference", "point_service"))
    limited_bytes = contract["decoded_case_payload_budget_bytes"]
    contribution = {"candidate": None, "reference": None, "point_service": point_service["source"]["body_bytes"]}
    for name, item in (("candidate", candidate), ("reference", reference)):
        if "source" in item:
            contribution[name] = row["index"]["body_bytes"]+item["source"]["body_bytes"]
    ready = (candidate["disposition"] == reference["disposition"] == "AVAILABLE" and
             candidate["source"]["etag"] == reference["source"]["etag"])
    equivalent = bool(ready and candidate["index"] == reference["index"] and
                      abs(candidate["temperature_k"]-reference["temperature_k"]) <= contract["agreement_tolerance_k"])
    service_equal = (point_service["disposition"] == reference["disposition"] == "AVAILABLE" and
                     abs(point_service["temperature_k"]-reference["temperature_k"]) <= contract["agreement_tolerance_k"])
    return {"same_direct_origin_value": equivalent, "body_bytes": contribution,
            "candidate_within_budget": equivalent and contribution["candidate"] <= limited_bytes,
            "whole_field_within_budget": bool(reference["disposition"] == "AVAILABLE" and contribution["reference"] <= limited_bytes),
            "conventional_service_agrees": service_equal}


def identities():
    return {p.name: sha(p.read_bytes()) for p in (REGISTRATION, HERE / "point.py", Path(__file__))}


def run(state, output):
    require(not output.resolve().is_relative_to(state.resolve()), "EXPORT_REQUIRES_DISTINCT_DIRECTORY")
    with exclusive_state(state):
        config = read(REGISTRATION)
        registration = {"identities": identities(), "frozen_utc": clock()}
        frozen = state / "frozen.json"
        if frozen.exists():
            prior = read(frozen)
            require(prior["identities"] == registration["identities"], "FROZEN_ARCHIVE_EXPERIMENT_CHANGED")
            registration = prior
        else:
            atomic(frozen, registration)
        def case(spec):
            path = state / (spec["name"]+".json")
            if not path.exists():
                row = trial(spec, config)
                row["scored"] = accepted(row, config["test_contract"])
                atomic(path, row)
            result = read(path)
            require(result["case"] == spec, "FROZEN_ARCHIVE_CASE_CHANGED")
            return result
        execution = {}
        with measure(execution, "all_measurement_arms"):
            with ThreadPoolExecutor(max_workers=2) as workers:
                cases = list(workers.map(case, config["confirmation"]))
        receipt = {"schema": "frontier-omega-alpha/archive-point-receipt-v1", "finished_utc": clock(),
                   "registration": registration, "execution": execution, "cases": cases,
                   "direct_origin_budget_cases": sum(x["scored"]["candidate_within_budget"] for x in cases),
                   "conventional_service_agreement": sum(x["scored"]["conventional_service_agrees"] for x in cases),
                   "economic_advantage": "UNPROVEN", "productive_s1": "UNQUALIFIED",
                   "complete_operating_cost": None, "endpoint": "ABSTAIN", "incumbent": "indexed-sqlite"}
        output.parent.mkdir(parents=True, exist_ok=True)
        atomic(output, signature(state, receipt))


def audit(path, key):
    receipt = verify(path, key)["receipt"]
    require(receipt["registration"]["identities"] == identities(), "ARCHIVE_EXPERIMENT_CHANGED")
    config = read(REGISTRATION)
    require([r["case"] for r in receipt["cases"]] == config["confirmation"], "ARCHIVE_CASE_DENOMINATOR_CHANGED")
    require(all(row["scored"] == accepted(row, config["test_contract"]) for row in receipt["cases"]), "ARCHIVE_CASE_SCORE_CHANGED")
    return {"signature_verified": True, "registered_cases": len(receipt["cases"]),
            "direct_origin_budget_cases": receipt["direct_origin_budget_cases"],
            "conventional_service_agreement": receipt["conventional_service_agreement"]}


def main():
    parser = ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    execute = modes.add_parser("run")
    execute.add_argument("--state", type=Path, required=True)
    execute.add_argument("--output", type=Path, required=True)
    inspect = modes.add_parser("audit")
    inspect.add_argument("receipt", type=Path)
    inspect.add_argument("--key-sha256", required=True)
    args = parser.parse_args()
    if args.mode == "run":
        run(args.state, args.output)
    else:
        print(encode(audit(args.receipt, args.key_sha256)).decode(), end="")


if __name__ == "__main__":
    main()
