"""Constructive conventional event-sourced offsite recovery control (synthetic).

An ordinary competent offsite incremental-event replay can reconstruct remaining
obligations without a new three-custodian signing invention when complete,
authentic, currently relevant events are available. The source-availability
assumption is *not* demonstrated by this model. No financial or shipping action.
This independent algorithm does NOT import the owner engine or reference replay.
"""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = "continuity-omega/restored-active-v2"
ID = re.compile(r"^[A-Z0-9._-]{1,64}$")
HEX = re.compile(r"^[0-9a-f]{64}$")


class OrdinaryRestoreRefused(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value):
    if type(value) is not str or ID.fullmatch(value) is None:
        raise OrdinaryRestoreRefused("INVALID_SOURCE_IDENTIFIER")


def _pos(value):
    if type(value) is not int or value <= 0:
        raise OrdinaryRestoreRefused("INVALID_SOURCE_POSITIVE_INTEGER")


def _rebuild(events, source_pin):
    if type(source_pin) is not str or HEX.fullmatch(source_pin) is None:
        raise OrdinaryRestoreRefused("EXTERNAL_OFFSITE_SOURCE_PIN_REQUIRED")
    if type(events) is not list or not 1 <= len(events) <= 20000:
        raise OrdinaryRestoreRefused("SOURCE_EVENTS_INVALID")
    if _hash(events) != source_pin:
        raise OrdinaryRestoreRefused("OFFSITE_SOURCE_PIN_MISMATCH")
    # Independently written, conventional append-log state transition.
    orders = {}
    for i, event in enumerate(events, 1):
        if type(event) is not dict:
            raise OrdinaryRestoreRefused("SOURCE_EVENT_SHAPE_INVALID")
        if type(event.get("sequence")) is not int or event["sequence"] != i:
            raise OrdinaryRestoreRefused("SOURCE_EVENT_SEQUENCE_INVALID")
        kind = event.get("type")
        fields = {"sequence", "type", "order_id"}
        if kind == "ACCEPT":
            fields |= {"quantity", "product", "spec_sha256", "deadline_hours"}
        elif kind in ("AMEND", "FULFILL"):
            fields |= {"quantity"}
        elif kind != "CANCEL":
            raise OrdinaryRestoreRefused("SOURCE_EVENT_TYPE_INVALID")
        if set(event) != fields:
            raise OrdinaryRestoreRefused("SOURCE_EVENT_FIELDS_INVALID")
        oid = event["order_id"]
        _id(oid)
        if kind == "ACCEPT":
            if oid in orders:
                raise OrdinaryRestoreRefused("DUPLICATE_SOURCE_ACCEPT")
            _id(event["product"])
            if type(event["spec_sha256"]) is not str or HEX.fullmatch(event["spec_sha256"]) is None:
                raise OrdinaryRestoreRefused("SOURCE_SPEC_INVALID")
            _pos(event["deadline_hours"])
            _pos(event["quantity"])
            orders[oid] = {"gross_quantity": event["quantity"],
                           "fulfilled_quantity": 0,
                           "source_event_sequences": [i], "active": True}
            continue
        if oid not in orders or not orders[oid]["active"]:
            raise OrdinaryRestoreRefused("SOURCE_EVENT_INACTIVE_ORDER")
        row = orders[oid]
        row["source_event_sequences"].append(i)
        if kind == "AMEND":
            _pos(event["quantity"])
            if event["quantity"] < row["fulfilled_quantity"]:
                raise OrdinaryRestoreRefused("AMENDMENT_ERASES_FULFILLMENT")
            row["gross_quantity"] = event["quantity"]
        elif kind == "FULFILL":
            _pos(event["quantity"])
            if row["fulfilled_quantity"] + event["quantity"] > row["gross_quantity"]:
                raise OrdinaryRestoreRefused("OVERFULFILLMENT")
            row["fulfilled_quantity"] += event["quantity"]
        else:
            row["active"] = False
    records = []
    for oid, row in sorted(orders.items()):
        if row["active"] and row["fulfilled_quantity"] < row["gross_quantity"]:
            records.append({"order_id": oid, "gross_quantity": row["gross_quantity"],
                            "fulfilled_quantity": row["fulfilled_quantity"],
                            "source_event_sequences": row["source_event_sequences"]})
    return {"schema": SCHEMA, "source_events_sha256": source_pin, "records": records}


def restore(events, *, independently_held_offsite_source_sha256):
    """Rebuild a hypothetical complete archived event stream, without side effects.

    Out-of-band source identity is essential and must be truly kept offsite to
    qualify actual archival integrity. A program-generated hash is not a
    real-world chain of custody. No actual independent archive is provided.
    """
    result = {"schema": "continuity-omega/ordinary-offsite-rebuild-research-v1",
              "verdict": "REFUSED", "reason": None, "restored_snapshot": None,
              "real_archive_custody": False, "currentness_verified": False,
              "real_customer_acceptance": False, "business_profit_usd": None}
    try:
        result["restored_snapshot"] = _rebuild(
            events, independently_held_offsite_source_sha256)
        result["verdict"] = "CONVENTIONAL_OFFSITE_REPLAY_SYNTHETIC"
    except (OrdinaryRestoreRefused, ValueError, TypeError, OverflowError,
            RecursionError) as exc:
        result["reason"] = (str(exc) if isinstance(exc, OrdinaryRestoreRefused)
                            else "SOURCE_NOT_CANONICAL")
    return result
