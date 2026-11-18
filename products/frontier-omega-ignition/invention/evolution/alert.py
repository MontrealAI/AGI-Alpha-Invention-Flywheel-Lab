"""Issue same-band change alerts and test them on the first eligible later detection."""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
INVENTION = HERE.parent
# The legacy selector imports its sibling geometry module by its short name.
# Load the selector by package identity even if Endpoint Lab's reference is cached.
sys.path[:0] = [str(INVENTION.parent), str(INVENTION)]
try:
    from invention.reference import select_in_window
finally:
    del sys.path[:2]

D = Decimal
DAY = D(86400)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
EPOCH_JD = D("2440587.5")
MIN_CHANGE = D("0.20")
MIN_RATE = D("0.10")
MIN_LAG = D("0.5")
BANDS = {1: "g", 2: "r"}
FINAL_UTC = "2026-11-17T00:00:00Z"
SOURCES = {
    "nov01": ("sources", "fink-alerts.json", "fink-holdout.json",
              "5a50023cc996b443ae4d4aea6d599d184f76caea9aa94f5e614e462793e5c250",
              "d8677d608223f3119eb13c5f54d820d4f5f5b064da23cd1d5da310db75d91597"),
    "nov10": ("next_week/sources", "alerts.json", "objects.json",
              "a55a4d43d46ea18cec4a838504d6ac7058b753c7f1fae0119ac9a91e65788fcc",
              "e3e82fd193ded81c804c80e01fdfbc35ad88effb958ff73e72b7c3f442292ced"),
}
ACTIONS = {
    "no_trigger": "monitor_archive",
    "awaiting_repeat": "inspect_next_same_band_detection",
    "persisted": "inspect_subtractions_and_reference_identity",
    "reversed": "withdraw_review_alert",
    "not_reproduced": "withdraw_review_alert",
    "coverage_gap": "seek_missing_in_window_data",
    "right_censored": "obtain_remaining_ledger_interval",
}


def utc_datetime(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value):
        raise ValueError("use an ISO UTC date and time ending in Z")
    return datetime.fromisoformat(value)


def julian(value):
    elapsed = utc_datetime(value) - EPOCH
    return EPOCH_JD + elapsed.days + (D(elapsed.seconds) + D(elapsed.microseconds) / 10**6) / DAY


def stamp(jd, *, midnight=False):
    # Publisher decimal epoch, truncated to the advertised millisecond.
    ms = int((jd - EPOCH_JD) * DAY * 1000)
    instant = EPOCH + timedelta(milliseconds=ms)
    return instant.isoformat(timespec="seconds" if midnight else "milliseconds").replace("+00:00", "Z")


def checked_bytes(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"source digest differs: {path.name}")
    return data


def decimal_number(value):
    if type(value) in (int, float, D):
        number = D(str(value))
        if number.is_finite():
            return number
    return None


@dataclass(frozen=True)
class Detection:
    candid: int
    jd: Decimal
    mag: Decimal
    error: Decimal
    detector: tuple | None = None

    def record(self):
        row = {"candid": str(self.candid), "utc": stamp(self.jd), "jd": float(self.jd),
               "mag": float(self.mag), "error_mag": float(self.error)}
        if self.detector is not None:
            row["field"], row["rcid"] = self.detector
        return row


def six(value):
    return float(round(value, 6))


def followup_result(alert, observations, baseline, current, issued, until, end):
    deadline = issued + 3
    repeat = next((row for row in observations
                   if issued <= row.jd < min(deadline, until)
                   and row.jd - current.jd >= MIN_LAG and row.detector == current.detector), None)
    alert.update(followup=None, followup_delta_mag=None, followup_formal_error_mag=None)
    if repeat:
        delta = repeat.mag - baseline.mag
        variance = repeat.error**2 + baseline.error**2
        displaced = abs(delta) >= MIN_CHANGE and delta**2 >= 4 * variance
        if displaced:
            status = "persisted" if delta * (current.mag - baseline.mag) > 0 else "reversed"
        else:
            status = "not_reproduced"
        alert.update(followup=repeat.record(), followup_delta_mag=six(delta),
                     followup_formal_error_mag=six(variance.sqrt()))
    elif until >= deadline:
        status = "coverage_gap"
    elif until >= end:
        status = "right_censored"
    else:
        status = "awaiting_repeat"
    alert.update(status=status, deadline_utc=stamp(deadline, midnight=True), action=ACTIONS[status])


