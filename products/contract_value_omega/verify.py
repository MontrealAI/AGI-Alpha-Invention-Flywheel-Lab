"""Independent-style evidence reconciliation for CONTRACT VALUE Ω.

Separate financial arithmetic and input/output integrity checks; does not
import the finding constructor. Not a third-party attestation, contract
interpretation, legal opinion, or verification of supplier source documents.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

from .core import InputError,validate


def demand(ok,message):
    if not ok:
        raise InputError("VERIFIER_REJECTED: "+message)


def verify(input_dir,report_dir):
    origin=validate(input_dir)
    out=Path(report_dir)
    receipt=json.loads((out/"SHA256SUMS.json").read_text("utf-8"))
    demand(receipt["schema"]=="montreal-ai/contract-value-omega/output-checksums/v1","manifest schema")
    for filename,sha in receipt["files"].items():
        candidate=(out/filename)
        demand(candidate.resolve().is_relative_to(out.resolve()),"path traversal")
        demand(candidate.is_file() and not candidate.is_symlink(),"missing or linked report")
        demand(hashlib.sha256(candidate.read_bytes()).hexdigest()==sha,"modified report "+filename)
    demand(receipt["input_sha256"]=={k:v["sha256"] for k,v in origin["sources"].items()},
           "inputs modified since audit")
    result=json.loads((out/"audit.json").read_text("utf-8"))
    demand(result["schema"]=="montreal-ai/contract-value-omega/1.0","audit schema")
    demand(result["status"]=="SCREENED_NOT_VALIDATED_OR_COLLECTED","claim scope changed")
    demand(result["input_manifest"]==origin["sources"],"source manifest mismatch")
    lines=result["all_lines"]
    originals={x["line_id"]:x for x in origin["invoices"]}
    demand(len(lines)==len(originals),"line coverage")
    demand(set(x["line_id"] for x in lines)==set(originals),"different lines")
    demand(len(set(x["line_id"] for x in lines))==len(lines),"repeated line")
    counters={};reconstructed={}
    for x in lines:
        raw=originals[x["line_id"]]
        iso=x["currency"]
        demand(x["invoice_id"]==raw["invoice_id"] and x["supplier_id"]==raw["supplier_id"] and
               x["service_code"]==raw["service_code"] and x["service_period"]==raw["service_period"] and
               iso==raw["currency"],"line identity changed")
        demand(x["billed_cents"]==raw["_quantity"]*raw["_rate_cents"],"billed amount changed")
        billed=x["billed_cents"];expected=x["expected_cents"];gross=x["gross_discrepancy_cents"]
        credit=x["applied_credit_cents"];net=x["net_review_cents"]
        demand(all(type(a) is int and a>=0 for a in (billed,expected,gross,credit,net)),"invalid cents")
        demand(expected<=billed and billed-expected==gross,"gross/expected arithmetic")
        demand(net==max(0,gross-credit) and credit==origin["credits"].get(x["line_id"],0),"credit arithmetic")
        demand(not ("EXACT_DUPLICATE_SUPPLIER_DOCUMENT" in x["reasons"]) or
               raw["invoice_id"] in origin["duplicates"],"fake duplicate")
        demand(x["evidence"]["invoice"]==f"invoices.csv:{raw['_source_row']}" and
               x["evidence"]["invoice_ref"]==raw["invoice_ref"],"evidence path changed")
        pay=origin["payments"].get(raw["invoice_id"],0)
        total=origin["invoice_totals"][raw["invoice_id"]]
        category=("PAYMENTS_EXCEED_INVOICE_RECONCILE" if pay>total
                  else "FULL_PAYMENT_RECORDED" if pay>=total
                  else "PARTIAL_PAYMENT_UNALLOCATED" if pay>0
                  else "NO_PAYMENT_IN_SUPPLIED_EXPORT")
        demand(category==x["payment_state"],"payment evidence mismatch")
        if net:
            wanted="PAID_REVIEW_CANDIDATE" if category=="FULL_PAYMENT_RECORDED" else "PREPAYMENT_OR_PAYMENT_EVIDENCE_REVIEW"
            demand(x["decision"]==wanted,"inconsistent review decision")
        bucket=counters.setdefault(iso,{
            "billed_cents":0,"gross_review_cents":0,"net_review_cents":0,
            "paid_review_cents":0,"unpaid_or_unclear_review_cents":0,
            "candidate_lines":0,"evidence_gaps":0,"realized_recoveries_cents":0
        })
        bucket["billed_cents"]+=billed
        bucket["gross_review_cents"]+=gross
        bucket["net_review_cents"]+=net
        if net:
            bucket["candidate_lines"]+=1
            amount_key="paid_review_cents" if x["decision"]=="PAID_REVIEW_CANDIDATE" else "unpaid_or_unclear_review_cents"
            bucket[amount_key]+=net
        if x["decision"]=="EVIDENCE_GAP":
            bucket["evidence_gaps"]+=1
        reconstructed[x["line_id"]]=x
    demand(counters==result["summary_by_currency"],"aggregate mismatch")
    summary=json.loads((out/"summary.json").read_text("utf-8"))
    demand(summary=={k:v for k,v in result.items() if k!="all_lines"},"summary mismatch")
    with (out/"review.csv").open(newline="",encoding="utf-8") as f:
        review=list(csv.DictReader(f))
    expected={r["line_id"] for r in lines if r["net_review_cents"]>0 or r["decision"]=="EVIDENCE_GAP"}
    demand({r["line_id"] for r in review}==expected and len(review)==len(expected),
           "review CSV coverage mismatch")
    for r in review:
        x=reconstructed[r["line_id"]]
        demand(r["decision"]==x["decision"] and r["payment_state"]==x["payment_state"],
               "review CSV decision altered")
        # Decimal string exactly matches source integer cents, no float comparisons.
        cents=x["net_review_cents"]
        demand(r["net_review_amount"].replace(",","")==f"{cents//100}.{cents%100:02d}",
               "review CSV currency value changed")
        demand(r["vendor_confirmed"]=="NO" and r["cash_recovered"]=="0.00",
               "fabricated claims or cash collections")
    return {"status":"PASS_SCOPED_BUYER_SCREEN_RECONCILIATION",
            "source_files":len(origin["sources"]),"lines":len(lines),
            "review_lines":len(review),"summary_by_currency":counters,
            "not_proved":"Signed contract applicability; supplier delivery; right to refund; cash actually collected; independent external audit."}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(verify(args.input,args.report),indent=2,sort_keys=True))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("VERIFICATION_FAILED:",exc,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
