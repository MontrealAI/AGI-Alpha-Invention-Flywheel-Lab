"""Synthetic merchant reconciliation corpus and independent known-truth checker.

This is not accounting advice, a real statement, a posting tool, or a payment
interface. Truth is constructed alongside synthetic records, not obtained from
or recomputed by the producer. Holdout packets are a procedurally separated
synthetic test, not evidence about real customer data or secret forever-holdouts.
"""
from __future__ import annotations
import copy
import hashlib
import json
import random
import time

DEVELOPMENT_SEEDS = (6601, 6602, 6603)
HOLDOUT_SEEDS = (66101, 66102, 66103, 66104, 66105, 66106)
INPUT_SCHEMA = 'growth066/reconciliation-input/v1'
OUTPUT_SCHEMA = 'growth066/reconciliation-output/v1'
TRUTH_SCHEMA = 'growth066/reconciliation-truth/v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def make_case(seed, *, groups=24):
    """Return (public packet, independent truth); never hand truth to producer.

    All monetary quantities are integer cents. Duplicate references are flagged,
    not deduplicated from statement totals. Invalid dates/currency/link records
    are excluded from eligible bridge totals and explicitly reported.
    """
    if type(seed) is not int or type(groups) is not int or groups < 3 or groups > 1000:
        raise ValueError('FINITE_INTEGER_CASE_SPEC_REQUIRED')
    rng=random.Random(seed)
    packet={'schema':INPUT_SCHEMA,'packet_id':f'synthetic-merchant-{seed}',
            'currency':'USD','period':'2026-01','opening_balance_cents':rng.randrange(100000,900000),
            'invoices':[],'payments':[],'bank':[]}
    matches=[]; exceptions=[]; eligible_bank=[]; eligible_payment=[]
    day='2026-01-15'; counter={'i':0,'p':0,'b':0}
    def ident(kind):
        counter[kind]+=1
        return f'{kind}-{seed}-{counter[kind]:04d}'
    def invoice(amount):
        row={'id':ident('i'),'amount_cents':amount,'currency':'USD','date':day}
        packet['invoices'].append(row); return row
    def payment(amount,settlement,inv=None,**kw):
        if inv is None:inv=invoice(amount)
        row={'id':ident('p'),'invoice_id':inv['id'],'settlement_id':settlement,
             'gross_cents':amount,'currency':'USD','date':day};row.update(kw)
        packet['payments'].append(row);return row
    def bank(amount,fee,settlement,**kw):
        key=ident('b');row={'id':key,'bank_ref':'ref-'+key,'settlement_id':settlement,
                          'net_cents':amount,'fee_cents':fee,'currency':'USD','date':day};row.update(kw)
        packet['bank'].append(row);return row
    def issue(code,rows):exceptions.append({'code':code,'record_ids':sorted(r['id'] for r in rows)})
    for index in range(groups):
        settlement=f's-{seed}-{index:04d}'
        payments=[payment(rng.randrange(5000,50000),settlement) for _ in range(1+index%3)]
        gross=sum(p['gross_cents'] for p in payments);fee=gross//100 if index%4 else 0
        net=gross-fee
        if index%2:
            first=net//3;banks=[bank(first,0,settlement),bank(net-first,fee,settlement)]
        else:banks=[bank(net,fee,settlement)]
        eligible_bank.extend(banks);eligible_payment.extend(payments)
        matches.append({'settlement_id':settlement,'bank_ids':sorted(b['id'] for b in banks),
                        'payment_ids':sorted(p['id'] for p in payments),
                        'invoice_ids':sorted(set(p['invoice_id'] for p in payments)),
                        'gross_cents':gross,'fee_cents':fee,'net_cents':net})
    # Duplicate statement references: retain both in eligible statement activity,
    # quarantine both from matching. Do not invent which observation is genuine.
    duplicates=[bank(700,0,'duplicate-a',bank_ref='DUPLICATE-REF'),bank(900,0,'duplicate-b',bank_ref='DUPLICATE-REF')]
    eligible_bank.extend(duplicates);issue('DUPLICATE_BANK_REFERENCE',duplicates)
    # Ambiguous amount-only evidence: never infer a match.
    ambiguous_p=[payment(1337,''),payment(1337,'')]; ambiguous_b=[bank(1337,0,'')]
    eligible_payment.extend(ambiguous_p);eligible_bank.extend(ambiguous_b)
    for row in ambiguous_p+ambiguous_b:issue('MISSING_REFERENCE',[row])
    issue('AMBIGUOUS_AMOUNT',ambiguous_p+ambiguous_b)
    only_b=bank(4567,0,'bank-only');eligible_bank.append(only_b);issue('UNMATCHED_BANK',[only_b])
    only_p=payment(3456,'payment-only');eligible_payment.append(only_p);issue('UNMATCHED_PAYMENT',[only_p])
    mismatch_p=payment(2100,'mismatch');mismatch_b=bank(2000,30,'mismatch')
    eligible_payment.append(mismatch_p);eligible_bank.append(mismatch_b);issue('AMOUNT_MISMATCH',[mismatch_p,mismatch_b])
    invalid_b=bank(100,0,'wrong-currency',currency='EUR');issue('INVALID_CURRENCY',[invalid_b])
    invalid_b2=bank(200,0,'wrong-date',date='2026-02-30');issue('INVALID_DATE',[invalid_b2])
    used_invoice=packet['invoices'][0]
    invalid_p=payment(300,'wrong-currency',used_invoice,currency='EUR');issue('INVALID_CURRENCY',[invalid_p])
    invalid_p2=payment(400,'wrong-date',used_invoice,date='2026-02-01');issue('INVALID_DATE',[invalid_p2])
    bad_link=payment(500,'bad-link',used_invoice,invoice_id='MISSING-INVOICE');issue('INVALID_INVOICE_REFERENCE',[bad_link])
    unpaid=invoice(777);issue('UNPAID_INVOICE',[unpaid])
    bank_total=sum(b['net_cents'] for b in eligible_bank)
    payment_total=sum(p['gross_cents'] for p in eligible_payment)
    matched_bank=sum(m['net_cents'] for m in matches)
    matched_gross=sum(m['gross_cents'] for m in matches)
    expected={'schema':OUTPUT_SCHEMA,'packet_id':packet['packet_id'],'matches':matches,'exceptions':exceptions,
              'bridge':{'opening_balance_cents':packet['opening_balance_cents'],
                        'bank_activity_cents':bank_total,'closing_balance_cents':packet['opening_balance_cents']+bank_total,
                        'matched_bank_cents':matched_bank,'unmatched_bank_cents':bank_total-matched_bank,
                        'payment_gross_cents':payment_total,'unmatched_payment_gross_cents':payment_total-matched_gross,
                        'matched_fee_cents':sum(m['fee_cents'] for m in matches)}}
    for field in ('invoices','payments','bank'):rng.shuffle(packet[field])
    truth={'schema':TRUTH_SCHEMA,'input_sha256':digest(packet),'expected':expected,
           'construction':{'seed':seed,'matched_groups':groups,'truth_basis':'Independent synthetic construction, not producer result',
                           'partition':'development' if seed in DEVELOPMENT_SEEDS else 'heldout' if seed in HOLDOUT_SEEDS else 'other'},
           'scope':'SYNTHETIC_ONLY_NO_REAL_STATEMENT_OR_CUSTOMER'}
    return packet,truth


