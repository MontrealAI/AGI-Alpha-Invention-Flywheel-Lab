"""Qualify only the registered ZTF notice and the evidence visible on its chosen clock."""
import json
from datetime import datetime

from .desk import instant
from invention.early_survey import survey


def example_scope():
    return {"band": "g", "as_of": "2026-10-29T00:00:00Z", "clock": "event"}


def report(state, reason, evidence=(), finding=None):
    return {"state": state, "reason": reason, "evidence": list(evidence), "finding": finding}


def attribution(row):
    return {key: row[key] for key in ("url", "sha256", "observed_utc")}


def inspect_source(scope, route):
    cutoff, band = instant(scope["as_of"]), scope["band"]
    issue = "2026-10-26T00:00:00Z"
    deadline = "2026-10-29T00:00:00Z"
    if cutoff < instant(issue):
        return report("pending", "This retrospective notice had not yet been issued on the selected clock.")
    primary = survey.HERE / "sources"
    # Both pinned Fink queries establish the original question, including its reference.
    meta = json.loads((primary / "index.json").read_bytes())["requests"] + json.loads((primary / "reference-index.json").read_bytes())
    observation_time = min(cutoff, instant(deadline)).isoformat().replace("+00:00", "Z")
    if scope["clock"] == "received" and any(datetime.fromisoformat(r["observed_utc"]) > cutoff for r in meta):
        return report("unavailable", "The receiver had no recorded acquisition of all sources defining the notice by this cutoff.")
    history = survey.calculate(observation_time)
    entries = next(c for c in history["cohorts"] if c["id"] == "early_warm")["alerts"]
    notice = next(row for row in entries if row["target_id"] == "ZTF26acbezdh" and row["band"] == band)
    notice_support = {"record_id": notice["trigger"]["candid"], "publisher": "ZTF via Fink", "target_id": notice["target_id"],
                      "band": band, "issued_utc": issue, "deadline_utc": deadline, "baseline": notice["baseline"],
                      "trigger": notice["trigger"], "reference": notice["reference_image"], "sources": [attribution(r) for r in meta],
                      "event_utc": notice["trigger"]["utc"], "broker_ingested_utc": None, "units": "difference-image mag"}
    if route == "fink":
        return report("incomplete" if cutoff >= instant(deadline) else "pending",
                      "The original object response supplies the notice but no eligible later detection by the selected cutoff. Telescope coverage is unknown.",
                      [notice_support])
    from invention.early_survey.exposures import verify
    index = json.loads((verify.HERE / "sources/index.json").read_bytes())
    used = ["astrometry", "alerce-api", "packet-" + band]
    if scope["clock"] == "received" and any(datetime.fromisoformat(index[k]["observed_utc"]) > cutoff for k in used):
        return report("unavailable", "An original survey packet or its qualifying cross-archive record lacks a local acquisition by this cutoff.")
    try:
        row = verify.calculate(observation_time)["witnesses"][band]
    except (OSError, ValueError) as exc:
        return report("incomplete", "The original packet or its reference-stream qualification failed: " + str(exc))
    if row["witness"] is None:
        return report("pending" if cutoff < instant(deadline) else "incomplete", "No eligible original packet in this event-time prefix.")
    witness = {**row["witness"], "record_id": row["witness"]["candid"], "publisher": "Zwicky Transient Facility",
               "route": "ALeRCE light curve and original public ZTF Avro packet", "target_id": row["target_id"], "band": band,
               "issued_utc": issue, "deadline_utc": deadline, "baseline": row["baseline"], "trigger": row["trigger"],
               "delta_from_baseline_mag": row["delta_from_baseline_mag"], "formal_error_mag": row["formal_error_mag"],
               "sources": [attribution(index[k]) for k in used], "notice_sources": [attribution(r) for r in meta],
               "event_utc": row["witness"]["utc"], "broker_ingested_utc": None, "units": "positive difference-image mag"}
    return report("observed", "The first eligible public packet matches the Fink reference and detector and the ALeRCE measurement.", [witness], row["status"])
