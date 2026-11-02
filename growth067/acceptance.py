"""Independent acceptance for the bounded synthetic receivables-close offer.

No producer imports or producer-derived expected output. Reconciliation is
checked against separately constructed truth; office schedules are recomputed
from source rows and that truth. This does not certify real client accounting.
"""
from datetime import date
import time
from growth066.quality import canonical, digest, verify as verify_reconciliation

FIELDS = {'schema', 'packet_id', 'input_sha256', 'intake', 'reconciliation',
          'receivables_open_items', 'draft_postings', 'exception_handoff',
          'management_summary', 'support_response'}
SUPPORT_QUESTION = 'Why are duplicate bank references not simply removed, and where do fees go?'
SUPPORT_ANSWER = ('Duplicate references remain in source statement totals and require clarification; no speculative deletion is posted. '
                  'Matched net deposits plus explicit fees equal gross linked settlement receipts. '
                  'Draft entries debit bank and processing fees and credit receivables, only for independently matched settlements.')
SCOPE = 'Monthly receivables-close preparation only; linked payment is not proof of bank clearing; no posting or whole-office replacement.'


def _valid_source(row, packet):
    try:
        return row['currency'] == packet['currency'] and date.fromisoformat(row['date']).isoformat()[:7] == packet['period']
    except (KeyError, TypeError, ValueError):
        return False


def _equal(actual, expected):
    # Canonical bytes preserve the distinction between bool and integer money.
    return canonical(actual) == canonical(expected)


def _sorted(rows, key):
    if not isinstance(rows, list):
        raise ValueError('OFFICE_ARRAY_REQUIRED')
    return sorted(rows, key=key)


def _expectations(packet, truth):
    invoices = {r['id']: r for r in packet['invoices'] if _valid_source(r, packet)}
    payments = [r for r in packet['payments'] if _valid_source(r, packet) and r['invoice_id'] in invoices]
    items = []
    for ident, invoice in sorted(invoices.items()):
        linked = [r for r in payments if r['invoice_id'] == ident]
        paid = sum(r['gross_cents'] for r in linked)
        remaining = invoice['amount_cents'] - paid
        if paid == 0:
            status = 'unpaid'
        elif remaining < 0:
            status = 'overpaid_needs_review'
        elif remaining > 0:
            status = 'part_paid'
        else:
            status = 'settled_by_link_not_necessarily_bank_cleared'
        items.append({'invoice_id': ident, 'invoiced_cents': invoice['amount_cents'],
                      'linked_payment_cents': paid, 'open_balance_cents': remaining,
                      'payment_ids': sorted(r['id'] for r in linked), 'status': status})
    matches = truth['expected']['matches']
    postings = []
    for match in matches:
        postings.append({'settlement_id': match['settlement_id'],
                         'source_bank_ids': sorted(match['bank_ids']),
                         'source_payment_ids': sorted(match['payment_ids']),
                         'debits': [{'account': 'SYNTHETIC_BANK', 'cents': match['net_cents']},
                                    {'account': 'SYNTHETIC_PROCESSING_FEES', 'cents': match['fee_cents']}],
                         'credits': [{'account': 'SYNTHETIC_RECEIVABLES', 'cents': match['gross_cents']}],
                         'status': 'DRAFT_NOT_POSTED'})
    exceptions = truth['expected']['exceptions']
    handoff = [{'code': r['code'], 'record_ids': sorted(r['record_ids']),
                'disposition': 'REQUEST_SOURCE_CLARIFICATION_NO_UNSUPPORTED_CORRECTION'} for r in exceptions]
    totals = {'invoiced_cents': sum(r['amount_cents'] for r in invoices.values()),
              'linked_payment_cents': sum(r['gross_cents'] for r in payments),
              'open_balance_cents': sum(r['amount_cents'] for r in invoices.values()) - sum(r['gross_cents'] for r in payments),
              'bank_cleared_gross_cents': sum(r['gross_cents'] for r in matches),
              'fees_cents': sum(r['fee_cents'] for r in matches)}
    return {
        'intake': {'currency': packet['currency'], 'period': packet['period'],
                   'source_rows': sum(len(packet[k]) for k in ('invoices', 'payments', 'bank')),
                   'rights': 'INDEPENDENT_SYNTHETIC_BENCHMARK_ONLY'},
        'receivables_open_items': items,
        'draft_postings': sorted(postings, key=lambda r: r['settlement_id']),
        'exception_handoff': sorted(handoff, key=lambda r: (r['code'], r['record_ids'])),
        'management_summary': {'packet_id': packet['packet_id'], 'source_sha256': digest(packet),
                               'resolved_settlement_groups': len(matches), 'unresolved_exceptions': len(exceptions),
                               'balanced_draft_postings': True, 'totals': totals, 'scope': SCOPE},
        'support_response': {'question': SUPPORT_QUESTION, 'answer': SUPPORT_ANSWER,
                             'duplicate_record_ids': sorted({ident for r in exceptions if r['code'] == 'DUPLICATE_BANK_REFERENCE' for ident in r['record_ids']}),
                             'fee_settlement_ids': sorted(r['settlement_id'] for r in matches if r['fee_cents'])}}


def verify(packet, output, truth):
    wall, cpu = time.monotonic(), time.process_time()
    errors = []
    try:
        if not isinstance(output, dict) or set(output) != FIELDS:
            raise ValueError('EXACT_OFFICE_OUTPUT_FIELDS_REQUIRED')
        if output['schema'] != 'growth067/receivables-close-output/v1' or output['packet_id'] != packet['packet_id'] or output['input_sha256'] != digest(packet):
            raise ValueError('OFFICE_SOURCE_OR_IDENTITY_MISMATCH')
        receipt = verify_reconciliation(packet, output['reconciliation'], truth)
        if not receipt['accepted']:
            raise ValueError('RECONCILIATION_REJECTED:' + ','.join(receipt['errors']))
        expected = _expectations(packet, truth)
        normalized = dict(output)
        normalized['receivables_open_items'] = _sorted(output['receivables_open_items'], lambda r: r['invoice_id'])
        normalized['draft_postings'] = _sorted(output['draft_postings'], lambda r: r['settlement_id'])
        normalized['exception_handoff'] = _sorted(output['exception_handoff'], lambda r: (r['code'], r['record_ids']))
        for field, value in expected.items():
            if not _equal(normalized[field], value):
                errors.append(field.upper() + '_MISMATCH')
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        errors.append(str(exc))
    def safe_hash(value):
        try:
            return digest(value)
        except (ValueError, TypeError):
            return None
    return {'schema': 'growth067/office-acceptance/v1', 'accepted': not errors, 'errors': errors,
            'input_sha256': safe_hash(packet), 'output_sha256': safe_hash(output),
            'scope': 'BOUNDED_SYNTHETIC_RECEIVABLES_CLOSE_NOT_WHOLE_OFFICE_OR_REAL_ACCOUNTING_ASSURANCE',
            'wall_seconds': time.monotonic() - wall, 'process_cpu_seconds': time.process_time() - cpu}
