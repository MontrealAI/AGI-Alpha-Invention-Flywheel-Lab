"""Replay one archival action, or reproduce all registered issue-time comparisons."""

import argparse
import json
from datetime import datetime, timedelta, timezone

if __package__:
    from . import adapter, capture, direct
else:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import adapter
    import capture
    import direct


def utc(when):
    return when.isoformat().replace("+00:00", "Z")


def cutoffs(history):
    edges = {edge for r in history for edge in (r["time"] - timedelta(microseconds=1), r["time"])}
    return sorted(edges | {history[0]["time"] + timedelta(days=7)})


def registered():
    reg = capture.manifest()
    rows = capture.roster(reg)
    consecutive, control = capture.selection(rows)
    run = {}
    for event in consecutive + ([control] if control else []):
        history = direct.schedule(event)
        matches = pending = incorrect = first_only_accepted = unqualified_received = 0
        cases = cutoffs(history)
        for t in cases:
            scope = {"event": event, "clock": "issued", "as_of": utc(t)}
            integrated = adapter.inspect_source(scope, "status_history")
            answer = integrated["finding"] if integrated["state"] == "observed" else integrated["state"]
            sql = direct.query(history, t)
            matches += (answer == sql)
            pending += (answer == "pending")
            scheduled = sql in {"active", "retracted"}
            if scheduled:
                # Descriptive naive keep-first policy, separate from the qualified first-only arm.
                incorrect += (sql == "retracted")
                first_only_accepted += adapter.inspect_source(scope, "first_notice")["state"] == "observed"
                live = adapter.inspect_source(dict(scope, clock="received"), "status_history")
                unqualified_received += live["state"] == "incomplete" and live["finding"] is None
        final = adapter.inspect_source({"event": event, "clock": "issued", "as_of": utc(cases[-1])}, "status_history")
        if not final["evidence"]:
            raise ValueError(f"Registered case could not qualify at the horizon: {event}")
        last = final["evidence"][-1]
        run[event] = {
            "group": ("enriched_mechanism_control" if event == control else
                      "consecutive_fifth_receiver_transfer" if event == consecutive[-1] else "consecutive"),
            "notices": len(history), "cutoffs": len(cases), "sql_matches": matches,
            "pending_cutoffs": pending, "finding_at_horizon": final["finding"],
            "keep_first_wrong_issued_cutoffs": incorrect,
            "qualified_from_first_only": first_only_accepted,
            "received_clock_deferrals_after_issue": unqualified_received,
            "first_issue_utc": history[0]["issued_utc"], "horizon_utc": utc(cases[-1]),
            "latest_record_id": last["record_id"], "latest_issue_utc": last["issued_utc"],
            "latest_gcn_text_notice_utc": utc(history[-1]["notice_utc"]),
        }
    circ_meta = reg["originals"]["36190.json"]
    circ = json.loads(capture.original("36190.json", circ_meta))
    if (circ["circularId"] != 36190 or circ["eventId"] != f"LIGO/Virgo/KAGRA {control}"
            or "Retraction" not in circ["subject"] or
            f"The trigger {control} is no longer considered to be a candidate of interest." not in circ["body"]):
        raise ValueError("The collaboration circular does not corroborate this withdrawal.")
    published = datetime.fromtimestamp(circ["createdOn"] / 1000, tz=timezone.utc)
    before = capture.instant(run[control]["latest_issue_utc"])
    return {
        "archive_april_rows": len(rows),
        "sampling_interval_rows": sum(r["trigger"] >= "2024-04-10" for r in rows),
        "sampling_interval_events": len({r["event"] for r in rows if r["trigger"] >= "2024-04-10"}),
        "consecutive": consecutive, "enriched_control": control,
        "outcomes": run,
        "total_registered_cutoffs": sum(v["cutoffs"] for v in run.values()),
        "total_sql_matches": sum(v["sql_matches"] for v in run.values()),
        "circular": {"source_url": circ_meta["url"], "record_id": "GCN Circular 36190",
                     "created_utc": utc(published), "seconds_after_issued_retraction": (published - before).total_seconds(),
                     "relationship": "A later public statement by the same collaboration corroborates its withdrawal."},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event")
    parser.add_argument("--as-of")
    parser.add_argument("--clock", choices=("issued", "received"), default="issued")
    parser.add_argument("--route", choices=("first_notice", "status_history"), default="status_history")
    parser.add_argument("--check", action="store_true", help="Rebuild all findings and compare the published receipt.")
    args = parser.parse_args()
    if args.check:
        result = registered()
        expected = json.loads((capture.HERE / "result.json").read_text(encoding="utf-8"))
        if result != expected or result["total_sql_matches"] != result["total_registered_cutoffs"]:
            raise SystemExit("Registered findings differ. Requalification required.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if not args.event or not args.as_of:
            parser.error("Provide --event and --as-of, or use --check.")
        result = adapter.inspect_source({"event": args.event, "as_of": args.as_of, "clock": args.clock}, args.route)
        action = {"active": "retain_shadow_review", "retracted": "withdraw_shadow_review"}.get(
            result["finding"], "defer_shadow_action")
        print(json.dumps({**result, "shadow_recommendation": action}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
