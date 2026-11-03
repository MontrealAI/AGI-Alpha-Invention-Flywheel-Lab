"""Read-only account reconciliation followed by exclusive all110 summary writes.

An interruption between output files requires explicit exact-byte read-only
reconciliation; this entry point never overwrites surviving output artifacts.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import sys

from commercial.ledger import canonical, digest
from connected_enterprise.scale import aggregate_native, trailing_profit
from connected_enterprise.finance import source_identity
from experiments.public_portfolio_20261102 import dispatch_case, economics, service


def _read_exact(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("FINALIZATION_REGULAR_PUBLIC_FILES_REQUIRED")
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical(value) + b"\n":
        raise ValueError("FINALIZATION_EXACT_CANONICAL_CASE_BYTES_REQUIRED")
    return value


def _assert_state_native_consistency(state, record, aggregation, protocol):
    tape = record["ledger"]
    if state["final_native_summary_microUSD"] != tape["summary"]:
        raise ValueError("FINALIZATION_REPORTED_SUMMARY_MUST_MATCH_EXACT_NATIVE_SUMMARY")
    expected = trailing_profit(tape, operating_end_hour=protocol["operating_end_hour_exclusive"],
                               operating_complete=True, aggregation=aggregation)
    if state["observer"] != expected:
        raise ValueError("FINALIZATION_REPORTED_OBSERVER_MUST_MATCH_EXACT_NATIVE_OBSERVER")
    calendar = {"start_inclusive": economics._calendar(protocol["epoch_utc"], expected["interval"]["start_hour_inclusive"]),
                "end_exclusive": economics._calendar(protocol["epoch_utc"], expected["interval"]["end_hour_exclusive"])}
    if state["window_calendar_utc"] != calendar:
        raise ValueError("FINALIZATION_EXACT_MODELED_WINDOW_CALENDAR_REQUIRED")
    collected = {row["buyer"] for row in tape["orders"] if row["state"] == "released"}
    if state["distinct_synthetic_customers_collected"] != len(collected):
        raise ValueError("FINALIZATION_EXACT_DISTINCT_COLLECTED_CUSTOMERS_REQUIRED")


@contextmanager
def _all_slots_idle(output):
    streams = []
    try:
        for index in range(4):
            stream = (output / "control" / ("financial-worker-slot-" + str(index) + ".lock")).open("a+b")
            streams.append(stream)
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for stream in streams:
            stream.close()


def finalize(root, output, publication_sha):
    root, output = Path(root).resolve(), Path(output).resolve()
    dispatch_case._assert_publication_sha(publication_sha)
    amendment, _, protocol, plans, products = dispatch_case._load(root, output)
    stage = json.loads((output / "public" / dispatch_case.STAGE).read_text())
    dispatch_case._check_stage(root, output, stage["publication_sha"])
    if len(plans) != 110:
        raise ValueError("ORIGINAL_110_CASE_DENOMINATOR_REQUIRED")
    if (output / "public/RESULTS.json").exists():
        raise ValueError("COMPLETE_CAMPAIGN_SUMMARY_IS_NOT_OVERWRITTEN")
    if (output / "public" / dispatch_case.STOP).exists():
        raise ValueError("ACTUAL_FAILURE_STOP_PREVENTS_COMPLETE_CAMPAIGN_FINALIZATION")
    for plan in plans:
        reservation = output / "control/reservations" / (plan["case_id"] + ".json")
        if not reservation.is_file() or json.loads(reservation.read_text())["status"] != "COMPLETE":
            raise ValueError("ALL_ORIGINAL_110_ACCOUNTS_MUST_BE_COMPLETE:" + plan["case_id"])
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(root / economics.PREFIX / "verification"))
        from experiments.public_portfolio_20261102.verification.verify_finance import check_case
    finally:
        sys.path[:] = previous_path
    with _all_slots_idle(output):
        # The last worker may have completed its native account before failing
        # its dispatch receipt and setting STOP. Recheck after its slot is free.
        if (output / "public" / dispatch_case.STOP).exists():
            raise ValueError("ACTUAL_FAILURE_STOP_PREVENTS_COMPLETE_CAMPAIGN_FINALIZATION")
        for plan in plans:
            reservation = output / "control/reservations" / (plan["case_id"] + ".json")
            if not reservation.is_file() or json.loads(reservation.read_text())["status"] != "COMPLETE":
                raise ValueError("ALL_ORIGINAL_110_ACCOUNTS_MUST_BE_COMPLETE:" + plan["case_id"])
        cases, arithmetic, commitments = [], [], {}
        for plan in plans:
            folder = output / "public" / plan["case_id"]
            state = _read_exact(folder / "RESULT.json")
            manifest = _read_exact(folder / "manifest.json")
            record = _read_exact(folder / "account.public.json")
            aggregation = _read_exact(folder / "aggregation.json")
            expected_manifest = service.prepare_manifest(root, [p for p in products if p["route"] == plan["route"]], plan["case_id"])
            if manifest != expected_manifest or state["case_id"] != plan["case_id"] or state["scenario"] != plan["scenario"] or state["route"] != plan["route"]:
                raise ValueError("FINALIZATION_ORIGINAL_PLAN_MANIFEST_REQUIRED")
            if state["native_source_sha256"] != amendment["unchanged_financial_source_sha256"] or record["connected_journal"]["source"]["sha256"] != state["native_source_sha256"]:
                raise ValueError("FINALIZATION_ORIGINAL_NATIVE_SOURCE_REQUIRED")
            if record["connected_journal"]["source"] != source_identity(root, expected_manifest):
                raise ValueError("FINALIZATION_EXACT_NATIVE_SOURCE_FILE_MAP_REQUIRED")
            profile = economics._profile(protocol, plan["route"], plan["scenario"])
            opening = economics._capital(protocol, profile, plan["scenario"])
            config = record["ledger"]["config"]
            if state["cost_profile_microUSD"] != profile or state["opening_microUSD"] != opening or config["opening"] != opening or config["working"] != 0 or config["contract"] != "public-portfolio-" + plan["case_id"]:
                raise ValueError("FINALIZATION_ORIGINAL_PROFILE_CAPITAL_ACCOUNT_LINEAGE_REQUIRED")
            if digest(record["connected_journal"]) != record["connected_journal_sha256"] or aggregation != aggregate_native(record["ledger"]):
                raise ValueError("FINALIZATION_EXACT_JOURNAL_AGGREGATION_REQUIRED")
            _assert_state_native_consistency(state, record, aggregation, protocol)
            check = check_case(folder, state, manifest, record, protocol["operating_end_hour_exclusive"])
            if not check["passed"]:
                raise ValueError("FINALIZATION_FULL_FINANCIAL_ARITHMETIC_REQUIRED:" + plan["case_id"])
            profit = check["independent_trailing365_profit_microUSD"]
            if state["target_1b"] != (profit >= economics.micro(1_000_000_000)) or state["target_3b"] != (profit >= economics.micro(3_000_000_000)):
                raise ValueError("FINALIZATION_EXACT_MILESTONE_FLAGS_REQUIRED")
            cases.append(economics._compact(state))
            arithmetic.append(check)
            commitments[plan["case_id"]] = {name: dispatch_case._hash(folder / name) for name in ("manifest.json", "RESULT.json", "account.public.json", "aggregation.json")}
        summary = json.loads((output / "public/RUN_IDENTITY.json").read_text())
        summary.update({"status": "COMPLETE", "cases": cases, "completed_businesses": 110,
            "failed_businesses": 0, "target_1b_count": sum(row["target_1b"] for row in cases),
            "target_3b_count": sum(row["target_3b"] for row in cases),
            "execution002_dispatch_stage": stage,
            "finalization": {"publication_sha": publication_sha,
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "case_commitments_sha256": digest(commitments), "case_count": 110,
                "all_completed_window_arithmetic_passed": True,
                "scope": "Integration reconciliation, not an independent verifier or market/physical qualification"}})
        summary["execution_stage_commitments"] = {name: {"sha256": dispatch_case._hash(output / "public" / name),
            "record": json.loads((output / "public" / name).read_text())} for name in
            ("RECOVERY_STAGE_001.json", dispatch_case.STAGE, "FAST_RECOVERY_STAGE_002.json")
            if (output / "public" / name).is_file()}
        summary["working_capital_pairs"] = []
        for route in economics.ROUTES:
            pair = {row["scenario"]: row for row in cases if row["route"] == route and row["scenario"].startswith("working-capital-")}
            aware, greedy = pair["working-capital-aware"], pair["working-capital-greedy"]
            if aware["matched_world_sha256"] != greedy["matched_world_sha256"]:
                raise ValueError("FINALIZATION_MATCHED_WORKING_CAPITAL_WORLD_REQUIRED")
            summary["working_capital_pairs"].append({"route": route, "matched_world_sha256": aware["matched_world_sha256"], "aware_minus_greedy_profit_microUSD": aware["profit_microUSD"] - greedy["profit_microUSD"], "aware_minus_greedy_collected_orders": aware["accepted_and_collected_orders"] - greedy["accepted_and_collected_orders"]})
        dispatch_case._check_stage(root, output, stage["publication_sha"])
        measured = []
        for path in sorted((output / "public").glob("*/*.json")):
            if path.name == "RESOURCES.json" or path.name.startswith(("RECOVERY_001", "FAST_RECOVERY_002_", "DISPATCH002_RECEIPT_")):
                measured.append({"path": str(path.relative_to(output / "public")), "sha256": dispatch_case._hash(path)})
        telemetry = {"schema": "public-portfolio/interrupted-execution-resource-index/v2",
            "completed_businesses": 110, "measured_component_receipts": measured,
            "original_interrupted_process_total_wall_cpu_tokens_billing": None,
            "exact_whole_campaign_actual_resource_total_available": False,
            "scope": "Known per-case/call measurements indexed without pooling parallel wall times or inventing lost host usage; complete modeled ledger costs remain in each original business."}
        economics._save(output / "public/FINALIZATION_CHECKS_002.json", {"status": "PASS", "cases": arithmetic, "case_commitments": commitments, "independence": "Integration check reuses frozen checker; independent audit remains separate"})
        economics._save(output / "public/EXECUTION_TELEMETRY_002.json", telemetry)
        economics._save(output / "public/RESULTS.json", summary)
        economics._write_report(output, protocol, summary)
        return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--publication-sha", required=True)
    args = parser.parse_args()
    result = finalize(args.root, args.output, args.publication_sha)
    print(json.dumps({"status": result["status"], "complete": result["completed_businesses"], "target3b": result["target_3b_count"]}))
