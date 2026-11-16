"""Local, buyer-operated CONTRACT VALUE Ω review-room builder."""
from __future__ import annotations

import argparse
import csv
from html import escape
import hashlib
import io
import json
from pathlib import Path
import re
import sys

from .core import InputError,audit,canonical,validate


def dollars(cents):
    return f"{cents//100:,}.{cents%100:02d}"


def field(value):
    return escape(str(value or ""),quote=True)


def csv_bytes(rows,columns):
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=columns,lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key:row.get(key,"") for key in columns})
    return stream.getvalue().encode("utf-8")


def review_rows(result):
    for x in result["all_lines"]:
        if x["net_review_cents"]==0 and x["decision"]!="EVIDENCE_GAP":
            continue
        ev=x["evidence"]
        yield {
            "line_id":x["line_id"],"invoice_id":x["invoice_id"],
            "supplier_id":x["supplier_id"],"service_code":x["service_code"],
            "service_period":x["service_period"],"currency":x["currency"],
            "net_review_amount":dollars(x["net_review_cents"]),
            "gross_review_amount":dollars(x["gross_discrepancy_cents"]),
            "applied_credit":dollars(x["applied_credit_cents"]),
            "decision":x["decision"],"payment_state":x["payment_state"],
            "reasons":";".join(x["reasons"]),
            "invoice_source":ev["invoice"],"contract_source":ev["contract"] or "",
            "usage_source":ev["usage"] or "",
            "invoice_ref":ev["invoice_ref"],"term_ref":ev["term_ref"] or "",
            "usage_ref":ev["usage_ref"] or "",
            "vendor_confirmed":"NO","cash_recovered":"0.00"
        }


def report_html(result):
    groups=result["summary_by_currency"]
    currency_cards=[]
    for iso,s in sorted(groups.items()):
        currency_cards.append(f'''<section class="stat" aria-label="{field(iso)} audit summary">
        <div class="kicker">{field(iso)} · SCREENED VALUE</div>
        <strong>{field(dollars(s["net_review_cents"]))}</strong>
        <div class="note">Candidates for review, not savings realized</div>
        <div class="small">Paid records: {field(dollars(s["paid_review_cents"]))} ·
        Unpaid/unclear: {field(dollars(s["unpaid_or_unclear_review_cents"]))}<br>
        Lines requiring review: {s["candidate_lines"]} · Evidence gaps: {s["evidence_gaps"]}</div></section>''')
    rows=[]
    for x in result["all_lines"]:
        if x["net_review_cents"]==0 and x["decision"]!="EVIDENCE_GAP":
            continue
        ev=x["evidence"]
        reasons=", ".join(x["reasons"])
        rows.append("<tr>"+
                    f"<td><strong>{field(x['supplier_id'])}</strong><small>{field(x['invoice_id'])} · {field(x['line_id'])}</small></td>"+
                    f"<td>{field(x['service_code'])}<small>{field(x['service_period'])}</small></td>"+
                    f"<td>{field(x['currency'])} {field(dollars(x['net_review_cents']))}</td>"+
                    f"<td><strong>{field(x['decision'])}</strong><small>{field(x['payment_state'])}</small></td>"+
                    f"<td>{field(reasons)}<small>{field(ev['invoice'])} · {field(ev['invoice_ref'])}</small><small>{field(ev['term_ref'] or 'No verified term reference')} · {field(ev['usage_ref'] or 'No independently evidenced usage')}</small></td>"+
                    "</tr>")
    if not rows:
        rows.append('<tr><td colspan="5">No quantified candidate or evidence gap in the supplied structured scope. This is not a certificate that all supplier charges are correct.</td></tr>')
    file_sources=" · ".join(f'{field(name)} SHA256 {field(meta["sha256"][:16])}…' for name,meta in result["input_manifest"].items())
    doc='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>CONTRACT VALUE Ω | Confidential buyer review</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0c0819;color:#f8f3fc;font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:auto;padding:42px 28px 70px}header{border-bottom:1px solid #53436b;padding-bottom:25px;display:flex;gap:24px;flex-wrap:wrap;align-items:center;justify-content:space-between}
