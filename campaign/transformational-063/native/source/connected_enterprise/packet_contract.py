"""Bounded entity-period receivables packet contract; no price or payment authority."""
import hashlib
import json
from datetime import date

SERVICE = 'receivables_packet'
SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
PROMISE = 'Receivables cash application, source-derived balances and unresolved exception evidence; no ledger writeback, collections contact, tax advice or full-books assurance.'
PARTS = ('reconciliation', 'receivables_metrics', 'exception_evidence')
RAW = {'schema','order_id','service_id','scope','currency','entity_id','period','source_id','source_sha256','invoices','payments','requested_scope'}


def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def source_material(raw):
    return {k:raw[k] for k in ('entity_id','period','source_id','invoices','payments')}


def _text(x):
    return type(x) is str and 0 < len(x.strip()) <= 200


def _date(x):
    if type(x) is not str or len(x)!=10: raise ValueError('ISO_DATE_REQUIRED')
    d=date.fromisoformat(x)
    if d.isoformat()!=x: raise ValueError('CANONICAL_DATE_REQUIRED')
    return d


def validate_input(raw):
    if type(raw) is not dict or set(raw)!=RAW or raw['schema']!='receivables-packet-input/v1' or raw['service_id']!=SERVICE or raw['scope']!=SCOPE or raw['currency']!='USD' or raw['requested_scope']!='cash_application_and_exceptions':
        raise ValueError('EXACT_BOUNDED_RECEIVABLES_SCOPE_REQUIRED')
    if not all(_text(raw[k]) for k in ('order_id','entity_id','source_id')): raise ValueError('SOURCE_ENTITY_ORDER_REQUIRED')
    p=raw['period']
    if type(p) is not dict or set(p)!={'start_inclusive','end_exclusive'}: raise ValueError('EXACT_PERIOD_REQUIRED')
    start,end=_date(p['start_inclusive']),_date(p['end_exclusive'])
    if not 1 <= (end-start).days <= 93: raise ValueError('BOUNDED_PERIOD_REQUIRED')
    seen_rows=set(); inv={}
    for field in ('invoices','payments'):
        rows=raw[field]
        if type(rows) is not list or not 1<=len(rows)<=1000: raise ValueError('BOUNDED_SOURCE_ROWS_REQUIRED')
        ids=set()
        for row in rows:
            keys={'id','customer','amount_cents','source_row_id'} | ({'basis','issued_date','due_date'} if field=='invoices' else {'invoice_refs','received_date'})
            if type(row) is not dict or set(row)!=keys or not all(_text(row[k]) for k in ('id','customer','source_row_id')) or row['id'] in ids or row['source_row_id'] in seen_rows:
                raise ValueError('UNIQUE_EXACT_SOURCE_ROWS_REQUIRED')
            ids.add(row['id']);seen_rows.add(row['source_row_id'])
            if type(row['amount_cents']) is not int or not 0<row['amount_cents']<=10**14: raise ValueError('POSITIVE_INTEGER_CENTS_NO_REVERSALS')
            if field=='invoices':
                issued,due=_date(row['issued_date']),_date(row['due_date'])
                if due<issued or row['basis'] not in ('OPEN_AT_START','ISSUED_IN_PERIOD'): raise ValueError('INVOICE_DATES_AND_BASIS_REQUIRED')
                if not (issued<start if row['basis']=='OPEN_AT_START' else start<=issued<end): raise ValueError('INVOICE_PERIOD_MISMATCH')
                inv[row['id']]=row
            else:
                if not start<=_date(row['received_date'])<end: raise ValueError('PAYMENT_PERIOD_MISMATCH')
                refs=row['invoice_refs']
                if type(refs) is not list or any(not _text(x) for x in refs) or len(set(refs))!=len(refs) or any(x not in inv or inv[x]['customer']!=row['customer'] for x in refs): raise ValueError('AUTHORIZED_SAME_CUSTOMER_REFERENCES_REQUIRED')
    if raw['source_sha256']!=digest(source_material(raw)): raise ValueError('SOURCE_CONTENT_BINDING_MISMATCH')
    return raw


def reconciliation_order(raw):
    validate_input(raw)
    return {'order_id':raw['order_id'],'scope':SCOPE,'currency':'USD','require_complete':False,
            'invoices':[{k:r[k] for k in ('id','customer','amount_cents')} for r in raw['invoices']],
            'payments':[{k:r[k] for k in ('id','customer','amount_cents','invoice_refs')} for r in raw['payments']]}


def work_contract(raw):
    validate_input(raw)
    # Corrections/renamed exports are the same entity-period work, not new sales.
    identity=digest({k:raw[k] for k in ('entity_id','period')})
    return {'schema':'receivables-packet-work/v1','service_id':SERVICE,'source_sha256':raw['source_sha256'],
            'work_keys':['receivables-packet:'+identity+':'+p for p in PARTS],
            'capacity_units':3,'production_units':3,'supplier_units':3,'support_units':3,
            'accounting_scope':'Engine binds configured per-unit resource costs; onboarding, quote, payment fees and liability premium charged once separately. This contract grants no spending authority.'}


def synthetic_input(index=0, cohort_seed=0, rows=12):
    """Explicit synthetic workload only; never evidence of demand or human hours."""
    if type(index) is not int or index<0 or type(rows) is not int or not 4<=rows<=1000: raise ValueError('BOUNDED_SYNTHETIC_ROWS_REQUIRED')
    tag=digest([cohort_seed,index])[:16]; invoices=[]; payments=[]
    for n in range(rows):
        amount=10000+(n%9)*1700; customer='customer-'+str(n%4)
        invoices.append({'id':'i'+str(n),'customer':customer,'amount_cents':amount,'source_row_id':'invoice:'+str(n),
                         'basis':'OPEN_AT_START' if n%3==0 else 'ISSUED_IN_PERIOD',
                         'issued_date':'2026-09-15' if n%3==0 else '2026-10-02','due_date':'2026-10-15'})
        payments.append({'id':'p'+str(n),'customer':customer,'amount_cents':amount+(1 if n%5==0 else 0),
                         'source_row_id':'payment:'+str(n),'invoice_refs':['i'+str(n)],'received_date':'2026-10-20'})
    raw={'schema':'receivables-packet-input/v1','order_id':'packet-'+tag,'service_id':SERVICE,'scope':SCOPE,'currency':'USD',
         'entity_id':'entity-'+tag,'period':{'start_inclusive':'2026-10-01','end_exclusive':'2026-11-01'},
         'source_id':'synthetic-export-'+tag,'source_sha256':'','invoices':invoices,'payments':payments,'requested_scope':'cash_application_and_exceptions'}
    raw['source_sha256']=digest(source_material(raw));return validate_input(raw)
