"""Independent source-derived replay for CONTRACT VALUE Omega buyer reports.

Supplemental math and deterministic report consistency, NOT an attestation or
authority to approve supplier claims. Reuses the original CSV schema/parser and
presentation writer but does not use core.audit() to derive financial findings.
No network, credentials, money transfers or supplier contact.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from . import run, verify
from .core import InputError, period_bounds, validate


def demand(test, explanation):
    if not test:
        raise InputError("SOURCE_REPLAY_REJECTED: " + explanation)


def no_duplicate_json(path: Path):
    def object_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise InputError("SOURCE_REPLAY_REJECTED: duplicate JSON field " + key)
            obj[key] = value
        return obj
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs)


def independently_derived_duplicates(src):
    seen = set()
    duplicate = set()
    for invoice_id, group in sorted(
        src["grouping"].items(), key=lambda item: (item[1][0]["invoice_date"], item[0])
    ):
        first = group[0]
        key = (
            first["supplier_id"], first["supplier_invoice_no"], first["currency"],
            tuple(sorted(
                (x["service_code"], x["service_period"], x["_quantity"],
                 x["_rate_cents"], x["_amount_cents"]) for x in group
            )),
        )
        if key in seen:
            duplicate.add(invoice_id)
        else:
            seen.add(key)
    demand(duplicate == src["duplicates"], "supplier-document duplicate classification")
    return duplicate


def independently_derived_lines(src):
    """Derive contract/usage/duplicate/cash classification without core.audit()."""
    duplicate_invoices = independently_derived_duplicates(src)
    consumed = {}
    rows = []
    for entry in sorted(
        src["invoices"], key=lambda v: (v["invoice_date"], v["invoice_id"], v["line_id"])
    ):
        group_key = (
            entry["supplier_id"], entry["service_code"],
            entry["service_period"], entry["currency"]
        )
        from_day, through_day = period_bounds(entry["service_period"], "replay service period")
        eligible = [
            c for c in src["contracts"]
            if c["supplier_id"] == entry["supplier_id"]
            and c["service_code"] == entry["service_code"]
            and c["currency"] == entry["currency"]
            and c["_start"] <= from_day and c["_end"] >= through_day
        ]
        contract = eligible[0] if len(eligible) == 1 else None
        use = src["entitlements"].get(group_key)
        duplicate = entry["invoice_id"] in duplicate_invoices
        original_charge = entry["_quantity"] * entry["_rate_cents"]
        expected_charge = original_charge
        eligible_quantity = None
        eligible_rate = None
        reasons = []

        if len(eligible) != 1:
            reasons.append("MISSING_OR_AMBIGUOUS_CONTRACT")
        if duplicate:
            reasons.append("EXACT_DUPLICATE_SUPPLIER_DOCUMENT")
            expected_charge = 0
        elif contract is not None:
            eligible_rate = min(entry["_rate_cents"], contract["_max_rate_cents"])
            eligible_quantity = entry["_quantity"]
            if use is not None:
                remaining = max(0, use["_limit"] - consumed.get(group_key, 0))
                eligible_quantity = min(eligible_quantity, remaining)
                consumed[group_key] = consumed.get(group_key, 0) + eligible_quantity
                if eligible_quantity != entry["_quantity"]:
                    reasons.append("ABOVE_EVIDENCED_BILLABLE_QUANTITY")
            else:
                reasons.append("QUANTITY_EVIDENCE_NOT_PROVIDED")
            if eligible_rate != entry["_rate_cents"]:
                reasons.append("CONTRACT_UNIT_RATE_EXCEEDED")
            expected_charge = eligible_quantity * eligible_rate

        gross = max(original_charge - expected_charge, 0)
        credited = src["credits"].get(entry["line_id"], 0)
        net = max(gross - credited, 0)
        amount_paid = src["payments"].get(entry["invoice_id"], 0)
        total_invoice = src["invoice_totals"][entry["invoice_id"]]
        if amount_paid > total_invoice:
            paid_state = "PAYMENTS_EXCEED_INVOICE_RECONCILE"
        elif amount_paid >= total_invoice:
            paid_state = "FULL_PAYMENT_RECORDED"
        elif amount_paid > 0:
            paid_state = "PARTIAL_PAYMENT_UNALLOCATED"
        else:
            paid_state = "NO_PAYMENT_IN_SUPPLIED_EXPORT"

        if net > 0:
            decision = ("PAID_REVIEW_CANDIDATE" if paid_state == "FULL_PAYMENT_RECORDED"
                        else "PREPAYMENT_OR_PAYMENT_EVIDENCE_REVIEW")
        elif "MISSING_OR_AMBIGUOUS_CONTRACT" in reasons or "QUANTITY_EVIDENCE_NOT_PROVIDED" in reasons:
            decision = "EVIDENCE_GAP"
        else:
            decision = "NO_QUANTIFIED_DISCREPANCY"

        evidence = {
            "invoice": f"invoices.csv:{entry['_source_row']}",
            "contract": f"contracts.csv:{contract['_source_row']}" if contract else None,
            "usage": f"usage.csv:{use['_source_row']}" if use else None,
            "invoice_ref": entry["invoice_ref"],
            "term_ref": contract["term_ref"] if contract else None,
            "usage_ref": use["usage_ref"] if use else None,
        }
        rows.append({
            "line_id": entry["line_id"],
            "invoice_id": entry["invoice_id"],
            "supplier_id": entry["supplier_id"],
            "supplier_invoice_no": entry["supplier_invoice_no"],
            "service_code": entry["service_code"],
            "service_period": entry["service_period"],
            "currency": entry["currency"],
            "billed_cents": original_charge,
            "expected_cents": expected_charge,
            "gross_discrepancy_cents": gross,
            "applied_credit_cents": credited,
            "net_review_cents": net,
            "billed_quantity": entry["_quantity"],
            "max_evidenced_quantity": eligible_quantity,
            "max_contract_unit_rate_cents": contract["_max_rate_cents"] if contract else None,
            "reasons": reasons,
            "decision": decision,
            "payment_state": paid_state,
            "evidence": evidence,
        })
    return rows


def verify_report(input_dir, report_dir):
    """Recheck native source-derived money and all buyer-visible report bytes."""
    input_dir, report_dir = Path(input_dir), Path(report_dir)
    demand(report_dir.is_dir() and not report_dir.is_symlink(),
           "report must be a real directory")
    # The old verifier remains an independent guard for input SHA, arithmetic,
    # source matching, CSV scope, currency totals and zero claimed collections.
    base = verify.verify(input_dir, report_dir)
    origin = validate(input_dir)
    actual = no_duplicate_json(report_dir/"audit.json")
    no_duplicate_json(report_dir/"summary.json")
    no_duplicate_json(report_dir/"SHA256SUMS.json")
    expected_lines = independently_derived_lines(origin)
    demand(actual.get("all_lines") == expected_lines,
           "source-derived rate, quantity, duplicate, payment, evidence or decision mismatch")
    demand(actual.get("input_manifest") == origin["sources"],
           "original-source hash and row-count mismatch")

    # A writable SHA256SUMS file cannot authenticate claims made inside the
    # package. Reconstruct ALL presentations (HTML, CSV, supplier packets),
    # then compare exact file bytes, not merely self-reported checksums.
    with TemporaryDirectory(prefix="contract-value-replay-") as temporary:
        shadow = Path(temporary)/"reference"
        run.write(shadow, actual)
        def inventory(folder):
            result = {}
            for path in folder.rglob("*"):
                demand(not path.is_symlink(), "linked report component")
                if path.is_file():
                    result[path.relative_to(folder).as_posix()] = path
            return result
        real_files = inventory(report_dir)
        expected_files = inventory(shadow)
        demand(real_files.keys() == expected_files.keys(),
               "unregistered, missing or additional buyer-side report file")
        for name in sorted(expected_files):
            actual_path, reference_path = real_files[name], expected_files[name]
            demand(actual_path.stat().st_size == reference_path.stat().st_size and
                   hashlib.sha256(actual_path.read_bytes()).digest() ==
                   hashlib.sha256(reference_path.read_bytes()).digest(),
                   "buyer-facing file content differs: " + name)

    return {
        "status": "PASS_SOURCE_DERIVED_FINANCIAL_REPLAY",
        "source_files": len(origin["sources"]),
        "lines": len(expected_lines),
        "summary_by_currency": base["summary_by_currency"],
        "protection": "Source-derived money and deterministic buyer presentations; no trusted signature.",
        "not_proved": "Signed contract interpretation, independently observed delivery, refund rights, cash collection, buyer demand or third-party audit."
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify_report(args.input, args.report), sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("SOURCE_REPLAY_FAILED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
