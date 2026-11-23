"""Read-only source provenance and deadline contradiction instrument.

Does not fetch websites, authenticate, claim an official live inventory, or submit bids.
Normalized readings must be independently checked against the cited public pages.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SCHEMA = "agi-alpha/tender-sourceguard244/v1"
OFFICIAL_HOST = "canadabuys.canada.ca"
FIELDS = frozenset({"id", "role", "sequence", "issued_on", "solicitation",
                    "url", "locator", "reading_local", "zone", "excerpt"})
REQUIRED_CHECKS = frozenset({"offeror_experience", "buyer_need_fulfillable",
                             "bilingual_delivery", "support_cost_cap",
                             "subcontract_permission", "complete_cash_costs"})


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _datetime(reading: str, zone: str) -> datetime:
    _require(type(reading) is str and type(zone) is str and zone in ("EST", "EDT", "UTC"),
             "EXPLICIT_EST_EDT_OR_UTC_REQUIRED")
    try:
        local = datetime.strptime(reading, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValueError("INVALID_CANONICAL_LOCAL_DATETIME") from exc
    if zone == "UTC":
        return local.replace(tzinfo=timezone.utc)
    # A bare tzinfo replacement can invent nonexistent DST-gap timestamps or
    # reject the valid second occurrence of a fall-back wall clock instant.
    region = ZoneInfo("America/Toronto")
    expected = timedelta(hours=-5 if zone == "EST" else -4)
    valid = []
    for fold in (0, 1):
        candidate = local.replace(tzinfo=region, fold=fold)
        if candidate.utcoffset() != expected:
            continue
        # Only the correct fold of an existing wall time survives an exact
        # UTC -> local round trip. Ordinary unambiguous instants use fold=0.
        roundtrip = candidate.astimezone(timezone.utc).astimezone(region)
        if (roundtrip.replace(tzinfo=None) == local and
                roundtrip.fold == fold):
            valid.append(candidate)
    _require(len(valid) == 1, "TIMEZONE_LABEL_CONFLICTS_OR_LOCAL_TIME_NONEXISTENT")
    return valid[0]


def _normalize_doc(d: dict, solicitation: str) -> dict:
    _require(type(d) is dict and set(d) == FIELDS, "EXACT_PROVENANCE_RECORD_REQUIRED")
    _require(d["role"] in ("official_base", "official_addendum", "third_party"), "UNRECOGNIZED_ROLE")
    for field in ("id", "solicitation", "url", "locator", "excerpt", "issued_on"):
        _require(type(d[field]) is str and bool(d[field].strip()), "MISSING_PROVENANCE_" + field.upper())
    _require(d["solicitation"] == solicitation, "CROSS_SOLICITATION_SOURCE_REJECTED")
    _require(type(d["sequence"]) is int and 0 <= d["sequence"] <= 99, "INVALID_SOURCE_SEQUENCE")
    _require((d["role"] == "official_base") == (d["sequence"] == 0), "BASE_SEQUENCE_MISMATCH")
    _require((d["role"] == "official_addendum") == (d["sequence"] > 0) or d["role"] == "third_party",
             "ADDENDUM_SEQUENCE_MISMATCH")
    try:
        date.fromisoformat(d["issued_on"])
    except ValueError as exc:
        raise ValueError("INVALID_ISSUE_DATE") from exc
    u = urlsplit(d["url"])
    _require(u.scheme == "https" and bool(u.hostname) and not u.username and not u.password,
             "HTTPS_PUBLIC_SOURCE_REQUIRED")
    if d["role"].startswith("official_"):
        _require(u.hostname == OFFICIAL_HOST and u.path.endswith(".pdf"), "OFFICIAL_DOMAIN_AND_PDF_REQUIRED")
    else:
        _require(u.hostname != OFFICIAL_HOST, "THIRD_PARTY_CANNOT_MASQUERADE_AS_OFFICIAL")
    stamp = _datetime(d["reading_local"], d["zone"])
    return {"id": d["id"], "role": d["role"], "sequence": d["sequence"],
            "issued_on": d["issued_on"], "url": d["url"],
            "reading_utc": stamp.astimezone(timezone.utc).isoformat(timespec="seconds")}


def reconcile(spec: dict) -> dict:
    _require(type(spec) is dict and set(spec) == {"schema", "solicitation", "document_inventory_closed",
                                                  "documents", "commercial_readiness"}, "EXACT_INPUT_SCHEMA_REQUIRED")
    _require(spec["schema"] == SCHEMA, "INVALID_SCHEMA")
    solicitation = spec["solicitation"]
    _require(type(solicitation) is str and len(solicitation) <= 50 and solicitation.isascii() and solicitation,
             "SOLICITATION_ID_REQUIRED")
    _require(type(spec["document_inventory_closed"]) is bool, "INVENTORY_CLOSURE_BOOLEAN_REQUIRED")
    _require(type(spec["documents"]) is list and 1 <= len(spec["documents"]) <= 100,
             "BOUNDED_DOCUMENT_SET_REQUIRED")
    readiness = spec["commercial_readiness"]
    _require(type(readiness) is dict and set(readiness) == REQUIRED_CHECKS, "COMPLETE_READINESS_DISCLOSURE_REQUIRED")
    _require(all(type(v) is bool or v is None for v in readiness.values()), "READINESS_MUST_BE_BOOL_OR_UNKNOWN")

    docs = [_normalize_doc(d, solicitation) for d in spec["documents"]]
    _require(len({d["id"] for d in docs}) == len(docs), "DUPLICATE_DOCUMENT_ID")
    official = sorted([d for d in docs if d["role"] != "third_party"], key=lambda d: d["sequence"])
    _require(bool(official) and official[0]["role"] == "official_base", "OFFICIAL_BASE_REQUIRED")
    _require(len({d["sequence"] for d in official}) == len(official), "DUPLICATE_OFFICIAL_SEQUENCE")
    expected = list(range(official[-1]["sequence"] + 1))
    missing = sorted(set(expected) - {d["sequence"] for d in official})
    official_times = sorted({d["reading_utc"] for d in official})
    conflict = len(official_times) != 1
    latest = official[-1]
    missing_inventory = bool(missing) or not spec["document_inventory_closed"]
    # A source listing provided by an operator is not a live official inventory API proof.
    status = "CONFLICT" if conflict else "INDETERMINATE" if missing_inventory else "SELF_ATTESTED_CONSISTENT"
    observed = None if conflict or missing else official_times[0]
    external = [{"id": d["id"], "published_instant_utc": d["reading_utc"],
                 "conflicts_with_known_official": (None if observed is None else d["reading_utc"] != observed)}
                for d in docs if d["role"] == "third_party"]
    return {"schema": SCHEMA, "solicitation": solicitation, "schedule_status": status,
            "observed_official_instant_utc": observed,
            "final_current_deadline_verified": False,
            "inventory_completeness_self_attested": spec["document_inventory_closed"],
            "missing_official_sequences": missing,
            "latest_known_official_source": latest["url"],
            "official_conflict_instants": official_times if conflict else [],
            "external_discrepancies": external,
            "commercial_decision": "HOLD_NO_BID" if not all(v is True for v in readiness.values()) else "REVIEW_REQUIRED_NO_AUTO_BID",
            "unqualified_requirements": sorted(k for k, v in readiness.items() if v is not True),
            "source_evidence_tier": "MANUALLY_EXTRACTED_PUBLIC_URL_NOT_BYTE_VERIFIED",
            "account_activity": "NONE", "external_commerce": "NOT_EVALUATED"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    args = p.parse_args()
    try:
        with args.input.open(encoding="utf-8") as f:
            spec = json.load(f, object_pairs_hook=_reject_duplicate_keys)
        print(json.dumps(reconcile(spec), sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 2


def _reject_duplicate_keys(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[k] = v
    return result


if __name__ == "__main__":
    raise SystemExit(main())
