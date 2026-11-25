"""Compare two real preflight acquisitions with unchanged official GGUF decoding."""

import argparse
from datetime import datetime, UTC
import json
from pathlib import Path
import resource
import subprocess
import sys
from time import perf_counter

from fetch_gguf_range import fetch, vendor_observation
from gguf_preflight import PrefixIncomplete, raw_digest, read_index, summarize


HERE = Path(__file__).resolve().parent
REGISTRATION = HERE / "REGISTRATION.json"
PREFIX = 8_000_000
MAX = 10_000_000
RECOVERY_PREFIX = 14_000_000
RECOVERY_MAX = 20_000_000
CODE = ("fetch_gguf_range.py", "gguf_preflight.py", "ordinary_gguf.mjs", "run_preflight.py")


def measured(call, *args):
    time_start, own, children = perf_counter(), resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    result = call(*args)
    cpu_ranges = (resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN))
    cpu = sum(end.ru_utime + end.ru_stime - start.ru_utime - start.ru_stime
              for start, end in zip((own, children), cpu_ranges, strict=True))
    return result, {"wall_seconds": round(perf_counter() - time_start, 6), "cpu_seconds": round(cpu, 6)}


def candidate(source, folder, initial_bytes, maximum_bytes):
    first = folder / "prefix.gguf"
    receipts = [fetch(source, 0, initial_bytes - 1, first)]
    raw = first.read_bytes()
    try:
        index = read_index(raw, source["size_bytes"])
    except PrefixIncomplete:
        last = folder / "append.gguf"
        receipts.append(fetch(source, initial_bytes, maximum_bytes - 1, last))
        raw += last.read_bytes()
        first.write_bytes(raw)
        index = read_index(raw, source["size_bytes"])
    return {"index": index, "prefix": first, "captures": receipts, "wire_body_bytes": len(raw)}


def ordinary(case, package, limit, prefix="-"):
    command = ["node", str(HERE / "ordinary_gguf.mjs"), str(package), case, str(prefix), sys.executable, str(limit)]
    result = subprocess.run(command, check=True, capture_output=True)
    return json.loads(result.stdout)


def scope_estimate(index, summary):
    metadata = index["metadata"]
    architecture = summary["architecture"]
    keys = [architecture + ".attention." + name for name in ("head_count_kv", "key_length", "value_length")]
    values = [metadata.get(key) for key in keys]
    result = {"requested_context_tokens": [4096, 32768], "observed_gpu_fit": None,
              "disposition": "AWAIT_OWNER_RUNTIME_TELEMETRY", "retention": "operator planning evidence"}
    if any(type(item) is not int or item <= 0 for item in values):
        result["dense_f16_kv_scenario_bytes"] = None
        return result
    kv_heads, key_len, value_len = values
    bpt = 2 * summary["block_count"] * kv_heads * (key_len + value_len)
    result["dense_f16_kv_scenario_bytes"] = {size: size * bpt for size in result["requested_context_tokens"]}
    result["assumptions"] = "One sequence, full dense per-layer allocation, both KV formats float16. Actual sliding-window, layout and scratch allocations may differ."
    return result


def validators(raw, index, source, receipt):
    controls = {}
    for name, data, size in (
        ("truncated_index", raw[:100], source["size_bytes"]),
        ("invalid_magic", b"xxxx" + raw[4:], source["size_bytes"]),
        ("file_size_before_data", raw, index["tensor_data_offset"] - 1),
    ):
        try:
            read_index(data, size)
        except ValueError as error:
            controls[name] = str(error)
        else:
            raise ArithmeticError(f"{name} accepted inadmissible evidence")
    wrong_digest = "0" * 64
    changed_headers = (
        "HTTP/2 302\r\n"
        f"x-repo-commit: {source['revision']}\r\n"
        f"x-linked-size: {source['size_bytes']}\r\n"
        f"x-linked-etag: \"{wrong_digest}\"\r\n\r\n"
        f"HTTP/2 206\r\ncontent-range: {receipt['content_range']}\r\n\r\n"
    )
    try:
        vendor_observation(changed_headers.encode(), source, 0, receipt["response_body_bytes"] - 1)
    except ValueError as error:
        controls["same_size_different_release_digest"] = str(error)
    else:
        raise ArithmeticError("wrong publisher linked digest accepted")
    return controls


