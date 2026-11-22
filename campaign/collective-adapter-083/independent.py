"""Independent exhaustive feasibility and delivered-byte audit for 083."""
import hashlib
import itertools
import json
from pathlib import Path
from engine import fixtures, digest, SCHEMA

FROZEN_CASE_DIGEST = '5caa2514128c438616db9572b89de6927322e2cecf03846b6afb9bb8098e7ef6'


def independently_apply(artifact, message):
    if artifact.get('schema') != SCHEMA or not isinstance(artifact.get('normalizer'), dict):
        raise ValueError('INDEPENDENT_INVALID_ADAPTER')
    mapping = artifact['normalizer'].get('source_fields')
    if not isinstance(mapping, dict) or set(mapping) != {'event_type', 'measurement'} or len(set(mapping.values())) != 2:
        raise ValueError('INDEPENDENT_INVALID_MAPPING')
    if not isinstance(message, dict) or any(v not in message for v in mapping.values()):
        raise ValueError('INDEPENDENT_MISSING_SOURCE_FIELD')
    return {'event_type': message[mapping['event_type']], 'measurement': message[mapping['measurement']]}



def ordinary_coalitions(case):
    candidates = []
    eligible = [x for x in case['buyers'] if x['consent'] is True and x['rights'] is True]
    for size in range(1, len(eligible) + 1):
        for selected in itertools.combinations(eligible, size):
            spend = case['fixed'] + case['variable'] * size + case['seller_margin']
            total = sum(min(b['budget'], max(0, b['value'] - b['outside'])) for b in selected)
            if total >= spend:
                surplus = sum(b['value'] - b['outside'] for b in selected) - spend
                candidates.append((surplus, size, tuple(b['id'] for b in selected)))
    if not candidates: return ()
    return max(candidates)[2]


def audit(folder):
    folder = Path(folder)
    result = json.loads((folder/'RESULT.json').read_text())
    if (result['schema'] != SCHEMA or digest(fixtures()) != FROZEN_CASE_DIGEST
            or result['source_world_digest'] != FROZEN_CASE_DIGEST):
        raise ValueError('CHANGED_REGISTRATION_OR_WORLD')
    if set(result['worlds']) != set(fixtures()): raise ValueError('LOST_REGISTERED_WORLD')
    if result.get('actual_buyers') != 0 or result.get('actual_collections') != 0 or result.get('actual_365_day_complete_cost_profit') is not None or result.get('target_3b_achieved') is not False or result.get('deployment_authorized') is not False:
        raise ValueError('INVALID_REAL_COMMERCE_UPGRADE')
    checked = 0
    for name, case in fixtures().items():
        row = result['worlds'][name]
        if row['case_sha256'] != digest(case): raise ValueError('CHANGED_CASE')
        oracle = ordinary_coalitions(case)
        if tuple(row['plan']['buyers']) != oracle: raise ValueError('INCORRECT_COALITION_OR_ORDINARY_CONTROL')
        selected = [b for b in case['buyers'] if b['id'] in oracle]
        if not oracle:
            if (folder/name).exists():
                raise ValueError('UNAUTHORIZED_ADAPTER_FOR_REFUSED_CASE')
            if row['plan']['status'] != 'NO_FEASIBLE_VOLUNTARY_COALITION' or row['artifact_file_sha256'] or row['conditional_cost_incurred']:
                raise ValueError('FALSE_NO_DEPLOY_OR_SPEND')
            continue
        if row['plan']['construction_cost'] != case['fixed'] + len(selected) * case['variable']:
            raise ValueError('INCOMPLETE_COST')
        if row['plan']['price_total'] != row['plan']['construction_cost'] + case['seller_margin']:
            raise ValueError('MISSING_SELLER_COST_OR_MARGIN')
        if sum(row['plan']['shares'].values()) != row['plan']['price_total']:
            raise ValueError('DUPLICATED_OR_UNFUNDED_PLEDGE')
        if any(row['plan']['shares'][b['id']] > min(b['budget'], b['value'] - b['outside']) or row['plan']['shares'][b['id']] < 0 for b in selected):
            raise ValueError('PARTICIPATION_OR_BUDGET_VIOLATION')
        if row['conditional_cost_incurred'] != row['plan']['construction_cost']:
            raise ValueError('FAILED_ATTEMPT_COST_ERASED')
        escrow = row['plan']['price_total']
        collateral = case['seller_refund_collateral']
        if (row['hypothetical_escrow_receipts'] != escrow
                or row['hypothetical_preconstruction_cash'] != escrow + collateral
                or row['hypothetical_cash_after_cost'] != escrow + collateral - row['conditional_cost_incurred']
                or row['refund_reserve_before_acceptance'] != escrow
                or row['refund_reserve_covered_before_acceptance'] != (collateral >= row['conditional_cost_incurred'])
                or row['hypothetical_cash_after_full_refund'] != row['hypothetical_cash_after_cost'] - row['conditional_refund_liability']):
            raise ValueError('BROKEN_ESCROW_COLLATERAL_CASH_TIMELINE')
        observed_files = {p.name for p in (folder/name).glob('*.json')} if (folder/name).is_dir() else set()
        expected_files = {b['id'] + '.json' for b in selected}
        if observed_files != expected_files or set(row['artifact_file_sha256']) != {b['id'] for b in selected}:
            raise ValueError('UNAUTHORIZED_EXTRA_OR_MISSING_ADAPTER')
        for b in selected:
            artifact_path = folder/name/(b['id']+'.json')
            blob = artifact_path.read_bytes()
            if hashlib.sha256(blob).hexdigest() != row['artifact_file_sha256'][b['id']]:
                raise ValueError('CHANGED_DELIVERABLE_BYTES')
            art = json.loads(blob)
            if art['buyer_id'] != b['id'] or art['schema'] != SCHEMA:
                raise ValueError('WRONG_BUYER_OR_ADAPTER')
            if art['normalizer']['source_fields'] != b['fields']:
                raise ValueError('SOURCE_MAPPING_CHANGED_OR_UNAUTHORIZED')
            found = all(independently_apply(art, t['input']) == t['expected'] for t in b['tests'])
            if row['acceptance'][b['id']] != found: raise ValueError('FALSE_ACCEPTANCE')
            checked += len(b['tests'])
        if not all(row['acceptance'].values()):
            if row['economic_status'] != 'FAILED_ACCEPTANCE_REFUND_DUE' or row['conditional_refund_liability'] != row['plan']['price_total']:
                raise ValueError('MISSING_REFUND_AFTER_FAILURE')
        elif row['declared_hypothetical_collateral'] < row['required_preconstruction_refund_collateral']:
            if row['economic_status'] != 'INSUFFICIENT_REFUND_COLLATERAL': raise ValueError('INSOLVENT_ACCEPTANCE')
        elif row['economic_status'] != 'CONDITIONAL_ACCEPTED_NOT_COLLECTED' or row['conditional_refund_liability'] != 0:
            raise ValueError('FALSE_CONDITIONAL_RESULT')
    return {'accepted': True, 'worlds': len(result['worlds']), 'checked_independent_artifact_vectors': checked,
            'ordinary_complete_coalition_matches': len(result['worlds']), 'actual_paid_commerce': False,
            'special_invention_advantage': False, 'objective_USD_3b': False}
