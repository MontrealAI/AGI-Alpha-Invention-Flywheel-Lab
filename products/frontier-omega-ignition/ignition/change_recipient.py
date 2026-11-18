"""Receive and reproduce one dated, source-bound historical review queue."""
import csv
from datetime import datetime, timezone
import io
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent


def controls(value):
    if type(value) is not dict or not {"as_of_utc", "arm"} <= set(value) <= {"as_of_utc", "arm", "check_other_archive"}:
        raise ValueError("Supply a UTC cutoff and one baseline arm.")
    cutoff, arm = value["as_of_utc"], value["arm"]
    if arm not in ("early_cold", "early_warm"):
        raise ValueError("Choose the within-week or seven-day-history baseline.")
    if not isinstance(cutoff, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", cutoff):
        raise ValueError("Use an ISO UTC cutoff ending in Z.")
    instant = datetime.fromisoformat(cutoff)
    check_other = value.get("check_other_archive", False)
    if type(check_other) is not bool:
        raise ValueError("Choose whether this revision may use the second public archive.")
    last = datetime(2026, 11, 17 if check_other else 1, tzinfo=timezone.utc)
    if not datetime(2026, 10, 25, tzinfo=timezone.utc) <= instant <= last:
        raise ValueError("Choose a UTC cutoff from October 25 through the selected archive's closing date.")
    return {"as_of_utc": cutoff, "arm": arm, "check_other_archive": check_other}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def archive_csv(witnesses):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("target_id", "band", "issued_utc", "deadline_utc", "fink_status", "archive_status",
                     "witness_candid", "witness_utc", "delta_from_baseline_mag", "formal_error_mag",
                     "aperture_status", "forced_status", "forced_carrier_utc"))
    for band, item in sorted(witnesses.items()):
        witness = item["witness"] or {}
        forced = item.get("forced_photometry") or {}
        writer.writerow((item["target_id"], band, item["issued_utc"], item["deadline_utc"], item["fink_status"],
                         item["status"], witness.get("candid"), witness.get("utc"), item["delta_from_baseline_mag"], item["formal_error_mag"],
                         (item.get("aperture") or {}).get("status"), forced.get("status"), forced.get("carrier_utc")))
    return stream.getvalue().encode()


def main():
    args = sys.argv[1:]
    construct = args == ["--construct"]
    expected_sha = None
    if args and not construct:
        if len(args) != 2 or args[0] != "--expect-queue" or not re.fullmatch(r"[0-9a-f]{64}", args[1]):
            raise ValueError("Use --expect-queue with the SHA-256 shown by the issuing workbench.")
        expected_sha = args[1]
    sys.path.insert(0, str(ROOT))
    from invention.early_survey.survey import calculate
    from invention.evolution.alert import csv_bytes

    scope_bytes = (ROOT / "scope.json").read_bytes()
    specification = controls(json.loads(scope_bytes))
    if scope_bytes != json_bytes(specification):
        raise ValueError("Received scope differs from the canonical issued specification.")
    result = calculate(as_of=specification["as_of_utc"])
    selected, = [c for c in result["cohorts"] if c["id"] == specification["arm"]]
    queue = {"schema": "ignition.dated-change-queue.v1", "as_of_utc": result["as_of_utc"], "cohorts": [selected]}
    additional_csv = None
    if specification["check_other_archive"]:
        from invention.early_survey.exposures.verify import calculate as second_archive
        notices = {(a["target_id"], a["band"]): a for a in selected["alerts"]}
        evidence = second_archive(as_of=specification["as_of_utc"])["witnesses"] if notices else {}
        witnesses = {}
        for band, item in evidence.items():
            key = (item["target_id"], band)
            if key not in notices:
                raise ValueError("The second archive names an unissued target or band.")
            if notices[key]["status"] != item["fink_status"] or notices[key]["issued_utc"] != item["issued_utc"]:
                raise ValueError("The two archives disagree about the original notice.")
            if item["witness"] and datetime.fromisoformat(item["witness"]["utc"]) >= datetime.fromisoformat(specification["as_of_utc"]):
                raise ValueError("The second archive witness is outside the selected cutoff.")
            witnesses[band] = item
        if set(notices) != {(item["target_id"], band) for band, item in witnesses.items()}:
            raise ValueError("The second-archive check did not account for each issued target and band.")
        queue["archive_recheck"] = witnesses
        additional_csv = archive_csv(witnesses)
    worklist = csv_bytes(queue)
    receipt = {"scope": specification, "route": "source-reconstruction-and-independent-sql",
               "target_bands": len(selected["coverage"]), "issued": len(selected["alerts"]),
               "queue_sha256": hashlib.sha256(json_bytes(queue)).hexdigest(),
               "csv_sha256": hashlib.sha256(worklist).hexdigest()}
    if additional_csv is not None:
        receipt["archive_csv_sha256"] = hashlib.sha256(additional_csv).hexdigest()
    if expected_sha is not None and receipt["queue_sha256"] != expected_sha:
        raise ValueError("The reconstructed queue differs from the independently retained digest.")
    if construct:
        result = {"queue": queue, "receipt": receipt, "csv": worklist.decode("utf-8")}
        if additional_csv is not None:
            result["archive_csv"] = additional_csv.decode("utf-8")
        print(json.dumps(result, allow_nan=False))
        return
    if (ROOT / "queue.json").read_bytes() != json_bytes(queue):
        raise ValueError("Delivered archive queue differs from the historical reconstruction.")
    if (ROOT / "worklist.csv").read_bytes() != worklist:
        raise ValueError("Delivered CSV differs from the checked queue.")
    if additional_csv is not None and (ROOT / "archive-recheck.csv").read_bytes() != additional_csv:
        raise ValueError("The supplemental witness CSV differs from the second archive.")
    if additional_csv is None and (ROOT / "archive-recheck.csv").exists():
        raise ValueError("Unexpected second-archive result for this scope.")
    if (ROOT / "verification.json").read_bytes() != json_bytes(receipt):
        raise ValueError("Received verification differs from the reproduced receipt.")
    print(json.dumps(receipt, allow_nan=False))


if __name__ == "__main__":
    main()
