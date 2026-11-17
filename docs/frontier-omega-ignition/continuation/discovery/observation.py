"""One prospective, evidence-only model exchange against an immutable IGNITION checkout."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

FROZEN = "4719005c957e53716ccd3f328688d8a9c40ee4cc"
HERE = Path(__file__).resolve().parent
SOURCES = {
    "A": {"published": "2026-09-17", "url": "https://arxiv.org/abs/2609.20804",
          "record": "Fan et al. varied context management, window budget, planning and action space across four models and 176 matched settings on two software benchmarks. Effects depended on model and context."},
    "B": {"published": "2026-10-23", "url": "https://arxiv.org/abs/2610.32131",
          "record": "Zhao, Poskitt and Lo evaluated six open-source harnesses and three lightweight coding models on the same 100 SWE-bench Verified issues under common serving and grading. For one model the harness changed aggregate resolution by as much as 44 percentage points."},
    "C": {"published": "2026-10-22", "url": "https://doi.org/10.6084/m9.figshare.34744362.v1",
          "record": "Figshare v1 provides 1,800 completed run records, issue-level outcomes, per-run token aggregates and failure labels. Reported prompt and completion tokens include repeated or cached context at full weight. Missing usage was not imputed. These are public benchmark observations."},
    "D": {"published": "2026-11-16", "url": "https://arxiv.org/abs/2611.21515",
          "record": "Srinivasan and Menzies evaluated budget-constrained agent selection and trial acquisition using 58,197 public HAL run-task rows. Estimated costs depended on accounting assumptions. Many apparent performance differences were statistically unresolved."}
}
PAYLOAD = {
    "beneficiary": "MONTREAL.AI engineering operator",
    "objective": "Which self-hosted coding systems, if any, merit a private repository maintenance pilot under a mean charged-token allowance? A pilot needs independent issue-level acceptance.",
    "authority": "Public material and offline analysis only. No private source, purchases, new model service or deployment. The actual private backlog is unknown.",
    "records": SOURCES,
    "instruction": "Propose up to five genuinely different useful opportunities. Challenge them with a further write-in alternative if you can improve the decision. Freely choose, use a conventional specialist or defer. Explain the strongest alternative, the smallest discriminating test and the costs or unknowns. Reference the supplied record IDs only for claims they support. Use succinct specific prose; supply a complete JSON object.",
    "format": {"opportunities": [{"title": "your write-in", "move": "what to do and why", "sources": ["record IDs"]}],
               "challenger": "null or another object of the same shape",
               "decision": "your decision with the reason", "incumbent": "strong existing alternative",
               "test": "smallest discriminating test", "limitations": "missing or uncertain facts"}
}


def assess(reply):
    """No automated semantic verdict. This gate checks transport shape and references only."""
    errors = []
    if not isinstance(reply, dict):
        return {"valid": False, "errors": ["Model did not return an object."]}
    opportunities = reply.get("opportunities")
    if not isinstance(opportunities, list) or len(opportunities) > 5:
        return {"valid": False, "errors": ["Missing list or more than five initial proposals."]}
    if "challenger" not in reply:
        errors.append("Missing challenger field (explicit null is allowed).")
    challenge = reply.get("challenger")
    for index, candidate in enumerate(opportunities + ([challenge] if challenge is not None else [])):
        if not isinstance(candidate, dict):
            errors.append(f"Proposal {index + 1} is not an object.")
            continue
        if not all(isinstance(candidate.get(f), str) and candidate[f].strip() for f in ("title", "move")):
            errors.append(f"Proposal {index + 1} lacks a written title or move.")
        refs = candidate.get("sources")
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) and r in SOURCES for r in refs):
            errors.append(f"Proposal {index + 1} lacks valid supplied source references.")
    for key in ("decision", "incumbent", "test", "limitations"):
        if not isinstance(reply.get(key), str) or not reply[key].strip():
            errors.append(f"Missing or empty {key}.")
    return {"valid": not errors, "initial_count": len(opportunities), "challenger_present": challenge is not None,
            "errors": errors, "semantic_verdict": "Independent source review required."}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", type=Path, required=True, help="Frozen repository checkout")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol-revision", required=True)
    args = parser.parse_args()
    root, work, output = args.product.resolve(), args.work.resolve(), args.output.resolve()
    if git(root, "rev-parse", "HEAD") != FROZEN:
        parser.error("Frozen checkout differs from registered product.")
    if git(HERE, "rev-parse", "HEAD") != args.protocol_revision or git(HERE, "status", "--porcelain", "--", "."):
        parser.error("The observation protocol differs from its checkout.")
    work.mkdir(parents=True, exist_ok=False, mode=0o700)
    if output.is_relative_to(work) or output.is_relative_to(root) or output.exists():
        parser.error("Choose a fresh external receipt path outside the temporary model directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root / "products/frontier-omega-ignition"))
    import qualify_live as frozen
    from ignition.provider import LocalProvider, transport

    start = time.monotonic()
    record = {"protocol": "ignition/opportunity-observation/1", "source_revision": FROZEN,
              "protocol_revision": args.protocol_revision, "driver_sha256": sha(Path(__file__).read_bytes()),
              "registered_sha256": sha((HERE / "REGISTRATION.md").read_bytes()),
              "started_at": datetime.now(timezone.utc).isoformat(), "model": frozen.MODEL_ALIAS,
              "model_url": frozen.pinned.MODEL_URL, "runtime_url": frozen.pinned.BINARY_URL,
              "workload": "One public text-only opportunity exchange. Model has no tools.",
              "actions_run": os.getenv("GITHUB_RUN_ID"), "actions_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
              "cash_spend": "unmeasured", "complete_cost_known": False,
              "model_calls": 0, "observation": "unavailable", "semantic_verdict": "unassessed"}
    provider = None
    try:
        if frozen.checked_source() != FROZEN:
            raise RuntimeError("Product checkout check failed")
        binary, weights = frozen.setup_model(work, record)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        threads = frozen.available_threads()
        record["threads"] = threads
        env = {"HOME": str(work), "PATH": os.defpath, "LANG": "C.UTF-8", "LD_LIBRARY_PATH": str(binary.parent),
               "NO_PROXY": "127.0.0.1"}
        cmd = [str(binary), "-m", str(weights), "--alias", frozen.MODEL_ALIAS, "--host", "127.0.0.1", "--port", str(port),
               "--ctx-size", "8192", "--threads", str(threads), "--threads-batch", str(threads), "--parallel", "1",
               "--n-gpu-layers", "0", "--seed", "6144", "--temp", "0"]

        def observe(url, headers, body=None, timeout=60):
            result = transport(url, headers, body, timeout=timeout)
            choices = result.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or {}
                # Publish only the final content from this entirely public prompt. Never include reasoning traces.
                if isinstance(message.get("content"), str):
                    record["model_text"] = message["content"]
                    record["finish_reason"] = choices[0].get("finish_reason")
            return result

        with (work / "server.log").open("wb") as log:
            server = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            try:
                frozen.wait_ready(server, port)
                # The frozen adapter allows at most 600 seconds for one HTTP request; never extend its envelope.
                remaining = frozen.runner_window()
                provider = LocalProvider("llama-cpp", frozen.MODEL_ALIAS, port, frozen.pinned.MODEL_SHA, output_tokens=2500,
                                         timeout=min(600, max(1, int(remaining))) if remaining else 600, sender=observe)
                request = provider.request("opportunity-observation", PAYLOAD)
                record["prompt_sha256"] = sha(request["prompt"].encode())
                record["request_sha256"] = request["sha256"]
                response = provider.propose("opportunity-observation", PAYLOAD)
                record["response"] = response
                record["structural_check"] = assess(response)
                record["observation"] = "structured" if record["structural_check"]["valid"] else "rejected_structure"
            finally:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        if frozen.checked_source() != FROZEN:
            raise RuntimeError("Source changed after observation")
    except (OSError, RuntimeError, ValueError, frozen.Blocked) as exc:
        record["error"] = {"type": type(exc).__name__, "message": str(exc)[:200]}
        record["observation"] = "unavailable_or_incomplete"
    finally:
        if provider is not None:
            record["exchanges"] = [{k: v for k, v in row.items() if k in frozen.PUBLIC_ROUTES} for row in provider.receipts]
            record["model_calls"] = sum(r.get("application_model_calls", 0) for r in provider.receipts)
        record["wall_seconds"] = round(time.monotonic() - start, 6)
        output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"observation": record["observation"], "model_calls": record["model_calls"],
                      "source": FROZEN, "protocol": args.protocol_revision,
                      "response": record.get("response"), "structural_check": record.get("structural_check"),
                      "error": record.get("error"), "wall_seconds": record["wall_seconds"]},
                     ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
