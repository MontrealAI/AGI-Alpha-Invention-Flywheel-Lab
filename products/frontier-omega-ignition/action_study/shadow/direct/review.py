#!/usr/bin/env python3
"""Reproduce the six independent, exposure-cutoff ZTF decisions offline.

Run python -B review.py to print the answers. Add --record to save the answers
and the clocks of that particular run. --step allows inspection between events.
"""
import time
ENTRY_WALL = time.perf_counter()
ENTRY_CPU = time.process_time()

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

from tools import avro_packet
from tools import broker_control as conventional

ROOT = Path(__file__).resolve().parent
MATCH = ("field", "rcid", "fid", "rfid")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def mjd(utc):
    return (conventional.utc(utc) - conventional.MJD_EPOCH).total_seconds() / 86400


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, value):
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def checked(condition, message):
    if not condition:
        raise ValueError(message)


def read_candidate(folder, indexed, expected_hash, target):
    candid = indexed["candid"]
    if not any((folder / (candid + ext)).is_file() for ext in (".avro", ".avro.gz")):
        return None
    body = conventional.local_packet(folder, candid)
    digest = sha256(body).hexdigest()
    checked(digest == expected_hash, f"Packet hash mismatch for {candid}")
    alert = avro_packet.record(body)
    row = alert["candidate"]
    checked(alert["objectId"] == target and alert["candid"] == row["candid"]
            and str(row["candid"]) == candid, f"Packet identity mismatch for {candid}")
    checked(all(row[key] == indexed[key] for key in ("fid", "rfid", "pid"))
            and abs(row["jd"] - conventional.MJD_ZERO - indexed["mjd"]) < 1e-8,
            f"Packet and index disagree for {candid}")
    return row, digest


def classify_band(folder, task, notice, tap):
    band = task["band"]
    fid = conventional.BANDS[band]
    records = [dict(zip(tap["columns"], values, strict=True)) for values in tap["rows"]]
    indexed = {row["candid"]: row for row in records}
    checked(len(records) == len(indexed), "Repeated TAP candidate")

    def packet(row):
        return read_candidate(folder, row, tap["packet_sha256"].get(row["candid"]), notice.target)

    anchors = {}
    for role in conventional.ROLES:
        issued = notice.bands[band][role]
        aid = issued["candid"]
        entry = packet(indexed[aid]) if aid in indexed else None
        if entry is None:
            return {"action": "keep_open"}, f"Missing original {role} packet"
        row, _ = entry
        checked(row["fid"] == fid and conventional.eligible(row), f"Ineligible {role}")
        checked(all(row[key] == issued[key] for key in ("field", "rcid", "jd"))
                and abs(row["magpsf"] - issued["mag"]) < 1e-6
                and abs(row["sigmapsf"] - issued["error_mag"]) < 1e-8,
                f"Notice and {role} packet disagree")
        anchors[role] = row

    base, trigger = anchors["baseline"], anchors["trigger"]
    checked(all(base[key] == trigger[key] for key in MATCH), "Notice anchors use different references")
    trigger_delta = trigger["magpsf"] - base["magpsf"]
    start = max(notice.start_mjd, trigger["jd"] - conventional.MJD_ZERO + 0.5)
    stop = min(notice.stop_mjd, mjd(task["cutoff_utc"]))
    window = sorted((row for row in records if start <= row["mjd"] < stop
                     and row["fid"] == fid and row["rfid"] == base["rfid"]),
                    key=lambda row: (row["mjd"], int(row["candid"])))

    for indexed_row in window:
        entry = packet(indexed_row)
        if entry is None:
            return {"action": "keep_open"}, "Earlier matching TAP row lacks its original packet"
        witness, digest = entry
        if not conventional.eligible(witness) or any(witness[key] != base[key] for key in MATCH):
            continue
        delta = witness["magpsf"] - base["magpsf"]
        sigma = math.hypot(witness["sigmapsf"], base["sigmapsf"])
        direction = "not_reproduced"
        if abs(delta) >= max(0.2, 2 * sigma):
            direction = "persisted" if trigger_delta * delta > 0 else "reversed"
        measurement = {
            "witness": str(witness["candid"]), "reference": str(witness["rfid"]),
            "baseline": str(base["candid"]), "trigger": str(trigger["candid"]),
            "packet_sha256": digest, "direction": direction, "unit": "mag",
            "delta_mag": delta, "sigma_mag": sigma
        }
        return {"action": "deliver", "measurement": measurement}, "Earliest qualified original packet"
    return {"action": "keep_open"}, "No qualified repeat inside this exposure prefix"


