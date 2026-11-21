#!/usr/bin/env python3
"""CANADA-OPEN-NEED227: independent public procurement signal, never a buyer/payment claim.

Read one official open-tender CSV; produce a byte-bound, replayable conservative
requirements-review shortlist. All external commercial actions are out of scope.
"""
import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, build_opener, HTTPRedirectHandler

SOURCE = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
SCHEMA = "agi-alpha/canada-open-need227/v1"
REFERENCE = "referenceNumber-numeroReference"
TITLE = "title-titre-eng"
CLOSING = "tenderClosingDate-appelOffresDateCloture"
BUYER = "contractingEntityName-nomEntiteContractante-eng"
CATEGORY = "procurementCategory-categorieApprovisionnement"
REQUIRED = (REFERENCE, TITLE, CLOSING)
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 100_000
MAX_FIELD = 2 * 1024 * 1024
MAX_VISIBLE = 20
PHRASES = (
    "software development", "data analysis", "data management",
    "artificial intelligence", "machine learning", "automation",
    "digital transformation", "document processing",
    "intelligence artificielle", "analyse de données",
)
PATTERN = re.compile(r"(?<!\\w)(?:" + "|".join(re.escape(x) for x in PHRASES) + r")(?!\\w)", re.I)
COSTS = (
    "research_and_failed_attempts", "acquisition", "eligibility_and_bid",
    "production_and_tool_inference", "independent_acceptance", "corrections",
    "support_and_recurring_maintenance", "taxes", "refunds_and_warranty",
    "financing_and_liability_reserves", "infrastructure", "human_attention",
)
ALTERNATIVES = (
    "one-off bilingual decision dossier versus competent conventional and AI-assisted analysts",
    "recurring procurement intelligence versus free CanadaBuys and incumbent monitoring",
    "complete accepted machine-assisted outcome versus incumbent specialized suppliers",
    "NO BID / NO DEPLOY",
)


class Refusal(ValueError):
    """A deliberately preserved, fail-closed input or authority boundary."""


