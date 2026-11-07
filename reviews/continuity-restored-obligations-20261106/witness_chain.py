"""Optional, read-only, *synthetic* multi-custodian continuation evidence.

This is NOT an authority to ship, spend, reserve, access a buyer, or migrate an
operating/financial account. Keys used by the demo are generated ephemerally in
memory. The independent verifier receives only role-pinned PUBLIC keys and a
caller-held latest anchor reference; no private keys are persisted or returned.

The scheme tests a missing technical means: independently attested evidence that
already-fulfilled obligations survived an ERP restoration. Neither a valid
signature nor a synthetic replay proves real shipment or custodian independence.
"""
from __future__ import annotations

import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from reference_oracle import digest, reconcile

BUNDLE_SCHEMA = "continuity-omega/witness-chain-research-v1"
RECEIPT_SCHEMA = "continuity-omega/witness-receipt-research-v1"
ANCHOR_SCHEMA = "continuity-omega/witness-anchor-research-v1"
ROLES = ("ERP", "FULFILLMENT", "AUDITOR")
ZERO = "0" * 64


class WitnessRefused(ValueError):
    pass


def _valid_id(value):
    return type(value) is str and 0 < len(value) <= 64 and all(
        c.isascii() and (c.isupper() or c.isdigit() or c in "._-") for c in value
    )


def _raw_public(key):
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _signed(key, obj):
    return key.sign(_encode(obj)).hex()


