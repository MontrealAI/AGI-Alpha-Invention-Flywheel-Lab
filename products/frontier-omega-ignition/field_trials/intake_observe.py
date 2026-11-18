"""Run the registered public intake comparison on an owned local CPU."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

import observe

FIELD = observe.FIELD
WORKLOAD = FIELD / "intake_workload.json"
FROZEN = "e99cf0ae927510164ce7a52307fe02a6f04e27e2fd2b0430ef0eccf744ebcd46"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", required=True, type=Path, help="Already verified public archive and model cache")
    ap.add_argument("--work", required=True, type=Path, help="New private scratch directory")
    ap.add_argument("--output", required=True, type=Path, help="New directory for the registered public recording")
    ap.add_argument("--threads", type=int, default=4)
    opt = ap.parse_args()
    if not 1 <= opt.threads <= observe.hardware()["threads"]:
        ap.error("Thread count must fit the available CPU allocation.")
    if observe.PINS.sha(WORKLOAD) != FROZEN:
        ap.error("The approved public workload differs.")
    if not all((opt.assets / name).is_file() for name in ("model.gguf", "llama.tar.gz")):
        ap.error("The two pinned public assets must already exist in the approved local cache.")
    work, output = opt.work.resolve(), opt.output.resolve()
    work.mkdir(mode=0o700, parents=True)
    output.mkdir(mode=0o700, parents=True)
    start = time.monotonic()
    cpu = time.process_time() + observe.child_cpu()
    files = [WORKLOAD, FIELD / "INTAKE_REGISTRATION.md", Path(__file__).resolve(), Path(observe.__file__),
             observe.PRODUCT / "qualify_live.py", *(FIELD / name for name in
             ("capture.py", "field.py", "verify.py", "fixture_server.py", "protocol.py", "REGISTRATION.md"))]
    hardware = observe.hardware()
    hardware["threads"] = opt.threads
    rec = {"schema": 1, "executed": False, "hosting": "local shared engineering CPU", "started_utc": observe.now(),
           "hardware": hardware, "registered_workload_sha256": FROZEN, "model": observe.local.MODEL_ALIAS,
           "revision_at_launch": observe.local.git("rev-parse", "HEAD"),
           "source_sha256": {p.relative_to(observe.PRODUCT).as_posix(): observe.PINS.sha(p) for p in files},
           "scope": "12 public authored briefs, once at concurrency 1", "observed_supplier_price": None}
    trace = work / "field.json"
    try:
        binary, weights = observe.prepare(opt.assets.resolve(), work, rec)
        with observe.server(binary, weights, work, rec, "intake") as port:
            permit = work / "permit.json"
            observe.write(permit, {
                "schema": 1, "scope": "authorized-workload-pilot", "target": "qwen-public-intake",
                "base_url": f"http://127.0.0.1:{port}", "model": rec["model"],
                "model_sha256": rec["assets"]["weights_sha256"], "runtime_sha256": rec["assets"]["server_sha256"],
                "hardware": f'{hardware["processor"]}, {opt.threads} threads',
                "configuration": " ".join(rec["serving_configuration"]), "workload_sha256": FROZEN,
                "max_concurrency": 1, "max_attempts": 12,
                "tokenizer": "llama.cpp-/tokenize-add_special=false-parse_special=false",
                "locally_owned_no_forwarding": True,
            })
            measure = ["field_lab/field.py", "run", "--route", "field", "--workload", WORKLOAD,
                       "--authority", permit, "--output", trace]
            verify = ["field_lab/verify.py", "--workload", WORKLOAD, "--receipt", trace]
            for name, command in (("measure", measure), ("wire_sql", verify),
                                  ("native_retokenization", [*verify, "--retokenize-authority", permit])):
                phase = time.monotonic()
                code = observe.run_child(command, work / (name + ".log"))
                rec[name] = {"exit_code": code, "wall_seconds": round(time.monotonic() - phase, 6)}
                if code:
                    raise RuntimeError(f"{name} exited with status {code}")
        data = trace.read_bytes()
        rec["receipt_sha256"] = hashlib.sha256(data).hexdigest()
        (output / "wire.json.gz").write_bytes(gzip.compress(data, mtime=0))
        rec["executed"] = True
    finally:
        rec["wall_seconds"] = round(time.monotonic() - start, 6)
        rec["cpu_seconds_including_children"] = round(time.process_time() + observe.child_cpu() - cpu, 6)
        observe.write(output / "operation.json", rec)
    print(json.dumps({"executed": rec["executed"], "wall_seconds": rec["wall_seconds"]}))


if __name__ == "__main__":
    main()
