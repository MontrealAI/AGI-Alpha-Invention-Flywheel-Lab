#!/usr/bin/env python3
"""TRUST Omega: fail-closed evidence adapter for FlashProve's official checker.

This code DOES NOT implement a ZK proof or extend FlashProve security guarantees.
Its output is an unsigned, replayable audit record, not a cryptographic receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

HEX_ID = re.compile(r"^[0-9a-f]{64}$")
OUTCOME = re.compile(r"^result: outcome=([a-z-]+)(?: |$)")
MAX_LOG_BYTES = 2_000_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checker_output(returncode: int, stdout: str) -> tuple[str, str]:
    """Read authoritative final lines; never treat an exit code alone as success."""
    lines = stdout.splitlines()
    if len(lines) < 2:
        return "NO_VERDICT", "checker did not return both final lines"
    match = OUTCOME.match(lines[-2])
    if not match:
        return "NO_VERDICT", "malformed checker result line"
    outcome = match.group(1)
    terminal = lines[-1]
    if (
        returncode == 0 and outcome == "verified"
        and re.search(r"(?<!\S)claim=exact-match(?:\s|$)", lines[-2])
        and terminal.startswith("check_proof: verified: ")
    ):
        return "UPSTREAM_EXACT_ACCEPTED", "upstream exact-match check accepted; verify model binding independently"
    if returncode == 0 and outcome == "within-limits" and terminal.startswith("check_proof: within limits: "):
        return "POLICY_ONLY", "clipped-gap acceptance is NOT exact model output"
    if returncode == 1 and outcome in ("rejected", "no-proof") and terminal.startswith("check_proof: rejected: "):
        return "REJECTED", "upstream checker rejected the claim"
    if returncode == 14 and outcome == "not-a-verification":
        return "NOT_A_VERIFICATION", "upstream did not perform an accepted verification"
    if returncode == 2 and outcome == "error":
        return "ERROR", "upstream checker reported an error"
    return "NO_VERDICT", "inconsistent checker exit status and terminal lines"


def read_anchor(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "trust-omega-anchor-v1":
        raise ValueError("unknown anchor schema")
    if not HEX_ID.fullmatch(str(data.get("commitment_id", ""))):
        raise ValueError("invalid, missing, or unpinned model commitment ID")
    if not isinstance(data.get("model_label"), str) or not data["model_label"].strip():
        raise ValueError("missing model label")
    if not isinstance(data.get("independent_source"), str) or not data["independent_source"].strip():
        raise ValueError("missing independently obtained source for model identification")
    if data.get("policy") != "exact-match":
        raise ValueError("v1 only accepts the exact-match policy")
    end_tokens = data.get("end_token_ids")
    if not isinstance(end_tokens, list) or not end_tokens or any(type(x) is not int or x < 0 for x in end_tokens):
        raise ValueError("explicit nonempty list of end-token IDs required")
    if type(data.get("allow_proof_of_work")) is not bool:
        raise ValueError("explicit allow_proof_of_work decision required")
    required = ("checker_source", "verifier_binary", "parameter_file", "scales_file", "layout_file")
    pins = data.get("trusted_sha256")
    if not isinstance(pins, dict) or any(not HEX_ID.fullmatch(str(pins.get(k, ""))) for k in required):
        raise ValueError("independently pinned checker, verifier and config SHA256 hashes required")
    return data


def evidence_files(args: argparse.Namespace) -> dict[str, Path]:
    files = {
        "request": args.request,
        "proof": args.response / "proof.bin",
        "response_token": args.response / "y.bin",
        "parameter_file": args.parameter_file,
        "scales_file": args.scales_file,
        "layout_file": args.layout_file,
        "checker_source": args.checker,
        "verifier_binary": args.verifier,
        "anchor": args.anchor,
    }
    for name, file in files.items():
        if not file.is_file():
            raise ValueError(f"missing {name}: {file}")
    return files


def verify(args: argparse.Namespace) -> tuple[int, dict]:
    anchor = read_anchor(args.anchor)
    if args.prompt_tokens < 1 or args.reply_tokens < 1:
        raise ValueError("positive prompt/reply token counts required (reply includes EOS)")
    if args.next_token is not None and not (0 <= args.next_token < 2 ** 32):
        raise ValueError("client next-token must be a uint32 token ID")
    files = evidence_files(args)
    hashes = {name: sha256_file(path) for name, path in files.items()}
    for key, trusted_digest in anchor["trusted_sha256"].items():
        if key not in hashes or hashes[key] != trusted_digest:
            raise ValueError(f"trusted hash mismatch for {key}: fail closed")
    # Values defining the verified claim come from the client, never from the proof sender.
    command = [
        sys.executable, "-I", str(args.checker.resolve()), str(args.response.resolve()),
        str(args.request.resolve()), "--commitment-id", anchor["commitment_id"],
        "--reply", f"{args.prompt_tokens}:{args.reply_tokens}",
        "--end-token", ",".join(map(str, sorted(set(anchor["end_token_ids"])))),
        "--policy", "exact", "--public-key-dir", str(args.public_key_dir.resolve()),
        "--parameter-file", str(args.parameter_file.resolve()),
        "--scales-file", str(args.scales_file.resolve()),
        "--layout-file", str(args.layout_file.resolve()),
        "--verifier", str(args.verifier.resolve()),
    ]
    if args.next_token is not None:
        command.extend(("--next-token", str(args.next_token)))
    if not anchor["allow_proof_of_work"]:
        command.append("--no-proof-of-work")
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=args.timeout,
            check=False, errors="replace"
        )
        out = result.stdout[-MAX_LOG_BYTES:]
        outcome, detail = parse_checker_output(result.returncode, out)
        if outcome == "POLICY_ONLY":
            outcome, detail = "NO_VERDICT", "unexpected weaker policy accepted; fail closed"
        exit_code = 0 if outcome == "UPSTREAM_EXACT_ACCEPTED" else 1
        upstream_exit = result.returncode
        stderr = result.stderr[-3000:]
    except subprocess.TimeoutExpired:
        outcome, detail, exit_code, upstream_exit, stderr = "NO_VERDICT", "checker timed out", 1, None, ""
    receipt = {
        "schema": "trust-omega-evidence-v1",
        "result": outcome,
        "detail": detail,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_label": anchor["model_label"],
        "claimed_model_binding_source": anchor["independent_source"],
        "commitment_id": anchor["commitment_id"],
        "proof_statement": "client-specified reply range exact-match accepted by upstream checker",
        "checked_token_range_requested": {
            "prompt_tokens": args.prompt_tokens, "reply_tokens": args.reply_tokens,
            "client_next_token": args.next_token,
        },
        "allow_proof_of_work": anchor["allow_proof_of_work"],
        "upstream_exit_code": upstream_exit,
        "evidence_sha256": hashes,
        "limitations": [
            "Unsigned replayable record, not cryptographically signed or externally timestamped",
            "An upstream acceptance is not independent authentication of model identity",
            "Validity depends on the FlashProve implementation and its documented limits",
            "No guarantee of natural-language correctness, model safety, or hardware use",
            "No claim about unchecked tokens or uncommitted server configuration",
            "Client must independently pin commitment, tokenize input/output and validate EOS",
        ],
        "checker_stderr_excerpt": stderr,
    }
    return exit_code, receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Strict, replayable FlashProve evidence adapter (not a prover)."
    )
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--checker", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--parameter-file", type=Path, required=True)
    parser.add_argument("--scales-file", type=Path, required=True)
    parser.add_argument("--layout-file", type=Path, required=True)
    parser.add_argument("--public-key-dir", type=Path, required=True)
    parser.add_argument("--prompt-tokens", type=int, required=True)
    parser.add_argument("--reply-tokens", type=int, required=True)
    parser.add_argument("--next-token", type=int, help="client-confirmed token after request, when full checked reply reaches request end")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.timeout <= 3600:
            raise ValueError("timeout must be 1..3600 seconds")
        code, result = verify(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        code, result = 1, {
            "schema": "trust-omega-evidence-v1", "result": "NO_VERDICT", "detail": str(exc)
        }
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
