#!/usr/bin/env python3
"""Real pinned-upstream synthetic adapter smoke, not a live model certificate.

Called by trust-omega.yml after its pinned upstream checkout/build. All hashes are
computed inside one controlled CI checkout, not an independent model identity
attestation. The official example is synthetic.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PINNED_COMMITMENT = "79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_key_tree_sha(path: Path) -> str:
    if path.is_symlink():
        raise AssertionError("synthetic public key root must not be a symlink")
    entries = []
    for p in sorted(path.rglob("*")):
        if p.is_symlink():
            raise AssertionError("synthetic public key tree contains symlink")
        if p.is_file():
            entries.append([p.relative_to(path).as_posix(), sha(p)])
        elif not p.is_dir():
            raise AssertionError("synthetic public key tree contains special entry")
    if not entries:
        raise AssertionError("no public key files")
    return hashlib.sha256(
        json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def run() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: trust_omega_upstream_smoke.py UPSTREAM_FOLDER")
    root = Path(__file__).resolve().parents[1]
    upstream = Path(sys.argv[1]).resolve()
    example = upstream / "examples" / "accepted-proof"
    paths = {
        "checker_source": upstream / "integrations" / "check_proof.py",
        "verifier_binary": upstream / "bin" / "cp_verify",
        "parameter_file": example / "config" / "policy.txt",
        "scales_file": example / "config" / "KL.bin",
        "layout_file": example / "config" / "layout.txt",
    }
    if not all(p.is_file() for p in paths.values()):
        raise AssertionError("official pinned source/config or built verifier missing")

    with tempfile.TemporaryDirectory(prefix="trust-omega-synthetic-") as tmp:
        folder = Path(tmp)
        response = folder / "response"
        response.mkdir()
        shutil.copyfile(example / "example.proof", response / "proof.bin")
        shutil.copyfile(example / "example.y", response / "y.bin")
        anchor = {
            "schema": "trust-omega-anchor-v2",
            "model_label": "OFFICIAL STORED SYNTHETIC EXAMPLE: not live inference",
            "independent_source": "CI fixture checked out at pinned upstream revision; not external model attestation",
            "commitment_id": PINNED_COMMITMENT,
            "end_token_ids": [199],  # artificial fixture EOS used for a full-range check
            "policy": "exact-match",
            "allow_proof_of_work": True,  # official sample counts declared PoW; NOT production policy
            "trusted_sha256": {
                **{k: sha(v) for k, v in paths.items()},
                "public_key_tree": independent_key_tree_sha(example / "ivk"),
            },
        }
        anchor_file = folder / "anchor.json"
        anchor_file.write_text(json.dumps(anchor, sort_keys=True), encoding="utf-8")
        cmd = [
            sys.executable, str(root / "products" / "trust-omega" / "verify.py"),
            "--anchor", str(anchor_file),
            "--checker", str(paths["checker_source"]),
            "--verifier", str(paths["verifier_binary"]),
            "--response", str(response),
            "--request", str(example / "example.req"),
            "--parameter-file", str(paths["parameter_file"]),
            "--scales-file", str(paths["scales_file"]),
            "--layout-file", str(paths["layout_file"]),
            "--public-key-dir", str(example / "ivk"),
            "--prompt-tokens", "61", "--reply-tokens", "4",
            "--next-token", "199",
        ]

        def check(case: str, expected: str, expect_code: int) -> None:
            observed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=180)
            try:
                payload = json.loads(observed.stdout.strip().splitlines()[-1])
            except Exception as exc:
                raise AssertionError(f"{case}: malformed local adapter output: {observed.stdout[-900:]} {observed.stderr[-900:]}") from exc
            actual = payload.get("result")
            if (observed.returncode == 0) != (expect_code == 0) or actual != expected:
                raise AssertionError(
                    f"{case}: expected {expected}/code {expect_code}, observed "
                    f"{actual}/code {observed.returncode}: {payload.get('detail')}"
                )
            print(f"{case}: {actual} exit={observed.returncode}")

        check("authentic synthetic exact fixture", "UPSTREAM_EXACT_ACCEPTED", 0)
        cmd[-1] = "198"  # client-controlled last token differs from official y.bin=199
        check("wrong client next token", "REJECTED", 1)
        cmd[-1] = "199"
        anchor["commitment_id"] = "a" * 64
        anchor_file.write_text(json.dumps(anchor, sort_keys=True), encoding="utf-8")
        check("wrong client pinned commitment", "REJECTED", 1)
    print("PASS: full adapter+official CPU checker, client-bound exact scope and two refusals; synthetic only")


if __name__ == "__main__":
    run()