def resolve_pair(number, tasks):
    folder = ROOT / str(number)
    notice = conventional.notice_from_file(ROOT / "notice.json")
    tap = read_json(folder / "tap-prefix.json")
    checked(tap["columns"] == ["candid", "mjd", "fid", "rfid", "pid"], "Unrecognized TAP projection")
    checked(tap["tap_query"] == conventional.selection_query(notice), "Index query differs from notice")
    checked(all(task["cutoff_utc"] == tap["cutoff_utc"] for task in tasks), "Prefix cutoff mismatch")
    checked(all(float(row[1]) < mjd(tap["cutoff_utc"]) for row in tap["rows"]), "Future exposure in prefix")
    responses, reasons = [], {}
    for task in tasks:
        decision, reason = classify_band(folder, task, notice, tap)
        responses.append({"case_id": task["case_id"], "source_set_sha256": task["source_set_sha256"],
                          "answer": decision})
        reasons[task["case_id"]] = reason
    return responses, reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--review-start-utc", help="Earlier observed UTC for broader worker elapsed time")
    args = parser.parse_args()
    program_start = utc_now()
    protocol = read_json(ROOT / "tasks.json")
    cutoffs = sorted({task["cutoff_utc"] for task in protocol["tasks"]})
    answers = {"protocol_sha256": protocol["protocol_sha256"], "responses": []}
    events = []
    for number, cutoff in enumerate(cutoffs, 1):
        event_start = utc_now()
        wall, cpu = time.perf_counter(), time.process_time()
        responses, reasons = resolve_pair(number, [t for t in protocol["tasks"] if t["cutoff_utc"] == cutoff])
        events.append({"folder": number, "cutoff_utc": cutoff, "started_utc": event_start,
                       "finished_utc": utc_now(), "wall_s": time.perf_counter() - wall,
                       "process_cpu_s": time.process_time() - cpu, "decisions": reasons})
        answers["responses"].extend(responses)
        if args.step:
            print(json.dumps(responses, indent=2), flush=True)
            if number < len(cutoffs):
                input("Completed this pair. Press Enter to open the next exposure prefix. ")
    checked(len(answers["responses"]) == len(protocol["tasks"]) == 6, "Incomplete review")
    if args.record:
        write_json(ROOT / "answers.json", answers)
        end = utc_now()
        start = args.review_start_utc or program_start
        worker = {
            "route": ("Included Codex decision-maker (GPT-6 family) with local CPython. The worker wrote "
                      "the per-cutoff selector, reused broker_control for notice and TAP validation, "
                      "eligibility and local packet reads, and decoded originals with avro_packet. "
                      "The TAP index supplied order and candidate identities. Original packets supplied "
                      "photometry, qualifying metadata, and SHA-256. Each pair was decided in its own "
                      "numbered folder before the next was opened."),
            "resource": {"worker": "Included Codex agent", "exact_model_deployment": None,
                         "python": sys.version, "platform": sys.platform, "network_requests": 0,
                         "paid_external_calls": 0, "incremental_external_charge_usd": 0,
                         "script": Path(__file__).name, "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                         "command": ["python", "-B", Path(__file__).name, *sys.argv[1:]]},
            "started_utc": start, "finished_utc": end,
            "elapsed_wall_s": (conventional.utc(end) - conventional.utc(start)).total_seconds(),
            "timing_scope": ("The broader start marker was taken after reading TASK.md, alongside the first "
                             "input inventory. The end marker follows writing answers.json. This elapsed "
                             "time includes review, script construction and checkpoint inspection. "
                             "The program clocks below include setup from the first lines of Python and "
                             "checkpoint waits. Event clocks exclude waits and output serialization."),
            "program_started_utc_after_imports": program_start,
            "program_wall_s": time.perf_counter() - ENTRY_WALL,
            "program_process_cpu_s": time.process_time() - ENTRY_CPU,
            "events": events,
            "failures": [],
            "unmeasured": ["Exact agent inference tokens, server compute, internal cost or allocation",
                           "CPU for preparatory shell commands, interpreter startup and final worker receipt write",
                           "Time to dispatch this worker and read TASK.md before its first explicit UTC marker",
                           "Historical source ingestion times at the exposure cutoffs"],
            "historical_interpretation": "Archival shadow recommendations grouped by exposure timestamp."
        }
        write_json(ROOT / "worker.json", worker)
    if not args.step:
        print(json.dumps(answers, indent=2))


if __name__ == "__main__":
    main()
