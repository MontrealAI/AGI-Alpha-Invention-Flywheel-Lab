"""Rebuild the nine case selections from the registered contracts and original report facts."""
import argparse
import json
from pathlib import Path

from decide import HERE, REPORTS_SHA256, decide, frozen_sources, strict_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path, default=HERE.parent / "endpoint_study/contracts.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = strict_json(args.contracts.read_bytes())
    scenarios = []
    for name, contract in cases.items():
        receipt = decide(contract)
        result = {k: receipt[k] for k in ("decision", "selected", "next_test", "contract_sha256",
                                          "instrument_sha256", "deployment_authorized")}
        result["eligible_count"] = len(receipt["eligible"])
        result["excluded_count"] = len(receipt["excluded"])
        scenarios.append({"id": name, "requirement": contract, "result": result})
    payload = {"schema": "frontier-endpoints/exhibition/v1", "timestamp": "2026-11-17",
               "reports_sha256": REPORTS_SHA256, "scenarios": scenarios,
               "sources": frozen_sources(HERE / "reports.json")}
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


if __name__ == "__main__":
    main()
