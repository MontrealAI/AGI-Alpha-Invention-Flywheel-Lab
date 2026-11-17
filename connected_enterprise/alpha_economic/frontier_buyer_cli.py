"""Buyer-controlled local request/acceptance CLI; no outbound network or payment.

Only a genuine customer operating their own registered signing key can choose
to issue meaningful consent. This CLI cannot establish buyer independence.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .core import atomic, digest, read, safe
from .frontier_buyer import sign_request, sign_verified_delivery


def _private_output(path):
    path = safe(path)
    if not path.parent.is_dir() or path.parent.stat().st_mode & 0o077:
        raise ValueError("BUYER_OUTPUT_DIRECTORY_MUST_BE_PRIVATE_0700")
    if path.exists():
        raise ValueError("BUYER_SIGNATURE_OUTPUT_MUST_BE_NEW")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--buyer-key-env", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    req = sub.add_parser("request")
    req.add_argument("--output", type=Path, required=True)
    acceptance = sub.add_parser("accept")
    acceptance.add_argument("--artifact", type=Path, required=True)
    acceptance.add_argument("--receipt", type=Path, required=True)
    acceptance.add_argument("--archive", type=Path, required=True)
    acceptance.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    secret = os.environ.get(args.buyer_key_env, "")
    key = secret.encode()
    if len(key) < 32:
        raise ValueError("BUYER_REGISTERED_SECRET_REQUIRED")
    c = read(args.contract)
    if args.command == "request":
        value = sign_request(c, key)
    else:
        value = sign_verified_delivery(
            c, read(args.artifact), read(args.receipt),
            safe(args.archive).read_bytes(), key)
    path = _private_output(args.output)
    atomic(path, json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    print(json.dumps({
        "kind": args.command,
        "private_output_path": str(path),
        "envelope_sha256": digest(value),
        "financial_action_performed": False,
        "buyer_independence_established_by_software": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
