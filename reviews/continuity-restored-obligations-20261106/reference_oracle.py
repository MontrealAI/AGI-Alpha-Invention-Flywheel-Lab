"""Independent, synthetic-only reference oracle for outstanding obligation recovery.

This is a research review instrument, NOT the CONTINUITY Omega constructor or a
replacement verifier, an authorized customer record, a signed ledger or a live
recovery system. Caller-held source AND snapshot pins are essential to a
meaningful conditional reconciliation. Neither pin establishes legal custody.
"""
from __future__ import annotations

import hashlib
import json

SOURCE_SCHEMA = "continuity-omega/restored-active-v2"
EVENT_BASE = {"sequence", "type", "order_id"}
ROW_FIELDS = {"order_id", "gross_quantity", "fulfilled_quantity", "source_event_sequences"}
ACCEPT_FIELDS = EVENT_BASE | {"quantity", "product", "spec_sha256", "deadline_hours"}
QUANTITY_FIELDS = EVENT_BASE | {"quantity"}


class InvalidEvidence(ValueError):
    """Malformed, unsupported, or internally inconsistent synthetic evidence."""


def digest(value):
    """Exact canonical JSON identity, not authentication."""
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _positive(value, label):
    if type(value) is not int or value <= 0:
        raise InvalidEvidence(label)
    return value


def _identifier(value, label):
    if type(value) is not str or not value or len(value) > 64 or not all(
        ch.isascii() and (ch.isupper() or ch.isdigit() or ch in "._-")
        for ch in value
    ):
        raise InvalidEvidence(label)
    return value


def replay(events):
    """Replay the actual input events once; the restored snapshot is never trusted."""
    if type(events) is not list or not events or len(events) > 20000:
        raise InvalidEvidence("SOURCE_EVENTS_INVALID")
    orders = {}
    for index, event in enumerate(events, 1):
        if type(event) is not dict or set(event) not in (
            ACCEPT_FIELDS, QUANTITY_FIELDS, EVENT_BASE
        ):
            raise InvalidEvidence("SOURCE_EVENT_SHAPE_INVALID")
        if type(event.get("sequence")) is not int or event["sequence"] != index:
            raise InvalidEvidence("SOURCE_SEQUENCE_CHANGED")
        kind = event.get("type")
        required = (ACCEPT_FIELDS if kind == "ACCEPT" else
                    QUANTITY_FIELDS if kind in ("AMEND", "FULFILL") else
                    EVENT_BASE if kind == "CANCEL" else None)
        if required is None or set(event) != required:
            raise InvalidEvidence("SOURCE_EVENT_KIND_FIELDS_INVALID")
        oid = _identifier(event["order_id"], "SOURCE_ORDER_ID_INVALID")
        if kind == "ACCEPT":
            if oid in orders:
                raise InvalidEvidence("SOURCE_DUPLICATE_ACCEPT")
            _identifier(event["product"], "SOURCE_PRODUCT_INVALID")
            spec = event["spec_sha256"]
            if (type(spec) is not str or len(spec) != 64
                    or any(c not in "0123456789abcdef" for c in spec)):
                raise InvalidEvidence("SOURCE_SPEC_DIGEST_INVALID")
            orders[oid] = {
                "gross_quantity": _positive(event["quantity"], "SOURCE_QUANTITY_INVALID"),
                "fulfilled_quantity": 0,
                "status": "ACTIVE",
                "source_event_sequences": [index],
            }
            _positive(event["deadline_hours"], "SOURCE_DEADLINE_INVALID")
            continue
        if oid not in orders or orders[oid]["status"] != "ACTIVE":
            raise InvalidEvidence("SOURCE_INACTIVE_TARGET")
        row = orders[oid]
        row["source_event_sequences"].append(index)
        if kind == "AMEND":
            quantity = _positive(event["quantity"], "SOURCE_QUANTITY_INVALID")
            if quantity < row["fulfilled_quantity"]:
                raise InvalidEvidence("SOURCE_AMEND_ERASES_FULFILLED")
            row["gross_quantity"] = quantity
        elif kind == "FULFILL":
            quantity = _positive(event["quantity"], "SOURCE_FULFILL_INVALID")
            if row["fulfilled_quantity"] + quantity > row["gross_quantity"]:
                raise InvalidEvidence("SOURCE_OVERFULFILL")
            row["fulfilled_quantity"] += quantity
        else:
            row["status"] = "CANCELLED"
    return orders


