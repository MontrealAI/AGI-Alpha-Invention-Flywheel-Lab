#!/usr/bin/env python3
"""OPEN-DEMAND211: conservative public procurement notice observation (research only).

No bidding, buyer contacts, private data, payments, native account changes or
contract/profit claims. A published notice is not an acquired customer.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler

URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=2"
SCHEMA = "open-demand211/receipt/v1"
MAX_BYTES = 512 * 1024
COSTS = ("acquisition", "research", "eligibility", "submission", "development",
         "delivery", "verification", "support", "correction", "refunds",
         "financing", "taxes", "failure", "infrastructure", "model", "overhead")


class Refusal(ValueError):
    pass


def deny(reason):
    raise Refusal(reason)


def pairs_unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            deny("DUPLICATE_KEY")
        obj[key] = value
    return obj


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded_text(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 240:
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return None
    return value.strip()


def parse_utc(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def amount_value(value):
    if type(value) not in (str, int, float):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return str(amount)


def notice(item, now):
    if not isinstance(item, dict):
        return {"decision": "NO_DEPLOY", "reasons": ["INVALID_RELEASE"]}
    release_id = bounded_text(item.get("id"))
    ocid = bounded_text(item.get("ocid"))
    tender = item.get("tender") if isinstance(item.get("tender"), dict) else {}
    buyer = item.get("buyer") if isinstance(item.get("buyer"), dict) else {}
    tags = item.get("tag") if isinstance(item.get("tag"), list) else []
    title = bounded_text(tender.get("title"))
    buyer_name = bounded_text(buyer.get("name"))
    tender_status = tender.get("status")
    period = tender.get("tenderPeriod") if isinstance(tender.get("tenderPeriod"), dict) else {}
    end = period.get("endDate")
    deadline = parse_utc(end)
    value = tender.get("value") if isinstance(tender.get("value"), dict) else {}
    currency = bounded_text(value.get("currency"))
    amount = amount_value(value.get("amount"))
    reasons = []
    if not release_id or not ocid:
        reasons.append("MISSING_SOURCE_IDENTIFIERS")
    if not title or not buyer_name:
        reasons.append("MISSING_PUBLIC_BUYER_OR_TITLE")
    if "tender" not in tags or "award" in tags:
        reasons.append("NOT_NEW_TENDER_RELEASE")
    if tender_status != "active":
        reasons.append("NOT_EXPLICITLY_ACTIVE")
    if deadline is None:
        reasons.append("DEADLINE_MISSING_OR_UNVERIFIABLE")
    elif deadline <= now:
        reasons.append("DEADLINE_NOT_FUTURE")
    # Value is disclosure only, never revenue/profit. Unknown is allowed.
    return {
        "release_id": release_id,
        "ocid": ocid,
        "buyer": buyer_name,
        "title": title,
        "tags": sorted(t for t in tags if isinstance(t, str) and len(t) < 50),
        "tender_status": bounded_text(tender_status),
        "deadline_utc": deadline.isoformat() if deadline else None,
        "declared_value": amount if currency and amount else None,
        "declared_currency": currency if currency and amount else None,
        "decision": "REVIEW_ELIGIBILITY_ONLY" if not reasons else "NO_DEPLOY",
        "reasons": reasons,
        "paid_customer": False,
        "supplier_eligibility_confirmed": False,
    }


def summarize(raw, observed_at):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        deny("RESPONSE_SIZE_BOUND")
    observed = parse_utc(observed_at)
    if observed is None:
        deny("OBSERVATION_TIME_INVALID")
    try:
        package = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs_unique,
                             parse_constant=lambda _: deny("NONFINITE_NUMBER"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal("MALFORMED_UTF8_JSON") from exc
    if not isinstance(package, dict) or not isinstance(package.get("releases"), list):
        deny("RELEASE_PACKAGE_REQUIRED")
    releases = package["releases"]
    if len(releases) > 2:
        deny("UNREQUESTED_RELEASE_COUNT")
    seen = set()
    result = []
    for item in releases:
        row = notice(item, observed)
        rid = row.get("release_id")
        if rid and rid in seen:
            deny("DUPLICATE_RELEASE_ID")
        if rid:
            seen.add(rid)
        result.append(row)
    reviews = sum(item["decision"] == "REVIEW_ELIGIBILITY_ONLY" for item in result)
    return {
        "schema": SCHEMA,
        "source_url": URL,
        "source_license_attribution": "Contains public sector information licensed under the Open Government Licence v3.0.",
        "source_sha256": sha256(raw),
        "source_bytes": len(raw),
        "observed_at_utc": observed.isoformat(),
        "records": result,
        "records_observed": len(result),
        "eligibility_reviews_possible": reviews,
        "operating_decision": "HOLD_NO_BID_NO_DEPLOY",
        "source_notices_are_not_customers": True,
        "cash_collected": None,
        "complete_cost_profit": None,
        "costs_unknown": list(COSTS),
        "target_3b_trailing_365_qualified": False,
        "alternatives": [
            "existing C$2,995 decision dossier against human/hybrid/self-service",
            "government procurement data against free official portal/procurement analyst",
            "recurring notice intelligence against incumbent alerts and no-purchase",
            "NO DEPLOY",
        ],
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        deny("REDIRECT_REFUSED")


def retrieve():
    request = Request(URL, headers={
        "User-Agent": "MONTREAL-AI-OPEN-DEMAND211-Research/1.0",
        "Accept": "application/json",
    }, method="GET")
    response = build_opener(NoRedirect()).open(request, timeout=15)
    with response:
        if response.status != 200 or response.geturl() != URL:
            deny("HTTP_OR_LOCATION_REFUSED")
        if "json" not in response.headers.get("Content-Type", "").lower():
            deny("NON_JSON_MEDIA")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BYTES):
            deny("DECLARED_BODY_TOO_LARGE")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            deny("RESPONSE_SIZE_BOUND")
        return raw


def fetch(output):
    root = Path(output)
    if root.exists():
        deny("OUTPUT_MUST_NOT_EXIST")
    raw = retrieve()  # single request; no retry or alternate endpoint
    observed = datetime.now(timezone.utc).isoformat()
    receipt = summarize(raw, observed)
    root.mkdir(parents=True)
    (root / "SOURCE.json").write_bytes(raw)
    (root / "RECEIPT.json").write_bytes(canonical(receipt))
    verify(root)
    return receipt


def verify(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        deny("OUTPUT_NOT_DIRECTORY")
    for filename in ("SOURCE.json", "RECEIPT.json"):
        p = root / filename
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
            deny("UNSAFE_OUTPUT_FILE")
    raw = (root / "SOURCE.json").read_bytes()
    receipt_raw = (root / "RECEIPT.json").read_bytes()
    receipt = json.loads(receipt_raw.decode("utf-8"), object_pairs_hook=pairs_unique)
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        deny("RECEIPT_SCHEMA")
    expected = summarize(raw, receipt.get("observed_at_utc"))
    if canonical(expected) != receipt_raw:
        deny("SOURCE_OR_RECEIPT_CHANGED")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        r = fetch(args.out) if args.action == "fetch" else verify(args.out)
    except (Refusal, HTTPError, OSError) as exc:
        parser.exit(2, f"OPEN_DEMAND211_REFUSED: {exc}\n")
    print(canonical(r).decode("utf-8"))


if __name__ == "__main__":
    main()
