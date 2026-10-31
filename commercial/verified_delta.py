"""Source-bound differential verification for the existing synthetic reconciliation.

Only globally validated customer-isolated records are eligible for reuse. A
previous certificate is trusted solely through an externally retained SHA256
pin; it does not confer financial authority or attest a real customer.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from commercial import service, service_verifier

SCHEMA = 'agi-alpha/verified-delta-production/v1'
SCOPE = 'SYNTHETIC_PUBLIC_RECONCILIATION_ONLY'
TOTALS = ('invoice_cents', 'payment_cents', 'matched_invoice_cents',
          'matched_payment_cents', 'open_invoice_cents', 'unallocated_payment_cents')


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def sources():
    return {name: hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest()
            for name, mod in [('producer', service), ('checker', service_verifier),
                              ('delta', __import__(__name__, fromlist=['_']))]}


def partition(order):
    service.validate(order)
    customers = sorted({row['customer'] for k in ('invoices', 'payments') for row in order[k]})
    result = {}
    for customer in customers:
        sub = {key: copy.deepcopy(order[key]) for key in ('scope', 'currency', 'order_id', 'require_complete') if key in order}
        sub['invoices'] = [copy.deepcopy(row) for row in order['invoices'] if row['customer'] == customer]
        sub['payments'] = [copy.deepcopy(row) for row in order['payments'] if row['customer'] == customer]
        if not sub['invoices'] or not sub['payments']:
            return None
        result[customer] = sub
    return result


def combine(order, parts):
    matches, invoices, payments = [], [], []
    totals = {key: 0 for key in TOTALS}
    for data in parts.values():
        report = data['report']
        matches.extend(copy.deepcopy(report['matches']))
        invoices.extend(report['unmatched_invoices'])
        payments.extend(report['unmatched_payments'])
        for key in TOTALS:
            totals[key] += report['totals'][key]
    invoices.sort()
    payments.sort()
    return {'order_id': order['order_id'], 'scope': service.SCOPE, 'currency': 'USD',
            'matches': sorted(matches, key=lambda row: row['invoice_ids']),
            'unmatched_invoices': invoices, 'unmatched_payments': payments,
            'exceptions': ([{'kind': 'UNMATCHED_INVOICE', 'id': i} for i in invoices] +
                           [{'kind': 'UNMATCHED_PAYMENT', 'id': i} for i in payments]),
            'totals': totals,
            'accepted': not order.get('require_complete', False) or not (invoices or payments)}


def _pin(previous, expected_pin):
    if previous is None:
        if expected_pin is not None:
            raise ValueError('UNEXPECTED_PRIOR_PIN')
        return None
    if (type(expected_pin) is not str or len(expected_pin) != 64
            or any(ch not in '0123456789abcdef' for ch in expected_pin)):
        raise ValueError('EXTERNAL_PRIOR_CERTIFICATE_PIN_REQUIRED')
    if digest(previous) != expected_pin:
        raise ValueError('PRIOR_CERTIFICATE_PIN_MISMATCH')
    if previous.get('schema') != SCHEMA or previous.get('source_hashes') != sources():
        raise ValueError('PRIOR_PROOF_OR_EXECUTING_SOURCE_CHANGED')
    return previous


def execute(order, previous=None, *, expected_previous_sha256=None):
    """Produce current output with fresh checks for changed independent groups."""
    previous = _pin(previous, expected_previous_sha256)
    source = sources()
    groups = partition(order)
    initial = len(order['invoices']) + len(order['payments'])
    if groups is None:
        report = service.reconcile(order)
        checker = service_verifier.audit_delivery(order, report)
        cert = {'schema': SCHEMA, 'scope': SCOPE, 'mode': 'DIRECT_FALLBACK',
                'reason': 'GROUP_WITH_EMPTY_SIDE', 'source_hashes': source,
                'input_sha256': digest(order), 'prior_sha256': None,
                'groups': {}, 'report': report, 'complete_checker': checker,
                'reused_groups': 0, 'fresh_groups': 0, 'semantic_rows_rechecked': initial,
                'global_input_rows_scanned': initial, 'actual_collections': 0,
                'actual_profit': None, 'financial_authority': False}
        return cert
    prev_groups = previous.get('groups', {}) if previous and previous.get('mode') == 'PARTITIONED' else {}
    entries, reused, processed = {}, 0, 0
    for customer, suborder in groups.items():
        identity = digest(suborder)
        old = prev_groups.get(customer)
        if old and old.get('input_sha256') == identity and old.get('checker', {}).get('accepted') is True:
            entry = {'input_sha256': identity, 'report': copy.deepcopy(old['report']),
                     'checker': copy.deepcopy(old['checker']), 'reused': True}
            reused += 1
        else:
            report = service.reconcile(suborder)
            checker = service_verifier.audit_delivery(suborder, report)
            entry = {'input_sha256': identity, 'report': report, 'checker': checker, 'reused': False}
            processed += len(suborder['invoices']) + len(suborder['payments'])
        entries[customer] = entry
    report = combine(order, entries)
    return {'schema': SCHEMA, 'scope': SCOPE, 'mode': 'PARTITIONED', 'reason': None,
            'source_hashes': source, 'input_sha256': digest(order),
            'prior_sha256': expected_previous_sha256 if reused else None,
            'groups': entries, 'report': report, 'complete_checker': None,
            'reused_groups': reused, 'fresh_groups': len(entries)-reused,
            'semantic_rows_rechecked': processed,
            'global_input_rows_scanned': initial, 'actual_collections': 0,
            'actual_profit': None, 'financial_authority': False}


def verify(order, cert, previous=None, *, expected_previous_sha256=None, full=True):
    """Independently reconstruct every proof claim; full=True reruns the strong direct specialist."""
    if not isinstance(cert, dict) or cert.get('schema') != SCHEMA or cert.get('scope') != SCOPE:
        raise ValueError('CERTIFICATE_SCHEMA_OR_SCOPE_REQUIRED')
    if cert.get('source_hashes') != sources() or cert.get('input_sha256') != digest(order):
        raise ValueError('CURRENT_EXECUTING_SOURCE_OR_INPUT_CHANGED')
    if cert.get('actual_collections') != 0 or cert.get('actual_profit') is not None or cert.get('financial_authority') is not False:
        raise ValueError('FORGED_COMMERCE_OR_FINANCIAL_AUTHORITY')
    groups = partition(order)
    if groups is None:
        if cert != execute(order):
            raise ValueError('FALLBACK_CERTIFICATE_DOES_NOT_RECOMPUTE')
    else:
        if cert.get('mode') != 'PARTITIONED' or set(cert.get('groups', {})) != set(groups):
            raise ValueError('EXACT_CUSTOMER_PROOF_CLOSURE_REQUIRED')
        parent = _pin(previous, expected_previous_sha256) if cert.get('reused_groups', 0) else None
        prior_groups = parent.get('groups', {}) if parent and parent.get('mode') == 'PARTITIONED' else {}
        entries = cert['groups']
        reused, processed = 0, 0
        for customer, suborder in groups.items():
            entry = entries[customer]
            identity = digest(suborder)
            if entry.get('input_sha256') != identity:
                raise ValueError('SHARD_INPUT_BINDING_CHANGED')
            if entry.get('reused') is True:
                old = prior_groups.get(customer)
                if not old or old.get('input_sha256') != identity or old.get('checker', {}).get('accepted') is not True:
                    raise ValueError('UNQUALIFIED_OR_UNPINNED_INHERITANCE')
                if entry['report'] != old['report'] or entry['checker'] != old['checker']:
                    raise ValueError('RETAINED_PROOF_CONTENT_CHANGED')
                reused += 1
            elif entry.get('reused') is False:
                fresh = service.reconcile(suborder)
                independent = service_verifier.audit_delivery(suborder, entry['report'])
                if entry['report'] != fresh or entry['checker'] != independent:
                    raise ValueError('NEW_SHARD_PRODUCTION_OR_CHECKER_MISMATCH')
                processed += len(suborder['invoices']) + len(suborder['payments'])
            else:
                raise ValueError('SHARD_REUSE_VERDICT_REQUIRED')
        if (cert['report'] != combine(order, entries)
                or cert.get('reused_groups') != reused
                or cert.get('fresh_groups') != len(groups)-reused
                or cert.get('semantic_rows_rechecked') != processed
                or cert.get('prior_sha256') != (expected_previous_sha256 if reused else None)
                or cert.get('global_input_rows_scanned') != len(order['invoices'])+len(order['payments'])
                or cert.get('complete_checker') is not None or cert.get('reason') is not None):
            raise ValueError('GLOBAL_CAUSAL_ASSEMBLY_OR_WORK_RECEIPT_CHANGED')
    if full:
        direct = service.reconcile(order)
        independent = service_verifier.audit_delivery(order, cert['report'])
        if direct != cert['report'] or independent['accepted'] is not bool(cert['report']['accepted']):
            raise ValueError('FRESH_FULL_SPECIALIST_DISAGREES')
    return {'source_bound': True, 'current_input_sha256': digest(order),
            'certificate_sha256': digest(cert), 'fresh_full_comparison': bool(full),
            'current_complete_outcome_accepted': bool(cert['report']['accepted']) if full else None,
            'semantic_rows_rechecked': cert['semantic_rows_rechecked'],
            'full_specialist_rows': len(order['invoices'])+len(order['payments']),
            'reused_groups': cert['reused_groups'], 'actual_collections': 0,
            'claim_scope': 'CURRENT_SYNTHETIC_SERVICE_ONLY_NOT_AUTONOMOUS_OR_BEYOND_HUMAN_DISCOVERY'}
