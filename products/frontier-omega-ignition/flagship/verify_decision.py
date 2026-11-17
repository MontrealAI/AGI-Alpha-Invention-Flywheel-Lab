"""Reproduce the decision delivered by the private workbench in a fresh recipient directory."""
import argparse
import json
from pathlib import Path

from conventional import enumerate_sql
from pairing_lab import PUBLIC_HASH, ROOT, analyze, digest


def verify(received, raw):
    if digest(raw) != PUBLIC_HASH:
        raise ValueError("Public study data identity differs")
    params = received["parameters"]
    analysis = analyze(raw, **params, witnesses=False)
    chosen, scores = enumerate_sql(raw, params["budget"], params["width"], params["model"], params["repository"])
    if (list(chosen) if chosen else None) != analysis["selected"]:
        raise ValueError("The independent policy selections disagree")
    if chosen and any(scores[section][chosen] != analysis[section] for section in ("calibration", "audit")):
        raise ValueError("The independent scores disagree")
    if dict(analysis, sql_agreement=True) != received:
        raise ValueError("The received decision differs from the reproduction")
    return analysis["verdict"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=ROOT / "mission-decision.json")
    args = parser.parse_args()
    print("Decision reproduced. Pilot verdict:", verify(json.loads(args.receipt.read_bytes()), (ROOT / "runs.csv").read_bytes()))
