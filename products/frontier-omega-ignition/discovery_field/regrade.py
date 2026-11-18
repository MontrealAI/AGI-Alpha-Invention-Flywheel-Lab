"""Regrade the three byte-pinned public Qwen receipts. No generation or network."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from . import open_trial, protocol, study

SOURCE = "d96ed9e3fe67f70ffdf1585b7b4bbe46b5243075"
HERE = Path(__file__).resolve().parent
MEMBERS = {
    "direct": "1b18725e03adbdde527eee1bb8a336d34b16eb5e43c7531d0062aa84f407cf8f",
    "targeted": "dc95416150ca212fa70cfafcfe26527180bf6bd7fe24fa2c5b76c2e14162dafe",
    "open": "e59032324401a81c14440d8d5e37f8e009d356845d7189590977699dc260334b",
}
# Independent reader decisions on these exact answer bytes only.
ACTIONS = {
    ("direct", "queue"): "Uses a CAD reward as an astronomical candidate-selection criterion.",
    ("direct", "metrology"): "Tests a supernova detection list instead of the drawing-to-part objective.",
    ("targeted", "queue"): "Simulates the recovery rate assumed at input; neither later observations nor feasible queued visits independently test it.",
    ("targeted", "metrology"): "Compares a binary conversion success rate directly with a continuous mean reward. Their denominators and meanings differ.",
}


def read(archive, arm):
    if archive.is_dir():
        path = archive / (arm + ".json")
        if path.stat().st_size > 64_000:
            raise ValueError("Oversize public observation")
        raw = path.read_bytes()
    else:
        with zipfile.ZipFile(archive) as z:
            entries = [m for m in z.infolist() if m.filename == arm + ".json"]
            if len(entries) != 1 or entries[0].file_size > 64_000:
                raise ValueError("Expected one bounded, unambiguous observation member")
            raw = z.read(entries[0])
    if hashlib.sha256(raw).hexdigest() != MEMBERS[arm]:
        raise ValueError("Original observation bytes differ")
    result = json.loads(raw)
    packet = open_trial.PACKET if arm == "open" else study.FROZEN_PACKET
    if result["git_head"] != SOURCE or result["packet_sha256"] != packet:
        raise ValueError("Observation source or mission differs")
    return result


def compare(discovery, open_archive):
    packet = study.read_packet()
    tasks = {t["id"]: t for t in packet["tasks"]}
    sources = study.available(packet)
    score = {"source": SOURCE, "member_sha256": MEMBERS, "observations": []}
    for arm in MEMBERS:
        original = read(open_archive if arm == "open" else discovery, arm)
        for case in original["cases"]:
            answer = case["answer"]
            row = {"arm": arm, "mission": case["task"]}
            if arm == "open":
                row["old_supported"] = sum(r["binding"] == "supported" for r in case["assessment"]["original"]["rows"])
                checked = open_trial.score(answer)
                row.update(new_supported=sum(r["binding"] == "supported" for r in checked["rows"]),
                           new_rounded=sum(r["binding"] == "rounded_consistent" for r in checked["rows"]),
                           returned=checked["returned"])
            else:
                task = tasks[case["task"]]
                observed = protocol.observe(sources[answer["source"]])
                new = study.assess(packet, task, answer)
                witness = "22/24" if observed["metric"] == "recovered_fraction" else "61.03%"
                row.update(source_cited=answer["source"], reported=answer["value"], source_value=observed["value"],
                           quantity_against_cited_source=protocol.quantity(observed, answer),
                           original_factual=case["assessment"]["factual_status"], revised_factual=new["factual_status"],
                           exact_source_expression_in_test=witness if witness in answer["test"] else None,
                           offline_decision_exactly_grounded=new["decision_eligible"], action_accepted=False,
                           scientific_reading=ACTIONS[(arm, task["id"])])
            score["observations"].append(row)
    return score


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery_archive", type=Path, nargs="?", default=HERE / "recorded")
    parser.add_argument("open_archive", type=Path, nargs="?", default=HERE / "recorded")
    parser.add_argument("--check", action="store_true", help="Require agreement with the retained historical regrade")
    args = parser.parse_args()
    outcome = compare(args.discovery_archive, args.open_archive)
    if args.check and outcome != json.loads((HERE / "QWEN_REGRADE.json").read_text(encoding="utf-8")):
        raise SystemExit("Scientific regrade differs from the retained result")
    print(json.dumps(outcome, indent=2))
