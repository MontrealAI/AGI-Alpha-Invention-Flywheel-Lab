"""Recompute and verify a delivered contract using the two independent receivers."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from endpoint_lab.decide import decide
from endpoint_study.reference import connect, selection, verify


def main():
    contract = json.loads((ROOT / "contract.json").read_bytes())
    delivered = json.loads((ROOT / "decision.json").read_bytes())
    if decide(contract) != delivered:
        raise SystemExit("Stored decision differs from a fresh execution.")
    with connect() as db:
        if selection(contract, db) != json.loads((ROOT / "reference-result.json").read_bytes()):
            raise SystemExit("Stored independent SQL observation differs from a fresh execution.")
    report = verify(contract, delivered)
    print(json.dumps({"decision": delivered["decision"], "verification": report}, indent=2))


if __name__ == "__main__":
    main()