def report_case(key, source, working, package, standard_first, initial_bytes, maximum_bytes):
    folder = working / key
    folder.mkdir()
    baseline, stock_time = (measured(ordinary, key, package, maximum_bytes) if standard_first else (None, None))
    audited, candidate_time = measured(candidate, source, folder, initial_bytes, maximum_bytes)
    if not standard_first:
        baseline, stock_time = measured(ordinary, key, package, maximum_bytes)
    coalesced, coalesced_time = measured(ordinary, key, package, maximum_bytes, audited["prefix"])
    if ("index" not in coalesced or audited["index"] != coalesced["index"]
            or ("index" in baseline and audited["index"] != baseline["index"])):
        raise ValueError("published GGUF layout disagrees with the independent official parser")
    summary = summarize(audited["index"], source["size_bytes"])
    controls = validators(audited["prefix"].read_bytes(), audited["index"], source, audited["captures"][0])
    combined = {
        "candidate": {**candidate_time, "captures": audited["captures"], "wire_body_bytes": audited["wire_body_bytes"]},
        "ordinary_stock": {**stock_time, "captures": baseline["captures"], "wire_body_bytes": baseline["wire_body_bytes"]},
        "ordinary_same_prefix": {**coalesced_time, "shared_captures": True, "additional_wire_body_bytes": 0},
    }
    if "error" in baseline:
        combined["ordinary_stock"]["error"] = baseline["error"]
    return {
        "source": source, "stock_run_first": standard_first, "verified_exact_matches": len(audited["index"]["tensors"]),
        "conforming_field_count": len(audited["index"]["metadata"]), "metadata": audited["index"]["metadata"],
        "facts": summary, "retention_conditions": scope_estimate(audited["index"], summary), "timings": combined,
        "controls_refused": controls, "full_weight_digest_independently_verified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Exact installed @huggingface/gguf dist/index.mjs")
    parser.add_argument("working", type=Path)
    parser.add_argument("--case", choices=("first", "repeat"))
    parser.add_argument("--recover-repeat", action="store_true")
    args = parser.parse_args()
    started = datetime.now(UTC).isoformat()
    args.working.mkdir(parents=True, exist_ok=False)
    raw = REGISTRATION.read_bytes()
    sources = json.loads(raw)["sources"]
    package = args.package.resolve()
    selected = ("repeat",) if args.recover_repeat else (args.case,) if args.case else tuple(sources)
    initial_bytes, maximum_bytes = (RECOVERY_PREFIX, RECOVERY_MAX) if args.recover_repeat else (PREFIX, MAX)
    observations = {}
    for name in selected:
        observations[name] = report_case(name, sources[name], args.working, package, name == "repeat",
                                         initial_bytes, maximum_bytes)
        (args.working / f"{name}-receipt.json").write_text(json.dumps(observations[name], indent=2) + "\n")
    print(json.dumps({
        "schema": "frontier/model-preflight-execution-v1", "started_at_utc": started,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": raw_digest(raw),
        "recovery_registration_sha256": raw_digest((HERE / "RECOVERY-REGISTRATION.json").read_bytes())
        if args.recover_repeat else None,
        "study_code_sha256": {name: raw_digest((HERE / name).read_bytes()) for name in CODE},
        "official_gguf_parse_bundle_sha256": raw_digest(package.read_bytes()),
        "cases": observations,
        "authority": "Anonymous original Registry and bounded linked publisher data. Local CPU parse only.",
    }, indent=2))
