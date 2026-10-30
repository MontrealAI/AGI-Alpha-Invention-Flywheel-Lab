"""Bounded receivables reconciliation; no external accounts or payment execution."""
import csv
import hashlib
import io
import json
from pathlib import Path

SCOPE = "SYNTHETIC_PUBLIC_WORKLOAD"
MAX_CENTS = 10**14


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 200


def validate(order):
    if not isinstance(order, dict) or order.get("scope") != SCOPE or order.get("currency") != "USD":
        raise ValueError("service requires explicitly public synthetic USD workload")
    if not _text(order.get("order_id")) or type(order.get("require_complete", False)) is not bool:
        raise ValueError("invalid order identity or completeness requirement")
    for key in ("invoices", "payments"):
        rows = order.get(key)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
            raise ValueError("each table requires 1..50 rows")
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not _text(row.get("id")) or row["id"] in ids or not _text(row.get("customer")):
                raise ValueError("invalid or duplicate row identity")
            if row.get("currency", "USD") != "USD":
                raise ValueError("incompatible row currency")
            if type(row.get("amount_cents")) is not int or not 0 < row["amount_cents"] <= MAX_CENTS:
                raise ValueError("positive bounded integer cents required; reversals are outside scope")
            ids.add(row["id"])
    inv = {x["id"]: x for x in order["invoices"]}
    for pay in order["payments"]:
        refs = pay.get("invoice_refs")
        if not isinstance(refs, list) or any(not _text(x) for x in refs) or len(refs) != len(set(refs)):
            raise ValueError("payment requires explicit unique invoice_refs array")
        if any(x not in inv or inv[x]["customer"] != pay["customer"] for x in refs):
            raise ValueError("unknown invoice reference or customer mismatch")
    return order


def reconcile(order):
    validate(order)
    invoices = {x["id"]: x for x in order["invoices"]}
    payments = {x["id"]: x for x in order["payments"]}
    groups = {}
    for pay in payments.values():
        if pay["invoice_refs"]:
            groups.setdefault(tuple(sorted(pay["invoice_refs"])), []).append(pay["id"])
    exact = []
    for refs, pids in groups.items():
        ic = sum(invoices[x]["amount_cents"] for x in refs)
        pc = sum(payments[x]["amount_cents"] for x in pids)
        if ic == pc:
            exact.append((refs, tuple(sorted(pids)), ic))
    contested = set().union(*(set(g[0]) for g in exact if any(g is not h and set(g[0]) & set(h[0]) for h in exact)))
    safe = [g for g in exact if not set(g[0]) & contested]
    matches = []
    used_i, used_p = set(), set()
    for refs, pids, amount in safe:
        matches.append({"invoice_ids": list(refs), "payment_ids": list(pids), "invoice_cents": amount, "payment_cents": amount, "status": "MATCHED"})
        used_i.update(refs)
        used_p.update(pids)
    implicit = {}
    for pay in payments.values():
        if not pay["invoice_refs"]:
            for inv in invoices.values():
                if inv["id"] not in used_i and inv["id"] not in contested and inv["customer"] == pay["customer"] and inv["amount_cents"] == pay["amount_cents"]:
                    implicit.setdefault(pay["id"], []).append(inv["id"])
    inverse = {}
    for pid, iids in implicit.items():
        for iid in iids:
            inverse.setdefault(iid, []).append(pid)
    for pid, iids in sorted(implicit.items()):
        if len(iids) == 1 and len(inverse[iids[0]]) == 1:
            iid = iids[0]
            amount = invoices[iid]["amount_cents"]
            matches.append({"invoice_ids": [iid], "payment_ids": [pid], "invoice_cents": amount, "payment_cents": amount, "status": "MATCHED"})
            used_i.add(iid)
            used_p.add(pid)
    ui, up = sorted(set(invoices) - used_i), sorted(set(payments) - used_p)
    totals = {"invoice_cents": sum(x["amount_cents"] for x in invoices.values()), "payment_cents": sum(x["amount_cents"] for x in payments.values()), "matched_invoice_cents": sum(invoices[x]["amount_cents"] for x in used_i), "matched_payment_cents": sum(payments[x]["amount_cents"] for x in used_p), "open_invoice_cents": sum(invoices[x]["amount_cents"] for x in ui), "unallocated_payment_cents": sum(payments[x]["amount_cents"] for x in up)}
    return {"order_id": order["order_id"], "scope": SCOPE, "currency": "USD", "matches": sorted(matches, key=lambda x: x["invoice_ids"]), "unmatched_invoices": ui, "unmatched_payments": up, "exceptions": [{"kind": "UNMATCHED_INVOICE", "id": x} for x in ui] + [{"kind": "UNMATCHED_PAYMENT", "id": x} for x in up], "totals": totals, "accepted": not order.get("require_complete", False) or not (ui or up)}


def exception_csv(report):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(["order_id", "kind", "row_id"])
    writer.writerows((report["order_id"], x["kind"], x["id"]) for x in report["exceptions"])
    return out.getvalue()


def deliver(order, output):
    """Produce reviewable files; refuse all overwrite including directory reuse."""
    report = reconcile(order)
    target = Path(output)
    target.mkdir(parents=True, exist_ok=False)
    (target / "reconciliation.json").write_bytes(canonical(report))
    (target / "exceptions.csv").write_text(exception_csv(report), encoding="utf-8")
    return report
