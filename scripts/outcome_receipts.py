"""Compact publication of already-audited synthetic customer outcomes.

This is a projection, not another verifier or a portable financial audit.
Never export account authority, customer inputs, or full execution artifacts.
"""
import hashlib
import json


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def customer_outcomes(result, audit):
    if result.get('scope') != 'CONDITIONAL_SIMULATION':
        raise ValueError('SYNTHETIC_OUTCOME_PUBLICATION_ONLY')
    if result.get('complete') is not True or audit.get('accepted') is not True:
        raise ValueError('COMPLETED_AUDITED_OUTCOME_PROJECTION_REQUIRED')
    if audit.get('scope') != 'NATIVE_FINANCIAL_AND_OPERATING_SEMANTICS':
        raise ValueError('NATIVE_OPERATING_AUDIT_REQUIRED')
    source = result.get('source', {}).get('sha256')
    verifier = audit.get('verifier_source_sha256')
    if (not _hash(source) or not _hash(verifier) or audit.get('source_sha256') != source
            or audit.get('verifier_matches_world_source_snapshot') is not True):
        raise ValueError('SOURCE_AND_VERIFIER_IDENTITIES_REQUIRED')
    rows = []
    seen = set()
    hashes = ('actual_execution_artifact_sha256', 'native_delivered_artifact_sha256',
              'useful_outcome_sha256')
    for order in result['orders']:
        ident = order['id']
        if ident in seen:
            raise ValueError('DUPLICATE_OUTCOME_ORDER')
        seen.add(ident)
        outcome = order['outcome']
        service = order.get('service_receipt', {})
        produced, accepted, paid = (order.get(k) for k in
                                   ('production_time', 'acceptance_time', 'collection_time'))
        qualified = order.get('qualified_time')
        if any(type(t) is not int or t < 0 for t in (qualified, produced)) or produced < qualified:
            raise ValueError('QUALIFIED_PRODUCTION_TIMES_REQUIRED')
        if outcome not in {'SETTLED', 'REFUNDED', 'QUALITY_REJECTED'}:
            raise ValueError('UNRESOLVED_OUTCOME_CANNOT_BE_COMPLETED')
        is_accepted = outcome != 'QUALITY_REJECTED'
        is_paid = outcome == 'SETTLED'
        if service.get('accepted') is not is_accepted:
            raise ValueError('SERVICE_ACCEPTANCE_CONTRADICTS_OUTCOME')
        if is_accepted:
            if type(accepted) is not int or accepted < produced:
                raise ValueError('ACCEPTANCE_TIME_REQUIRED')
            if service.get('outcome_scope') != 'complete_outcome' or not all(_hash(service.get(k)) for k in hashes):
                raise ValueError('USEFUL_COMPLETE_OUTPUT_IDENTITIES_REQUIRED')
        elif accepted is not None:
            raise ValueError('REJECTED_OUTPUT_CANNOT_BE_ACCEPTED')
        if is_paid:
            if type(paid) is not int or paid < accepted:
                raise ValueError('COLLECTION_AFTER_ACCEPTANCE_REQUIRED')
        elif paid is not None:
            raise ValueError('UNPAID_OUTPUT_CANNOT_HAVE_COLLECTION')
        rows.append({'order_id': ident, 'job_id': order['job_id'],
                     'service_id': order['offer']['service_id'], 'outcome': outcome,
                     'production_attempted': True, 'useful_output_accepted': is_accepted,
                     'paid': is_paid, 'qualified_time': qualified, 'production_time': produced,
                     'acceptance_time': accepted, 'collection_time': paid,
                     **{k: service.get(k) if is_accepted else None for k in hashes}})
    counts = (len(rows), sum(r['useful_output_accepted'] for r in rows), sum(r['paid'] for r in rows))
    if counts[1] != audit.get('orders_reexecuted') or counts[1:] != (result.get('accepted_jobs'), result.get('paid_jobs')):
        raise ValueError('AUDITED_OUTCOME_COUNTS_MISMATCH')
    return {'schema': 'agi-alpha/customer-outcome-receipts/v1',
            'scope': 'ALREADY_AUDITED_SYNTHETIC_OUTCOME_PROJECTION',
            'source_sha256': source, 'verifier_source_sha256': verifier,
            'audited_result_sha256': _digest(result), 'audit_receipt_sha256': _digest(audit),
            'production_attempts': len(rows),
            'useful_outputs_accepted': sum(r['useful_output_accepted'] for r in rows),
            'paid_outputs': sum(r['paid'] for r in rows), 'orders': rows,
            'limits': 'In-job native and operating audit; hashes identify outputs but do not supply portable replay. Synthetic customer acceptance, not live buyer approval. Quality rejection and nonpayment are retained.'}
