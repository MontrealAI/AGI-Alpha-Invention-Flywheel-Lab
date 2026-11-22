"""Exact-schema, source-bound public AI Register interop; NO compliance inference.

This is a read-only research bridge from the published CSV to deterministic
record-identity and field-level version witnesses. Source hashes are not
authentication. Governance applicability, human approvals, and economic
benefits cannot be derived from this public register.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

from tools.gc_ai_register231 import Rejected as SourceRejected, scan

SCHEMA = "registry-interop233/public-source-records/v1"
SOURCE_URL = (
    "https://open.canada.ca/data/dataset/"
    "fcbc0200-79ba-4fa4-94a6-00e32facea6b/resource/"
    "369f6f34-148a-42ed-b581-8c164e941a89/download/"
    "gc-ai-register-mvp-registre-de-lia-du-gc-pmv-04-26.csv"
)
EXPECTED_COLUMNS = (
    "ai_register_id", "name_ai_system_en", "name_ai_system_fr",
    "government_organization", "description_ai_system_en",
    "description_ai_system_fr", "ai_system_primary_users_en",
    "ai_system_primary_users_fr", "developed_by_en",
    "developed_by_fr", "vendor_information", "ai_system_status_en",
    "ai_system_status_fr", "status_date", "ai_system_capabilities_en",
    "ai_system_capabilities_fr", "data_sources_en", "data_sources_fr",
    "involves_personal_information", "personal_information_banks_en",
    "personal_information_banks_fr", "notification_ai",
    "ai_system_results_en", "ai_system_results_fr",
)


class Rejected(ValueError):
    """An unsupported or inconsistent source; never repair data silently."""


def _canon(obj):
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect(raw: bytes, *, source_url=SOURCE_URL, expected_sha256=None):
    """Return minimal publication receipt and nonpublished internal row map.

    The internal rows are used for an in-memory comparison only. No original
    values/descriptions appear in the published snapshot or delta receipts.
    """
    try:
        structural = scan(
            raw, source_url=source_url, expected_sha256=expected_sha256,
            requested_fields=("ai_register_id", "government_organization"),
        )
    except SourceRejected as exc:
        raise Rejected("SOURCE231_" + str(exc)) from exc
    columns = tuple(c["name"] for c in structural["columns"])
    if columns != EXPECTED_COLUMNS:
        raise Rejected("EXACT_SCHEMA_NOT_RECOGNIZED")
    try:
        reader = csv.DictReader(
            io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True
        )
        rows = {}
        count = 0
        for row in reader:
            count += 1
            if None in row or any(value is None for value in row.values()):
                raise Rejected("MALFORMED_RECORD")
            ident = row["ai_register_id"]
            if not ident or ident != ident.strip() or not ident.strip():
                raise Rejected("EMPTY_OR_NONCANONICAL_ID")
            if ident in rows:
                raise Rejected("DUPLICATE_REGISTER_ID")
            if not row["government_organization"].strip():
                raise Rejected("EMPTY_ORGANIZATION")
            if not row["name_ai_system_en"].strip() or not row["name_ai_system_fr"].strip():
                raise Rejected("EMPTY_BILINGUAL_SYSTEM_NAME")
            rows[ident] = row
    except (csv.Error, UnicodeDecodeError) as exc:
        raise Rejected("BAD_CSV") from exc
    if count != structural["row_count"] or count != len(rows):
        raise Rejected("FULL_DENOMINATOR_MISMATCH")
    record_receipts = [
        {"ai_register_id": ident, "record_sha256": _sha(_canon(rows[ident]))}
        for ident in sorted(rows)
    ]
    report = {
        "schema": SCHEMA,
        "source_url_claim": source_url,
        "source_authentication": "UNESTABLISHED_CALLER_SUPPLIED_BYTES",
        "source_sha256": structural["source_sha256"],
        "source_bytes": structural["source_bytes"],
        "column_count": len(columns),
        "row_count": count,
        "id_set_sha256": _sha(_canon(sorted(rows))),
        "record_set_sha256": _sha(_canon(record_receipts)),
        "records": record_receipts,
        "real_governance_policy_or_compliance_claim": "NONE",
        "complete_cost_and_economic_advantage": None,
        "public_raw_descriptions_in_receipt": False,
    }
    report["receipt_sha256"] = _sha(_canon(report))
    return report, rows


def compare(old_raw, new_raw, *, source_url=SOURCE_URL,
            old_expected_sha256=None, new_expected_sha256=None):
    """Exact field changes only; NOT legal/policy impact and NOT date evidence."""
    old, old_rows = inspect(
        old_raw, source_url=source_url, expected_sha256=old_expected_sha256
    )
    new, new_rows = inspect(
        new_raw, source_url=source_url, expected_sha256=new_expected_sha256
    )
    before, after = set(old_rows), set(new_rows)
    added = sorted(after - before)
    removed = sorted(before - after)
    changes = []
    for ident in sorted(before & after):
        fields = [
            {"name": name,
             "previous_value_sha256": _sha(old_rows[ident][name].encode("utf-8")),
             "next_value_sha256": _sha(new_rows[ident][name].encode("utf-8"))}
            for name in EXPECTED_COLUMNS
            if old_rows[ident][name] != new_rows[ident][name]
        ]
        if fields:
            changes.append({"ai_register_id": ident, "changed_fields": fields})
    receipt = {
        "schema": SCHEMA + "/comparison",
        "old_source_sha256": old["source_sha256"],
        "new_source_sha256": new["source_sha256"],
        "old_record_set_sha256": old["record_set_sha256"],
        "new_record_set_sha256": new["record_set_sha256"],
        "old_total_records": old["row_count"],
        "new_total_records": new["row_count"],
        "added_ids": added,
        "removed_ids": removed,
        "changed_records": changes,
        "added_count": len(added),
        "removed_count": len(removed),
        "changed_count": len(changes),
        "unchanged_count": len(before & after) - len(changes),
        "interpretation": "EXACT_PUBLIC_CSV_FIELD_CHANGES_ONLY",
        "historical_official_amendment_proven": False,
        "governance_or_risk_assessment": "NOT_PERFORMED",
        "source_authentication": "UNESTABLISHED_CALLER_SUPPLIED_BYTES",
        "real_customer_and_economic_gain": None,
    }
    receipt["receipt_sha256"] = _sha(_canon(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current_csv", type=Path)
    parser.add_argument("--old-csv", type=Path)
    parser.add_argument("--expect-sha256")
    parser.add_argument("--old-expect-sha256")
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        current = args.current_csv.read_bytes()
        if args.old_csv is None:
            report, _ = inspect(
                current, source_url=args.source_url,
                expected_sha256=args.expect_sha256
            )
        else:
            report = compare(
                args.old_csv.read_bytes(), current,
                source_url=args.source_url,
                old_expected_sha256=args.old_expect_sha256,
                new_expected_sha256=args.expect_sha256
            )
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, sort_keys=True, ensure_ascii=False, indent=2)
            out.write("\n")
        print(
            "REGISTER233_PASS", report.get("row_count",
                report.get("new_total_records")), report["receipt_sha256"]
        )
        return 0
    except (Rejected, OSError, ValueError) as exc:
        print("REGISTER233_REJECTED:" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