def first_alert(name, band, observations, start, end, until):
    comparisons = 0
    strongest = None
    largest_change = D("-1")
    for day in range(1, int(until - start) + 1):
        issued = start + day
        recent = [row for row in observations if issued - 1 <= row.jd < issued]
        if not recent:
            continue
        current = min(recent, key=lambda row: (-row.jd, row.candid))
        earlier = [row for row in observations
                   if row.detector == current.detector and MIN_LAG <= current.jd - row.jd <= 7]
        if not earlier:
            continue
        baseline = min(earlier, key=lambda row: (abs(current.jd - row.jd - 2), row.jd, row.candid))
        comparisons += 1
        gap = current.jd - baseline.jd
        delta = current.mag - baseline.mag
        variance = current.error**2 + baseline.error**2
        gates = {"change": abs(delta) >= MIN_CHANGE, "rate": abs(delta) >= MIN_RATE * gap,
                 "formal_error": delta**2 >= 9 * variance}
        measurement = {"issued_utc": stamp(issued, midnight=True), "baseline": baseline.record(),
                       "trigger": current.record(), "delta_mag": six(delta),
                       "formal_error_mag": six(variance.sqrt()), "rate_mag_per_day": six(delta / gap),
                       "gap_days": six(gap), "gates": gates}
        if abs(delta) > largest_change:
            largest_change, strongest = abs(delta), measurement
        if not all(gates.values()):
            continue
        alert = {"target_id": name, "band": band, "direction": "fading" if delta > 0 else "brightening",
                 **measurement}
        followup_result(alert, observations, baseline, current, issued, until, end)
        return comparisons, alert, strongest
    return comparisons, None, strongest


