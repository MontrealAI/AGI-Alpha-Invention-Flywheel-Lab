import argparse
import copy
import hashlib
import importlib.util
import json
import math
import resource
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def independent_fixture():
    observation = {
        "source_tag": "REFERENCE_A", "unit": "uS/cm", "temperature_basis": "REF_25C",
        "calibration_id": "REFERENCE_CAL", "clock_offset_s": 0,
        "samples": [{"time_s": t, "value": v, "batch_id": "REF_B17"} for t, v in [(1000, 430), (1002, 431), (1004, 432)]],
        "batch": {"id": "REF_B17", "start_s": 1000, "end_s": 1004, "mixed": False},
        "state_code": 7, "reversal": False,
        "release": {"kind": "batch_release", "time_s": 1004.5, "batch_id": "REF_B17"},
        "discharge_interval_s": [1005, 1007],
        "counter": {"start": 50, "end": 60, "unit": "L", "route": "one_pass_product", "batch_id": "REF_B17"},
    }
    evidence = {
        "channel_to_stream": {"REFERENCE_A": "diluate_outlet", "REFERENCE_B": "concentrate_outlet"},
        "installed_calibration": {"id": "REFERENCE_CAL", "valid_from_s": 900, "valid_until_s": 1100},
        "temperature_compensation": "REF_25C", "clock_alignment": "REFERENCE_CLOCK",
        "archive_state_tag": "REFERENCE_STATE", "batch_release_rule": "REFERENCE_RELEASE",
        "batch_mixing_rule": "REFERENCE_MIXING", "one_pass_quantity_route": "REFERENCE_METER",
        "proxy_contract": {"maximum_uS_cm": 900, "absolute_uncertainty_uS_cm": 20},
    }
    return observation, evidence, {"maximum_gap_s": 2, "maximum_clock_offset_s": 0.05}


def cases():
    names = ["complete", "exact_envelope_boundary", "above_envelope_boundary", "wrong_stream", "empty_mapping", "empty_calibration", "empty_state_evidence", "missing_release", "unknown_reversal", "stale_calibration", "wrong_batch_sample", "infinite_sample", "counter_reset"]
    for name in names:
        o, e, p = independent_fixture()
        expected = "MODEL_HOLD"
        if name == "complete":
            expected = "MODEL_PASS"
        elif name == "exact_envelope_boundary":
            o["samples"][1]["value"] = 880
            expected = "MODEL_PASS"
        elif name == "above_envelope_boundary":
            o["samples"][1]["value"] = 881
            expected = "MODEL_REJECT"
        elif name == "wrong_stream":
            o["source_tag"] = "REFERENCE_B"
        elif name == "empty_mapping":
            e["channel_to_stream"] = {}
        elif name == "empty_calibration":
            e["installed_calibration"] = {}
        elif name == "empty_state_evidence":
            e["archive_state_tag"] = ""
        elif name == "missing_release":
            o.pop("release")
        elif name == "unknown_reversal":
            o.pop("reversal")
        elif name == "stale_calibration":
            e["installed_calibration"]["valid_until_s"] = 999
        elif name == "wrong_batch_sample":
            o["samples"][1]["batch_id"] = "OTHER"
        elif name == "infinite_sample":
            o["samples"][0]["value"] = math.inf
        elif name == "counter_reset":
            o["counter"]["end"] = 1
        yield name, o, e, p, expected, False
    for i in range(1, 5):
        o, e, p = independent_fixture()
        o["source_tag"] = f"DD/EDR/conductivity{i}_DS"
        for sample in o["samples"]:
            sample["value"] = 0
        yield f"public_channel_{i}", o, e, p, "HOLD", True


def run():
    before = time.monotonic()
    cpu0 = resource.getrusage(resource.RUSAGE_SELF)
    spec = importlib.util.spec_from_file_location("reviewed_n1_adapter", BASE / "n1" / "adapter.py")
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    rows = []
    for name, observation, evidence, policy, expected, public in cases():
        try:
            result = candidate.adapt_public(copy.deepcopy(observation)) if public else candidate.assess(copy.deepcopy(observation), copy.deepcopy(evidence), copy.deepcopy(policy), True)
            ok = result["quality_status"] == expected and result["physical_admission"] is False
            if expected == "MODEL_PASS":
                ok = ok and result["qualified_volume_l"] == 10 and result["physical_stream"] == "diluate_outlet"
            else:
                ok = ok and result["qualified_volume_l"] is None
            if public:
                ok = ok and result["physical_stream"] == "UNKNOWN" and "UNKNOWN_CHANNEL_IDENTITY" in result["reasons"]
            rows.append({"case": name, "expected": expected, "actual": result["quality_status"], "pass": ok, "reasons": result["reasons"]})
        except Exception as exc:
            rows.append({"case": name, "expected": expected, "actual": "EXCEPTION", "pass": False, "exception_type": type(exc).__name__})
    manifest = json.loads((BASE / "n1" / "SOURCE_MANIFEST.json").read_text())
    required_unknown = ["channel_to_stream", "installed_calibration", "temperature_compensation", "clock_alignment", "archive_state_tag", "batch_release_rule", "batch_mixing_rule", "one_pass_quantity_route", "proxy_contract"]
    unknown_ok = all(manifest["adapter_evidence"].get(k) is None for k in required_unknown)
    rows.append({"case": "public_evidence_remains_unresolved", "pass": unknown_ok, "expected_unknown_fields": required_unknown})
    cpu1 = resource.getrusage(resource.RUSAGE_SELF)
    sources = [Path(__file__), BASE / "n1" / "adapter.py", BASE / "n1" / "SOURCE_MANIFEST.json", BASE / "n1" / "CONTRACT.json"]
    return {
        "reviewer": "independent_scientist", "scope": "INDEPENDENT_AUTHORED_IMPLEMENTATION_CONTROLS_AND_DIRECT_PROVENANCE_REVIEW",
        "independence": "Reference fixtures and expected decisions authored separately; candidate mapping is invoked but never supplies reference labels. See N1_PROVENANCE_REVIEW.md for direct source inspection.",
        "registered_denominator": len(rows), "passed": sum(r["pass"] for r in rows), "failed": sum(not r["pass"] for r in rows), "cases": rows,
        "physical_admission": False, "fresh_sensor_dates": 0, "empirical_error_rate": None,
        "resource": {"wall_s": time.monotonic() - before, "process_cpu_s": cpu1.ru_utime + cpu1.ru_stime - cpu0.ru_utime - cpu0.ru_stime},
        "source_sha256": {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
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
    print(json.dumps({k: result[k] for k in ("registered_denominator", "passed", "failed", "physical_admission")}))
    raise SystemExit(0 if result["failed"] == 0 else 1)
