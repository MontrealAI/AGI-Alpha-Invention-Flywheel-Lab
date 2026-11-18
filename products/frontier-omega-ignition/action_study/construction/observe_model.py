"""Measure the registered direct pinned Qwen route with existing, owned CPU assets."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
sys.path.insert(0, str(PRODUCT))
from field_trials import observe
from ignition.controller import Controller
from ignition.provider import LocalProvider
from ignition.store import Store, runtime_source
from mission import mission


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("assets", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--resume-after-transport", type=Path,
                    help="Prior retained observation with exactly one transport failure. Spend the one remaining call.")
    args = ap.parse_args()
    if args.output.exists() or not all((args.assets / f).is_file() for f in ("llama.tar.gz", "model.gguf")):
        ap.error("Provide existing pinned assets and a new output path")
    m, _ = mission()
    m["authority"]["local_model"] = True
    m["resources"] = {"execution_strategy": "direct", "direct_method": "model", "max_model_calls": 2, "max_repairs": 1}
    prior = None
    if args.resume_after_transport:
        previous_bytes = args.resume_after_transport.read_bytes()
        prior = json.loads(previous_bytes)
        if (prior["status"] != "blocked" or len(prior["calls"]) != 1
                or prior["calls"][0]["error_code"] != "PROVIDER_CONNECTION" or prior["proposed"]):
            ap.error("Previous run did not leave exactly one unconsumed call after a transport failure")
        m["resources"].update(max_model_calls=1, max_repairs=0)
    rec = {"arm": "live local direct Qwen construction", "registration_revision": "66478c6c03fa74b44240d3ba89855021b7bb4235",
           "product_runtime_sha256": runtime_source(), "hardware": observe.hardware(), "model": observe.local.MODEL_ALIAS,
           "registration_sha256": hashlib.sha256((HERE / "REGISTRATION.md").read_bytes()).hexdigest(),
           "wall_time_model_setup_and_delivery_seconds": None, "billed_amount": None}
    if prior:
        rec["previous_run_sha256"] = hashlib.sha256(previous_bytes).hexdigest()
    rec["hardware"]["threads"] = min(rec["hardware"]["threads"], 4)
    start, cpu = time.monotonic(), time.process_time() + observe.child_cpu()
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp)
        try:
            binary, weights = observe.prepare(args.assets.resolve(), wd, rec)
            with observe.server(binary, weights, wd, rec, "construction") as port:
                provider = LocalProvider("llama-cpp", rec["model"], port, observe.PINS.MODEL_SHA,
                                         output_tokens=1800, timeout=550 if prior else 200, schema_output=True)
                ctrl = Controller(Store(wd / "store"), lambda: provider)
                rid, rev = ctrl.create({"request_id": "git-clocks-live-direct", "mission": m})
                state = ctrl.advance(rid, rev)
                internal = ctrl.store.get(rid)
                result = state.get("evaluation")
                rec.update(status=state["status"], obstruction=state.get("error"), calls=provider.receipts,
                           attempts=state.get("construction_attempts", []), contract_sha256=state["contract_sha256"],
                           proposed=[{"stage": c["stage"], "response": c["response"]} for c in internal["calls"].values()],
                           acceptance_checks=len(result["cases"]) if result else 0,
                           accepted_checks=sum(c["candidate_pass"] for c in result["cases"]) if result else 0,
                           delivered_bytes=len(ctrl.deliver(rid, rev)) if state["status"] == "verified" else None)
        except (ValueError, OSError, RuntimeError) as err:
            rec["obstruction"] = str(err)
        if (wd / "server.log").is_file():
            rec["server_timing_lines"] = [line.strip() for line in (wd / "server.log").read_text(errors="replace").splitlines()
                                          if "eval time" in line or "total time =" in line][-6:]
    rec.update(wall_time_model_setup_and_delivery_seconds=round(time.monotonic()-start, 6),
               process_and_child_cpu_seconds=round(time.process_time()+observe.child_cpu()-cpu, 6))
    args.output.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(rec.get("status"), rec.get("accepted_checks"), "/", rec.get("acceptance_checks"), rec.get("obstruction"))


if __name__ == "__main__":
    main()
