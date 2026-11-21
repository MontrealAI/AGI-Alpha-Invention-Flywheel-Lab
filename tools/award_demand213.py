#!/usr/bin/env python3
"""AWARD-DEMAND213: public federal award-history evidence, NOT buyer or revenue proof.

This is a read-only source-bound research instrument; it cannot bid, quote,
commit funds, contact buyers, or update the canonical financial account.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler

SOURCE = ("https://canadabuys.canada.ca/opendata/pub/"
          "2026-2027-awardNotice-avisAttribution.csv")
SCHEMA = "agi-alpha/award-demand213-source-linked/v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 100000
MAX_FIELD = 2 * 1024 * 1024
MAX_VISIBLE = 25
TITLE_EN = "title-titre-eng"
TITLE_FR = "title-titre-fra"
STATUS = "awardStatus-attributionStatut-eng"
SOLICITATION = "solicitationNumber-numeroSollicitation"
REQUIRED = (TITLE_EN, TITLE_FR, STATUS, SOLICITATION)
# Frozen 2026-11-21. Whole phrases only; never substring "AI" in Canada.
KEYWORDS = re.compile(
    r"\b(?:artificial intelligence|machine learning|generative ai|"
    r"agentic ai|intelligence artificielle|apprentissage automatique)\b",
    flags=re.IGNORECASE,
)
COSTS = [
    "search_and_failed_attempts", "acquisition_and_bid", "model_and_inference",
    "production", "independent_acceptance", "correction", "support",
    "warranty_and_refunds", "financing_and_liability_reserves", "taxes",
    "infrastructure_and_maintenance", "human_intervention", "overhead",
]


class Refusal(ValueError):
    """Fail-closed data or evidence rejection."""


def refuse(reason):
    raise Refusal(reason)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def pair_unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            refuse("DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def clean(value, max_chars=240):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not (1 <= len(value) <= max_chars):
        return None
    if value[0] in "=+@":
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value


def observation_time(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", value):
        refuse("INVALID_OBSERVATION_TIME")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError as exc:
        raise Refusal("INVALID_OBSERVATION_TIME") from exc


def parse_csv(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        refuse("SOURCE_SIZE_BOUND")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Refusal("SOURCE_NOT_UTF8") from exc
    if "\x00" in text:
        refuse("NUL_IN_CSV")
    csv.field_size_limit(MAX_FIELD)
    reader = csv.DictReader(StringIO(text, newline=""), strict=True)
    header = reader.fieldnames
    if not header or len(header) != len(set(header)) or any(not h for h in header):
        refuse("MISSING_OR_DUPLICATE_HEADERS")
    if any(field not in header for field in REQUIRED):
        refuse("UNSUPPORTED_AWARD_SCHEMA")
    return reader, header


def assess(raw, observed_at):
    observed = observation_time(observed_at)
    reader, header = parse_csv(raw)
    candidates = {}
    rows = 0
    keyword_matches = 0
    active_keyword_rows = 0
    invalid_identity_rows = 0
    nonactive_keyword_rows = 0
    try:
        for item in reader:
            rows += 1
            if rows > MAX_ROWS:
                refuse("ROWS_RESOURCE_BOUND")
            if None in item:
                refuse("RAGGED_CSV_EXTRA_COLUMNS")
            en = clean(item.get(TITLE_EN))
            fr = clean(item.get(TITLE_FR))
            if not (en or fr):
                continue
            if not KEYWORDS.search((en or "") + " " + (fr or "")):
                continue
            keyword_matches += 1
            status = clean(item.get(STATUS), 90)
            if status != "Active":
                nonactive_keyword_rows += 1
                continue
            active_keyword_rows += 1
            ref = clean(item.get(SOLICITATION), 120)
            if not ref:
                invalid_identity_rows += 1
                continue
            # One solicitation reference is not necessarily one unique purchase.
            # Do not count duplicate award revisions as additional buyers.
            key = ref.casefold()
            entry = {"reference": ref, "title_en": en, "title_fr": fr,
                     "public_award_status": status}
            if key not in candidates:
                candidates[key] = entry
            else:
                old = candidates[key]
                # Deterministic representative, regardless of file row ordering.
                if (entry["reference"], entry["title_en"] or "",
                    entry["title_fr"] or "") < (
                    old["reference"], old["title_en"] or "", old["title_fr"] or ""):
                    candidates[key] = entry
    except csv.Error as exc:
        raise Refusal("MALFORMED_CSV") from exc
    entries = sorted(candidates.values(), key=lambda r: (
        r["reference"].casefold(), r["title_en"] or "", r["title_fr"] or ""))
    return {
        "schema": SCHEMA,
        "source": SOURCE,
        "source_category": "published_government_award_notices_not_payment_evidence",
        "source_scope": "CanadaBuys federal FY2026-2027 only, not all Canadian purchasers",
        "government_open_data_attribution": "Contains information licensed under the Open Government Licence - Canada",
        "observed_at_utc": observed,
        "source_sha256": sha256(raw),
        "source_bytes": len(raw),
        "csv_columns": header,
        "rows_total": rows,
        "keyword_matching_rows": keyword_matches,
        "keyword_matching_active_award_rows": active_keyword_rows,
        "keyword_matching_nonactive_or_unverified_rows": nonactive_keyword_rows,
        "active_rows_missing_solicitation_identity": invalid_identity_rows,
        "distinct_matching_active_solicitation_refs": len(entries),
        "published_entries": entries[:MAX_VISIBLE],
        "published_entries_truncated": len(entries) > MAX_VISIBLE,
        "repeat_buyers_proven": None,
        "delivered_contracts_proven": None,
        "government_payments_proven": None,
        "montreal_ai_contracts_proven": False,
        "montreal_ai_cash_collected": None,
        "buyer_willingness_to_pay_this_service": None,
        "complete_cost_profit": None,
        "cost_categories_unknown": COSTS,
        "research_next_action": ("INVESTIGATE_ORIGINAL_SOLICITATION_AND_STRONG_FREE_ALTERNATIVES"
                                 if entries else "NO_QUALIFIED_MATCH_IN_FROZEN_SOURCE"),
        "operating_action": "NO_BID_NO_DEPLOY_NO_FINANCIAL_AUTHORIZATION",
        "compared_options": [
            "existing C$2,995 public-only custom dossier vs competent analyst/internal AI",
            "recurring source-linked award intelligence vs free CanadaBuys and incumbents",
            "proof-carrying bid and delivery vs incumbent specialized suppliers",
            "no purchase / no deploy",
        ],
        "us_3b_trailing365_complete_cost_profit_qualified": False,
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        refuse("REDIRECT_REFUSED")


def retrieve():
    request = Request(SOURCE, headers={
        "User-Agent": "MONTREAL-AI-AWARD-DEMAND213-PublicResearch/1.0",
        "Accept": "text/csv,application/octet-stream",
    }, method="GET")
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        if response.status != 200 or response.geturl() != SOURCE:
            refuse("SOURCE_OR_HTTP_STATUS_CHANGED")
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            if not content_length.isdecimal() or int(content_length) > MAX_BYTES:
                refuse("DECLARED_SIZE_BOUND")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            refuse("BODY_SIZE_BOUND")
        return raw


def validate_output_path(root):
    if root.is_symlink() or not root.is_dir():
        refuse("UNSAFE_OUTPUT_DIRECTORY")
    for name in ("SOURCE.csv", "RECEIPT.json"):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            refuse("UNSAFE_OUTPUT_FILE")


def verify(root):
    root = Path(root)
    validate_output_path(root)
    raw = (root / "SOURCE.csv").read_bytes()
    receipt_bytes = (root / "RECEIPT.json").read_bytes()
    try:
        saved = json.loads(receipt_bytes.decode("utf-8"), object_pairs_hook=pair_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal("BAD_RECEIPT_JSON") from exc
    if not isinstance(saved, dict) or saved.get("schema") != SCHEMA:
        refuse("BAD_RECEIPT_SCHEMA")
    if canonical(assess(raw, saved.get("observed_at_utc"))) != receipt_bytes:
        refuse("SOURCE_OR_RECEIPT_CHANGED")
    return saved


def fetch(root):
    root = Path(root)
    if root.exists() or root.is_symlink():
        refuse("OUTPUT_EXISTS")
    raw = retrieve()  # one official read, never retry or adapt query.
    receipt = assess(raw, datetime.now(timezone.utc).isoformat())
    root.mkdir(parents=True)
    (root / "SOURCE.csv").write_bytes(raw)
    (root / "RECEIPT.json").write_bytes(canonical(receipt))
    verify(root)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = fetch(args.out) if args.action == "fetch" else verify(args.out)
    except (Refusal, OSError, ValueError) as exc:
        parser.exit(2, "AWARD_DEMAND213_REFUSED: " + str(exc) + "\n")
    print(canonical(result).decode("utf-8"))


if __name__ == "__main__":
    main()
