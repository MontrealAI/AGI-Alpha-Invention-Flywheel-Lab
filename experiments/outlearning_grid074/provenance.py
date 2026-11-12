"""Compact public-safe generated-artifact provenance, never private reasoning."""
import datetime
import hashlib
import json
from pathlib import Path


def record(directory, event, observations, decision, artifacts=(), evidence_role="development"):
    root = Path(directory)
    row = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event,
        "evidence_role": evidence_role,
        "permitted_observations": observations,
        "decision_summary": decision,
        "provenance": "included assistant model generated source during this session; no paid model API",
        "artifacts": {
            str(Path(p).name): hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in artifacts
        },
    }
    with (root / "PROVENANCE.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    root = Path(__file__).parent
    print(json.dumps(record(root, "opportunity_selection", [
        "current public AGENTS and relevant mechanism/operator/resource guides",
        "DOE interconnection roadmap; established inverter probing and robust DOE literature",
        "EPA/WHO water-reuse acceptance; ARENA industrial heat operating report",
    ], "Select a cheap rejection-capable calibration-ambiguity development test. No flagship, customer, acceptance or profit claim.",
        [root / "OPPORTUNITIES.md", __file__]), indent=2))