def public_packet(seed, *, groups=24):
    return make_case(seed,groups=groups)[0]


def _normalized(output):
    if not isinstance(output,dict) or set(output)!={'schema','packet_id','matches','exceptions','bridge'}:
        raise ValueError('EXACT_OUTPUT_FIELDS_REQUIRED')
    value=copy.deepcopy(output)
    if value['schema']!=OUTPUT_SCHEMA or not isinstance(value['packet_id'],str):
        raise ValueError('OUTPUT_IDENTITY_REQUIRED')
    if not isinstance(value['matches'],list) or not isinstance(value['exceptions'],list):
        raise ValueError('MATCH_AND_EXCEPTION_ARRAYS_REQUIRED')
    seen_settlements=set();seen_bank=set();seen_payments=set()
    for row in value['matches']:
        if not isinstance(row,dict) or set(row)!={'settlement_id','bank_ids','payment_ids','invoice_ids','gross_cents','fee_cents','net_cents'}:
            raise ValueError('EXACT_MATCH_FIELDS_REQUIRED')
        if not isinstance(row['settlement_id'],str) or not row['settlement_id'] or row['settlement_id'] in seen_settlements:
            raise ValueError('UNIQUE_NONEMPTY_SETTLEMENT_REQUIRED')
        seen_settlements.add(row['settlement_id'])
        for name,seen in [('bank_ids',seen_bank),('payment_ids',seen_payments),('invoice_ids',None)]:
            ids=row[name]
            if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids):
                raise ValueError('UNIQUE_RECORD_IDS_REQUIRED')
            if seen is not None:
                if seen.intersection(ids):raise ValueError('MATCH_RECORD_REUSED')
                seen.update(ids)
            row[name]=sorted(ids)
        for field in ('gross_cents','fee_cents','net_cents'):
            if type(row[field]) is not int or row[field]<0:raise ValueError('EXACT_NONNEGATIVE_CENTS_REQUIRED')
        if row['gross_cents']!=row['net_cents']+row['fee_cents']:raise ValueError('MATCH_FEE_BRIDGE_INVALID')
    seen_issues=set()
    for issue in value['exceptions']:
        if not isinstance(issue,dict) or set(issue)!={'code','record_ids'} or not isinstance(issue['code'],str):
            raise ValueError('EXACT_EXCEPTION_FIELDS_REQUIRED')
        ids=issue['record_ids']
        if not isinstance(ids,list) or not ids or any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids):
            raise ValueError('EXACT_EXCEPTION_RECORDS_REQUIRED')
        issue['record_ids']=sorted(ids);key=(issue['code'],tuple(issue['record_ids']))
        if key in seen_issues:raise ValueError('DUPLICATE_EXCEPTION')
        seen_issues.add(key)
    fields={'opening_balance_cents','bank_activity_cents','closing_balance_cents','matched_bank_cents','unmatched_bank_cents','payment_gross_cents','unmatched_payment_gross_cents','matched_fee_cents'}
    if not isinstance(value['bridge'],dict) or set(value['bridge'])!=fields or any(type(v) is not int for v in value['bridge'].values()):
        raise ValueError('EXACT_INTEGER_BRIDGE_REQUIRED')
    value['matches'].sort(key=lambda r:r['settlement_id'])
    value['exceptions'].sort(key=lambda r:(r['code'],r['record_ids']))
    return value


