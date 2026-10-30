"""Independent acceptance checks for the bounded reconciliation service.

This module does not import the producer. It derives required safe matches from
the order, checks row conservation, and rejects summary or partition tampering.
"""
import hashlib
import json
from collections import Counter, defaultdict


def _digest(value):
    try:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError):
        return None


def _read_order(order):
    if not isinstance(order, dict) or order.get("scope") != "SYNTHETIC_PUBLIC_WORKLOAD" or order.get("currency") != "USD":
        raise ValueError("unsupported scope or currency")
    def valid_text(value):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= 200

    if not valid_text(order.get("order_id")):
        raise ValueError("missing order_id")
    if "require_complete" in order and not isinstance(order["require_complete"], bool):
        raise ValueError("require_complete must be boolean")
    records = []
    for field in ("invoices", "payments"):
        rows = order.get(field)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
            raise ValueError("bounded row list required")
        indexed = {}
        for row in rows:
            if not isinstance(row, dict) or not valid_text(row.get("id")) or row["id"] in indexed:
                raise ValueError("invalid or duplicate record id")
            if not valid_text(row.get("customer")):
                raise ValueError("invalid customer")
            if row.get("currency", "USD") != "USD":
                raise ValueError("row currency mismatch")
            cents = row.get("amount_cents")
            if type(cents) is not int or not 0 < cents <= 10**14:
                raise ValueError("positive bounded integer cents required")
            if field == "payments":
                refs = row.get("invoice_refs")
                if not isinstance(refs, list) or any(not valid_text(x) for x in refs) or len(set(refs)) != len(refs):
                    raise ValueError("invalid invoice references")
            indexed[row["id"]] = row
        records.append(indexed)
    for payment in records[1].values():
        if any(i not in records[0] or records[0][i]["customer"] != payment["customer"] for i in payment["invoice_refs"]):
            raise ValueError("unknown invoice reference or customer mismatch")
    return records


def _safe_matches(invoices, payments):
    ref_buckets = defaultdict(list)
    for pid, payment in payments.items():
        if payment["invoice_refs"]:
            ref_buckets[tuple(sorted(payment["invoice_refs"]))].append(pid)
    exact = []
    for refs, pids in ref_buckets.items():
        if not all(i in invoices for i in refs):
            continue
        customers = {invoices[i]["customer"] for i in refs} | {payments[p]["customer"] for p in pids}
        if len(customers) == 1 and sum(invoices[i]["amount_cents"] for i in refs) == sum(payments[p]["amount_cents"] for p in pids):
            exact.append((refs, tuple(sorted(pids))))
    incidence = Counter(i for refs, _ in exact for i in refs)
    matches = [(refs, pids) for refs, pids in exact if all(incidence[i] == 1 for i in refs)]
    used_i = {i for refs, _ in matches for i in refs}
    used_p = {p for _, pids in matches for p in pids}
    contested_i = {i for refs, _ in exact if any(incidence[i] > 1 for i in refs) for i in refs}
    implicit = []
    for pid, payment in payments.items():
        if pid not in used_p and not payment["invoice_refs"]:
            candidates = [iid for iid, invoice in invoices.items() if iid not in used_i | contested_i and invoice["customer"] == payment["customer"] and invoice["amount_cents"] == payment["amount_cents"]]
            implicit.extend((iid, pid) for iid in candidates)
    i_counts = Counter(i for i, _ in implicit)
    p_counts = Counter(p for _, p in implicit)
    matches.extend(((i,), (p,)) for i, p in implicit if i_counts[i] == p_counts[p] == 1)
    return set(matches)


