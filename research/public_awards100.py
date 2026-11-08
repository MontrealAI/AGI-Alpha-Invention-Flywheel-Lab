"""Read one public CanadaBuys FY award snapshot into a strictly aggregate, noncommercial receipt.

No account, key, bidder portal, supplier or contact fields are read into the output.
Current source is mutable: this reports one observed byte snapshot, not a historical price.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

URL = "https://canadabuys.canada.ca/opendata/pub/2026-2027-awardNotice-avisAttribution.csv"
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_ROWS = 100_000   # Scoped observation guard, not a universal business-scale ceiling
AI = re.compile(r"\b(?:artificial\s+intelligence|machine\s+learning|generative\s+ai|ai)\b", re.I)
GOV = re.compile(r"\b(?:regulatory|compliance|governance|oversight|audit|traceability)\b", re.I)
CATEGORIES = {"SRV", "SRVTGD", "GD", "CNST"}


def _column(names: list[str], prefix: str, *, lang: str | None = None) -> str | None:
    """Reject ambiguous mappings. CanadaBuys bilingual columns have stable prefixes."""
    candidates = [n for n in names if n.casefold().split("-", 1)[0] == prefix.casefold()
                  and (lang is None or n.casefold().endswith("-" + lang))]
    if len(candidates) > 1:
        raise ValueError("AMBIGUOUS_OFFICIAL_COLUMN")
    return candidates[0] if candidates else None


def _fields(names: list[str]) -> dict[str, str | None]:
    if not names or len(names) != len(set(names)) or any(not n for n in names):
        raise ValueError("DUPLICATE_OR_EMPTY_CSV_HEADER")
    mapped = {}
    # Do not conflate a French translation with an English body.
    for field in ("title", "tenderDescription"):
        en = _column(names, field, lang="eng")
        fr = _column(names, field, lang="fra")
        plain = _column(names, field)
        if en is None and fr is None:
            en = plain
        if en is None:
            raise ValueError("ENGLISH_OFFICIAL_TITLE_OR_DESCRIPTION_MISSING")
        mapped[field] = en
        mapped[field + "_fra"] = fr
    for field in ("contractAmount", "totalContractValue", "contractCurrency", "procurementCategory"):
        mapped[field] = _column(names, field)
    if not (mapped["contractAmount"] or mapped["totalContractValue"]):
        raise ValueError("OFFICIAL_AWARD_AMOUNT_COLUMNS_MISSING")
    if not mapped["contractCurrency"]:
        raise ValueError("OFFICIAL_AWARD_CURRENCY_COLUMN_MISSING")
    if not mapped["procurementCategory"]:
        raise ValueError("OFFICIAL_PROCUREMENT_CATEGORY_MISSING")
    return mapped


def _amount(raw: str) -> str:
    """Only classify values, never add currencies or infer missing values are free."""
    from decimal import Decimal, InvalidOperation
    if raw.strip() == "":
        return "unknown"
    try:
        number = Decimal(raw.strip().replace(",", ""))
        if not number.is_finite() or number < 0:
            raise ValueError("UNUSABLE_OFFICIAL_AMOUNT")
    except InvalidOperation as exc:
        raise ValueError("UNUSABLE_OFFICIAL_AMOUNT") from exc
    return "positive" if number else "unknown"


def aggregate(raw: bytes) -> dict:
    csv.field_size_limit(4 * 1024 * 1024)
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("OFFICIAL_SOURCE_NOT_UTF8") from exc
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        header = next(reader)
        mapping = _fields(header)
        idx = {col: i for i, col in enumerate(header)}
        partitions = Counter()
        disclosure = Counter()
        currency_counts = Counter()
        category_counts = Counter()
        rows = 0
        for row in reader:
            if len(row) != len(header):
                raise ValueError("MALFORMED_AWARD_ROW")
            rows += 1
            if rows > MAX_ROWS:
                raise ValueError("SCOPED_ROW_LIMIT")
            def get(field: str) -> str:
                col = mapping[field]
                return row[idx[col]] if col else ""
            title = get("title") or get("title_fra")
            description = get("tenderDescription") or get("tenderDescription_fra")
            text = title + "\n" + description
            a, g = bool(AI.search(text)), bool(GOV.search(text))
            classification = "joint_signal" if a and g else "ai_only" if a else "governance_only" if g else "neither"
            partitions[classification] += 1
            category = get("procurementCategory")
            listed = {v for v in re.split(r"[\s,*]+", category) if v}
            if not listed.issubset(CATEGORIES):
                category_counts["unknown_or_new_category"] += 1
            for code in listed & CATEGORIES:
                if classification == "joint_signal":
                    category_counts[code] += 1
            first = _amount(get("contractAmount"))
            second = _amount(get("totalContractValue"))
            if first == "positive" or second == "positive":
                disclosure["at_least_one_positive_disclosed_field"] += 1
                currency_counts[(get("contractCurrency") or "CURRENCY_UNDISCLOSED").upper()] += 1
                if first == "positive" and second == "positive" and get("contractAmount") != get("totalContractValue"):
                    disclosure["two_field_text_disagreement_not_reconciled"] += 1
            else:
                disclosure["unknown_or_zero_not_free"] += 1
        if not rows:
            raise ValueError("EMPTY_AWARD_SNAPSHOT")
        if sum(partitions.values()) != rows or sum(disclosure.get(x, 0) for x in
                ("at_least_one_positive_disclosed_field", "unknown_or_zero_not_free")) != rows:
            raise ValueError("AGGREGATE_DENOMINATOR_MISMATCH")
        return {
            "rows_observed": rows,
            "lexical_classes": {key: partitions[key] for key in
                               ("joint_signal", "ai_only", "governance_only", "neither")},
            "category_occurrences_among_joint_notices": {key: category_counts[key] for key in
                            ("SRV", "SRVTGD", "GD", "CNST", "unknown_or_new_category")},
            "award_value_disclosure": {key: disclosure[key] for key in
                       ("at_least_one_positive_disclosed_field", "unknown_or_zero_not_free",
                        "two_field_text_disagreement_not_reconciled")},
            "currency_labels_for_positive_disclosed_fields": dict(sorted(currency_counts.items())),
            "schema": {"column_count": len(header),
                       "selected_field_names": {k: v for k, v in mapping.items() if v is not None}},
            "unit": "award notice row; not contract count, unique buyer, collected revenue or annualized spend",
        }
    except (csv.Error, StopIteration) as exc:
        raise ValueError("INVALID_OFFICIAL_CSV") from exc


def observe() -> dict:
    parsed = urlparse(URL)
    if parsed.scheme != "https" or parsed.hostname != "canadabuys.canada.ca":
        raise ValueError("SOURCE_HOST_NOT_PERMITTED")
    req = Request(URL, headers={"User-Agent": "AGIALPHA/0.1", "Accept": "text/csv"})
    with urlopen(req, timeout=90) as response:
        last = urlparse(response.geturl())
        if response.status != 200 or last.scheme != "https" or last.hostname != parsed.hostname:
            raise ValueError("OFFICIAL_GET_ORIGIN_CHANGED")
        payload = response.read(MAX_SOURCE_BYTES + 1)
        if len(payload) > MAX_SOURCE_BYTES:
            raise ValueError("OFFICIAL_SOURCE_EXCEEDS_SCOPED_BYTE_GUARD")
        return {"source_sha256": hashlib.sha256(payload).hexdigest(),
                "source_bytes": len(payload),
                "response_last_modified_unverified": response.headers.get("Last-Modified"),
                **aggregate(payload)}


def run(path: Path) -> dict:
    if path.exists() or path.is_symlink():
        raise FileExistsError("CREATE_ONLY_PUBLIC_AWARD_RECEIPT")
    started = time.perf_counter()
    cpu = time.process_time()
    report = {
        "schema": "agi-alpha/public-award-evidence100/v1",
        "source": URL,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED",
        "scope": "OFFICIAL_PUBLIC_AWARD_SNAPSHOT_LEXICAL_COUNTS_ONLY",
        "buyer_acceptance": "NOT_ESTABLISHED",
        "paid_contract_for_agi_alpha": "NONE_OBSERVED",
        "native_profit": None,
        "complete_costs": "UNKNOWN",
        "actual_model_and_host_billing": "UNKNOWN",
        "commercial_decision": "NO_BID_NO_DEPLOY",
    }
    try:
        report.update(observe())
        report["status"] = "ACCEPTED_OBSERVATIONAL_MEASUREMENT"
    except (ValueError, OSError, UnicodeError) as exc:
        report["error_class"] = type(exc).__name__
        report["error_code"] = str(exc)[:140] if isinstance(exc, ValueError) else "OFFICIAL_PUBLIC_GET_UNAVAILABLE"
    finally:
        report["process_cpu_seconds"] = round(time.process_time() - cpu, 6)
        report["wall_seconds"] = round(time.perf_counter() - started, 6)
        report["limitations"] = [
            "Mutable FY2026-27 federal awards only; not a full year, annual spending or all buyers",
            "Lexical matches may be false positives; do not infer reachable or actual customers",
            "Published positive award values are not our prices, cash collections or margins",
            "Amount zero/blank is unknown/not disclosed, not a free contract",
            "No supplier, contacts, private fields, descriptions or CSV are exported",
            "No bid, eligibility, financing, qualified production or economic advantage",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"status": result["status"], "source_sha256": result.get("source_sha256"),
                      "rows": result.get("rows_observed"), "error": result.get("error_code")}, sort_keys=True))
    return 0 if result["status"] == "ACCEPTED_OBSERVATIONAL_MEASUREMENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
