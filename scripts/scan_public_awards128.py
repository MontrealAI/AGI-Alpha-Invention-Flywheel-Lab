"""Source-bound, title-only CanadaBuys award-notice preflight.

Supporting market research, NOT a bidder, demand forecast, price estimator,
accepted production instrument, or independent commercial qualification.
No network access, contacts, full data exports or account operations here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

SOURCE_URL = ("https://canadabuys.canada.ca/opendata/pub/"
              "2026-2027-awardNotice-avisAttribution.csv")
FAMILIES = {
    "accessible_publication": (
        "accessibility", "accessible document", "pdf remediation",
        "wcag", "aoda", "document conversion",
    ),
    "physical_measurement": (
        "non-destructive testing", "nondestructive testing", "tomography",
        "metrology", "industrial inspection", "material testing",
    ),
    "material_recovery": (
        "material recovery", "recycling", "waste valorization",
        "electrolysis", "resource recovery", "waste processing",
    ),
}


class SourceRejected(ValueError):
    """A fail-closed provenance, parser, or schema failure."""


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def pick_title(headers: list[str]) -> str:
    """Choose exactly one English title column; no silent description proxy."""
    def is_english_title(name: str) -> bool:
        bits = re.split(r"[-_]", normalized(name))
        return (len(bits) >= 2 and bits[0] == "title"
                and bits[-1] in ("eng", "english")
                and all(bit.isalpha() for bit in bits))
    preferred = [col for col in headers if is_english_title(col)]
    fallback = [col for col in headers
                if normalized(col) in ("title", "notice title", "award title",
                                       "title-titre")]
    chosen = preferred if preferred else fallback
    if len(chosen) != 1:
        raise SourceRejected(
            "TITLE_COLUMN_MISSING_OR_AMBIGUOUS: expected one English title; "
            f"english_candidates={len(preferred)}, fallback_candidates={len(fallback)}"
        )
    return chosen[0]


def analyze(raw: bytes) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    try:
        # SIG strips a publisher UTF-8 BOM while rejecting invalid byte sequences.
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceRejected("INVALID_UTF8") from exc
    if not decoded.strip():
        raise SourceRejected("EMPTY_SOURCE")
    # CSV fields may contain long descriptions, though they are never inspected.
    csv.field_size_limit(64 * 1024 * 1024)
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        headers = next(reader)
    except (StopIteration, csv.Error) as exc:
        raise SourceRejected("INVALID_HEADER") from exc
    normalized_headers = [normalized(x) for x in headers]
    if (not headers or any(not h for h in normalized_headers)
            or len(set(normalized_headers)) != len(normalized_headers)):
        raise SourceRejected("EMPTY_OR_DUPLICATE_HEADERS")
    title = pick_title(headers)
    title_index = headers.index(title)
    row_count = 0
    blank_titles = 0
    counts = {family: 0 for family in FAMILIES}
    intersections = {"accessible_publication+physical_measurement": 0,
                     "accessible_publication+material_recovery": 0,
                     "physical_measurement+material_recovery": 0,
                     "all_three": 0}
    any_match = 0
    try:
        for row in reader:
            if len(row) != len(headers):
                raise SourceRejected(f"MALFORMED_ROW_AT_{row_count + 2}")
            row_count += 1
            value = normalized(row[title_index])
            if not value:
                blank_titles += 1
            matched = {name for name, terms in FAMILIES.items()
                       if any(term in value for term in terms)}
            if matched:
                any_match += 1
            for name in matched:
                counts[name] += 1
            for key in list(intersections):
                if key == "all_three":
                    if len(matched) == 3:
                        intersections[key] += 1
                elif set(key.split("+")).issubset(matched):
                    intersections[key] += 1
    except csv.Error as exc:
        raise SourceRejected(f"CSV_MALFORMED_AFTER_{row_count}_ROWS") from exc
    if not row_count:
        raise SourceRejected("NO_DATA_ROWS")
    return {
        "schema": "agi-alpha/public-evidence128-source-bound-scan/v1",
        "source": {"url": SOURCE_URL, "sha256": digest, "bytes": len(raw),
                   "rows": row_count, "columns": len(headers),
                   "title_column": title},
        "method": {
            "matching": "NFKC-casefolded substring match on English title only",
            "families": {k: list(v) for k, v in FAMILIES.items()},
            "license": "Contains information licensed under the Open Government Licence – Canada.",
        },
        "results": {
            "source_rows": row_count, "blank_english_titles": blank_titles,
            "any_family_matched_rows": any_match,
            "family_matched_rows_not_unique_buyers": counts,
            "overlapping_rows": intersections,
        },
        "classification": "WEAK_TITLE_LEVEL_PUBLIC_RECORD_SIGNAL_ONLY",
        "unknown": {
            "original_buyer_requirements": None,
            "rights_or_supplier_eligibility": None,
            "buyer_consent_or_reach": None,
            "future_demand": None,
            "supplier_prices_or_complete_costs": None,
            "real_commerce_or_collections": None,
            "native_trailing365_profit": None,
        },
        "decision": "NO_BID_NO_DEPLOY",
        "interpretation": ("Published awards to other suppliers are not open bids, "
                           "distinct qualified buyers, buyer willingness to pay our "
                           "enterprise, calibrated demand, accepted outputs or profit. "
                           "This title scan cannot admit a flagship."),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    try:
        result = analyze(args.input.read_bytes())
        if args.output.exists():
            raise SourceRejected("OUTPUT_ALREADY_EXISTS")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
        print(json.dumps({"accepted": True, "sha256": result["source"]["sha256"],
                          "rows": result["results"]["source_rows"],
                          "decision": result["decision"]}, sort_keys=True))
        return 0
    except (OSError, SourceRejected) as exc:
        print(f"PUBLIC_EVIDENCE128_REJECTED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