def audit_delivery(order, delivery):
    """Return an independently derived receipt; never trust stored acceptance."""
    errors = []
    try:
        invoices, payments = _read_order(order)
        if not isinstance(delivery, dict):
            raise ValueError("delivery must be object")
        for key in ("scope", "currency", "order_id"):
            if delivery.get(key) != order[key]:
                errors.append("IDENTITY_" + key.upper())
        expected = _safe_matches(invoices, payments)
        observed = set()
        used_i, used_p = [], []
        if not isinstance(delivery.get("matches"), list):
            raise ValueError("matches must be list")
        for match in delivery.get("matches", []):
            if not isinstance(match, dict):
                raise ValueError("invalid match")
            iids, pids = match.get("invoice_ids"), match.get("payment_ids")
            if not isinstance(iids, list) or not isinstance(pids, list) or not iids or not pids:
                raise ValueError("match rows required")
            if any(i not in invoices for i in iids) or any(p not in payments for p in pids):
                raise ValueError("unknown matched row")
            if len(set(iids)) != len(iids) or len(set(pids)) != len(pids):
                errors.append("DUPLICATE_MATCH_ROW")
            invoice_sum = sum(invoices[i]["amount_cents"] for i in iids)
            payment_sum = sum(payments[p]["amount_cents"] for p in pids)
            if invoice_sum != payment_sum or match.get("invoice_cents") != invoice_sum or match.get("payment_cents") != payment_sum or type(match.get("invoice_cents")) is not int or type(match.get("payment_cents")) is not int:
                errors.append("MATCH_AMOUNT")
            if match.get("status") != "MATCHED":
                errors.append("MATCH_STATUS")
            observed.add((tuple(sorted(iids)), tuple(sorted(pids))))
            used_i.extend(iids)
            used_p.extend(pids)
        if observed != expected:
            errors.append("UNSAFE_OR_MISSING_MATCH")
        unmatched_i, unmatched_p = delivery.get("unmatched_invoices"), delivery.get("unmatched_payments")
        if not isinstance(unmatched_i, list) or not isinstance(unmatched_p, list):
            raise ValueError("unmatched schedules required")
        if Counter(used_i + unmatched_i) != Counter(invoices.keys()):
            errors.append("INVOICE_PARTITION")
        if Counter(used_p + unmatched_p) != Counter(payments.keys()):
            errors.append("PAYMENT_PARTITION")
        exception_rows = delivery.get("exceptions")
        if not isinstance(exception_rows, list):
            raise ValueError("exception schedule required")
        exception_keys = [(row.get("kind"), row.get("id")) for row in exception_rows if isinstance(row, dict)]
        expected_exceptions = [("UNMATCHED_INVOICE", x) for x in unmatched_i] + [("UNMATCHED_PAYMENT", x) for x in unmatched_p]
        if len(exception_keys) != len(exception_rows) or Counter(exception_keys) != Counter(expected_exceptions):
            errors.append("EXCEPTION_SCHEDULE")
        sums = {
            "invoice_cents": sum(x["amount_cents"] for x in invoices.values()),
            "payment_cents": sum(x["amount_cents"] for x in payments.values()),
            "matched_invoice_cents": sum(invoices[i]["amount_cents"] for i in used_i),
            "matched_payment_cents": sum(payments[p]["amount_cents"] for p in used_p),
            "open_invoice_cents": sum(invoices[i]["amount_cents"] for i in unmatched_i if i in invoices),
            "unallocated_payment_cents": sum(payments[p]["amount_cents"] for p in unmatched_p if p in payments),
        }
        if delivery.get("totals") != sums or not isinstance(delivery.get("totals"), dict) or any(type(x) is not int for x in delivery.get("totals", {}).values()):
            errors.append("TOTALS")
        if sums["invoice_cents"] != sums["matched_invoice_cents"] + sums["open_invoice_cents"] or sums["payment_cents"] != sums["matched_payment_cents"] + sums["unallocated_payment_cents"]:
            errors.append("CONSERVATION")
        required_complete = not order.get("require_complete", False) or not unmatched_i and not unmatched_p
        if delivery.get("accepted") is not required_complete:
            errors.append("ACCEPTANCE_FIELD")
        if not required_complete:
            errors.append("REQUIRED_COMPLETE_UNMET")
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        errors.append("INVALID: " + str(exc))
    return {
        "order_id": order.get("order_id") if isinstance(order, dict) else None,
        "scope": "SYNTHETIC_PUBLIC_WORKLOAD",
        "accepted": not errors,
        "errors": sorted(set(errors)),
        "input_sha256": _digest(order),
        "delivery_sha256": _digest(delivery),
        "independence": "separate checker implementation; shared host and agent family; no external certification",
    }
