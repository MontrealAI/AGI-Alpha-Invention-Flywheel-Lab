"""Two-period *synthetic* native risk comparison, without simulated approval.

A changed authored observation sample is not, by itself, statistically
significant real-world model drift. Native risk152 remains the sole metric
calculator. No account, authentication, real buyer or compliance authority.
"""
from __future__ import annotations

import argparse
from datetime import date
import hmac
import json
from pathlib import Path
import re

from . import native_risk152 as native

SCHEMA = "agi-alpha/governance-temporal-drift159/input-v1"
RESULT_SCHEMA = "agi-alpha/governance-temporal-drift159/result-v1"
SCOPE = "OFFLINE_SYNTHETIC_TWO_PERIOD_RISK_REASSESSMENT"
FIELDS = {"schema", "system_id", "prior_date", "current_date",
          "thresholds", "prior_rows", "current_rows"}
CLASSIFY = {
    ("WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD", "ADVERSE_SYNTHETIC_THRESHOLD"):
        "NEW_ADVERSE_SYNTHETIC_SIGNAL",
    ("ADVERSE_SYNTHETIC_THRESHOLD", "WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD"):
        "RESOLVED_SYNTHETIC_SIGNAL",
    ("ADVERSE_SYNTHETIC_THRESHOLD", "ADVERSE_SYNTHETIC_THRESHOLD"):
        "PERSISTENT_ADVERSE_SYNTHETIC_SIGNAL",
    ("WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD", "WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD"):
        "BOTH_WITHIN_SYNTHETIC_THRESHOLDS",
}
HASH = re.compile(r"[0-9a-f]{64}\Z")


def _day(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("EXACT_OBSERVATION_DATE_REQUIRED")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("VALID_OBSERVATION_DATE_REQUIRED") from exc
    if d.isoformat() != value:
        raise ValueError("CANONICAL_OBSERVATION_DATE_REQUIRED")
    return d


def _rows(raw):
    if type(raw) is not list or not raw:
        raise ValueError("NONEMPTY_SEPARATE_NATIVE_OBSERVATIONS_REQUIRED")
    if any(type(row) is not dict or "claimed_review" in row for row in raw):
        raise ValueError("UNTRUSTED_REVIEW_CLAIMS_REFUSED")
    return raw


def evaluate(data):
    if type(data) is not dict or set(data) != FIELDS or data["schema"] != SCHEMA:
        raise ValueError("EXACT_TEMPORAL_REASSESSMENT_INPUT_REQUIRED")
    if type(data["system_id"]) is not str or not data["system_id"].strip() or len(data["system_id"]) > 160:
        raise ValueError("VALID_NATIVE_SYSTEM_ID_REQUIRED")
    first, second = _day(data["prior_date"]), _day(data["current_date"])
    if first >= second:
        raise ValueError("STRICTLY_ORDERED_OBSERVATION_PERIODS_REQUIRED")
    earlier, later = _rows(data["prior_rows"]), _rows(data["current_rows"])
    # Original evaluator validates rows, IDs, thresholds, exact ratio arithmetic.
    def native_report(rows):
        return native.evaluate({"schema": native.SCHEMA, "system_id": data["system_id"],
                                "thresholds": data["thresholds"], "rows": rows})
    prior = native_report(earlier)
    current = native_report(later)
    if set(r["case_id"] for r in earlier) & set(r["case_id"] for r in later):
        raise ValueError("REUSED_CASE_ID_CANNOT_COUNT_AS_FRESH_PERIOD")
    def raw_sha(rows):
        return native.digest({"schema": "agi-alpha/temporal-drift159/raw-cases/v1",
                              "system_id": data["system_id"],
                              "rows": sorted(rows, key=lambda r: r["case_id"])})
    prior_digest, current_digest = raw_sha(earlier), raw_sha(later)
    if prior_digest == current_digest:
        raise ValueError("IDENTICAL_RAW_OBSERVATION_CANNOT_BE_NEW_PERIOD")
    outcomes = []
    for metric in native.SCORE_NAMES:
        p = prior["signals"][metric]
        c = current["signals"][metric]
        classification = CLASSIFY.get((p["signal"], c["signal"]), "UNQUALIFIED_OBSERVATION")
        outcomes.append({"metric": metric, "prior": p, "current": c,
                         "classification": classification,
                         "requires_authorized_review": True})
    report = {
        "schema": RESULT_SCHEMA, "scope": SCOPE,
        "system_id": data["system_id"],
        "prior_date": data["prior_date"], "current_date": data["current_date"],
        "policy_sha256": native.digest(data["thresholds"]),
        "prior_raw_sha256": prior_digest, "current_raw_sha256": current_digest,
        "prior_native_receipt_sha256": prior["receipt_sha256"],
        "current_native_receipt_sha256": current["receipt_sha256"],
        "prior_count": prior["case_count"], "current_count": current["case_count"],
        "metric_comparisons": outcomes, "requires_authorized_review": True,
        "authorization": "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_APPROVAL",
        "statistical_inference": "NO_CAUSAL_OR_SIGNIFICANCE_INFERENCE_FROM_AUTHORED_PERIODS",
        "actual_buyer_acceptance": None, "actual_complete_cost_usd": None,
        "limitation": "Synthetic observations; no verified provenance, data permissions, representative field validity, enterprise integration or actual buyer.",
    }
    report["receipt_sha256"] = native.digest(report)
    return report


def verify_receipt(report, *, expected_receipt, expected_prior_raw, expected_current_raw):
    expected = [expected_receipt, expected_prior_raw, expected_current_raw]
    if any(type(v) is not str or HASH.fullmatch(v) is None for v in expected):
        raise ValueError("THREE_INDEPENDENT_SHA256_ANCHORS_REQUIRED")
    if type(report) is not dict or report.get("schema") != RESULT_SCHEMA or report.get("scope") != SCOPE:
        raise ValueError("TEMPORAL_REPORT_SCOPE_CHANGED")
    if report.get("authorization") != "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_APPROVAL":
        raise ValueError("TEMPORAL_AUTHORITY_FABRICATION")
    if not (hmac.compare_digest(str(report.get("prior_raw_sha256", "")), expected_prior_raw)
            and hmac.compare_digest(str(report.get("current_raw_sha256", "")), expected_current_raw)):
        raise ValueError("TEMPORAL_RAW_SOURCE_ANCHOR_MISMATCH")
    data = {k: v for k, v in report.items() if k != "receipt_sha256"}
    if not (hmac.compare_digest(str(report.get("receipt_sha256", "")), expected_receipt)
            and hmac.compare_digest(native.digest(data), expected_receipt)):
        raise ValueError("TEMPORAL_REPORT_ANCHOR_MISMATCH")
    return True


def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("DUPLICATE_JSON_FIELD")
        out[k] = v
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        raise ValueError("INPUT_OUTPUT_MUST_DIFFER")
    if not args.input.is_file() or args.input.is_symlink() or args.input.stat().st_size > 1_000_000:
        raise ValueError("BOUNDED_REGULAR_INPUT_REQUIRED")
    raw = args.input.read_bytes().decode("utf-8", errors="strict")
    data = json.loads(raw, object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    report = evaluate(data)
    with args.output.open("x", encoding="utf-8") as dest:
        json.dump(report, dest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        dest.write("\n")
    print(json.dumps({"receipt_sha256": report["receipt_sha256"], "scope": SCOPE},
                     sort_keys=True))
    return report


if __name__ == "__main__":
    main()