def _validated_snapshot(snapshot):
    if type(snapshot) is not dict or set(snapshot) != {
        "schema", "source_events_sha256", "records"
    } or snapshot["schema"] != SOURCE_SCHEMA:
        raise InvalidEvidence("RESTORED_SCHEMA_V2_REQUIRED")
    if type(snapshot["source_events_sha256"]) is not str:
        raise InvalidEvidence("RESTORED_SOURCE_DIGEST_INVALID")
    records = snapshot["records"]
    if type(records) is not list or len(records) > 20000:
        raise InvalidEvidence("RESTORED_RECORDS_INVALID")
    result = {}
    for row in records:
        if type(row) is not dict or set(row) != ROW_FIELDS:
            raise InvalidEvidence("RESTORED_ROW_SHAPE_INVALID")
        oid = _identifier(row["order_id"], "RESTORED_ORDER_ID_INVALID")
        if oid in result:
            raise InvalidEvidence("RESTORED_DUPLICATE_ORDER")
        gross = _positive(row["gross_quantity"], "RESTORED_GROSS_INVALID")
        count = row["fulfilled_quantity"]
        if type(count) is not int or not 0 <= count <= gross:
            raise InvalidEvidence("RESTORED_FULFILLED_INVALID")
        sequences = row["source_event_sequences"]
        if (type(sequences) is not list or not sequences
                or any(type(i) is not int or i <= 0 for i in sequences)
                or sequences != sorted(set(sequences))):
            raise InvalidEvidence("RESTORED_SEQUENCE_PROOF_INVALID")
        result[oid] = row
    return result


def reconcile(events, snapshot, *, expected_source_sha256=None,
              expected_restored_sha256=None):
    """Return a strict, non-executing comparison with explicit evidence tiers.

    Neither input pins nor a synthetic PASS creates a delivery authorization.
    Pins must originate OUTSIDE the evidence being evaluated.
    """
    result = {
        "schema": "continuity-omega/restored-reference-review/v1",
        "scope": "SYNTHETIC_ONLY_NO_EXTERNAL_AUTHORITY",
        "verdict": "UNVERIFIABLE",
        "source_sha256": None,
        "snapshot_sha256": None,
        "findings": [],
        "complete": False,
        "authority": "CALLER_PINS_NOT_REAL_WORLD_CUSTODY",
    }
    try:
        orders = replay(events)
        restored = _validated_snapshot(snapshot)
        source_hash, snapshot_hash = digest(events), digest(snapshot)
        result["source_sha256"] = source_hash
        result["snapshot_sha256"] = snapshot_hash
        if snapshot["source_events_sha256"] != source_hash:
            result["findings"].append("RESTORED_REFERENCES_DIFFERENT_SOURCE")
        for oid, source in sorted(orders.items()):
            active = (source["status"] == "ACTIVE" and
                      source["gross_quantity"] > source["fulfilled_quantity"])
            if active and oid not in restored:
                result["findings"].append(oid + ":ACTIVE_ORDER_MISSING")
            if not active and oid in restored:
                status = ("CANCELLED_ORDER_PRESENT" if source["status"] == "CANCELLED"
                          else "COMPLETED_ORDER_PRESENT")
                result["findings"].append(oid + ":" + status)
            if active and oid in restored:
                candidate = restored[oid]
                for key in ("gross_quantity", "fulfilled_quantity", "source_event_sequences"):
                    if candidate[key] != source[key]:
                        result["findings"].append(oid + ":" + key.upper() + "_MISMATCH")
        for oid in sorted(set(restored) - set(orders)):
            result["findings"].append(oid + ":UNSUPPORTED_ORDER_PRESENT")
        # Mismatched caller-held references invalidate even a coherent event and
        # snapshot pair; no attempt is made to re-sign or repair either input.
        if expected_source_sha256 is None or expected_restored_sha256 is None:
            result["findings"].append("BOTH_EXTERNAL_CALLER_PINS_REQUIRED")
        elif (type(expected_source_sha256) is not str or
              type(expected_restored_sha256) is not str or
              source_hash != expected_source_sha256 or
              snapshot_hash != expected_restored_sha256):
            result["findings"].append("EXTERNAL_REFERENCE_CHANGED")
        result["findings"].sort()
        if not result["findings"]:
            result["verdict"] = "RECONCILED_SYNTHETIC"
            result["complete"] = True
        elif all(x == "BOTH_EXTERNAL_CALLER_PINS_REQUIRED" for x in result["findings"]):
            result["verdict"] = "UNVERIFIABLE"
        else:
            result["verdict"] = "DISCREPANCY_OR_UNVERIFIABLE"
    except (InvalidEvidence, TypeError, ValueError, RecursionError) as exc:
        result["findings"] = [str(exc) if isinstance(exc, InvalidEvidence)
                              else "NONCANONICAL_EVIDENCE"]
        result["verdict"] = "INVALID"
    return result