def refuse(reason):
    raise Refusal(reason)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            refuse("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def clean(value, limit=240):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not 1 <= len(value) <= limit:
        return None
    if value[0] in "=+@":
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return None
    return value


def observed_date(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d(?:\\.\\d+)?(?:Z|[+-]\\d\\d:\\d\\d)", value
    ):
        refuse("INVALID_OBSERVED_AT")
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return observed.astimezone(timezone.utc)
    except ValueError as exc:
        raise Refusal("INVALID_OBSERVED_AT") from exc


def closing_day(value):
    # Timezone-ambiguous same-day deadlines are never actionable.
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not re.fullmatch(r"\\d{4}-\\d\\d-\\d\\d(?:[ T]\\d\\d:\\d\\d(?::\\d\\d)?(?:Z|[+-]\\d\\d:\\d\\d)?)?", value):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def assess(raw, observed_at):
    when = observed_date(observed_at)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        refuse("SOURCE_BYTES_BOUND")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Refusal("NOT_UTF8") from exc
    if "\x00" in text:
        refuse("NUL_IN_CSV")
    csv.field_size_limit(MAX_FIELD)
    reader = csv.DictReader(StringIO(text, newline=""), strict=True)
    headers = reader.fieldnames
    if not headers or any(not x for x in headers) or len(headers) != len(set(headers)):
        refuse("MISSING_OR_DUPLICATE_HEADERS")
    if any(x not in headers for x in REQUIRED):
        refuse("UNSUPPORTED_TENDER_SCHEMA")

    counts = {
        "rows_all": 0, "matched_title_rows": 0,
        "expired_or_same_day": 0, "unparseable_or_missing_closing": 0,
        "missing_or_unsafe_identity_title": 0,
        "ambiguous_reference_groups": 0,
        "duplicate_identical_rows": 0, "future_title_matches": 0,
    }
    by_ref = {}
    try:
        for row in reader:
            counts["rows_all"] += 1
            if counts["rows_all"] > MAX_ROWS:
                refuse("ROWS_BOUND")
            if None in row or any(v is None for v in row.values()):
                refuse("RAGGED_CSV")
            title = clean(row.get(TITLE))
            if not title or not PATTERN.search(title):
                continue
            counts["matched_title_rows"] += 1
            ref = clean(row.get(REFERENCE), 160)
            if not ref:
                counts["missing_or_unsafe_identity_title"] += 1
                continue
            deadline = closing_day(row.get(CLOSING))
            if deadline is None:
                counts["unparseable_or_missing_closing"] += 1
                continue
            if deadline <= when.date():
                counts["expired_or_same_day"] += 1
                continue
            counts["future_title_matches"] += 1
            current = {
                "reference": ref, "title": title,
                "closing_date_recorded": deadline.isoformat(),
                "buyer_from_source": clean(row.get(BUYER), 240),
                "category_from_source": clean(row.get(CATEGORY), 80),
                "buyer_acceptance": None,
                "supplier_eligibility": None,
                "authorized_offer_or_contract": False,
            }
            key = ref.casefold()
            if key not in by_ref:
                by_ref[key] = [current, False]
            elif by_ref[key][0] == current:
                counts["duplicate_identical_rows"] += 1
            else:
                by_ref[key][1] = True
    except csv.Error as exc:
        raise Refusal("MALFORMED_CSV") from exc

    valid = []
    for entry, ambiguous in by_ref.values():
        if ambiguous:
            counts["ambiguous_reference_groups"] += 1
        else:
            valid.append(entry)
    valid.sort(key=lambda x: (x["reference"].casefold(), x["title"], x["closing_date_recorded"]))
    return {
        "schema": SCHEMA, "official_source": SOURCE,
        "source_kind": "open_tender_not_award_payment_or_executed_buyer_agreement",
        "data_attribution": "Contains information licensed under the Open Government Licence - Canada",
        "observation_utc": when.isoformat(), "source_sha256": sha256(raw),
        "source_bytes": len(raw),
        "script_sha256": sha256(Path(__file__).read_bytes()),
        "header_fields": headers, "counts": counts,
        "review_candidates_total": len(valid),
        "review_candidates": valid[:MAX_VISIBLE],
        "truncated": len(valid) > MAX_VISIBLE,
        "selection_method": "frozen_title_phrases_and_strict_future_calendar_date_only",
        "decision": "INVESTIGATE_ELIGIBILITY_ONLY" if valid else "NO_QUALIFIED_MATCH",
        "actual_business_action": "NO_BID_NO_DEPLOY_NO_SPENDING",
        "real_payment_to_montreal_ai_observed_by_this_instrument": None,
        "buyer_willingness_to_pay_for_our_service": None,
        "complete_cost_profit": None,
        "cost_categories_not_measured": COSTS,
        "competing_business_arrangements": ALTERNATIVES,
        "usd_3b_trailing365_complete_cost_profit_proven": False,
        "native_financial_account_touched": False,
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        refuse("REDIRECT_REFUSED")


def retrieve():
    request = Request(SOURCE, method="GET", headers={
        "User-Agent": "MONTREAL-AI-Open-Need227-PublicResearch/1.0",
        "Accept": "text/csv,application/octet-stream,text/plain",
    })
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        if response.status != 200 or response.geturl() != SOURCE:
            refuse("SOURCE_OR_STATUS_CHANGED")
        content_type = response.headers.get("Content-Type", "").lower().split(";")[0]
        if content_type not in ("text/csv", "application/octet-stream", "text/plain", "application/csv"):
            refuse("UNEXPECTED_MEDIA_TYPE")
        length = response.headers.get("Content-Length")
        if length and (not length.isdecimal() or int(length) > MAX_BYTES):
            refuse("DECLARED_BYTES_BOUND")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            refuse("SOURCE_BYTES_BOUND")
        return raw


def verify(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        refuse("UNSAFE_OUTPUT_DIRECTORY")
    paths = [root / "SOURCE.csv", root / "RECEIPT.json"]
    if any(x.is_symlink() or not x.is_file() or x.stat().st_size > MAX_BYTES for x in paths):
        refuse("UNSAFE_OUTPUT_FILES")
    source = paths[0].read_bytes()
    receipt_raw = paths[1].read_bytes()
    try:
        receipt = json.loads(receipt_raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal("BAD_RECEIPT_JSON") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        refuse("BAD_RECEIPT_SCHEMA")
    if canonical(assess(source, receipt.get("observation_utc"))) != receipt_raw:
        refuse("SOURCE_OR_RECEIPT_CHANGED")
    return receipt


def observe(root):
    root = Path(root)
    if root.exists() or root.is_symlink():
        refuse("OUTPUT_ALREADY_EXISTS")
    raw = retrieve()  # One request, never retry from inside this process.
    receipt = assess(raw, datetime.now(timezone.utc).isoformat())
    root.mkdir(parents=True)
    (root / "SOURCE.csv").write_bytes(raw)
    (root / "RECEIPT.json").write_bytes(canonical(receipt))
    verify(root)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("observe", "verify"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = observe(args.out) if args.action == "observe" else verify(args.out)
    except (Refusal, OSError, UnicodeError) as exc:
        parser.exit(2, "CANADA_OPEN_NEED227_FAILED: " + str(exc) + "\n")
    print(canonical(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
