"""Offline, synthetic recovery-evidence falsifier. No network, keys, or account writes.

The operator supplies a buyer-pinned, pre-incident SHA-256 of an independently
held event tape. This program does NOT establish that the tape was honest,
independently retained, or externally anchored. It is not native accounting.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "agi-alpha/continuity-omega/recovery-proof/v1"
ORDER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def canonical(value: Any) -> bytes:
    """Canonical input encoding for this finite JSON grammar (no floats)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def replay(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Independently derive obligations; never silently discard a queued order."""
    require(type(events) is list and bool(events), "MISSING_EVENTS")
    state: dict[str, dict[str, Any]] = {}
    for i, e in enumerate(events, 1):
        require(type(e) is dict and set(e) in ({"seq", "kind", "order", "cents"}, {"seq", "kind", "order"}), "INVALID_EVENT_FIELDS")
        require(type(e["seq"]) is int and e["seq"] == i, "EVENT_SEQUENCE_GAP_OR_REPLAY")
        name, kind = e["order"], e["kind"]
        require(type(name) is str and bool(ORDER.fullmatch(name)), "INVALID_ORDER_ID")
        require(type(kind) is str and kind in ("commit", "deliver", "refund"), "INVALID_EVENT_KIND")
        if kind == "commit":
            require(set(e) == {"seq", "kind", "order", "cents"}, "COMMIT_NEEDS_AMOUNT")
            require(type(e["cents"]) is int and 0 < e["cents"] < 10**12, "INVALID_AMOUNT")
            require(name not in state, "DUPLICATE_ORDER")
            state[name] = {"cents": e["cents"], "status": "pending"}
        else:
            require(set(e) == {"seq", "kind", "order"}, "UNEXPECTED_AMOUNT")
            require(name in state and state[name]["status"] == "pending", "INVALID_TERMINAL_TRANSITION")
            state[name]["status"] = "delivered" if kind == "deliver" else "refunded"
    return state


def check_restore(events: list[dict[str, Any]], restored: dict[str, Any], pinned_anchor: str, measured_seconds: int, rto_seconds: int) -> list[str]:
    failures: list[str] = []
    if type(pinned_anchor) is not str or not re.fullmatch(r"[0-9a-f]{64}", pinned_anchor):
        failures.append("MISSING_EXTERNAL_ANCHOR")
    elif digest(events) != pinned_anchor:
        failures.append("EVENT_TAPE_ANCHOR_MISMATCH")
    try:
        expected = replay(events)
    except (TypeError, ValueError, KeyError) as exc:
        failures.append("EVENT_REPLAY_INVALID:" + str(exc))
    else:
        if type(restored) is not dict or restored != expected:
            failures.append("RESTORED_OBLIGATIONS_DIFFER")
    if type(measured_seconds) is not int or measured_seconds < 0:
        failures.append("INVALID_DURATION")
    if type(rto_seconds) is not int or rto_seconds < 0:
        failures.append("INVALID_RTO")
    elif type(measured_seconds) is int and measured_seconds > rto_seconds:
        failures.append("RTO_EXCEEDED")
    return failures


def make_proof(events: list[dict[str, Any]], restored: dict[str, Any], pinned_anchor: str, measured_seconds: int, rto_seconds: int) -> dict[str, Any]:
    failures = check_restore(events, restored, pinned_anchor, measured_seconds, rto_seconds)
    return {
        "schema": SCHEMA,
        "evidence_role": "SYNTHETIC_OFFLINE_ENGINEERING_ONLY",
        "accepted": not failures,
        "failures": failures,
        "event_tape_sha256": digest(events),
        "recovered_state_sha256": digest(restored),
        "pinned_external_anchor": pinned_anchor,
        "simulated_duration_seconds": measured_seconds,
        "registered_rto_seconds": rto_seconds,
        "anchoring_or_independence_observed": False,
        "real_buyer_evidence": False,
        "native_financial_activity": False,
    }


def verify_proof(proof: dict[str, Any], events: list[dict[str, Any]], restored: dict[str, Any], pinned_anchor: str, measured_seconds: int, rto_seconds: int) -> bool:
    """Reject a forged, partial, or stale proof; recompute each field."""
    return type(proof) is dict and proof == make_proof(events, restored, pinned_anchor, measured_seconds, rto_seconds)


def benchmark() -> dict[str, Any]:
    """Predeclared 4 fixtures. No probability, price, customer or paid contract."""
    tape = [
        {"seq": 1, "kind": "commit", "order": "A", "cents": 12000},
        {"seq": 2, "kind": "commit", "order": "B", "cents": 3500},
        {"seq": 3, "kind": "deliver", "order": "A"},
    ]
    snapshot = replay(tape)
    fixtures = [
        ("healthy", tape, snapshot, digest(tape), 60, True),
        ("lost_pending_liability", tape, {"A": snapshot["A"]}, digest(tape), 60, False),
        ("stale_recovery", tape, snapshot, digest(tape), 121, False),
        ("tampered_tape", tape[:-1], snapshot, digest(tape), 60, False),
    ]
    rows = []
    for name, actual_tape, recovered, anchor, duration, expected in fixtures:
        proof = make_proof(actual_tape, recovered, anchor, duration, 120)
        # Competent ordinary route gets the identical externally retained
        # event tape, replay rules, and anchor; it is NOT a health-only straw man.
        conventional = not check_restore(actual_tape, recovered, anchor, duration, 120)
        # Weak health-only control disclosed, never called a competent incumbent.
        health_only = type(recovered) is dict and bool(recovered)
        rows.append({"case": name, "registered_expected": expected,
                     "proof_accepted": proof["accepted"], "conventional_accepted": conventional,
                     "health_only_accepted": health_only,
                     "independent_verification": verify_proof(proof, actual_tape, recovered, anchor, duration, 120),
                     "failures": proof["failures"]})
    return {
        "schema": "agi-alpha/continuity-omega/finite-benchmark/v1",
        "cases": rows,
        "case_count": len(rows),
        "all_registered_verdicts_match": all(r["proof_accepted"] == r["registered_expected"] for r in rows),
        "competent_conventional_tie": all(r["proof_accepted"] == r["conventional_accepted"] for r in rows),
        "portable_proof_advantage_over_strong_control_established": False,
        "customer_acceptance_or_actual_commerce": False,
        "commercial_status": "HOLD_NO_OBSERVED_WILLINGNESS_TO_PAY_OR_COMPLETE_COSTS",
        "recommended_action": "NO_DEPLOY; investigate a useful portability/coordination residual before native funding",
    }


if __name__ == "__main__":
    print(json.dumps(benchmark(), indent=2, sort_keys=True))