def _encode(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def _public_keys(keys):
    if type(keys) is not dict or set(keys) != set(ROLES):
        raise WitnessRefused("PINNED_ROLE_KEYS_REQUIRED")
    public = {}
    seen = set()
    for role in ROLES:
        value = keys[role]
        if type(value) is not bytes or len(value) != 32:
            raise WitnessRefused("PINNED_KEY_INVALID")
        if value in seen:
            raise WitnessRefused("INDEPENDENT_ROLE_KEYS_REQUIRED")
        seen.add(value)
        try:
            public[role] = Ed25519PublicKey.from_public_bytes(value)
        except (ValueError, TypeError) as exc:
            raise WitnessRefused("PINNED_KEY_INVALID") from exc
    return public


def _check_signature(public, obj, signature, label):
    if type(signature) is not str or len(signature) != 128 or any(
            c not in "0123456789abcdef" for c in signature):
        raise WitnessRefused(label)
    try:
        public.verify(bytes.fromhex(signature), _encode(obj))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise WitnessRefused(label) from exc


def make_demo_bundle(events, snapshot, case_id, private_keys):
    """Synthetic test fixture creation only. Never serialize or publish the keys.

    The caller, NOT this helper, independently preserves the latest anchor hash.
    This models independent custodians only when the three keys truly are held
    by distinct parties; the tests use generated local ephemeral key material.
    """
    if not _valid_id(case_id):
        raise WitnessRefused("CASE_ID_INVALID")
    if type(private_keys) is not dict or set(private_keys) != set(ROLES) or any(
            not isinstance(private_keys[r], Ed25519PrivateKey) for r in ROLES):
        raise WitnessRefused("DEMO_PRIVATE_KEYS_INVALID")
    public_bytes = [_raw_public(private_keys[r].public_key()) for r in ROLES]
    if len(set(public_bytes)) != 3:
        raise WitnessRefused("INDEPENDENT_ROLE_KEYS_REQUIRED")
    if type(events) is not list or not events:
        raise WitnessRefused("SOURCE_EVENTS_INVALID")
    # Neither this fixture helper nor its signer is an independent replay oracle.
    prev = ZERO
    receipts = []
    for index, event in enumerate(events, 1):
        if type(event) is not dict or type(event.get("sequence")) is not int or event["sequence"] != index:
            raise WitnessRefused("SOURCE_SEQUENCE_INVALID")
        body = {"schema": RECEIPT_SCHEMA, "case_id": case_id, "sequence": index,
                "source_event_sha256": digest(event), "previous_receipt_sha256": prev}
        signers = ("ERP", "FULFILLMENT") if event.get("type") == "FULFILL" else ("ERP",)
        receipt = {"body": body, "signatures": {
            role: _signed(private_keys[role], body) for role in signers}}
        receipts.append(receipt)
        prev = digest(receipt)
    anchor_body = {"schema": ANCHOR_SCHEMA, "case_id": case_id,
                   "last_sequence": len(events), "head_receipt_sha256": prev,
                   "source_events_sha256": digest(events), "restored_snapshot_sha256": digest(snapshot)}
    return {"schema": BUNDLE_SCHEMA, "case_id": case_id, "receipts": receipts,
            "anchor": {"body": anchor_body,
                       "signature": _signed(private_keys["AUDITOR"], anchor_body)}}


def verify(events, snapshot, bundle, *, pinned_public_keys,
           expected_latest_anchor_sha256, expected_min_sequence):
    """Fail closed on forged, stale, forked or incomplete *synthetic* evidence.

    Both caller-held latest anchor SHA256 and minimum counter are mandatory and
    must be supplied outside the received payload. Neither proves true custody.
    """
    report = {"schema": "continuity-omega/witness-review-result-v1",
              "verdict": "FAIL", "scope": "SIMULATED_SIGNERS_NO_REAL_AUTHORITY",
              "reason": None, "replay_verdict": None, "latest_anchor_sha256": None,
              "real_delivery": False, "financial_authority": False,
              "buyer_acceptance": False}
    try:
        _verify(events, snapshot, bundle, pinned_public_keys,
                expected_latest_anchor_sha256, expected_min_sequence, report)
        report["verdict"] = "VERIFIED_SYNTHETIC_CUSTODY_ONLY"
    except (WitnessRefused, ValueError, TypeError, RecursionError, OverflowError) as exc:
        report["reason"] = str(exc) if isinstance(exc, WitnessRefused) else "INVALID_EVIDENCE"
    return report


def _verify(events, snapshot, bundle, pinned, expected_hash, min_sequence, report):
    keys = _public_keys(pinned)
    if type(expected_hash) is not str or len(expected_hash) != 64 or any(
            c not in "0123456789abcdef" for c in expected_hash):
        raise WitnessRefused("EXTERNAL_LATEST_ANCHOR_REQUIRED")
    if type(min_sequence) is not int or min_sequence <= 0:
        raise WitnessRefused("EXTERNAL_MIN_SEQUENCE_REQUIRED")
    if type(bundle) is not dict or set(bundle) != {"schema", "case_id", "receipts", "anchor"} or bundle["schema"] != BUNDLE_SCHEMA:
        raise WitnessRefused("BUNDLE_SCHEMA_INVALID")
    case_id = bundle["case_id"]
    if not _valid_id(case_id):
        raise WitnessRefused("CASE_ID_INVALID")
    receipts = bundle["receipts"]
    if type(events) is not list or type(receipts) is not list or len(events) != len(receipts) or not 1 <= len(receipts) <= 20000:
        raise WitnessRefused("CHAIN_LENGTH_OR_SOURCE_INVALID")
    prev = ZERO
    for i, (event, receipt) in enumerate(zip(events, receipts), 1):
        if type(event) is not dict or type(event.get("sequence")) is not int or event["sequence"] != i:
            raise WitnessRefused("EVENT_SEQUENCE_INVALID")
        if type(receipt) is not dict or set(receipt) != {"body", "signatures"}:
            raise WitnessRefused("RECEIPT_SHAPE_INVALID")
        body = receipt["body"]
        expected_body = {"schema": RECEIPT_SCHEMA, "case_id": case_id,
                         "sequence": i, "source_event_sha256": digest(event),
                         "previous_receipt_sha256": prev}
        if type(body) is not dict or _encode(body) != _encode(expected_body):
            raise WitnessRefused("CHAIN_EVENT_OR_PREDECESSOR_CHANGED")
        signatures = receipt["signatures"]
        expected_roles = {"ERP", "FULFILLMENT"} if event.get("type") == "FULFILL" else {"ERP"}
        if type(signatures) is not dict or set(signatures) != expected_roles:
            raise WitnessRefused("RECEIPT_MISSING_INDEPENDENT_FULFILLMENT_WITNESS")
        for role in sorted(expected_roles):
            _check_signature(keys[role], body, signatures[role], "WITNESS_SIGNATURE_INVALID")
        prev = digest(receipt)
    anchor = bundle["anchor"]
    if type(anchor) is not dict or set(anchor) != {"body", "signature"}:
        raise WitnessRefused("ANCHOR_SHAPE_INVALID")
    body = anchor["body"]
    expected_body = {"schema": ANCHOR_SCHEMA, "case_id": case_id,
                     "last_sequence": len(events), "head_receipt_sha256": prev,
                     "source_events_sha256": digest(events),
                     "restored_snapshot_sha256": digest(snapshot)}
    if type(body) is not dict or _encode(body) != _encode(expected_body):
        raise WitnessRefused("ANCHOR_SOURCE_OR_SNAPSHOT_CHANGED")
    _check_signature(keys["AUDITOR"], body, anchor["signature"], "ANCHOR_SIGNATURE_INVALID")
    anchor_hash = digest(anchor)
    report["latest_anchor_sha256"] = anchor_hash
    if anchor_hash != expected_hash:
        raise WitnessRefused("EXTERNAL_LATEST_ANCHOR_MISMATCH")
    if body["last_sequence"] < min_sequence:
        raise WitnessRefused("EXTERNAL_MONOTONIC_COUNTER_REGRESSION")
    replay = reconcile(events, snapshot, expected_source_sha256=body["source_events_sha256"],
                       expected_restored_sha256=body["restored_snapshot_sha256"])
    report["replay_verdict"] = replay["verdict"]
    if replay["verdict"] != "RECONCILED_SYNTHETIC":
        raise WitnessRefused("INDEPENDENT_REPLAY_OR_RESTORATION_DISCREPANCY")
