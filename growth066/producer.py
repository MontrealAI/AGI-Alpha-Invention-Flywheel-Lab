"""Conservative reference-based reconciliation; never posts entries or guesses matches.

This is conventional automation constructed with included agents, equally available
in the human comparator. It is not an independently novel matching algorithm.
"""
from collections import defaultdict
from datetime import date


def reconcile(packet):
    exceptions=[]
    def flag(code, ids):
        exceptions.append({'code':code,'record_ids':sorted(ids)})
    def valid(row):
        ok=True
        if row['currency']!=packet['currency']:
            flag('INVALID_CURRENCY',[row['id']]);ok=False
        try:
            d=date.fromisoformat(row['date'])
            if d.isoformat()[:7]!=packet['period']:raise ValueError()
        except (ValueError,TypeError):
            flag('INVALID_DATE',[row['id']]);ok=False
        return ok
    invoices={r['id']:r for r in packet['invoices'] if valid(r)}
    payments=[]
    for row in packet['payments']:
        ok=valid(row)
        if row['invoice_id'] not in invoices:
            flag('INVALID_INVOICE_REFERENCE',[row['id']]);ok=False
        if ok:payments.append(row)
    banks=[r for r in packet['bank'] if valid(r)]
    refs=defaultdict(list)
    for row in banks:
        if row['bank_ref']:refs[row['bank_ref']].append(row)
    duplicates=set()
    for rows in refs.values():
        if len(rows)>1:
            flag('DUPLICATE_BANK_REFERENCE',[r['id'] for r in rows]);duplicates.update(r['id'] for r in rows)
    pb=defaultdict(list);bb=defaultdict(list);missing_p=defaultdict(list);missing_b=defaultdict(list)
    for row in payments:
        if not row['settlement_id']:
            flag('MISSING_REFERENCE',[row['id']]);missing_p[(row['gross_cents'],row['currency'],row['date'])].append(row)
        else:pb[row['settlement_id']].append(row)
    for row in banks:
        if row['id'] in duplicates:continue
        if not row['settlement_id']:
            flag('MISSING_REFERENCE',[row['id']]);missing_b[(row['net_cents']+row['fee_cents'],row['currency'],row['date'])].append(row)
        else:bb[row['settlement_id']].append(row)
    for key in missing_p.keys()&missing_b.keys():
        pp,bs=missing_p[key],missing_b[key]
        if len(pp)>1 or len(bs)>1:flag('AMBIGUOUS_AMOUNT',[r['id'] for r in pp+bs])
    matches=[]
    for key in sorted(pb.keys()|bb.keys()):
        pp,bs=pb[key],bb[key]
        if not pp:flag('UNMATCHED_BANK',[r['id'] for r in bs]);continue
        if not bs:flag('UNMATCHED_PAYMENT',[r['id'] for r in pp]);continue
        gross=sum(r['gross_cents'] for r in pp);net=sum(r['net_cents'] for r in bs);fees=sum(r['fee_cents'] for r in bs)
        if gross!=net+fees:flag('AMOUNT_MISMATCH',[r['id'] for r in pp+bs]);continue
        matches.append({'settlement_id':key,'bank_ids':sorted(r['id'] for r in bs),'payment_ids':sorted(r['id'] for r in pp),'invoice_ids':sorted(set(r['invoice_id'] for r in pp)),'gross_cents':gross,'fee_cents':fees,'net_cents':net})
    paid={r['invoice_id'] for r in payments}
    for ident in invoices.keys()-paid:flag('UNPAID_INVOICE',[ident])
    bank_total=sum(r['net_cents'] for r in banks);payment_total=sum(r['gross_cents'] for r in payments)
    matched_bank=sum(r['net_cents'] for r in matches);matched_payment=sum(r['gross_cents'] for r in matches)
    bridge={'opening_balance_cents':packet['opening_balance_cents'],'bank_activity_cents':bank_total,'closing_balance_cents':packet['opening_balance_cents']+bank_total,'matched_bank_cents':matched_bank,'unmatched_bank_cents':bank_total-matched_bank,'payment_gross_cents':payment_total,'unmatched_payment_gross_cents':payment_total-matched_payment,'matched_fee_cents':sum(r['fee_cents'] for r in matches)}
    return {'schema':'growth066/reconciliation-output/v1','packet_id':packet['packet_id'],'matches':matches,'exceptions':sorted(exceptions,key=lambda x:(x['code'],x['record_ids'])),'bridge':bridge}
