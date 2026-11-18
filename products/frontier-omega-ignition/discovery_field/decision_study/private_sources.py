"""Export an opt-in source packet for the existing private mission research workbench."""
from __future__ import annotations

import argparse
import json

from . import evaluate

ROLE = "Registered public scientific decision excerpt"
# The first timestamp by which all passages had been acquired and checked.
# Individual browser retrieval times and full HTTP response hashes are unknown.
OBSERVED_BY = "2026-11-18T04:10:35Z"
PREMISES = {
    "A": ("edge_scenario_latency_ms", "12.2", "reported_distilled_model_jetson_case"),
    "B": ("conventional_solver_throughput", "matched_or_exceeded_tested_surrogates", "reported_parallel_ordinary_power_flow"),
    "C": ("hard_subset_selection", "shared_tracker_failures", "reported_celltracking_subset"),
    "D": ("challenge_image_origins", "real_and_computer_generated", "reported_general_challenge"),
}


def export(number):
    packet = evaluate.packet(number)
    records = evaluate.sources()
    source_rows = []
    for row in packet["sources"]:
        s = records[row["id"]]
        source_rows.append({**{key: s[key] for key in ("url", "title", "publisher", "version", "published_at")},
                            "text": s["excerpt"], "sha256": s["excerpt_sha256"], "retrieved_at": OBSERVED_BY,
                            "role": ROLE, "rights": "Attributed public excerpt for a local research decision."})
    return {"mission": {"purpose": packet["question"], "requirements": []}, "sources": source_rows}


def source_slot(signal):
    if signal.get("role") != ROLE:
        return None
    for slot, record in evaluate.sources().items():
        if (slot in PREMISES and signal.get("url") == record["url"]
                and signal.get("text") == record["excerpt"]
                and signal.get("sha256", record["excerpt_sha256"]) == record["excerpt_sha256"]
                and signal.get("source_response_sha256") is None):
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
    args = parser.parse_args()
    print(json.dumps(export(args.context), indent=2, ensure_ascii=False))
