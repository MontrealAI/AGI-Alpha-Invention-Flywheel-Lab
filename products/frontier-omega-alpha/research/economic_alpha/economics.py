"""Verify a locally authorized reviewer packet and reconcile exact minor units."""

from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from ..reflective_gate import assess_source_groups

MAX_RECORD = 12 * 1024 * 1024
IDENTITY = re.compile(r'[a-z0-9][a-z0-9._-]{0,79}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def bounded_file(path, maximum=MAX_RECORD):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Unexpected or oversized evidence file')
    with path.open('rb') as stream:
        value = stream.read(maximum + 1)
    if not value or len(value) > maximum:
        raise ValueError('Empty or oversized evidence file')
    return value


def source_index(entries, directory):
    if not isinstance(entries, list) or not 1 <= len(entries) <= 80:
        raise ValueError('Use the registered bounded evidence envelope')
    index = {}
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {'id', 'file', 'sha256', 'upstream', 'role'}
                or any(not isinstance(entry[key], str) or not IDENTITY.fullmatch(entry[key])
                       for key in ('id', 'file', 'upstream', 'role'))
                or entry['id'] in index or not SHA.fullmatch(entry['sha256'])):
            raise ValueError('Invalid source identity or path')
        payload = bounded_file(directory / entry['file'])
        if sha256(payload).hexdigest() != entry['sha256']:
            raise ValueError('Evidence digest mismatch')
        index[entry['id']] = entry
    by_digest = {}
    for entry in index.values():
        if by_digest.setdefault(entry['sha256'], entry['upstream']) != entry['upstream']:
            raise ValueError('One raw source was assigned multiple independent origins')
    return index


def required_source(index, reference, role):
    source = index.get(reference)
    if not source or source['role'] != role:
        raise ValueError('Missing or mismatched ' + role + ' evidence')
    return source


def measured_number(item, index, role):
    if item is None:
        return None
    if not isinstance(item, dict) or set(item) != {'minor', 'source'} or type(item['minor']) is not int or item['minor'] < 0:
        raise ValueError('Use positive or verified zero amounts in exact minor units')
    required_source(index, item['source'], role)
    return item['minor']


def route_net(route, roles, cost_categories):
    if (set(route) != {'collected', 'refunds', 'cash_reduction', 'costs', 'matched', 'comparison_source'}
            or type(route['matched']) is not bool or set(route['costs']) != set(cost_categories)):
        raise ValueError('Incomplete route and full-cost accounting schema')
    if route['matched']:
        required_source(roles, route['comparison_source'], 'matched_outcome')
    payments = measured_number(route['collected'], roles, 'settlement')
    refunds = measured_number(route['refunds'], roles, 'settlement')
    cash_reduction = measured_number(route['cash_reduction'], roles, 'cash_reduction')
    costs = [measured_number(route['costs'][category], roles, 'cost_ledger') for category in cost_categories]
    amounts = (payments, refunds, cash_reduction, *costs)
    if route['matched'] and None not in amounts:
        return payments, payments - refunds, payments - refunds + cash_reduction - sum(costs)
    return payments, None if payments is None or refunds is None else payments - refunds, None


def _assessment(packet, directory, protocol):
    fields = {'schema', 'period', 'currency', 'beneficiary', 'operator', 'reviewer', 'authorization',
              'acceptance', 'fulfillment', 'benefit', 'minimum_benefit_minor', 'evidence', 'routes'}
    if set(packet) != fields or packet['schema'] != 'frontier-omega-alpha/reviewed-economic-pilot-v1':
        raise ValueError('Unsupported economic pilot packet')
    start, end = packet['period']
    if (date.fromisoformat(start) > date.fromisoformat(end)
            or not re.fullmatch(r'[A-Z]{3}', packet['currency'])
            or type(packet['minimum_benefit_minor']) is not int or packet['minimum_benefit_minor'] <= 0
            or any(not isinstance(packet[key], str) or not IDENTITY.fullmatch(packet[key]) for key in ('beneficiary', 'operator', 'reviewer'))
            or packet['operator'] != 'montreal-ai'
            or len({packet['beneficiary'], packet['operator'], packet['reviewer']}) != 3):
        raise ValueError('Require a common period, currency and distinct reviewed roles')
    index = source_index(packet['evidence'], directory)
    if any(source['upstream'] == packet['reviewer'] for source in index.values()):
        raise ValueError('The evaluator cannot be an upstream origin of the commercial records')
    required_source(index, packet['authorization'], 'owner_authorization')
    acceptance = required_source(index, packet['acceptance'], 'beneficiary_acceptance')
    fulfilled = required_source(index, packet['fulfillment'], 'fulfillment')
    if acceptance['upstream'] != packet['beneficiary'] or fulfilled['upstream'] == acceptance['upstream']:
        raise ValueError('Need accepted delivery and a separately sourced fulfillment record')
    benefit = measured_number(packet['benefit'], index, 'benefit_ledger')
    routes = packet['routes']
    if set(routes) != {'alpha', *protocol['alternatives']}:
        raise ValueError('Use all preregistered competitive routes under the same period and acceptance terms')
    values = {name: route_net(route, index, protocol['cost_categories']) for name, route in routes.items()}
    payments, net_payments, alpha_net = values.pop('alpha')
    if payments and index[routes['alpha']['collected']['source']]['upstream'] in (packet['operator'], packet['beneficiary']):
        raise ValueError('Collected funds require an independent settlement record')
    alternatives = {name: row[2] for name, row in values.items()}
    best = max(alternatives.values()) if None not in alternatives.values() else None
    delta = alpha_net - best if alpha_net is not None and best is not None else None
    material_benefit = benefit is not None and benefit >= packet['minimum_benefit_minor']
    return {'currency': packet['currency'], 'period': packet['period'], 'beneficiary_benefit_minor': benefit,
            'montreal_collected_minor': payments, 'montreal_retained_payment_minor': net_payments,
            'montreal_net_minor': alpha_net, 'best_matched_alternative_minor': best,
            'incremental_net_minor': delta, 'technically_accepted': True,
            'level_2_material_benefit': material_benefit,
            'level_3_payment_collected': payments is not None and payments > 0,
            'level_4_positive_economic_alpha': material_benefit and delta is not None and delta > 0 and alpha_net > 0,
            'source_group_check': assess_source_groups(source['upstream'] for source in index.values()),
            'proof_scope': 'Arithmetic and source receipts under the authorized evaluator attestation',
            'external_action_authorized': False}


def review(packet_path, signature_path, key_path, trusted_key_digest, directory, protocol):
    payload = bounded_file(packet_path, 128 * 1024)
    signature = bounded_file(signature_path, 2048)
    key = bounded_file(key_path, 4096)
    if not SHA.fullmatch(trusted_key_digest) or sha256(key).hexdigest() != trusted_key_digest:
        raise ValueError('Reviewer key must match the owner-approved fingerprint')
    with TemporaryDirectory(prefix='alpha-1-review-') as temporary:
        locked = Path(temporary)
        (locked / 'packet').write_bytes(payload)
        (locked / 'signature').write_bytes(signature)
        (locked / 'reviewer.pem').write_bytes(key)
        command = ['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', 'reviewer.pem', '-rawin',
                   '-in', 'packet', '-sigfile', 'signature']
        verified = subprocess.run(command, cwd=locked, capture_output=True, timeout=10, check=False)
        if verified.returncode != 0:
            raise ValueError('Independent reviewer signature could not be authenticated')
    return _assessment(json.loads(payload), directory, protocol)
