"""Source preparation, comparative replay and one-pass local model observation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from . import protocol, open_trial

HERE = Path(__file__).resolve().parent
FROZEN_PACKET = "c2fc0a6370b329c85e03077d4dcd7a1aada083ea3ee1a26064facf76fcfae41f"


def read_packet():
    raw = (HERE / "missions.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_PACKET:
        raise ValueError("The registered mission packet changed")
    packet = json.loads(raw)
    for fragment in packet["source_fragments"].values():
        expected = protocol.sources()[fragment["id"]]["excerpt_sha256"]
        if protocol.digest(fragment["text"].encode()) != expected:
            raise ValueError("The acquired source differs from the registered mission input")
    return packet


def available(packet):
    rows = {protocol.record_key(x["url"]): x for x in protocol.inputs()}
    return {letter: dict(rows[frag["id"]], id=letter) for letter, frag in packet["source_fragments"].items()}


def compatible(available_sources, purpose):
    return [key for key, row in available_sources.items() if protocol.qualified(row)
            and protocol.observe(row) and protocol.relevant(row["url"], purpose)]


def payload(packet, task, targeted):
    fragments = packet["source_fragments"]
    if targeted:
        keys = compatible(available(packet), task["question"])
        if keys:
            fragments = {key: fragments[key] for key in keys}
    return {"authority": packet["authority"], "source_fragments": fragments,
            "task": task, "shape": packet["shape"],
            "instructions": "Choose an evidenced premise; propose your own design, uncertainty and test. Return only the answer object."}


def assess(packet, task, answer):
    result = {"factual_status": "missing", "decision_eligible": False, "design_fields_present": False,
              "design_scientifically_accepted": None}
    if not isinstance(answer, dict):
        return result
    sources = available(packet)
    key = answer.get("source")
    if not isinstance(key, str) or key not in sources:
        result["factual_status"] = "wrong_attribution"
        return result
    premise = {k: answer.get(k) for k in ("source", "metric", "value", "scope")}
    # The answer contract requests one positively reported quantity. The
    # unrestricted proposal protocol also supports explicit negative claims.
    result["factual_status"] = protocol.adjudicate({**premise, "polarity": "asserted"}, sources[key], task["question"])
    result["decision_eligible"] = result["factual_status"] == "supported" and answer.get("decision") == "offline_test"
    result["design_fields_present"] = all(isinstance(answer.get(k), str) and bool(answer[k].strip())
                                          for k in ("uncertainty", "action", "test"))
    return result


def bounded(packet, task):
    rows = available(packet)
    matched = compatible(rows, task["question"])
    if len(matched) != 1:
        return None
    source, = matched
    observation = protocol.observe(rows[source])
    # Factual lookup offers no invention. Its useful output is the material
    # premise and allowed action scope, with design fields intentionally empty.
    return {k: observation[k] for k in ("source", "metric", "value", "scope")} | {
        "decision": "offline_test", "uncertainty": None, "action": None, "test": None}


def replay():
    packet = read_packet()
    included = json.loads((HERE / "included.json").read_text())
    if included["packet_sha256"] != FROZEN_PACKET:
        raise ValueError("The included-agent answers refer to a different packet")
    routes = {}
    for route in ("included_direct", "targeted_retrieval", "bounded_lookup", "adaptive"):
        start = time.perf_counter()
        outcomes = []
        for task in packet["tasks"]:
            targets = compatible(available(packet), task["question"])
            if route == "included_direct":
                reply = included["answers"].get(task["id"])
                decision = "included_agent_answer"
            elif route == "targeted_retrieval":
                # Retrieval returns sources only; it cannot pass the operating decision.
                reply = None
                decision = "retrieved_without_proposal"
            else:
                reply = bounded(packet, task)
                decision = "bounded_lookup" if reply else "defer_for_research"
            outcomes.append({"mission": task["id"], "retrieved": list(packet["source_fragments"]) if route == "included_direct" else targets,
                             "route": decision, "verdict": assess(packet, task, reply)})
        routes[route] = {"cases": outcomes, "elapsed_replay_s": round(time.perf_counter() - start, 6),
                         "model_calls_in_observation": included["calls"] if route == "included_direct" else 0}
    return {"packet_sha256": FROZEN_PACKET, "routes": routes,
            "scope": "Two public premise and permitted-action decisions. Open designs are unvalidated hypotheses.",
            "historical_qwen": "Different missions and source packet; never pool denominators."}


def live(args):
    from ignition.provider import LocalProvider, ProviderUnavailable
    packet = read_packet()
    open_arm = args.mode == "open"
    provider = LocalProvider("llama-cpp", args.model, args.port, declared_sha256=args.weights_sha256,
                             output_tokens=1800 if open_arm else 400, timeout=600, schema_output=False, streaming=True)
    date = datetime.now(timezone.utc).isoformat()
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    tracked = [HERE / n for n in ("missions.json", "catalog.json", "study.py", "protocol.py")]
    if open_arm:
        tracked.extend([HERE / "open_mission.json", HERE / "open_trial.py"])
    measured = {"route": "local_qwen_" + args.mode, "packet_sha256": open_trial.PACKET if open_arm else FROZEN_PACKET,
                "git_head": head, "files": {p.name: protocol.digest(p.read_bytes()) for p in tracked},
                "model": args.model, "declared_weights_sha256": args.weights_sha256, "started": date,
                "python": platform.python_version(), "complete_cost_known": False, "cases": []}
    tasks = [{"id": "instrument-sharing"}] if open_arm else packet["tasks"]
    for task in tasks:
        prompt = open_trial.packet() if open_arm else payload(packet, task, args.mode == "targeted")
        answer = failure = None
        try:
            answer = provider.propose("public_discovery_decision", prompt)
        except ProviderUnavailable as error:
            failure = str(error)
        last = provider.receipts[-1] if provider.receipts else {}
        keep = ("status", "usage", "application_model_calls", "wall_seconds", "run_id", "request_sha256",
                "raw_response_sha256", "response_sha256", "reported_model", "error_code", "transport_mode",
                "harness_streaming_sha256", "harness_adapter_sha256", "stream_output_bytes", "stream_fragments")
        if open_arm:
            # Store only public answer fields. Never export inference traces.
            fields = prompt["shape"]["candidates"][0]
            compact_answer = None
            if isinstance(answer, dict) and isinstance(answer.get("candidates"), list):
                compact_answer = {"candidates": [{k: row[k] for k in fields if k in row}
                                                  if isinstance(row, dict) else None for row in answer["candidates"]]}
            assessment = open_trial.compare(compact_answer)
            sent = [s["source"] for s in prompt["sources"]]
        else:
            compact_answer = ({k: answer[k] for k in packet["shape"] if isinstance(answer.get(k), str)}
                              if isinstance(answer, dict) else None)
            assessment = assess(packet, task, answer)
            sent = list(prompt["source_fragments"])
        measured["cases"].append({"task": task["id"], "sent_sources": sent,
                                  "receipt": {k: last[k] for k in keep if k in last}, "failure": failure,
                                  "answer": compact_answer, "assessment": assessment})
        args.out.write_text(json.dumps(measured, indent=2, ensure_ascii=False) + "\n")
    return measured


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="cmd", required=True)
    subs.add_parser("replay")
    subs.add_parser("prepared", help="reconstruct the exact prepared open packet")
    sub = subs.add_parser("open", help="regrade a public open response")
    sub.add_argument("response", type=Path)
    subs.add_parser("inputs", help="emit public source imports for a private mission")
    run = subs.add_parser("live", help="use an already approved, local-only llama.cpp server")
    run.add_argument("--port", required=True, type=int)
    run.add_argument("--model", required=True)
    run.add_argument("--weights-sha256")
    run.add_argument("--mode", choices=("direct", "targeted", "open"), default="direct")
    run.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "prepared":
        result = open_trial.prepared_packet()
    elif args.cmd == "live":
        result = live(args)
    elif args.cmd == "open":
        open_trial.packet()
        result = open_trial.compare(json.loads(args.response.read_text()))
    else:
        result = protocol.inputs() if args.cmd == "inputs" else replay()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
