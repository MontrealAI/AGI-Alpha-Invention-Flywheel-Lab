"""Ω ALPHA — append-only LOCAL invention experiment register.

Stores research evidence identity, refusals and successor links, not accounting.
A local hash chain detects inadvertent edits but NOT a hostile file owner.
No automatic promotion to commercial, production, scientific or IP status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from invent import SCHEMA, Refused, canonical, digest, require, strict_json

REGISTRY_SCHEMA = "montreal.ai/mechanism-research-register/v1"


def _record_hash(record):
    return hashlib.sha256(canonical(record)).hexdigest()


def verify_records(path):
    prior_hash = "0" * 64
    seen = set()
    rows = []
    p = Path(path)
    if not p.is_file():
        return []
    for number, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        try:
            envelope = strict_json(line)
        except (ValueError, TypeError) as exc:
            raise Refused("INVALID_REGISTRY_JSON_AT_LINE_" + str(number)) from exc
        require(type(envelope) is dict and set(envelope) == {"payload", "hash"},
                "INVALID_REGISTRY_RECORD")
        payload = envelope["payload"]
        require(type(payload) is dict and set(payload) == {
            "schema", "index", "previous_hash", "mission_id", "result_digest",
            "decision", "reported_revenue", "fresh_successor", "scope",
        }, "INVALID_REGISTRY_PAYLOAD")
        require(payload["schema"] == REGISTRY_SCHEMA, "WRONG_REGISTRY_SCHEMA")
        require(payload["index"] == number and
                payload["previous_hash"] == prior_hash, "REGISTRY_CHAIN_MISMATCH")
        require(payload["decision"] == "HOLD_NO_DEPLOY_NO_REVENUE" and
                payload["reported_revenue"] == "NOT_OBSERVED",
                "UNSUPPORTED_ECONOMIC_PROMOTION")
        require(type(payload["mission_id"]) is str and
                payload["mission_id"] not in seen, "DUPLICATE_MISSION")
        require(type(payload["result_digest"]) is str and
                len(payload["result_digest"]) == 64, "INVALID_RESULT_DIGEST")
        require(envelope["hash"] == _record_hash(payload),
                "REGISTRY_HASH_MISMATCH")
        require(payload["scope"] == "RESEARCH_ONLY", "INVALID_REGISTRY_SCOPE")
        seen.add(payload["mission_id"])
        rows.append(payload)
        prior_hash = envelope["hash"]
    return rows


def append_result(path, result):
    require(type(result) is dict and result.get("schema") == SCHEMA,
            "NOT_A_FOUNDRY_RESULT")
    require(result.get("decision") == "HOLD_NO_DEPLOY_NO_REVENUE"
            and result.get("evidence", {}).get("real_collected_revenue") == "NOT_OBSERVED",
            "RESULT_MAY_NOT_CLAIM_REVENUE")
    # Use create-only on an initially empty register, then explicit append.
    # Single local writer; do not use network drives or simultaneous writers.
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.is_symlink():
        raise Refused("REGISTRY_SYMLINK_NOT_PERMITTED")
    history = verify_records(target)
    require(result["mission_id"] not in {x["mission_id"] for x in history},
            "MISSION_ALREADY_REGISTERED")
    previous_hash = _record_hash(history[-1]) if history else "0" * 64
    # Each record stores its own payload hash, not the preceding content hash.
    # The latter is recovered from the raw envelope.
    if history:
        last_line = target.read_text(encoding="utf-8").splitlines()[-1]
        previous_hash = strict_json(last_line)["hash"]
    payload = {
        "schema": REGISTRY_SCHEMA, "index": len(history) + 1,
        "previous_hash": previous_hash, "mission_id": result["mission_id"],
        "result_digest": digest(result), "decision": result["decision"],
        "reported_revenue": "NOT_OBSERVED",
        "fresh_successor": result.get("successor_comparison", {}).get("successor_mission"),
        "scope": "RESEARCH_ONLY",
    }
    envelope = {"payload": payload, "hash": _record_hash(payload)}
    # Simpler than a database, but not safe against two simultaneous writers.
    # Single-writer host is a mandatory operational precondition.
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return envelope


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--register", required=True)
    p.add_argument("--result")
    args = p.parse_args()
    if args.result:
        result = strict_json(Path(args.result).read_text(encoding="utf-8"))
        envelope = append_result(args.register, result)
        print(json.dumps(envelope, sort_keys=True))
    else:
        print(json.dumps({"verified_local_records": len(verify_records(args.register)),
                          "commercial_claims": "NONE"}))


if __name__ == "__main__":
    main()
