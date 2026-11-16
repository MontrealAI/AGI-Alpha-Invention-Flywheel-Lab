"""CONTRACT VALUE Ω — private-enterprise supplier billing assurance.

Local-only, standard-library financial screening. Outputs REVIEW CANDIDATES,
never an assertion that a refund is legally owed, accepted or collected.
Rate/usage rules must be transcribed from verified primary evidence and signed
off by an authorized buyer. No network, model API, payments or vendor contact.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re

SCHEMA="montreal-ai/contract-value-omega/1.0"
HEADERS={
    "contracts.csv":("contract_id","supplier_id","service_code","currency","valid_from","valid_to","max_unit_rate","term_ref"),
    "invoices.csv":("line_id","invoice_id","supplier_id","supplier_invoice_no","invoice_date","service_period","service_code","quantity","unit_rate","line_amount","currency","invoice_ref"),
    "usage.csv":("supplier_id","service_code","service_period","billable_quantity","usage_ref"),
    "payments.csv":("payment_id","invoice_id","paid_amount","currency","payment_ref"),
    "credits.csv":("credit_id","line_id","credit_amount","currency","credit_ref")
}
DOLLAR=re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")
WHOLE=re.compile(r"^(?:0|[1-9][0-9]*)$")
PERIOD=re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
CURRENCY=re.compile(r"^[A-Z]{3}$")
MAX_ROWS=200000
MAX_BYTES=25_000_000


class InputError(ValueError):
    pass


def money(raw,where):
    if not DOLLAR.fullmatch(raw):
        raise InputError(where+": monetary values must be nonnegative with at most two decimals")
    return int(Decimal(raw)*100)


def quantity(raw,where):
    if not WHOLE.fullmatch(raw):
        raise InputError(where+": integer quantity required")
    value=int(raw)
    if value>10**12:
        raise InputError(where+": quantity too large")
    return value


def day(raw,where):
    try:
        parsed=date.fromisoformat(raw)
    except ValueError as exc:
        raise InputError(where+": invalid ISO date") from exc
    if raw!=parsed.isoformat():
        raise InputError(where+": date must be YYYY-MM-DD")
    return parsed


def period_bounds(raw,where):
    if not PERIOD.fullmatch(raw):
        raise InputError(where+": period must be YYYY-MM")
    year,month=map(int,raw.split("-"))
    first=date(year,month,1)
    if month==12:
        last=date(year,12,31)
    else:
        last=date.fromordinal(date(year,month+1,1).toordinal()-1)
    return first,last


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_table(folder,name):
    path=folder/name
    if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_BYTES:
        raise InputError("Missing, linked, or oversized input: "+name)
    raw=path.read_bytes()
    try:
        content=raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError(name+": expected UTF-8") from exc
    parser=csv.DictReader(io.StringIO(content,newline=""))
    actual=parser.fieldnames
    if actual is None or len(actual)!=len(set(actual)) or any(h not in actual for h in HEADERS[name]):
        raise InputError(name+": expected required columns "+",".join(HEADERS[name]))
    rows=[]
    for number,row in enumerate(parser,start=2):
        if number>MAX_ROWS+1:
            raise InputError(name+": row limit")
        if None in row or any(value is None for value in row.values()):
            raise InputError(f"{name}:{number}: malformed CSV")
        cleaned={key:row[key].strip() for key in HEADERS[name]}
        cleaned["_source_file"]=name
        cleaned["_source_row"]=number
        rows.append(cleaned)
    return rows,{"sha256":digest(raw),"rows":len(rows),"bytes":len(raw)}


def require_id(raw,where):
    if not raw or len(raw)>160 or any(ord(c)<32 for c in raw):
        raise InputError(where+": missing or invalid identity")
    return raw


def currency(raw,where):
    if not CURRENCY.fullmatch(raw):
        raise InputError(where+": currency must be ISO-like three uppercase letters")
    return raw


def validate(folder):
    folder=Path(folder)
    if not folder.is_dir():
        raise InputError("Input directory does not exist")
    tables={};sources={}
    for name in HEADERS:
        tables[name],sources[name]=read_table(folder,name)
    contracts=[];contract_ids=set()
    for x in tables["contracts.csv"]:
        where=f"contracts.csv:{x['_source_row']}"
        for k in ("contract_id","supplier_id","service_code","term_ref"):
            require_id(x[k],where+" "+k)
        currency(x["currency"],where)
        start=day(x["valid_from"],where)
        end=day(x["valid_to"],where)
        if start>end:
            raise InputError(where+": inverted contract period")
        identity=(x["contract_id"],x["supplier_id"],x["service_code"],x["currency"],x["valid_from"],x["valid_to"])
        if identity in contract_ids:
            raise InputError(where+": duplicate contract rule")
        contract_ids.add(identity)
        x["_start"]=start;x["_end"]=end
        x["_max_rate_cents"]=money(x["max_unit_rate"],where)
        contracts.append(x)
    invoices=[];lines={};grouping={}
    for x in tables["invoices.csv"]:
        where=f"invoices.csv:{x['_source_row']}"
        for k in ("line_id","invoice_id","supplier_id","supplier_invoice_no","service_code","invoice_ref"):
            require_id(x[k],where+" "+k)
        if x["line_id"] in lines:
            raise InputError(where+": duplicate line_id")
        day(x["invoice_date"],where)
        period_bounds(x["service_period"],where)
        currency(x["currency"],where)
        q=quantity(x["quantity"],where)
        rate=money(x["unit_rate"],where)
        total=money(x["line_amount"],where)
        if total!=q*rate:
            raise InputError(where+": line amount must equal quantity x unit rate, before tax")
        x["_quantity"]=q;x["_rate_cents"]=rate;x["_amount_cents"]=total
        invoices.append(x);lines[x["line_id"]]=x
        grouping.setdefault(x["invoice_id"],[]).append(x)
    if not invoices:
        raise InputError("At least one invoice line is required")
    invoice_totals={}
    invoice_keys={}
    for invoice_id,entries in grouping.items():
        first=entries[0]
        header=(first["supplier_id"],first["supplier_invoice_no"],first["invoice_date"],first["currency"])
        if any((r["supplier_id"],r["supplier_invoice_no"],r["invoice_date"],r["currency"])!=header for r in entries):
            raise InputError("Inconsistent header across lines of invoice_id "+invoice_id)
        invoice_totals[invoice_id]=sum(r["_amount_cents"] for r in entries)
        # Exact duplicate of entire supplier document, NOT simply matching a service or amount.
        fingerprint=tuple(sorted((r["service_code"],r["service_period"],r["_quantity"],r["_rate_cents"],r["_amount_cents"]) for r in entries))
        invoice_keys[invoice_id]=(first["supplier_id"],first["supplier_invoice_no"],first["currency"],fingerprint)
    seen_documents={};duplicates=set()
    for invoice_id in sorted(grouping,key=lambda i:(grouping[i][0]["invoice_date"],i)):
        key=invoice_keys[invoice_id]
        if key in seen_documents:
            duplicates.add(invoice_id)
        else:
            seen_documents[key]=invoice_id
    entitlements={}
    for x in tables["usage.csv"]:
        where=f"usage.csv:{x['_source_row']}"
        for k in ("supplier_id","service_code","usage_ref"):
            require_id(x[k],where+" "+k)
        period_bounds(x["service_period"],where)
        key=(x["supplier_id"],x["service_code"],x["service_period"])
        if key in entitlements:
            raise InputError(where+": ambiguous multiple independent usage limits for the same period")
        x["_limit"]=quantity(x["billable_quantity"],where)
        entitlements[key]=x
    payments={};payment_ids=set()
    for x in tables["payments.csv"]:
        where=f"payments.csv:{x['_source_row']}"
        for k in ("payment_id","invoice_id","payment_ref"):
            require_id(x[k],where+" "+k)
        if x["payment_id"] in payment_ids:
            raise InputError(where+": duplicate payment identifier")
        payment_ids.add(x["payment_id"])
        if x["invoice_id"] not in grouping:
            raise InputError(where+": unknown invoice_id")
        currency(x["currency"],where)
        if x["currency"]!=grouping[x["invoice_id"]][0]["currency"]:
            raise InputError(where+": currency mismatch")
        x["_amount_cents"]=money(x["paid_amount"],where)
        payments[x["invoice_id"]]=payments.get(x["invoice_id"],0)+x["_amount_cents"]
    credits={};credit_ids=set()
    for x in tables["credits.csv"]:
        where=f"credits.csv:{x['_source_row']}"
        for k in ("credit_id","line_id","credit_ref"):
            require_id(x[k],where+" "+k)
        if x["credit_id"] in credit_ids:
            raise InputError(where+": duplicate credit identifier")
        credit_ids.add(x["credit_id"])
        if x["line_id"] not in lines:
            raise InputError(where+": unknown invoice line")
        currency(x["currency"],where)
        if x["currency"]!=lines[x["line_id"]]["currency"]:
            raise InputError(where+": currency mismatch")
        amt=money(x["credit_amount"],where)
        credits[x["line_id"]]=credits.get(x["line_id"],0)+amt
        if credits[x["line_id"]]>lines[x["line_id"]]["_amount_cents"]:
            raise InputError(where+": credits exceed line amount")
    return {"contracts":contracts,"invoices":invoices,"grouping":grouping,
            "invoice_totals":invoice_totals,"duplicates":duplicates,
            "entitlements":entitlements,"payments":payments,"credits":credits,
            "sources":sources}


def audit(loaded):
    # The candidate set is line-level and non-additive categories are resolved
    # by a SINGLE expected-charge formula per line. Duplicates are full-line
    # candidates; they do not additionally consume usage quota.
    used={};items=[]
    for x in sorted(loaded["invoices"],key=lambda r:(r["invoice_date"],r["invoice_id"],r["line_id"])):
        key=(x["supplier_id"],x["service_code"],x["service_period"])
        lo,hi=period_bounds(x["service_period"],"invoice period")
        matching=[r for r in loaded["contracts"]
                  if r["supplier_id"]==x["supplier_id"] and r["service_code"]==x["service_code"]
                  and r["currency"]==x["currency"] and r["_start"]<=lo and r["_end"]>=hi]
        contract=matching[0] if len(matching)==1 else None
        usage=loaded["entitlements"].get(key)
        dupe=x["invoice_id"] in loaded["duplicates"]
        reasons=[];expected=x["_amount_cents"];qty_allowed=None;rate_allowed=None
        if len(matching)!=1:
            reasons.append("MISSING_OR_AMBIGUOUS_CONTRACT")
        if dupe:
            reasons.append("EXACT_DUPLICATE_SUPPLIER_DOCUMENT")
            expected=0
            # Existing duplicate does not consume additional authorized usage.
        elif contract:
            rate_allowed=min(x["_rate_cents"],contract["_max_rate_cents"])
            qty_allowed=x["_quantity"]
            if usage:
                available=max(0,usage["_limit"]-used.get(key,0))
                qty_allowed=min(x["_quantity"],available)
                used[key]=used.get(key,0)+qty_allowed
                if qty_allowed<x["_quantity"]:
                    reasons.append("ABOVE_EVIDENCED_BILLABLE_QUANTITY")
            else:
                # NO guess of billable quantity from invoice quantity alone.
                reasons.append("QUANTITY_EVIDENCE_NOT_PROVIDED")
            if rate_allowed<x["_rate_cents"]:
                reasons.append("CONTRACT_UNIT_RATE_EXCEEDED")
            expected=qty_allowed*rate_allowed
        gross=max(0,x["_amount_cents"]-expected)
        applied=loaded["credits"].get(x["line_id"],0)
        net=max(0,gross-applied)
        paid=loaded["payments"].get(x["invoice_id"],0)
        invoice_total=loaded["invoice_totals"][x["invoice_id"]]
        if paid>invoice_total:
            payment_state="PAYMENTS_EXCEED_INVOICE_RECONCILE"
        elif paid>=invoice_total:
            payment_state="FULL_PAYMENT_RECORDED"
        elif paid>0:
            payment_state="PARTIAL_PAYMENT_UNALLOCATED"
        else:
            payment_state="NO_PAYMENT_IN_SUPPLIED_EXPORT"
        if net:
            decision=("PAID_REVIEW_CANDIDATE" if payment_state=="FULL_PAYMENT_RECORDED"
                      else "PREPAYMENT_OR_PAYMENT_EVIDENCE_REVIEW")
        elif "MISSING_OR_AMBIGUOUS_CONTRACT" in reasons or "QUANTITY_EVIDENCE_NOT_PROVIDED" in reasons:
            decision="EVIDENCE_GAP"
        else:
            decision="NO_QUANTIFIED_DISCREPANCY"
        evidence={
            "invoice":f"invoices.csv:{x['_source_row']}",
            "contract":None if not contract else f"contracts.csv:{contract['_source_row']}",
            "usage":None if not usage else f"usage.csv:{usage['_source_row']}",
            "invoice_ref":x["invoice_ref"],
            "term_ref":None if not contract else contract["term_ref"],
            "usage_ref":None if not usage else usage["usage_ref"]
        }
        items.append({
            "line_id":x["line_id"],"invoice_id":x["invoice_id"],"supplier_id":x["supplier_id"],
            "supplier_invoice_no":x["supplier_invoice_no"],"service_code":x["service_code"],
            "service_period":x["service_period"],"currency":x["currency"],
            "billed_cents":x["_amount_cents"],"expected_cents":expected,
            "gross_discrepancy_cents":gross,"applied_credit_cents":applied,
            "net_review_cents":net,"billed_quantity":x["_quantity"],
            "max_evidenced_quantity":qty_allowed,
            "max_contract_unit_rate_cents":None if not contract else contract["_max_rate_cents"],
            "reasons":reasons,"decision":decision,"payment_state":payment_state,
            "evidence":evidence
        })
    summary={}
    for x in items:
        bucket=summary.setdefault(x["currency"],{
            "billed_cents":0,"gross_review_cents":0,"net_review_cents":0,
            "paid_review_cents":0,"unpaid_or_unclear_review_cents":0,
            "candidate_lines":0,"evidence_gaps":0,"realized_recoveries_cents":0
        })
        bucket["billed_cents"]+=x["billed_cents"]
        bucket["gross_review_cents"]+=x["gross_discrepancy_cents"]
        bucket["net_review_cents"]+=x["net_review_cents"]
        if x["net_review_cents"]:
            bucket["candidate_lines"]+=1
            if x["decision"]=="PAID_REVIEW_CANDIDATE":
                bucket["paid_review_cents"]+=x["net_review_cents"]
            else:
                bucket["unpaid_or_unclear_review_cents"]+=x["net_review_cents"]
        if x["decision"]=="EVIDENCE_GAP":
            bucket["evidence_gaps"]+=1
    return {"schema":SCHEMA,"input_manifest":loaded["sources"],
            "status":"SCREENED_NOT_VALIDATED_OR_COLLECTED",
            "summary_by_currency":summary,
            "rows_screened":len(items),
            "all_lines":items,
            "scope":"Private business, structured monthly service invoices; pre-tax, nonnegative lines and independently supplied terms/usage/payment/credit exports.",
            "exclusions":["Legal entitlement to refund not established",
                          "Unpaid/partially-paid payment status not independently confirmed",
                          "Credits are subtracted from candidate amounts but not proof of settlement",
                          "No PDF/OCR/contract interpretation; operator signs off structured extracts",
                          "No services marked delivered solely on the basis of an invoice",
                          "No supplier contacted; no money collected; no commercial ROI demonstrated",
                          "No FX conversions; currencies remain isolated"]}


def canonical(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode("utf-8")
