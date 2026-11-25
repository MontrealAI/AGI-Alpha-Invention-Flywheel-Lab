#!/usr/bin/env python3
"""Summarize an exact archived registry observation window."""

import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

import observe_release


def summarize(directory):
    registration = json.loads((directory / "registration.json").read_bytes())
    code = Path(observe_release.__file__).read_bytes()
    if sha256(code).hexdigest() != registration["source_sha256"]:
        raise ValueError("requires the registered observation implementation")
    rows = [json.loads(line) for line in (directory / "observations.jsonl").read_text().splitlines()]
    arms = {}
    for name in registration["arms"]:
        attempts = [row for row in rows if row["arm"] == name]
        accepted = [row for row in attempts if "accepted" in row]
        if not accepted:
            arms[name] = {"completed_attestations": 0, "failures": len(attempts), "targets": {}}
            continue
        for row in accepted:
            raw = (directory / (row["sha256"] + ".json")).read_bytes()
            if sha256(raw).hexdigest() != row["sha256"] or observe_release.attest(raw, name) != row["accepted"]:
                raise ValueError("source capture and logged attestations disagree")
        arms[name] = {
            "completed_attestations": len(accepted), "failures": len(attempts) - len(accepted),
            "http_not_modified": sum(row["status"] == 304 for row in accepted),
            "received_response_bytes": sum(row["bytes"] for row in accepted),
            "median_request_seconds": median(row["elapsed_s"] for row in accepted),
            "targets": {},
        }
        for target in registration["targets"]:
            observed = next((row for row in accepted if target in row["accepted"]), None)
            missing = [row for row in accepted if target not in row["accepted"] and
                       (observed is None or row["round"] < observed["round"])]
            arms[name]["targets"][target] = {
                "first_observed_at": observed["completed_at"] if observed else None,
                "last_observed_absence": missing[-1]["completed_at"] if missing else None,
                "registry_metadata_at_positive_observation": observed["accepted"][target] if observed else None,
                "censoring": "RIGHT" if observed is None else "INTERVAL" if missing else "LEFT",
            }
    comparisons = {}
    for target in registration["targets"]:
        tag = arms["tag"]["targets"].get(target)
        assets = arms["assets"]["targets"].get(target)
        tag_date = tag["first_observed_at"] if tag else None
        assets_date = assets["first_observed_at"] if assets else None
        both = bool(tag_date and assets_date)
        # First responses alone cannot show publication order when intervals overlap.
        observed_delta = (datetime.fromisoformat(tag_date) - datetime.fromisoformat(assets_date)).total_seconds() if both else None
        same_round = (
            next(row["round"] for row in rows if row["arm"] == "tag" and row["completed_at"] == tag_date)
            == next(row["round"] for row in rows if row["arm"] == "assets" and row["completed_at"] == assets_date)
        ) if both else None
        comparisons[target] = {
            "observed_tag_minus_assets_seconds": observed_delta, "same_round": same_round,
            "lead_qualified": False,
            "reason": "No controlled acquisition lead established. The two endpoints use the same underlying registry."
            if both else "At least one first exact positive observation is missing.",
        }
    round_counts = Counter(row["round"] for row in rows)
    return {
        "schema": "frontier/prospective-independent-acquisition-v1",
        "registration": registration, "arms": arms, "comparisons": comparisons,
        "last_observation": max((row["completed_at"] for row in rows), default=None),
        "completed_scheduled_rounds": sum(number == len(arms) for number in round_counts.values()),
        "observation_trace_sha256": sha256((directory / "observations.jsonl").read_bytes()).hexdigest(),
        "scope": "Finite same-registry probe with independent request paths. No asset download, first-mover performance, "
                 "complete acquisition advantage or operating savings are established by this summary.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.directory), ensure_ascii=False, indent=2))