.brand{font-weight:800;letter-spacing:.24em;font-size:.75rem}.brand span{color:#ebcb8d}.stamp{font-size:.69rem;letter-spacing:.14em;text-transform:uppercase;color:#ddc2a1;border:1px solid #746044;border-radius:5px;padding:8px 12px}
h1,h2{font-family:Georgia,serif;font-weight:400;letter-spacing:-.055em}h1{font-size:clamp(3rem,6vw,5.8rem);line-height:.98;margin:50px 0 20px}h1 em{font-style:normal;color:#edcd94}h2{font-size:2.4rem;margin:30px 0 14px}
.lead{font-size:1.1rem;color:#d8cbdc;max-width:800px}.eyebrow{color:#e9c991;letter-spacing:.2em;font-size:.7rem;font-weight:700;text-transform:uppercase}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin:44px 0}
.stat{padding:26px;background:radial-gradient(circle at top right,#3a2358,#1a112d 75%);border:1px solid #5c4378;border-radius:10px}.stat strong{font:400 3rem Georgia,serif;color:#f0d59f;display:block;margin:10px 0}.stat .note{font-size:.85rem;color:#d6c8e1}.small{color:#b9aaca;font-size:.8rem;margin-top:12px}
.panel{border:1px solid #59476a;border-radius:10px;background:#151020;padding:24px;margin-top:30px}
table{width:100%;border-collapse:collapse}th,td{padding:15px 14px;border-bottom:1px solid #51425c;vertical-align:top;text-align:left}
th{text-transform:uppercase;letter-spacing:.1em;font-size:.66rem;color:#e7cf9f}td{font-size:.83rem}td small{display:block;color:#aa9bbd;margin-top:5px;overflow-wrap:anywhere}td strong{color:#f1d39b;font-weight:700}
.scroll{overflow:auto}p,li{overflow-wrap:anywhere}.muted{color:#b9aaca}.pill{display:inline-block;padding:4px 10px;background:#3a244c;border:1px solid #775990;border-radius:20px;font-size:.72rem}
footer{padding-top:25px;margin-top:45px;border-top:1px solid #443551;color:#a99eb9;font-size:.8rem}
@media(max-width:600px){main{padding:22px 16px}.panel{padding:14px}.stats{margin:24px 0}th,td{padding:10px}}
@media print{body{background:#fff;color:#16111d}.stat,.panel{background:#fff;border-color:#999}td strong,.stat strong{color:#302047}.muted,.small,td small{color:#444}}
</style></head><body><main><header><div class="brand">MONTREAL<span>.</span>AI · CONTRACT VALUE Ω</div>
<div class="stamp">Local evidence · Not a collected recovery</div></header>
<div class="eyebrow" style="margin-top:42px">Private-sector contract-to-cash intelligence</div>
<h1>Find the difference.<br><em>Prove the basis.</em></h1>
<p class="lead">An offline, source-bound screening of supplier invoices against structured contract terms, independently supplied billable quantities, recorded payment data and posted credits. These are hypotheses for authorized review—not legal demands, supplier admissions or realized profits.</p>
<div class="stats">'''+"".join(currency_cards)+'''</div>
<section class="panel"><div class="eyebrow">01 · Buyer-controlled findings</div><h2>Review the exact evidence.</h2>
<p class="muted">One combined discrepancy amount per line prevents double-counting rate and quantity issues. Exact duplicates are assigned to the repeated supplier document. Credits are subtracted from candidate exposure. Full-payment classifications depend on the completeness of the buyer's exported ledger.</p>
<div class="scroll"><table><thead><tr><th>Supplier / document</th><th>Service / period</th><th>Review value</th><th>Decision</th><th>Reasons / source references</th></tr></thead><tbody>'''+ "".join(rows)+'''</tbody></table></div></section>
<section class="panel"><div class="eyebrow">02 · What must happen before a claim</div><h2>Verification before negotiation.</h2>
<ol><li>Check the signed agreement and amendments underlying each structured contract rule; confirm rate/quantity rules and effective dates.</li>
<li>Match the original supplier invoice, delivery evidence, payment and issued credit memo. Review tax, minimums, bands, exclusions, service-level provisions and purchase-order authorizations separately.</li>
<li>Resolve missing/ambiguous clauses, shared entitlements, partial payments and any supplier explanations. Reject false positives.</li>
<li>Only an authorized finance/procurement owner may approve a vendor claim or pre-payment hold. This tool never sends one.</li>
<li>Record cash or applied credits separately after independent reconciliation. This report records zero realized recoveries.</li></ol></section>
<section class="panel"><div class="eyebrow">03 · Evidence & privacy</div><h2>Run within your boundary.</h2>
<p class="muted">No external calls, cloud account, AI model API, uploads, tracking, credentials or vendor contact are made by this software. Input data and the resulting report remain wherever the operator stores them. Files are not encrypted; handle them according to your organization's data policies.</p>
<p class="small">'''+file_sources+'''</p>
<p class="small">Scope excludes unstructured PDF contract interpretation, taxes, volume-tier rebates, currency conversion, legal enforceability and independent verification of supplier source documents. Separate authorized review is mandatory.</p></section>
<footer>CONTRACT VALUE Ω · MONTREAL.AI · Confidential local buyer output · Nothing in this report certifies a refund, collected cash, or an external customer engagement.</footer>
</main></body></html>'''
    return doc.encode("utf-8")


def write(folder,result):
    output=Path(folder)
    if output.exists() or output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
        raise InputError("Output must be a fresh path with no symlink ancestors")
    output.mkdir(parents=True)
    (output/"supplier_packets").mkdir()
    files={}
    files["audit.json"]=canonical(result)
    files["summary.json"]=canonical({k:v for k,v in result.items() if k!="all_lines"})
    rows=list(review_rows(result))
    cols=("line_id","invoice_id","supplier_id","service_code","service_period","currency",
          "net_review_amount","gross_review_amount","applied_credit","decision","payment_state",
          "reasons","invoice_source","contract_source","usage_source","invoice_ref","term_ref",
          "usage_ref","vendor_confirmed","cash_recovered")
    files["review.csv"]=csv_bytes(rows,cols)
    files["index.html"]=report_html(result)
    by_supplier={}
    for record in rows:
        by_supplier.setdefault(record["supplier_id"],[]).append(record)
    for supplier,entries in sorted(by_supplier.items()):
        safe=hashlib.sha256(supplier.encode()).hexdigest()[:12]
        lines=[f"# Buyer-side review dossier · supplier {supplier}\n",
               "**Not a claim or supplier accusation. Do not send without buyer verification and authorization.**\n",
               "Proposed review items based strictly on structured buyer-provided evidence:\n"]
        for x in entries:
            lines.append(f"- Invoice {x['invoice_id']}, line {x['line_id']} · "
                         f"{x['currency']} {x['net_review_amount']} · {x['decision']} "
                         f"({x['reasons']}). Sources: {x['invoice_source']} ({x['invoice_ref']}), "
                         f"terms {x['contract_source']} ({x['term_ref']}), "
                         f"usage {x['usage_source']} ({x['usage_ref']}).")
        lines.extend(["\n## Buyer verification gate\n",
                      "Confirm underlying contract rights, authorized units, refunds/credits, supplier evidence, invoice status, prior disputes and legal/commercial limits.\n",
                      "**No communication is automated. No money is recorded as recovered.**\n"])
        files[f"supplier_packets/{safe}.md"]=("\n".join(lines)+"\n").encode("utf-8")
    for rel,payload in files.items():
        (output/rel).write_bytes(payload)
    manifest={rel:hashlib.sha256(payload).hexdigest() for rel,payload in sorted(files.items())}
    (output/"SHA256SUMS.json").write_bytes(canonical({
        "schema":"montreal-ai/contract-value-omega/output-checksums/v1",
        "files":manifest,"input_sha256":{k:v["sha256"] for k,v in result["input_manifest"].items()}}))
    return {"files":len(files)+1,"candidates":len([r for r in rows if r["net_review_amount"]!="0.00"]),
            "evidence_gaps":len([r for r in rows if r["decision"]=="EVIDENCE_GAP"]),
            "summary_by_currency":result["summary_by_currency"],"output":str(output)}


def main(argv=None):
    parser=argparse.ArgumentParser(description="CONTRACT VALUE Ω — local private-enterprise supplier audit. No network.")
    parser.add_argument("--input",type=Path,required=True,help="Folder with exactly five required CSV files")
    parser.add_argument("--output",type=Path,required=True,help="NEW folder for confidential buyer report")
    args=parser.parse_args(argv)
    try:
        result=audit(validate(args.input))
        report=write(args.output,result)
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (InputError,PermissionError,OSError) as exc:
        print("REVIEW_NOT_PRODUCED:",exc,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
