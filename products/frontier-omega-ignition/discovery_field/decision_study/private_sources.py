"""Export an opt-in source packet for the existing private mission research workbench."""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from . import evaluate

ROLE = "Registered public scientific decision excerpt"
# The first timestamp by which all passages had been acquired and checked.
# Individual times for the first, web-reader observation are unknown.
OBSERVED_BY = "2026-11-18T04:10:35Z"
REACQUIRED_BY = "2026-11-18T04:34:00Z"
PUBLISHER_RECEIPT = "3525a7f3ecb0f33c3f444867d84240b156b1ec21fdc152be741246646b199d01"
PREMISES = {
    "A": ("edge_scenario_latency_ms", "12.2", "reported_distilled_model_jetson_case"),
    "B": ("conventional_solver_throughput", "matched_or_exceeded_tested_surrogates", "reported_parallel_ordinary_power_flow"),
    "C": ("hard_subset_selection", "shared_tracker_failures", "reported_celltracking_subset"),
    "D": ("challenge_image_origins", "real_and_computer_generated", "reported_general_challenge"),
}


def acquisitions():
    raw = (evaluate.HERE / "publisher_observations.json").read_bytes()
    if evaluate.sha(raw) != PUBLISHER_RECEIPT:
        raise ValueError("Registered primary-response evidence changed")
    return {r["id"]: r for r in json.loads(raw)["results"]}


def export(number, *, reacquired=False):
    packet = evaluate.packet(number)
    records = evaluate.sources()
    captures = acquisitions() if reacquired else {}
    source_rows = []
    for row in packet["sources"]:
        s = records[row["id"]]
        source_rows.append({**{key: s[key] for key in ("url", "title", "publisher", "version", "published_at")},
                            "text": s["excerpt"], "sha256": s["excerpt_sha256"], "retrieved_at": OBSERVED_BY,
                            "role": ROLE, "rights": "Attributed public excerpt for a local research decision."})
        if reacquired:
            source_rows[-1].update(source_response_sha256=captures[row["id"]]["observed_file_sha256"],
                                   retrieved_at=REACQUIRED_BY)
    return {"mission": {"purpose": packet["question"], "requirements": []}, "sources": source_rows}


def source_slot(signal):
    if signal.get("role") != ROLE:
        return None
    body_hash = signal.get("source_response_sha256")
    earliest = REACQUIRED_BY if body_hash is not None else OBSERVED_BY
    try:
        observed_at = datetime.fromisoformat(signal["retrieved_at"].replace("Z", "+00:00"))
        if observed_at < datetime.fromisoformat(earliest.replace("Z", "+00:00")):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    for slot, record in evaluate.sources().items():
        if (slot in PREMISES and signal.get("url") == record["url"]
                and signal.get("text") == record["excerpt"]
                and signal.get("sha256", record["excerpt_sha256"]) == record["excerpt_sha256"]
                and (body_hash is None or body_hash == acquisitions()[slot]["observed_file_sha256"])):
            return slot
    return None


def observe(signal):
    slot = source_slot(signal)
    if slot is None:
        return None
    metric, value, scope = PREMISES[slot]
    return {"source": signal.get("id", slot), "metric": metric, "value": value, "scope": scope,
            "polarity": "asserted", "excerpt_sha256": evaluate.sources()[slot]["excerpt_sha256"]}


def supports_decision(signal, purpose):
    slot = source_slot(signal)
    return any(task["question"] == purpose and evaluate.RELATIONS[task["id"]][0] == slot
               for task in evaluate.registered("missions.json")["missions"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=int, choices=range(1, 5))
    parser.add_argument("--reacquired", action="store_true", help="attach the later full publisher response identity")
    args = parser.parse_args()
    print(json.dumps(export(args.context, reacquired=args.reacquired), indent=2, ensure_ascii=False))
