"""Producer-independent packet acceptance; shared input schema is not an oracle."""
from datetime import date,timedelta
from commercial.service_verifier import audit_delivery
from .packet_contract import SERVICE,SCOPE,PROMISE,PARTS,validate_input,reconciliation_order,work_contract,digest

FIELDS={'order_id','service_id','scope','currency','outcome_scope','method','entity_id','period','source_id','source_sha256','work_keys','promise','components','work_observation'}


def audit_packet(raw,artifact):
    errors=[]
    try:
        validate_input(raw)
        if type(artifact) is not dict or set(artifact)!=FIELDS: raise ValueError('EXACT_PACKET_ARTIFACT_REQUIRED')
        identities={k:raw[k] for k in ('order_id','service_id','scope','currency','entity_id','period','source_id','source_sha256')}
        identities.update(outcome_scope='complete_outcome',method=SERVICE,promise=PROMISE,work_keys=work_contract(raw)['work_keys'])
        if any(artifact.get(k)!=v for k,v in identities.items()): raise ValueError('PACKET_ENTITY_PERIOD_SOURCE_OR_WORK_MISMATCH')
        parts=artifact['components']
        if type(parts) is not dict or set(parts)!=set(PARTS): raise ValueError('THREE_COMPLETE_COMPONENTS_REQUIRED')
        rec=parts['reconciliation'];checked=audit_delivery(reconciliation_order(raw),rec)
        if not checked.get('accepted'): raise ValueError('INDEPENDENT_RECONCILIATION_FAILED:'+str(checked.get('errors')))
        # Recompute from raw source + independently accepted row partitions, not producer summaries.
        ii={r['id']:r for r in raw['invoices']}; pp={r['id']:r for r in raw['payments']}
        used_i={i for match in rec['matches'] for i in match['invoice_ids']};used_p={i for match in rec['matches'] for i in match['payment_ids']}
        outstanding=set(ii)-used_i;unallocated=set(pp)-used_p
        closing=sum(ii[i]['amount_cents'] for i in outstanding)
        applied_i=sum(ii[i]['amount_cents'] for i in used_i);applied_p=sum(pp[i]['amount_cents'] for i in used_p)
        opening=sum(r['amount_cents'] for r in ii.values() if r['basis']=='OPEN_AT_START')
        new=sum(r['amount_cents'] for r in ii.values() if r['basis']=='ISSUED_IN_PERIOD')
        cash=sum(r['amount_cents'] for r in pp.values());unapplied=sum(pp[i]['amount_cents'] for i in unallocated)
        if opening+new-applied_i!=closing or cash-applied_p!=unapplied or applied_i!=applied_p: raise ValueError('INDEPENDENT_SOURCE_ROLLFORWARD_FAILED')
        as_of=date.fromisoformat(raw['period']['end_exclusive'])-timedelta(days=1)
        aging={label:0 for label in ('current','1_30','31_60','61_plus')}
        for ident in outstanding:
            elapsed=(as_of-date.fromisoformat(ii[ident]['due_date'])).days
            for label,lo,hi in (('current',-10**9,0),('1_30',1,30),('31_60',31,60),('61_plus',61,10**9)):
                if lo<=elapsed<=hi: aging[label]+=ii[ident]['amount_cents']
        expected={'schema':'receivables-packet-metrics/v1','as_of':as_of.isoformat(),'opening_outstanding_cents':opening,
          'period_invoiced_cents':new,'applied_receipts_cents':applied_p,'cash_received_cents':cash,'unallocated_receipts_cents':unapplied,
          'closing_unresolved_receivables_cents':closing,'unresolved_invoice_aging_cents':aging,'unresolved_invoice_count':len(outstanding),
          'interpretation':'Unresolved amounts are not confirmed delinquency or collectible value; no ambiguous allocation is invented.'}
        if parts['receivables_metrics']!=expected: raise ValueError('SOURCE_DERIVED_METRICS_MISMATCH')
        issues=[]
        for kind,records,ids in (('UNMATCHED_INVOICE',ii,sorted(outstanding)),('UNMATCHED_PAYMENT',pp,sorted(unallocated))):
            for ident in ids: issues.append({'kind':kind,'record_id':ident,'source_row_id':records[ident]['source_row_id'],
              'amount_cents':records[ident]['amount_cents'],'status':'UNRESOLVED_REQUIRES_SOURCE_CLARIFICATION'})
        evidence={'schema':'receivables-packet-evidence/v1','source_sha256':raw['source_sha256'],
          'coverage':{'invoice_rows':len(ii),'payment_rows':len(pp)},'issues':issues,
          'claim':'Every supplied source row is matched or explicitly unresolved. No source change, invoice collection, financial advice or full-books assurance is performed.'}
        expected_work={'instrumented_source_row_visits':len(ii)+len(issues),'scope':'Counted aging-loop and evidence-loop row visits only; excludes reconciliation internals, other preparation, schema validation and independent audit. Not total operations or monetary cost.'}
        if artifact['work_observation']!=expected_work: raise ValueError('INSTRUMENTED_ROW_VISITS_MISMATCH')
        if parts['exception_evidence']!=evidence: raise ValueError('COMPLETE_SOURCE_LINKED_EXCEPTION_EVIDENCE_REQUIRED')
    except (ValueError,KeyError,TypeError,OverflowError) as exc: errors.append(str(exc))
    return {'accepted':not errors,'decisive':True,'service_id':SERVICE,'order_id':raw.get('order_id') if type(raw)is dict else None,
            'errors':errors,'checker_scope':'Independent arithmetic, partitions and declared source scope; not external certification, market demand or real-world source truth.',
            'input_sha256':digest(raw),'artifact_sha256':digest(artifact)}
