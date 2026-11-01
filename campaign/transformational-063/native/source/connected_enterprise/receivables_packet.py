"""Execute a bounded receivables decision packet, not full bookkeeping or advice."""
from datetime import date, timedelta
from commercial.service import reconcile
from .packet_contract import SERVICE,SCOPE,PROMISE,PARTS,validate_input,reconciliation_order,work_contract,digest


def produce(raw):
    validate_input(raw)
    reconciled=reconcile(reconciliation_order(raw))
    open_ids=set(reconciled['unmatched_invoices'])
    as_of=date.fromisoformat(raw['period']['end_exclusive'])-timedelta(days=1)
    buckets={'current':0,'1_30':0,'31_60':0,'61_plus':0}
    visits=0
    for row in raw['invoices']:
        visits+=1
        if row['id'] not in open_ids: continue
        age=(as_of-date.fromisoformat(row['due_date'])).days
        bucket='current' if age<=0 else '1_30' if age<=30 else '31_60' if age<=60 else '61_plus'
        buckets[bucket]+=row['amount_cents']
    totals=reconciled['totals']
    metrics={'schema':'receivables-packet-metrics/v1','as_of':as_of.isoformat(),
        'opening_outstanding_cents':sum(r['amount_cents'] for r in raw['invoices'] if r['basis']=='OPEN_AT_START'),
        'period_invoiced_cents':sum(r['amount_cents'] for r in raw['invoices'] if r['basis']=='ISSUED_IN_PERIOD'),
        'applied_receipts_cents':totals['matched_payment_cents'],'cash_received_cents':totals['payment_cents'],
        'unallocated_receipts_cents':totals['unallocated_payment_cents'],'closing_unresolved_receivables_cents':totals['open_invoice_cents'],
        'unresolved_invoice_aging_cents':buckets,'unresolved_invoice_count':len(open_ids),
        'interpretation':'Unresolved amounts are not confirmed delinquency or collectible value; no ambiguous allocation is invented.'}
    by_invoice={r['id']:r for r in raw['invoices']};by_payment={r['id']:r for r in raw['payments']}
    issues=[]
    for item in reconciled['exceptions']:
        visits+=1
        row=(by_invoice if item['kind']=='UNMATCHED_INVOICE' else by_payment)[item['id']]
        issues.append({'kind':item['kind'],'record_id':item['id'],'source_row_id':row['source_row_id'],
                       'amount_cents':row['amount_cents'],'status':'UNRESOLVED_REQUIRES_SOURCE_CLARIFICATION'})
    evidence={'schema':'receivables-packet-evidence/v1','source_sha256':raw['source_sha256'],
              'coverage':{'invoice_rows':len(raw['invoices']),'payment_rows':len(raw['payments'])},'issues':issues,
              'claim':'Every supplied source row is matched or explicitly unresolved. No source change, invoice collection, financial advice or full-books assurance is performed.'}
    contract=work_contract(raw)
    return {'order_id':raw['order_id'],'service_id':SERVICE,'scope':SCOPE,'currency':'USD','outcome_scope':'complete_outcome',
            'method':SERVICE,'entity_id':raw['entity_id'],'period':raw['period'].copy(),'source_id':raw['source_id'],
            'source_sha256':raw['source_sha256'],'work_keys':contract['work_keys'],'promise':PROMISE,
            'components':dict(zip(PARTS,(reconciled,metrics,evidence))),
            'work_observation':{'instrumented_source_row_visits':visits,'scope':'Counted aging-loop and evidence-loop row visits only; excludes reconciliation internals, other preparation, schema validation and independent audit. Not total operations or monetary cost.'}}
