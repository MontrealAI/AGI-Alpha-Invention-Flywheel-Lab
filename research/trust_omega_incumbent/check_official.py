"""Independently exercise a pinned upstream verifier as TRUST Ω's strongest stock control.

This tests source-matched synthetic examples, NOT a served-model claim or proof soundness.
No network, private credentials, financial state or production operation is used here.
The workflow obtains a fixed public upstream Git checkout separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

UPSTREAM = "9e2bdd8ff5bf9c62f18263d7dac189b0400b260c"
EXPECTED_ID = "79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183"
FILES = (
    "LICENSE",
    "verifier/build.sh",
    "integrations/check_proof.py",
    "examples/accepted-proof/ID.txt",
    "examples/accepted-proof/example.req",
    "examples/accepted-proof/example.y",
    "examples/accepted-proof/example.proof",
    "examples/accepted-proof/config/policy.txt",
    "examples/accepted-proof/config/KL.bin",
    "examples/accepted-proof/ivk/key.bin",
    "examples/accepted-proof/ivk/leaf/0.bin",
    "examples/rejected-proofs/altered_copies.tsv",
    "examples/rejected-proofs/try_altered_copies.py",
)

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elapsed_usage(before: resource.struct_rusage) -> dict[str, float]:
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "children_user_cpu_seconds": round(after.ru_utime - before.ru_utime, 6),
        "children_system_cpu_seconds": round(after.ru_stime - before.ru_stime, 6),
    }


def invoke(root: Path, output: Path, label: str, args: list[str]) -> dict:
    """Record every attempt, including nonzero exits and unexpected outputs."""
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    item = {"label": label, "argv": args, "returncode": None}
    try:
        p = subprocess.run(args, cwd=root, capture_output=True, text=True, errors="replace")
        item["returncode"] = p.returncode
        (output / (label + ".stdout")).write_text(p.stdout)
        (output / (label + ".stderr")).write_text(p.stderr)
        lines = [s.strip() for s in p.stdout.splitlines() if s.strip()]
        item["last_stdout_line"] = lines[-1] if lines else None
        item["stdout_sha256"] = digest(output / (label + ".stdout"))
        item["stderr_sha256"] = digest(output / (label + ".stderr"))
    except BaseException as exc:
        item["exception_type"] = type(exc).__name__
        item["exception_message"] = str(exc)[:2000]
    item["wall_seconds"] = round(time.monotonic() - start, 6)
    item.update(elapsed_usage(before))
    return item


def run(root: Path, output: Path) -> int:
    if os.geteuid() == 0:
        raise ValueError("UPSTREAM_REQUIRES_UNPRIVILEGED_RUNNER")
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("REGULAR_EXISTING_ABSOLUTE_SOURCE_REQUIRED")
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError("NEW_ABSOLUTE_EVIDENCE_DIRECTORY_REQUIRED")
    output.mkdir(parents=True)
    proof = {
        "schema": "trust-omega/stock-incumbent-proof-check/v1",
        "original_protocol": "research/trust_omega_incumbent/PROTOCOL.md",
        "upstream_repo": "https://github.com/anthropics/FlashProve",
        "pinned_git_commit": UPSTREAM,
        "scope": "PINNED_PUBLIC_SYNTHETIC_PROOF_EXAMPLE_ONLY",
        "verifier_is_proved_cryptographically": False,
        "real_served_model_verified": False,
        "buyer_demand_observed": False,
        "new_revenue_microUSD": 0,
        "new_spending_authorized": False,
        "tests": [],
        "accepted": False,
        "decision": "NO_DEPLOY",
    }
    outcome = 1
    try:
        rev = invoke(root, output, "git-revision", ["git", "rev-parse", "HEAD"])
        proof["tests"].append(rev)
        if rev["returncode"] != 0 or rev["last_stdout_line"] != UPSTREAM:
            raise ValueError("PINNED_UPSTREAM_COMMIT_MISMATCH")
        if (root / "examples/accepted-proof/ID.txt").read_text().strip() != EXPECTED_ID:
            raise ValueError("FIXTURE_COMMITMENT_ID_MISMATCH")
        source = {}
        for name in FILES:
            p = root / name
            if not p.is_file() or p.is_symlink():
                raise ValueError("REQUIRED_UPSTREAM_FILE_MISSING_OR_SYMLINK:" + name)
            source[name] = digest(p)
        proof["upstream_input_sha256"] = source
        build = invoke(root, output, "build", ["bash", "verifier/build.sh"])
        proof["tests"].append(build)
        if build["returncode"] != 0:
            raise ValueError("UNMODIFIED_UPSTREAM_VERIFIER_BUILD_FAILED")
        if not (root / "bin/cp_verify").is_file():
            raise ValueError("BUILT_VERIFIER_NOT_FOUND")
        proof["verifier_binary_sha256"] = digest(root / "bin/cp_verify")
        positive = invoke(root, output, "accepted-original-client", [
            sys.executable, "integrations/check_proof.py",
            "examples/accepted-proof/example.proof",
            "examples/accepted-proof/example.req",
            "--public-key-dir", "examples/accepted-proof/ivk",
            "--parameter-file", "examples/accepted-proof/config/policy.txt",
            "--scales-file", "examples/accepted-proof/config/KL.bin",
            "--commitment-id", EXPECTED_ID,
            "--range", "60:64", "--next-token", "199", "--end-token", "none",
        ])
        proof["tests"].append(positive)
        if positive["returncode"] != 0 or not (positive.get("last_stdout_line") or "").startswith(
            "check_proof: verified: exact match:"
        ):
            raise ValueError("ORIGINAL_CLIENT_NOT_ACCEPTED")
        negative = invoke(root, output, "ten-original-negative-controls", [
            sys.executable, "examples/rejected-proofs/try_altered_copies.py",
            "bin/cp_verify", str(output / "altered-copies"),
        ])
        proof["tests"].append(negative)
        if negative["returncode"] != 0 or "10 altered sets: all rejected" not in (
            output / "ten-original-negative-controls.stdout"
        ).read_text():
            raise ValueError("ORIGINAL_NEGATIVE_INTERVENTION_SUITE_FAILED")
        proof["accepted"] = True
        proof["decision"] = "ESTABLISHED_ORDINARY_TECHNICAL_ROUTE; NO_DEPLOY"
        outcome = 0
    except BaseException as exc:
        proof["failure"] = {
            "type": type(exc).__name__,
            "detail": str(exc)[:2000],
        }
        proof["decision"] = "UNRESOLVED_OR_FAILED_CONTROL; NO_DEPLOY"
    finally:
        (output / "RESULT.json").write_text(
            json.dumps(proof, sort_keys=True, indent=2) + "\n"
        )
    return outcome


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    raise SystemExit(run(a.upstream.resolve(), a.output))


if __name__ == "__main__":
    main()
