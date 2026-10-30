"""Portable, source-bound proof of a bounded synthetic digital service outcome.

This is an independently checkable offer demonstration, not an order,
customer agreement, payment, cryptographic signature or certification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from commercial import service, service_verifier

SCHEMA = 'agi-alpha/portable-outcome-offer/v1'
FILES = ('ORDER.json', 'DELIVERY/reconciliation.json', 'DELIVERY/exceptions.csv',
         'VERDICT.json', 'OFFER.json')
MAX_BYTES = 2_000_000


def canonical(data):
    return (json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _safe_path(path):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('SYMLINK_PATH_REFUSED')
    return path


def _read(path):
    path = _safe_path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('BOUNDED_REGULAR_FILE_REQUIRED')
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('FILE_SIZE_EXCEEDED')
    return raw


def _json_bytes(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda n: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
    return value


def _source_hashes():
    return {name: digest(_read(Path(__file__).with_name(name)))
            for name in ('service.py', 'service_verifier.py', 'portable_offer.py')}


def _expected_exception_csv(report):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(('order_id', 'kind', 'row_id'))
    for row in report['exceptions']:
        writer.writerow((report['order_id'], row['kind'], row['id']))
    return out.getvalue().encode('utf-8')


def build(order, output, *, price_cents):
    if type(price_cents) is not int or not 1 <= price_cents <= 10**14:
        raise ValueError('BOUNDED_PROPOSED_PRICE_CENTS_REQUIRED')
    service.validate(order)
    target = _safe_path(output)
    target.mkdir(parents=True, exist_ok=False)
    (target / 'ORDER.json').write_bytes(canonical(order))
    report = service.deliver(order, target / 'DELIVERY')
    report_bytes = _read(target / 'DELIVERY/reconciliation.json')
    verdict = service_verifier.audit_delivery(order, report)
    qualification = verdict['accepted'] is True and report['accepted'] is True
    receipt = {'schema': SCHEMA, 'scope': service.SCOPE,
               'result': 'QUALIFIED_SYNTHETIC_DELIVERY' if qualification else 'NOT_QUALIFIED',
               'independent_checker_accepted': verdict['accepted'],
               'business_acceptance_accepted': report['accepted'],
               'verifier_errors': verdict['errors'],
               'checker_sha256': digest(_read(Path(service_verifier.__file__))),
               'source_and_checker_same_environment': True,
               'no_external_certification': True,
               'actual_customer_acceptance': False,
               'observed_revenue_cents': 0}
    (target / 'VERDICT.json').write_bytes(canonical(receipt))
    offer = {'schema': SCHEMA, 'scope': service.SCOPE, 'service_id': 'receivables_reconciliation',
             'order_id': order['order_id'], 'currency': 'USD', 'quoted_price_cents': price_cents,
             'quoted_terms': 'HYPOTHETICAL_PRICE_NOT_ACCEPTED_OR_PAYABLE',
             'acceptance_rule': 'Independent source-bound checker must accept reconciliation and all required completeness conditions.',
             'exceptions_disclosed': len(report['exceptions']),
             'qualification': receipt['result'],
             'consent_or_payment_collected': False,
             'customer_data_rights': 'Public synthetic input only; no confidential customer data authorization.',
             'economic_scope': 'No tested willingness to pay, market conversion, invoices, funded sale or real profit.'}
    (target / 'OFFER.json').write_bytes(canonical(offer))
    inputs = {rel: {'sha256': digest(_read(target / rel)), 'bytes': len(_read(target / rel))}
              for rel in FILES}
    manifest = {'schema': SCHEMA, 'scope': service.SCOPE, 'files': inputs,
                'source_sha256': _source_hashes(),
                'order_id': order['order_id'],
                'receipt_scope': 'SOURCE_BOUND_SYNTHETIC_ENGINEERING_NOT_THIRD_PARTY_SIGNATURE',
                'no_execution_authority': True}
    (target / 'MANIFEST.json').write_bytes(canonical(manifest))
    return verify(target)


def verify(path):
    root = _safe_path(path)
    allowed = set(FILES) | {'MANIFEST.json'}
    if not root.is_dir():
        raise ValueError('PACKAGE_DIRECTORY_REQUIRED')
    found = {f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file() or f.is_symlink()}
    if found != allowed:
        raise ValueError('EXACT_PACKAGE_CLOSURE_REQUIRED')
    manifest = _json_bytes(_read(root / 'MANIFEST.json'))
    if (not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA
            or manifest.get('scope') != service.SCOPE
            or set(manifest.get('files', {})) != set(FILES)
            or manifest.get('source_sha256') != _source_hashes()
            or manifest.get('no_execution_authority') is not True):
        raise ValueError('BOUND_SOURCE_OR_SCHEMA_CHANGED')
    for rel, expected in manifest['files'].items():
        raw = _read(root / rel)
        if expected != {'sha256': digest(raw), 'bytes': len(raw)}:
            raise ValueError('PACKAGE_FILE_IDENTITY_MISMATCH:' + rel)
    order = _json_bytes(_read(root / 'ORDER.json'))
    report = _json_bytes(_read(root / 'DELIVERY/reconciliation.json'))
    receipt = _json_bytes(_read(root / 'VERDICT.json'))
    offer = _json_bytes(_read(root / 'OFFER.json'))
    checker = service_verifier.audit_delivery(order, report)
    if _read(root / 'DELIVERY/exceptions.csv') != _expected_exception_csv(report):
        raise ValueError('EXCEPTION_SCHEDULE_CHANGED')
    if (receipt.get('schema') != SCHEMA or receipt.get('checker_sha256') != _source_hashes()['service_verifier.py']
            or receipt.get('verifier_errors') != checker['errors']
            or receipt.get('independent_checker_accepted') is not checker['accepted']
            or receipt.get('business_acceptance_accepted') is not report.get('accepted')
            or receipt.get('result') != ('QUALIFIED_SYNTHETIC_DELIVERY' if checker['accepted'] and report.get('accepted') is True else 'NOT_QUALIFIED')
            or receipt.get('observed_revenue_cents') != 0 or receipt.get('actual_customer_acceptance') is not False
            or receipt.get('no_external_certification') is not True):
        raise ValueError('INDEPENDENT_ACCEPTANCE_RECOMPUTATION_FAILED')
    if (offer.get('schema') != SCHEMA or offer.get('scope') != service.SCOPE
            or offer.get('order_id') != order.get('order_id')
            or offer.get('quoted_terms') != 'HYPOTHETICAL_PRICE_NOT_ACCEPTED_OR_PAYABLE'
            or offer.get('consent_or_payment_collected') is not False
            or offer.get('qualification') != receipt.get('result')
            or offer.get('exceptions_disclosed') != len(report['exceptions'])
            or type(offer.get('quoted_price_cents')) is not int
            or not 1 <= offer['quoted_price_cents'] <= 10**14):
        raise ValueError('QUOTE_OR_SCOPE_MANIPULATION')
    if manifest.get('order_id') != order.get('order_id'):
        raise ValueError('ORDER_IDENTITY_MISMATCH')
    return {'schema': SCHEMA, 'source_bound': True, 'recomputed_independently': True,
            'qualification': receipt['result'], 'quoted_price_cents': offer['quoted_price_cents'],
            'actual_customers': 0, 'actual_collections_cents': 0,
            'does_not_authorize_collection': True,
            'manifest_sha256': digest(_read(root / 'MANIFEST.json'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build_cmd = sub.add_parser('build')
    build_cmd.add_argument('--input', type=Path, required=True)
    build_cmd.add_argument('--output', type=Path, required=True)
    build_cmd.add_argument('--price-cents', type=int, required=True)
    verify_cmd = sub.add_parser('verify')
    verify_cmd.add_argument('--path', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'build':
            data = _json_bytes(_read(args.input))
            result = build(data, args.output, price_cents=args.price_cents)
        else:
            result = verify(args.path)
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()