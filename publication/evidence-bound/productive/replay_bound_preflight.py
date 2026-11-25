# SPDX-License-Identifier: Apache-2.0
"""Run real publisher metadata through the native mission evidence path."""

import argparse
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[2] / "products" / "alpha-genesis-harness"
sys.path.insert(0, str(BRIDGE))
from bridge.universal_missions import UniversalMissionService  # noqa: E402
from bridge.workflow_demo import FixtureRuntime  # noqa: E402
from bridge.workflows import digest  # noqa: E402

F16_BYTES = 2
TOKENS = 32768
SCOPE = {"scenario": "one fully dense float16 sequence", "actual_gpu_allocation": False}
PERMISSIONS = ["construct_instrument", "run_instrument"]
INPUTS = ["layers", "heads", "key_width", "value_width"]


def from_observation(name, path, record):
    metadata = record["metadata"]
    source = record["source"]
    arch = metadata["general.architecture"]
    base = f"{arch}.attention."
    values = dict(zip(INPUTS, (
        metadata[f"{arch}.block_count"], metadata[f"{base}head_count_kv"],
        metadata[f"{base}key_length"], metadata[f"{base}value_length"],
    ), strict=True))
    captured = record["timings"]["candidate"]["captures"][0]
    origin = {
        "kind": "values", "origin": "VERIFIED_EXTERNAL_SOURCE", "version": source["revision"],
        "sha256": digest(metadata), "facts": {"exact_range_digest": captured["response_sha256"]},
        "source": captured["url"], "values": metadata,
    }
    parent = f"{name}-publisher"
    local = {
        "kind": "values", "origin": "DERIVED_DATA", "version": source["revision"], "facts": SCOPE,
        "sha256": digest(values), "parents": {parent: origin["sha256"]}, "values": values,
    }
    key_bytes_per_head = TOKENS * values["key_width"] * F16_BYTES
    value_bytes_per_head = TOKENS * values["value_width"] * F16_BYTES
    independent = sum((key_bytes_per_head + value_bytes_per_head) * values["heads"] for _ in range(values["layers"]))
    assert independent == record["retention_conditions"]["dense_f16_kv_scenario_bytes"][str(TOKENS)]
    claim = {
        "id": f"{name}-dense-kv", "dataset": name, "tool": "run_instrument", "locator": ["output", "kv_bytes"],
        "version": local["version"], "dimension": "information", "unit": "byte", "requires": SCOPE,
        "required_fields": [[field] for field in INPUTS],
        "reference": {"value": str(independent), "source": "Per-tensor Python integer sum cross-checked with the captured model planning output"},
    }
    return {parent: origin, name: local}, claim, sha256(path.read_bytes()).hexdigest()


def run(root, output):
    first = HERE / "PREFLIGHT-FIRST.json"
    repeat = HERE / "PREFLIGHT-RECOVERY.json"
    cases = (("qwen", first, json.loads(first.read_bytes())),
             ("gpt-oss", repeat, json.loads(repeat.read_bytes())["cases"]["repeat"]))
    inputs, claims, source_receipts = {}, [], {}
    for name, path, record in cases:
        dataset, claim, source_receipt = from_observation(name, path, record)
        inputs.update(dataset)
        claims.append(claim)
        source_receipts[path.name] = source_receipt
    telemetry = "qwen-telemetry"
    telemetry_field = "measured_gpu_resident_bytes"
    telemetry_scope = {"actual_gpu_allocation": True}
    inputs[telemetry] = {
        "kind": "values", "origin": "OPERATOR_SUPPLIED_OBSERVATION", "version": "owner-host-measurement-v1",
        "facts": telemetry_scope, "sha256": digest({}), "values": {},
    }
    claims.append({
        "id": "qwen-measured-gpu", "dataset": telemetry, "tool": "run_instrument",
        "locator": ["output", "resident_bytes"], "unit": "byte", "dimension": "information",
        "version": inputs[telemetry]["version"], "requires": telemetry_scope, "required_fields": [[telemetry_field]],
    })
    actions = [{"tool": "construct_instrument", "name": "dense-kv.json", "spec": {
        "name": "Dense float16 KV cache planning scenario", "inputs": INPUTS,
        "outputs": {"kv_bytes": {"formula": "32768 * 2 * layers * heads * (key_width + value_width)"}},
        "conditions": "One sequence of exactly 32,768 tokens, dense float16 cache on each block.",
        "limitations": "Model loading, measured resident memory, inference throughput and GPU fit require owner-host telemetry.",
    }}, {"tool": "construct_instrument", "name": "gpu-memory.json", "spec": {
        "name": "Read observed owner-host GPU memory", "inputs": [telemetry_field],
        "outputs": {"resident_bytes": {"field": telemetry_field}},
    }}]
    for claim in claims:
        instrument = "gpu-memory.json" if claim["dataset"] == telemetry else "dense-kv.json"
        actions.append({"tool": "run_instrument", "name": instrument, "input": {"dataset": claim["dataset"]},
                        "claim": {key: claim[key] for key in ("id", "unit", "dimension")}})
    runtime = FixtureRuntime([{"summary": "Calculate each registered dense cache scenario and check telemetry availability.",
                                "actions": actions, "done": True}])
    service = UniversalMissionService(runtime, root)
    try:
        opened = service.submit({
            "ambition": "Prepare the next authorized dual-TITAN RTX comparison using exact publisher model layouts.",
            "context": "Public GGUF headers and layout. Owner-host GPU telemetry is unavailable.",
            "language": "en", "provider": "fixture", "model": "authored-layout-calculator",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=3)).isoformat(),
            "max_turns": 1, "max_actions": 5, "max_output_tokens": 1024, "tools": PERMISSIONS,
            "requirements": {"evidence": {"inputs": inputs, "claims": claims}},
        })
        view = service.step(opened["id"])
        archive = service.export(opened["id"])
    finally:
        service.close()
    reopened = UniversalMissionService(FixtureRuntime([]), root)
    try:
        restored = reopened.get(opened["id"])
        assert restored["original_ambition"] == view["original_ambition"]
        assert restored["evidence"] == view["evidence"]
    finally:
        reopened.close()
    outcomes = view["evidence"]["claims"]
    assert [(entry["status"], entry.get("value")) for entry in outcomes] == [
        ("VERIFIED", claims[0]["reference"]["value"]), ("VERIFIED", claims[1]["reference"]["value"]), ("ABSTAIN", None),
    ], outcomes
    assert outcomes[-1]["reason"] == "REQUIRED_FIELD_MISSING"
    output.write_text(json.dumps({
        "schema": "frontier/retained-model-preflight-mission/v1", "observation_receipt_sha256": source_receipts,
        "authority": "Authored local action transport against exact acquired public model metadata. No model invocation or GPU run.",
        "storage_reopened": True, "original_ambition": restored["original_ambition"],
        "mission_status": view["status"], "evidence": view["evidence"], "portable_archive": archive,
    }, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.workspace, args.output)