def _safe_digest(value):
    try:return digest(value)
    except (TypeError,ValueError):return None


def verify(packet,output,truth):
    """Independent exact acceptance against separately held construction truth."""
    wall=time.monotonic();cpu=time.process_time();errors=[]
    try:
        if not isinstance(truth,dict) or truth.get('schema')!=TRUTH_SCHEMA or truth.get('input_sha256')!=digest(packet):
            raise ValueError('TRUTH_INPUT_BINDING_MISMATCH')
        actual=_normalized(output);expected=_normalized(truth['expected'])
        if actual['packet_id']!=packet['packet_id']:errors.append('PACKET_ID_MISMATCH')
        for key in ('matches','exceptions','bridge'):
            if actual[key]!=expected[key]:errors.append(key.upper()+'_MISMATCH')
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        errors.append(str(exc))
    return {'schema':'growth066/reconciliation-acceptance/v1','accepted':not errors,'errors':errors,
            'input_sha256':_safe_digest(packet),'output_sha256':_safe_digest(output),
            'checker_scope':'Exact synthetic construction truth; no financial postings, legal assurance or real-world accuracy claim',
            'matched_groups':len(output.get('matches',[])) if isinstance(output,dict) else 0,
            'reported_exceptions':len(output.get('exceptions',[])) if isinstance(output,dict) else 0,
            'wall_seconds':time.monotonic()-wall,'process_cpu_seconds':time.process_time()-cpu}