def evaluate_cohort(cohort_id, targets, rows, start, end, as_of, *,
                    baseline_lookback_days=0, require_same_detector=False):
    """Evaluate an event-time prefix; the input rows may include earlier or later history.

    Times are Decimal Julian dates. The target roster must already be known at start.
    This function has no provider, network, model or observing side effects.
    """
    if end - start != 7 or (start - EPOCH_JD) % 1 != 0 or as_of < start:
        raise ValueError("this registered rule needs a known roster and a seven-day cohort")
    if type(baseline_lookback_days) is not int or not 0 <= baseline_lookback_days <= 7:
        raise ValueError("baseline warm-up must lie within the registered seven-day maximum lag")
    if type(require_same_detector) is not bool:
        raise ValueError("detector matching must be declared as a boolean")
    targets = list(targets)
    if (any(not isinstance(name, str) or not name for name in targets)
            or len(set(targets)) != len(targets)):
        raise ValueError("a distinct declared target roster is required")
    targets.sort()
    until = min(end, as_of)
    grouped = defaultdict(list)
    seen = set()
    source_rows = 0
    for row in rows:
        candid, name = row["i:candid"], row["i:objectId"]
        if type(candid) is not int or candid <= 0 or candid in seen or name not in targets:
            raise ValueError("duplicate or invalid detection identity or undeclared target")
        seen.add(candid)
        jd = decimal_number(row["i:jd"])
        if jd is None:
            raise ValueError("observation requires a finite event time")
        if not start - baseline_lookback_days <= jd < until:
            continue
        source_rows += int(jd >= start)
        fid = row["i:fid"]
        mag, error = decimal_number(row["i:magpsf"]), decimal_number(row["i:sigmapsf"])
        detector = None
        if require_same_detector:
            field, rcid = row.get("i:field"), row.get("i:rcid")
            if type(field) is not int or field <= 0 or type(rcid) is not int or not 0 <= rcid < 64:
                continue
            detector = (field, rcid)
        if (type(fid) is int and fid in BANDS and row["i:isdiffpos"] in ("t", "1")
                and mag is not None and error is not None and error > 0):
            grouped[name, BANDS[fid]].append(Detection(candid, jd, mag, error, detector))
    alerts, coverage = [], []
    for name in targets:
        for band in BANDS.values():
            history = sorted(grouped[name, band], key=lambda row: (row.jd, row.candid))
            count, alert, strongest = first_alert(name, band, history, start, end, until)
            status = "no_trigger" if alert is None else alert["status"]
            coverage.append({"target_id": name, "band": band,
                             "eligible_detections": sum(r.jd >= start for r in history),
                             "comparisons": count, "status": status, "action": ACTIONS[status],
                             "strongest_comparison": strongest})
            if alert:
                alerts.append(alert)
    alerts.sort(key=lambda row: (row["issued_utc"], row["target_id"], row["band"]))
    result = {"id": cohort_id, "start_utc": stamp(start, midnight=True), "end_utc": stamp(end, midnight=True),
              "targets": targets, "source_rows": source_rows,
              "eligible_rows": sum(item["eligible_detections"] for item in coverage),
              "alerts": alerts, "coverage": coverage}
    if baseline_lookback_days:
        result["eligible_baseline_history_rows"] = sum(map(len, grouped.values())) - result["eligible_rows"]
    return result


def registered_inputs(root, cohort_id):
    folder, class_file, observation_file, class_sha, observation_sha = SOURCES[cohort_id]
    folder = root / folder
    classes = json.loads(checked_bytes(folder / "alerts-source.json", class_sha))
    source = json.loads(checked_bytes(folder / "holdout-source.json", observation_sha), parse_float=D)
    raw_classes = checked_bytes(folder / class_file, classes["alerts_sha256"])
    if len(raw_classes) != classes["raw_bytes"]:
        raise ValueError("class response length differs from descriptor")
    selected, _ = select_in_window(json.loads(raw_classes), classes)
    names = [r["id"] for r in selected]
    queried = parse_qs(urlparse(source["query"]).query)["objectId"][0].split(",")
    if sorted(names) != sorted(queried):
        raise ValueError("object response scope differs from the class-selected roster")
    projected = cohort_id == "nov01"
    data_sha = source["projection_sha256" if projected else "upstream_sha256"]
    raw = checked_bytes(folder / observation_file, data_sha)
    rows = json.loads(raw, parse_float=D)
    if len(rows) != source["retained_rows" if projected else "upstream_rows"]:
        raise ValueError("observation count differs from descriptor")
    start, end = source["interval_jd"]
    if start != julian(classes["cutoff_utc"]) or end - start != 7:
        raise ValueError("measurement window differs from its selection cutoff")
    hashes = {"class_response": classes["alerts_sha256"], "observation_file": data_sha,
              "class_descriptor": class_sha, "observation_descriptor": observation_sha}
    return names, rows, start, end, hashes


def assemble(as_of, cohorts):
    counts = Counter(row["status"] for cohort in cohorts for row in cohort["alerts"])
    appearances = Counter(target for cohort in cohorts for target in cohort["targets"])
    return {"scope": "registered public archive event-time replay", "as_of_utc": as_of,
            "cohorts": cohorts, "overlap": sorted(key for key, count in appearances.items() if count > 1),
            "summary": {"alerts": sum(counts.values()), **{s: counts[s] for s in ACTIONS if s != "no_trigger"}}}


