"""Read-only public-state and disposable metadata finalization checks."""
from __future__ import annotations
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.public_portfolio_20261102 import dispatch_case, economics, finalize_run


def run(public_root):
    source_before = hashlib.sha256(Path(finalize_run.__file__).read_bytes()).hexdigest()
    checks, input_hashes = {}, {}
    protocol = json.loads((ROOT / economics.PROTOCOL).read_text())
    selected = ("purpose-central-100k", "interface-central-100k", "interface-earned-only-k2")
    reference = None
    for ident in selected:
        folder = public_root / ident
        data = {}
        for name in ("RESULT.json", "account.public.json", "aggregation.json"):
            path = folder / name
            raw = path.read_bytes()
            input_hashes[ident + "/" + name] = hashlib.sha256(raw).hexdigest()
            data[name] = json.loads(raw)
        finalize_run._assert_state_native_consistency(data["RESULT.json"], data["account.public.json"], data["aggregation.json"], protocol)
        checks["public_consistency_" + ident] = True
        if reference is None:
            reference = data
    state, record, aggregation = (reference["RESULT.json"], reference["account.public.json"], reference["aggregation.json"])
    mutations = (
        ("wrong_compacted_profit", lambda value: value["final_native_summary_microUSD"].__setitem__("profit", value["final_native_summary_microUSD"]["profit"] + 1)),
        ("wrong_trailing_profit", lambda value: value["observer"].__setitem__("trailing_365_day_profit_microUSD", value["observer"]["trailing_365_day_profit_microUSD"] + 1)),
        ("wrong_window_calendar", lambda value: value["window_calendar_utc"].__setitem__("end_exclusive", "2030-01-01T00:00:00Z")),
        ("wrong_distinct_buyers", lambda value: value.__setitem__("distinct_synthetic_customers_collected", value["distinct_synthetic_customers_collected"] + 1)),
    )
    for label, mutate in mutations:
        changed = copy.deepcopy(state)
        mutate(changed)
        try:
            finalize_run._assert_state_native_consistency(changed, record, aggregation, protocol)
        except ValueError:
            checks[label + "_refused"] = True
        else:
            checks[label + "_refused"] = False
    with tempfile.TemporaryDirectory(prefix="independent-finalization-metadata-") as temporary:
        out = Path(temporary)
        (out / "control/reservations").mkdir(parents=True)
        (out / "public").mkdir()
        with dispatch_case._slot(out):
            try:
                with finalize_run._all_slots_idle(out):
                    pass
            except BlockingIOError:
                checks["active_slot_refuses_finalization_lock"] = True
            else:
                checks["active_slot_refuses_finalization_lock"] = False
        with finalize_run._all_slots_idle(out):
            try:
                with dispatch_case._slot(out):
                    pass
            except BlockingIOError:
                checks["all_idle_slots_held_prevent_new_worker"] = True
            else:
                checks["all_idle_slots_held_prevent_new_worker"] = False
        with dispatch_case._slot(out):
            checks["slots_released_after_finalization_context"] = True
        plans = [{"case_id": "metadata-only-" + str(i)} for i in range(110)]
        for plan in plans:
            (out / "control/reservations" / (plan["case_id"] + ".json")).write_text(json.dumps({"status": "COMPLETE"}))
        (out / "public" / dispatch_case.STAGE).write_text(json.dumps({"publication_sha": "1" * 40}))
        @contextmanager
        def stop_after_early_check(_output):
            (out / "public" / dispatch_case.STOP).write_text("{}")
            yield
        with patch.object(dispatch_case, "_load", return_value=({}, {}, protocol, plans, [])), \
             patch.object(dispatch_case, "_check_stage", return_value={}), \
             patch.object(finalize_run, "_all_slots_idle", stop_after_early_check):
            try:
                finalize_run.finalize(ROOT, out, "1" * 40)
            except ValueError as error:
                checks["stop_appearing_before_idle_lock_is_rechecked"] = "ACTUAL_FAILURE_STOP_PREVENTS" in str(error)
            except FileNotFoundError:
                checks["stop_appearing_before_idle_lock_is_rechecked"] = False
            else:
                checks["stop_appearing_before_idle_lock_is_rechecked"] = False
        checks["stop_race_writes_no_results"] = not (out / "public/RESULTS.json").exists()
    for relative, expected in input_hashes.items():
        if hashlib.sha256((public_root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("PUBLIC_REVIEW_INPUT_CHANGED")
    source_after = hashlib.sha256(Path(finalize_run.__file__).read_bytes()).hexdigest()
    checks["reviewed_source_unchanged_during_checks"] = source_before == source_after
    return {"schema": "public-portfolio/independent-finalization-checks/v2",
            "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "finalizer_source_sha256": source_after,
            "checks": checks, "passed": all(checks.values()), "public_input_sha256": input_hashes,
            "scope": "Three fixed complete public exports were read without mutation; fault tests alter copies or disposable metadata only. No private campaign account/key was read or opened. No110-case finalization or independent complete financial audit is claimed."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    public_root = Path(args.public_root).resolve()
    output = Path(args.output)
    if output.exists():
        raise ValueError("INDEPENDENT_FINALIZATION_RESULT_MUST_NOT_BE_OVERWRITTEN")
    result = run(public_root)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"])}))
    raise SystemExit(0 if result["passed"] else 1)
