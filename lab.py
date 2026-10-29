# SPDX-License-Identifier: Apache-2.0
"""Minimal evidence-gap screener for Blue Sky discovery; no external calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FIELDS = (
    "id", "domain", "beneficiary", "future_possibility", "strongest_complete_alternative",
    "current_constraint", "missing_means", "donor_mechanism", "analogy_limit",
    "second_order_effect", "decisive_experiment", "falsifier", "economic_cohort",
    "evidence_sources", "known_complete_costs", "successor_family"
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def inspect(candidates: Any) -> dict[str, Any]:
    if not isinstance(candidates, list) or len(candidates) < 3:
        raise ValueError("At least three separately described possibilities are required")
    ids: set[str] = set()
    domains: set[str] = set()
    inspected = []
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("Every candidate must be a JSON object")
        if set(item) != set(FIELDS):
            raise ValueError("Candidate fields must match the fixed schema")
        if not all(isinstance(item[field], str) and item[field].strip() for field in FIELDS if field not in
                   {"evidence_sources", "known_complete_costs"}):
            raise ValueError("Text fields cannot be empty")
        cid, domain = item["id"], item["domain"]
        if cid in ids or domain in domains:
            raise ValueError("Candidate IDs and declared domains must differ")
        ids.add(cid)
        domains.add(domain)
        sources = item["evidence_sources"]
        costs = item["known_complete_costs"]
        if not isinstance(sources, list) or not all(isinstance(source, dict) and
             set(source) == {"url", "as_of", "supports"} and all(isinstance(v, str) and v.strip()
             for v in source.values()) for source in sources):
            raise ValueError("Evidence sources must have URL, cutoff date and supported claim")
        if costs is not None and (not isinstance(costs, dict) or set(costs) !=
                                  {"baseline", "candidate", "currency", "horizon", "source"}):
            raise ValueError("Cost fields must be either null or a complete signed record")
        missing = []
        if not sources:
            missing.append("Dated primary evidence for beneficiary, unmet need and alternatives")
        if costs is None:
            missing.append("Measured full-service conventional and proposed costs for the same cohort")
        if costs is not None:
            missing.append("Independent verification of cost model, cohort and outcome equivalence")
        missing.extend([
            "Executed decisive experiment with an independent outcome checker",
            "Sourced willingness-to-pay and buyer participation evidence",
            "Fresh counterfactual successor-benefit test"
        ])
        inspected.append({
            "id": cid, "domain": domain,
            "status": "NOT_ADMITTED", "missing": missing,
            "test_to_run_first": item["decisive_experiment"],
            "failure_witness": item["falsifier"],
            "source_entries_are_unverified": True,
            "source_count": len(sources),
            "proposed_means": item["missing_means"],
            "opportunity_origin": "developer-authored hypothesis; not autonomous discovery"
        })
    return {
        "schema": "alpha-blue-sky-screen/v1", "input_sha256": sha(candidates),
        "distinct_declared_domains": len(domains),
        "material_distinctness_verified": False,
        "admitted_cohorts": 0, "commercial_success": "UNESTABLISHED",
        "forecast_superiority": "UNMEASURED", "candidate_results": inspected,
        "next_decision": "Acquire independent opportunity and complete-cost evidence before selecting a flagship",
        "scope": "Authored example validation only; no data acquisition, no experiment, no payment or customer contact"
    }


def screen(source: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("Output exists; preserve all previous experiments")
    if source.stat().st_size > 2_000_000:
        raise ValueError("Source exceeds 2 MB")
    candidates = json.loads(source.read_text(encoding="utf-8"))
    result = inspect(candidates)
    output.mkdir(parents=True, exist_ok=False)
    (output / "SCREEN.json").write_bytes(canonical(result) + b"\n")
    (output / "INPUT.json").write_bytes(canonical(candidates) + b"\n")
    lines = ["# Blue Sky opportunity screen — development only", "",
             "**No admitted economic cohort. No invention or commercial success confirmed.**", "",
             f"Input SHA-256: {result['input_sha256']}", ""]
    for entry in result["candidate_results"]:
        lines.extend([f"## {entry['id']} — {entry['domain']}", "", "Status: **NOT_ADMITTED**", "",
                      "Next possible discriminating test: " + entry["test_to_run_first"], "",
                      "Missing evidence:", *["- " + m for m in entry["missing"]], ""])
    lines.extend(["The source entries, if any, were supplied by the operator and have not been independently checked.",
                  "This screen does not establish that the declared domains are genuinely different opportunities.", ""])
    (output / "DECISION.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("screen", help="Expose missing evidence without inventing success")
    cmd.add_argument("input", type=Path)
    cmd.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "screen":
        try:
            result = screen(args.input, args.output)
        except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
            parser.exit(2, f"REFUSED: {exc}\n")
        print(json.dumps({"output": str(args.output), "admitted": result["admitted_cohorts"],
                          "candidate_count": len(result["candidate_results"]),
                          "claim": result["commercial_success"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
