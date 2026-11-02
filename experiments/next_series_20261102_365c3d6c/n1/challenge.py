import argparse
import copy
import hashlib
import json
import math
import resource
import time
from pathlib import Path

from adapter import HERE, adapt_public, assess, model_fixture


def make_case(name):
    observation, evidence, policy = model_fixture()
    mode = "authored_model"
    if name.startswith("public_channel_"):
        mode = "public_sources"
        observation["source_tag"] = "conductivity" + name.rsplit("_", 1)[1] + "_DS"
        for sample in observation["samples"]:
            sample["value"] = 0
    elif name == "wrong_stream":
        observation["source_tag"] = "MODEL_BRINE"
    elif name == "unit_error":
        observation["unit"] = "mS/cm"
    elif name == "temperature_error":
        observation["temperature_basis"] = "UNCOMPENSATED"
    elif name == "counter_reset":
        observation["counter"]["end"] = 1
    elif name == "reversal_transition":
        observation["state_code"], observation["reversal"] = 3, True
    elif name == "stale_calibration":
        evidence["installed_calibration"]["valid_until_s"] = 4
    elif name == "timestamp_offset":
        observation["clock_offset_s"] = 1
    elif name == "missing_release":
        observation.pop("release")
    elif name == "gap_at_batch_boundary":
        observation["samples"] = [observation["samples"][0], observation["samples"][2]]
        observation["samples"][1]["batch_id"] = "OTHER_BATCH"
    elif name == "unresolved_mixing":
        observation["batch"]["mixed"] = True
    elif name == "nonfinite_value":
        observation["samples"][1]["value"] = math.nan
    elif name == "missing_samples":
        observation["samples"] = []
    elif name == "early_release":
        observation["release"]["time_s"] = 9
    elif name == "recycle_counter":
        observation["counter"]["route"] = "stack_recycle"
    elif name == "uncertainty_crosses_limit":
        observation["samples"][1]["value"] = 1000
    elif name == "unknown_tag":
        observation["source_tag"] = "MODEL_UNREGISTERED"
    elif name == "nonmonotone_clock":
        observation["samples"][1]["time_s"] = -1
    elif name == "empty_mapping":
        evidence["channel_to_stream"] = {}
    elif name == "malformed_evidence":
        evidence = []
    elif name == "malformed_mapping":
        evidence["channel_to_stream"] = ["MODEL_DILUATE"]
    elif name == "malformed_calibration":
        evidence["installed_calibration"] = "CLAIMED_VALID"
    elif name == "blank_release_provenance":
        evidence["batch_release_rule"] = " "
    elif name == "blank_state_provenance":
        evidence["archive_state_tag"] = ""
    elif name != "complete_authored_model":
        raise ValueError("Unregistered case: " + name)
    return observation, evidence, policy, mode


def run():
    started = time.monotonic()
    cpu0 = resource.getrusage(resource.RUSAGE_SELF)
    contract = json.loads((HERE / "CONTRACT.json").read_text())
    rows = []
    for case in contract["authored_cases"]:
        observation, evidence, policy, mode = make_case(case["id"])
        result = adapt_public(observation) if mode == "public_sources" else assess(observation, evidence, policy, True)
        expected_reasons = set(case["required_reasons"])
        passed = result["quality_status"] == case["expected_status"] and expected_reasons.issubset(result["reasons"]) and result["physical_admission"] is False
        if mode == "public_sources":
            passed = passed and result["qualified_volume_l"] is None and result["physical_stream"] == "UNKNOWN"
        rows.append({"id": case["id"], "mode": mode, "test_passed": passed, "result": result})
    cpu1 = resource.getrusage(resource.RUSAGE_SELF)
    source_files = ["adapter.py", "challenge.py", "CONTRACT.json", "SOURCE_MANIFEST.json", "ORIGINAL_W1.json"]
    return {
        "experiment": contract["experiment_id"], "evidence_scope": "AUTHORED_IMPLEMENTATION_CONTROLS_ONLY",
        "registered_denominator": len(contract["authored_cases"]), "passed": sum(r["test_passed"] for r in rows),
        "failed": sum(not r["test_passed"] for r in rows), "rows": rows,
        "public_proxy_admission": "HOLD", "fresh_date_sampling": "NOT_STARTED_PREREQUISITE_STOP",
        "empirical_failure_probability": None, "physical_delivery": False, "native_financial_trajectory": "NOT_RUN",
        "resource": {"wall_s": time.monotonic() - started, "process_cpu_s": cpu1.ru_utime + cpu1.ru_stime - cpu0.ru_utime - cpu0.ru_stime, "economic_model_and_host_cost": "UNKNOWN"},
        "source_sha256": {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest() for p in source_files},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new attempt-specific output path")
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ["experiment", "registered_denominator", "passed", "failed", "public_proxy_admission", "fresh_date_sampling"]}))
    raise SystemExit(0 if result["failed"] == 0 else 1)
