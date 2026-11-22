"""Read-only, purpose-relative challenge to FRONTIER Ω ALPHA's first receipt study.

The first version detects a consequential evidence gap; it does not invent a
mathematical proof, certify independence, establish buyer demand, or authorize
any operation. Run through `python -m research.reflective_gate` from the product
root using the pinned inputs and report produced by the existing experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "frontier-omega-alpha/reflective-gate-v1"
PROTOCOL_SCHEMA = "frontier-omega-alpha/research-protocol-v1"


def _source_hosts(plan: dict) -> dict[str, list[str]]:
    """Conservatively group evidence files by their exact publisher hostname.

    Hosts are *not* certified independent fault domains. A shared hostname is
    enough to rule out treating its files as multiple independent publishers.
    """
    grouped: dict[str, list[str]] = {}
    for stage in plan["stages"]:
        for source in stage["files"].values():
            url = urlsplit(source["url"])
            if (
                url.scheme != "https" or not url.hostname or url.username
                or url.password or url.port not in (None, 443)
                or url.query or url.fragment
            ):
                raise ValueError("Receipt source must be a plain HTTPS URL")
            grouped.setdefault(url.hostname.lower(), []).append(source["file"])
    if not grouped:
        raise ValueError("No registered evidence sources")
    return {host: sorted(set(files)) for host, files in sorted(grouped.items())}


def _report_counts(report: dict) -> tuple[int, int]:
    count = 0
    cohorts = report.get("stages", [])
    if not isinstance(cohorts, list):
        raise ValueError("Invalid experiment stages")
    for stage in cohorts:
        rows = stage.get("cases", [])
        if not isinstance(rows, list):
            raise ValueError("Invalid experiment cases")
        count += len(rows)
    return len(cohorts), count


def analyze(
    plan: dict,
    report: dict,
    *,
    protocol_sha256: str,
    independent_receipt_replay: bool,
    max_faulty_source_groups: int = 1,
) -> dict:
    """Produce explicit challenges without promoting any unmeasured claim.

    The caller must independently rerun the original registered receipt checker
    before setting independent_receipt_replay=True. This flag does NOT mean
    independent mathematical proof verification or external peer review.
    """
    if plan.get("schema") != PROTOCOL_SCHEMA:
        raise ValueError("Unsupported protocol; do not generalize this study silently")
    if not isinstance(max_faulty_source_groups, int) or not 0 <= max_faulty_source_groups <= 8:
        raise ValueError("Invalid source fault budget")
    if not isinstance(protocol_sha256, str) or len(protocol_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in protocol_sha256
    ):
        raise ValueError("Invalid protocol digest")
    cohorts, cases = _report_counts(report)
    host_groups = _source_hosts(plan)
    registered_cohorts = len(plan["stages"])
    is_receipt_agreement = bool(
        independent_receipt_replay
        and report.get("protocol_sha256") == protocol_sha256
        and report.get("technical_verdict") == "receipt-agreement"
        and cohorts == registered_cohorts
        and all(stage.get("acceptance_matrix_matched") is True for stage in report["stages"])
    )
    # If a source-group distance is > 2t, at least 2t+1 distinct groups must
    # exist. The converse does not hold: *counting* different hosts proves no
    # distance, source independence, admissible target class, or fault budget.
    necessary_groups = 2 * max_faulty_source_groups + 1
    host_count = len(host_groups)
    source_fault_status = (
        "necessary_group_count_failed" if host_count < necessary_groups
        else "necessary_group_count_only_not_certified"
    )
    returned_profile = report.get("retained_profile_sha256")
    profile_recorded = bool(is_receipt_agreement and returned_profile)
    findings = [
        {
            "id": "reference-fault-dependence",
            "challenged_claim": "Checker agreement independently establishes the source's truth",
            "scope": "Published statement-match and axiom logs, not Lean kernel reexecution",
            "evidence": {
                "publisher_hosts": host_groups,
                "publisher_host_count": host_count,
                "necessary_groups_for_t_fault_correction": necessary_groups,
                "correction_claim": source_fault_status,
            },
            "materiality": "A common upstream error can be accepted by both local implementations.",
            "discriminating_test": (
                "Independently acquire and execute the pinned formal proof in a qualified "
                "Lean toolchain, or obtain genuinely different evidence under an explicit fault model."
            ),
            "status": "supported_material_gap",
        },
        {
            "id": "reuse-versus-improvement",
            "challenged_claim": "Reloading a retained method proves a better inventor",
            "scope": "A retained parser was applied to a second, registered receipt cohort",
            "evidence": {"retained_profile_recorded": profile_recorded,
                         "matched_no_reuse_improvement": "not established"},
            "materiality": "Reuse alone cannot establish faster, cheaper, or better future invention.",
            "discriminating_test": (
                "Freeze a genuinely different beneficiary task and compare retained, no-reuse, "
                "direct specialist and equal-content constructor arms at complete costs."
            ),
            "status": "supported_material_gap",
        },
        {
            "id": "technical-to-economic-leap",
            "challenged_claim": "A successful proof-receipt adapter establishes commercial alpha",
            "scope": "Source-bound technical screening study",
            "evidence": {"beneficiary_acceptance": "not observed",
                         "customer_payment": "not observed",
                         "complete_cost_profit": "not established"},
            "materiality": "No actual buyer or accepted productive result has been established.",
            "discriminating_test": (
                "Name an authorized beneficiary, obtain an outcome acceptance contract, "
                "compare direct alternatives, count full costs, and seek real acceptance only under authority."
            ),
            "status": "supported_material_gap",
        },
    ]
    return {
        "schema": SCHEMA,
        "protocol_sha256": protocol_sha256,
        "scope": "FIRST REGISTERED LEAN RECEIPT EXPERIMENT ONLY",
        "technical_status": "registered_receipt_replay_verified" if is_receipt_agreement else "unverified_or_failed",
        "cohorts": cohorts,
        "cases_in_report": cases,
        "proven": {
            "receipt_agreement": is_receipt_agreement,
            "parser_reloaded": profile_recorded,
        },
        "not_proven": [
            "underlying theorem correctness by independent Lean kernel execution",
            "correction of an entire faulty upstream source group",
            "causal successor invention improvement",
            "real buyer acceptance or payment",
            "complete-cost economic advantage",
        ],
        "challenge_records": findings,
        "response_options": [
            {"kind": "measure", "action": "independently replay the declared Lean kernel proof",
             "authority": "new bounded experiment and vetted toolchain required"},
            {"kind": "compare", "action": "direct, retained and matched no-reuse alternatives",
             "authority": "fresh preregistered evaluation required"},
            {"kind": "construct", "action": "build a source-fault-resilient evidence instrument, if useful",
             "authority": "new source-fault assumptions and independent acceptance required"},
            {"kind": "economic", "action": "seek voluntary real beneficiary acceptance",
             "authority": "separate outreach, contracting and spending permissions required"},
            {"kind": "defer", "action": "retain source-bound research with no commercial claim",
             "authority": "permitted without operational changes"},
        ],
        "decision": "HOLD: technical research only; no independent-source, inventor, or commercial claim",
        "operational_authority_granted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from .__main__ import read_plan, verify_experiment, private_path

        plan, digest = read_plan(args.protocol)
        report = json.loads(args.report.read_text(encoding="utf-8"))
        inputs = private_path(args.inputs)
        if not inputs.is_dir():
            raise ValueError("Registered input directory unavailable")
        replay_ok = verify_experiment(plan, digest, inputs, report)
        result = analyze(
            plan, report, protocol_sha256=digest,
            independent_receipt_replay=replay_ok,
        )
        output = private_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps({"technical_status": result["technical_status"],
                          "challenges": len(result["challenge_records"]),
                          "decision": result["decision"]}, ensure_ascii=False))
        return 0 if replay_ok else 1
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
