"""Run the frozen paired study on checked local public weights with the installed HARNESS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import subprocess
import tempfile
import time
from datetime import datetime, timezone

from . import evaluate
from field_trials import observe as field
from ignition.provider import LocalProvider, ProviderUnavailable


def trial(port, number, route):
    source_packet = evaluate.packet(number, route == "prepared")
    provider = LocalProvider("llama-cpp", field.local.MODEL_ALIAS, port, field.PINS.MODEL_SHA,
                             output_tokens=512, streaming=True)
    answer = error = None
    try:
        answer = provider.propose("public_scientific_decision", source_packet)
    except ProviderUnavailable as exc:
        error = str(exc)
    execution = provider.receipts[-1] if provider.receipts else {}
    fields = ("request_sha256", "response_sha256", "raw_response_sha256", "reported_model",
              "usage", "status", "application_model_calls", "wall_seconds", "transport_mode",
              "harness_adapter_sha256", "harness_streaming_sha256", "error_code")
    return {"context": number, "route": route, "packet_sha256": evaluate.fingerprint(source_packet),
            "answer": answer, "answer_sha256": evaluate.fingerprint(answer), "failure": error,
            "execution": {key: execution[key] for key in fields if key in execution}}


def write(path, receipt):
    # An interrupted run retains completed observations in one atomically replaced file.
    tmp = path.with_suffix(".partial")
    tmp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def run(assets, out, threads):
    if out.exists():
        raise ValueError("Choose a fresh output path for a new observation")
    # This mode never acquires assets. Check the exact pinned cache and extract through the
    # existing verified field runner, keeping the operator's files and services separate.
    for name in ("llama.tar.gz", "model.gguf"):
        if not (assets / name).is_file():
            raise ValueError("Missing locally authorized pinned CPU assets")
    record = {"schema": "ignition/scoped-qwen-observation/1", "started_utc": datetime.now(timezone.utc).isoformat(),
              "git_head_at_launch": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=field.PRODUCT,
                                                           text=True).strip(),
              "source_hashes": dict(evaluate.PINS, **{
                  n: evaluate.sha((evaluate.HERE / n).read_bytes()) for n in ("evaluate.py", "observe.py")}),
              "model": field.local.MODEL_ALIAS, "hardware": field.hardware(), "complete_cost_known": False,
              "price": None, "cases": []}
    available = record["hardware"]["threads"]
    if threads < 1 or threads > available:
        raise ValueError(f"Choose 1 to {available} available CPU threads")
    record["hardware"]["threads"] = threads
    start = time.monotonic()
    child_start = field.child_cpu()
    self_start = time.process_time()
    with tempfile.TemporaryDirectory(prefix="ignition-discovery-") as work:
        work = Path(work)
        binary, weights = field.prepare(assets, work, record)
        with field.server(binary, weights, work, record, "research") as port:
            for number in range(1, 5):
                arms = ("direct", "prepared") if number in (1, 3) else ("prepared", "direct")
                for arm in arms:
                    record["cases"].append(trial(port, number, arm))
                    write(out, record)
    record.update(wall_seconds_including_setup=round(time.monotonic()-start, 4),
                  child_cpu_seconds=round(field.child_cpu()-child_start, 4),
                  client_cpu_seconds=round(time.process_time()-self_start, 4),
                  child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                  finished_utc=datetime.now(timezone.utc).isoformat())
    write(out, record)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--threads", required=True, type=int)
    opts = parser.parse_args()
    run(opts.assets, opts.output, opts.threads)