def calculate(as_of=None, *, root=INVENTION):
    if as_of is None:
        as_of = FINAL_UTC
    cutoff = julian(as_of)
    cohorts = []
    for key, start_utc in (("nov01", "2026-11-01T00:00:00Z"), ("nov10", "2026-11-10T00:00:00Z")):
        if cutoff < julian(start_utc):
            continue
        names, rows, start, end, hashes = registered_inputs(Path(root), key)
        result = evaluate_cohort(key, names, rows, start, end, cutoff)
        result["source_sha256"] = hashes
        cohorts.append(result)
    return assemble(as_of, cohorts)


def json_bytes(result):
    return (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def csv_bytes(result):
    """One row per exposed target and band, including untouched or unresolved combinations."""
    buf = io.StringIO(newline="")
    keys = ["as_of_utc", "cohort", "target_id", "band", "status", "action", "eligible_detections", "comparisons",
            "issued_utc", "direction", "baseline_candid", "baseline_utc", "trigger_candid", "trigger_utc",
            "delta_mag", "formal_error_mag", "gap_days", "rate_mag_per_day", "deadline_utc",
            "followup_candid", "followup_utc", "followup_delta_mag", "followup_formal_error_mag",
            "strongest_compared_utc", "strongest_baseline_candid", "strongest_current_candid",
            "strongest_delta_mag", "strongest_formal_error_mag", "strongest_rate_mag_per_day",
            "strongest_pass_change", "strongest_pass_rate", "strongest_pass_formal_error"]
    output = csv.DictWriter(buf, fieldnames=keys, lineterminator="\n")
    output.writeheader()
    for cohort in result["cohorts"]:
        by_target = {(a["target_id"], a["band"]): a for a in cohort["alerts"]}
        for group in cohort["coverage"]:
            row = {"as_of_utc": result["as_of_utc"], "cohort": cohort["id"],
                   **{key: group[key] for key in keys if key in group}}
            strongest = group["strongest_comparison"]
            if strongest:
                row.update(strongest_compared_utc=strongest["issued_utc"],
                           strongest_baseline_candid=strongest["baseline"]["candid"],
                           strongest_current_candid=strongest["trigger"]["candid"])
                for key in ("delta_mag", "formal_error_mag", "rate_mag_per_day"):
                    row["strongest_" + key] = strongest[key]
                for gate, passed in strongest["gates"].items():
                    row["strongest_pass_" + gate] = passed
            matched = by_target.get((group["target_id"], group["band"]))
            if matched:
                row.update({key: matched[key] for key in keys if key in matched})
                for phase in ("baseline", "trigger", "followup"):
                    if matched[phase]:
                        for key in ("candid", "utc"):
                            row[f"{phase}_{key}"] = matched[phase][key]
            output.writerow(row)
    return buf.getvalue().encode()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", help="UTC cutoff; only strictly earlier detections may enter the result")
    destination = ap.add_mutually_exclusive_group()
    destination.add_argument("--out", type=Path, help="write complete JSON to a new file")
    destination.add_argument("--csv", type=Path, help="write the action worklist to a new CSV file")
    destination.add_argument("--check", action="store_true", help="check the two frozen end-of-study files")
    args = ap.parse_args()
    if args.check and args.as_of and args.as_of != FINAL_UTC:
        ap.error("the frozen comparison applies to " + FINAL_UTC)
    try:
        result = calculate(args.as_of)
        if args.out or args.csv:
            with (args.out or args.csv).open("xb") as stream:
                stream.write(json_bytes(result) if args.out else csv_bytes(result))
        elif args.check:
            if (HERE / "RESULT.json").read_bytes() != json_bytes(result) or (
                    HERE / "worklist.csv").read_bytes() != csv_bytes(result):
                raise ValueError("the frozen change recipient differs from the reconstruction")
            print(json.dumps(result["summary"]))
        else:
            sys.stdout.buffer.write(json_bytes(result))
    except (ValueError, OSError) as exc:
        ap.exit(1, str(exc) + "\n")
