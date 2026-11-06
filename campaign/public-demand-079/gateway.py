"""Reproducible public-notice screening; no customer, money, or execution authority."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROTOCOL_GIT_BLOB = '1ae4207459a7aabeba2e6f01f6a079ce14515eac'
AS_OF = date(2026, 11, 3)
REASONS = ('NO_COLLECTED_BUYER_COMMITMENT', 'DELIVERY_AND_ACCEPTANCE_NOT_QUALIFIED',
           'COMPLETE_COSTS_UNVERIFIED', 'FUNDED_CAPACITY_UNVERIFIED',
           'CANONICAL_ACCOUNT_AND_LIABILITIES_NOT_AUTHENTICATED', 'STRONG_OUTSIDE_OPTIONS_UNCOSTED')

def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def registered_protocol() -> tuple[dict, str]:
    data = (ROOT / 'PROTOCOL.json').read_bytes()
    if git_blob(data) != PROTOCOL_GIT_BLOB:
        raise ValueError('REGISTERED_PROTOCOL_BYTES_CHANGED')
    p = json.loads(data)
    if len(p['routes']) != 3 or len({r['id'] for r in p['routes']}) != 3:
        raise ValueError('REGISTERED_DENOMINATOR_CHANGED')
    return p, hashlib.sha256(data).hexdigest()

def assess(route: dict) -> dict:
    registered, _ = registered_protocol()
    indexed = {r['id']: r for r in registered['routes']}
    if route['id'] not in indexed:
        raise ValueError('UNREGISTERED_ROUTE')
    if any(key in route for key in ('estimated_profit', 'paid', 'synthetic_buyer', 'native_cash', 'cost', 'contract')):
        raise ValueError('UNREGISTERED_TRANSACTION_OR_COST_FIELD')
    if any(type(route[key]) is not bool for key in ('primary_verified', 'formal_bid_allowed', 'buyer_commitment',
                                                    'our_deliverable_validated', 'full_costs_known', 'reach_verified')):
        raise ValueError('STRICT_REGISTERED_BOOLEAN_REQUIRED')
    if route != indexed[route['id']]:
        raise ValueError('REGISTERED_ROUTE_CHANGED_OR_UNVERIFIED_AMENDMENT')
    reasons = list(REASONS)
    closing = date.fromisoformat(route['response_deadline'])
    if route['notice_type'] == 'RFI_SOURCES_SOUGHT':
        reasons.append('RFI_IS_MARKET_RESEARCH_NOT_A_PURCHASE_ORDER')
    elif route['notice_type'] == 'CLOSED_TESTING_STREAM':
        reasons.append('PUBLIC_SOLICITATION_CLOSED')
    elif route['notice_type'] == 'RFP_UNVERIFIED_PRIMARY':
        reasons.append('PRIMARY_REQUIREMENTS_AND_AMENDMENTS_UNVERIFIED')
    else:
        raise ValueError('UNREGISTERED_NOTICE_CLASSIFICATION')
    if closing < AS_OF:
        reasons.append('RESPONSE_DATE_HAS_PASSED')
    if not route['primary_verified']:
        reasons.append('PRIMARY_SOURCE_NOT_VERIFIED')
    if route['formal_bid_allowed'] or route['buyer_commitment'] or route['our_deliverable_validated'] or route['full_costs_known'] or route['reach_verified']:
        raise ValueError('REGISTERED_ZERO_AUTHORITY_SCOPE_CHANGED')
    if route['expected_result'] != 'NO_DEPLOY':
        raise ValueError('REGISTERED_RESULT_CHANGED')
    return {'id': route['id'], 'arrangement': route['arrangement'], 'notice_type': route['notice_type'],
            'source_url': route.get('primary_source_url') or route.get('secondary_source_url'),
            'source_evidence': 'PRIMARY_NOTICE_PAGE_OBSERVED_NOT_BYTES_ATTESTED' if route['primary_verified'] else 'SECONDARY_LISTING_PRIMARY_UNVERIFIED',
            'response_deadline': closing.isoformat(), 'decision': 'NO_DEPLOY',
            'reasons': sorted(set(reasons)), 'customers_contractually_committed': 0,
            'paid_contracts_verified': 0, 'native_profit_microUSD': None,
            'source_bytes_independently_hashed': False}

def build() -> dict:
    p, sha = registered_protocol()
    routes = [assess(r) for r in p['routes']]
    if [r['id'] for r in routes] != [r['id'] for r in p['routes']]:
        raise ValueError('ROUTE_ORDER_CHANGED')
    return {'schema': 'agi-alpha/public-demand079/decision-v1', 'as_of_date': AS_OF.isoformat(),
            'registration_commit': 'dbdbafc5bb94ea98f8f4463dacbc8eac2fb590f1',
            'protocol_sha256': sha, 'registered_routes': len(routes), 'assessed_routes': routes,
            'no_deploy_available': True, 'selected': 'NO_DEPLOY',
            'actual_buyers': 0, 'actual_collected_revenue_USD': 0,
            'actual_trailing_365_complete_cost_profit_USD': None,
            'target_3b_qualified': False, 'native_account_opened_or_modified': False,
            'external_action_taken': False, 'new_external_spending': False,
            'scope': 'PUBLIC_NOTICE_SCREENING_NOT_TRANSACTIONAL_DEMAND_OR_BLUE_SKY_ADMISSION',
            'next_decision': 'Investigate exact primary requirement and independently accepted, fully costed outcome before any financial, bid or launch action.'}

def audit(candidate: dict) -> None:
    if candidate != build():
        raise ValueError('DECISION_OR_SOURCE_BINDING_MISMATCH')

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'audit'])
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    if args.action == 'run':
        if args.file.exists() or args.file.is_symlink():
            raise ValueError('FRESH_OUTPUT_REQUIRED')
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_text(json.dumps(build(), sort_keys=True, indent=2) + '\n')
    else:
        audit(json.loads(args.file.read_text()))
    print(json.dumps({'action': args.action, 'verified': True, 'decision': 'NO_DEPLOY'}))

if __name__ == '__main__':
    main()
