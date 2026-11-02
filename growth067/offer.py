"""Complete bounded receivables-close office packet, not a whole-office claim.

No financial posting, real customer messaging, tax opinion or audit assurance.
Account codes are explicit synthetic-contract labels, not client accounting advice.
"""
from datetime import date
from growth066.producer import reconcile
from growth066.quality import digest


def produce(packet):
    reconciliation=reconcile(packet)
    invalid={rid for e in reconciliation['exceptions'] if e['code'] in {'INVALID_DATE','INVALID_CURRENCY','INVALID_INVOICE_REFERENCE'} for rid in e['record_ids']}
    payments={}
    for row in packet['payments']:
        if row['id'] not in invalid:payments.setdefault(row['invoice_id'],[]).append(row)
    open_items=[]
    for inv in packet['invoices']:
        if inv['id'] in invalid:continue
        pp=payments.get(inv['id'],[]);paid=sum(p['gross_cents'] for p in pp);balance=inv['amount_cents']-paid
        open_items.append({'invoice_id':inv['id'],'invoiced_cents':inv['amount_cents'],'linked_payment_cents':paid,'open_balance_cents':balance,'payment_ids':sorted(p['id'] for p in pp),'status':'unpaid' if paid==0 else 'overpaid_needs_review' if balance<0 else 'part_paid' if balance>0 else 'settled_by_link_not_necessarily_bank_cleared'})
    proposals=[]
    for match in reconciliation['matches']:
        proposals.append({'settlement_id':match['settlement_id'],'source_bank_ids':match['bank_ids'],'source_payment_ids':match['payment_ids'],'debits':[{'account':'SYNTHETIC_BANK','cents':match['net_cents']},{'account':'SYNTHETIC_PROCESSING_FEES','cents':match['fee_cents']}],'credits':[{'account':'SYNTHETIC_RECEIVABLES','cents':match['gross_cents']}],'status':'DRAFT_NOT_POSTED'})
    queue=[{'code':e['code'],'record_ids':e['record_ids'],'disposition':'REQUEST_SOURCE_CLARIFICATION_NO_UNSUPPORTED_CORRECTION'} for e in reconciliation['exceptions']]
    totals={'invoiced_cents':sum(x['invoiced_cents'] for x in open_items),'linked_payment_cents':sum(x['linked_payment_cents'] for x in open_items),'open_balance_cents':sum(x['open_balance_cents'] for x in open_items),'bank_cleared_gross_cents':sum(m['gross_cents'] for m in reconciliation['matches']),'fees_cents':reconciliation['bridge']['matched_fee_cents']}
    summary={'packet_id':packet['packet_id'],'source_sha256':digest(packet),'resolved_settlement_groups':len(proposals),'unresolved_exceptions':len(queue),'balanced_draft_postings':all(sum(x['cents'] for x in p['debits'])==sum(x['cents'] for x in p['credits']) for p in proposals),'totals':totals,'scope':'Monthly receivables-close preparation only; linked payment is not proof of bank clearing; no posting or whole-office replacement.'}
    support={'question':'Why are duplicate bank references not simply removed, and where do fees go?','answer':'Duplicate references remain in source statement totals and require clarification; no speculative deletion is posted. Matched net deposits plus explicit fees equal gross linked settlement receipts. Draft entries debit bank and processing fees and credit receivables, only for independently matched settlements.','duplicate_record_ids':sorted({rid for e in queue if e['code']=='DUPLICATE_BANK_REFERENCE' for rid in e['record_ids']}),'fee_settlement_ids':sorted(m['settlement_id'] for m in reconciliation['matches'] if m['fee_cents'])}
    return {'schema':'growth067/receivables-close-output/v1','packet_id':packet['packet_id'],'input_sha256':digest(packet),'intake':{'currency':packet['currency'],'period':packet['period'],'source_rows':sum(len(packet[k]) for k in ['invoices','payments','bank']),'rights':'INDEPENDENT_SYNTHETIC_BENCHMARK_ONLY'},'reconciliation':reconciliation,'receivables_open_items':sorted(open_items,key=lambda x:x['invoice_id']),'draft_postings':proposals,'exception_handoff':queue,'management_summary':summary,'support_response':support}
