"""ME201: read-only arithmetic and evidence gate; never creates a buyer or account.

No wallet, on-chain payment, production delivery, or canonical finance authority.
Observed third-party transfers are not booked company collections.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
from pathlib import Path

TARGET = Decimal('3000000000')
SOURCES = {
    'observed_directory_october_2026': {
        'source': 'https://nohumans.directory/state/economy-2026-10',
        'published': '2026-11-05',
        'period': '2026-10-01/2026-10-31',
        'sampled_payto_addresses': 1536,
        'classified_usdc_transfers_usd': '40326.41',
        'approx_transfers': 1700000,
        'reported_wallets': 13019,
        'sellers_above_1000_usd': 7,
        'median_address_receipts_usd': '0.29',
        'coverage': 'listed directory payTo addresses; classified transfers, not all x402',
        'raw_source_sha256': None,
        'known_limitations': [
            'transfer to listed payTo does not independently prove purchased service',
            'wallet does not identify unique human, company or autonomous agent',
            'classification filters average daily transfers above USD1',
            'address may serve several APIs or represent several operators',
            'not MONTREAL.AI money, not a total-market estimate',
        ],
    },
    'quoted_competitor_2026_11_12': {
        'source': 'https://brave.com/blog/search-api-agentic-payments/',
        'published': '2026-11-12',
        'quoted_x402_price_usd': '0.005',
        'rights': 'advertised competing API price; not collected receipts',
    },
    'overlapping_context_2026_11_20': {
        'source': 'https://chainreport.co/agent-economy/',
        'as_of': '2026-11-20',
        'listed_endpoints': 37309,
        'endpoints_with_10plus_wallets': 729,
        'rights': 'source-claimed overlapping listing snapshot, not independently audited',
    },
}
OPTIONS = (
    {'id': 'A', 'name': 'Commodity search-like machine API', 'price_usd': '0.005', 'type': 'external_competitor_quoted_price'},
    {'id': 'B', 'name': 'Machine-verified decision', 'price_usd': '0.02', 'type': 'illustrative_unverified_price'},
    {'id': 'C', 'name': 'Accepted consequential outcome', 'price_usd': '10000', 'type': 'illustrative_unverified_price'},
)
MISSING = [
    'externally independently verified dated voluntary MONTREAL.AI buyers',
    'independently accepted and delivered outcomes',
    'actual source-bound reconciled MONTREAL.AI collections',
    'complete actual operating costs including failed acquisition and all tails',
    'dated reachable demand, capacity, and real alternatives',
    'original one-account finance authority and migration qualified',
]

def decimal_amount(value: str | Decimal, *, allow_zero: bool = False) -> Decimal:
    """Require exact finite decimal text, not a float/boolean/NaN convenience."""
    if isinstance(value, bool) or not isinstance(value, (str, Decimal)):
        raise ValueError('EXACT_DECIMAL_TEXT_REQUIRED')
    try:
        dec = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('EXACT_DECIMAL_TEXT_REQUIRED') from exc
    if not dec.is_finite() or (dec < 0 if allow_zero else dec <= 0):
        raise ValueError('NONNEGATIVE_FINITE_AMOUNT_REQUIRED' if allow_zero else 'POSITIVE_FINITE_AMOUNT_REQUIRED')
    return dec

def volume_floor(price: str, *, target: str = '3000000000', variable_cost: str | None = None) -> dict:
    """Gross lower bound; conditional variable-only cost bound, never complete cost."""
    p = decimal_amount(price)
    t = decimal_amount(target)
    gross = int((t / p).to_integral_value(rounding=ROUND_CEILING))
    result = {
        'gross_only_necessary_annual_units': gross,
        'conditional_variable_cost_necessary_annual_units': None,
        'complete_cost_feasibility': 'UNKNOWN',
        'variable_cost_assumption_usd': variable_cost,
        'price_usd': str(p),
    }
    if variable_cost is not None:
        cost = decimal_amount(variable_cost, allow_zero=True)
        margin = p - cost
        result['conditional_variable_cost_necessary_annual_units'] = (
            int((t / margin).to_integral_value(rounding=ROUND_CEILING)) if margin > 0 else None
        )
        result['variable_margin_positive'] = margin > 0
        if margin <= 0:
            result['variable_margin_status'] = 'NO_POSITIVE_PROFIT_AT_THIS_PRICE_AND_UNIT_COST'
    return result

def report() -> dict:
    rows = []
    for option in OPTIONS:
        row = dict(option)
        row['arithmetic'] = volume_floor(option['price_usd'])
        row['evidence_status'] = 'UNQUALIFIED'
        row['admit_to_native_commerce'] = False
        row['reason'] = 'No source-bound MONTREAL.AI accepted buyer/collections/cost/capacity proof'
        rows.append(row)
    rows.append({
        'id': 'D', 'name': 'No-deploy / preserve qualified incumbent',
        'price_usd': None, 'gross_only_necessary_annual_units': None,
        'new_artifacts': 0, 'new_orders': 0, 'new_collections_usd': '0',
        'new_operating_profit_usd': '0', 'admit_to_native_commerce': False,
        'evidence_status': 'DEFAULT_NONENTRY',
        'reason': 'Preserves existing cash/obligations; zero new activity is not achieved profit',
    })
    return {
        'schema': 'agi-alpha/observed-agent-demand201/v1',
        'date': '2026-11-20',
        'source_main_commit': 'f0987aa48d5c9136b28540f54eabf5367e63bbe6',
        'target_usd_trailing_365_complete_cost_profit': '3000000000',
        'observation': SOURCES,
        'sampled_market_is_global_ceiling': False,
        'sampled_wallets_are_confirmed_purchasers': False,
        'sampled_payto_transfers_are_our_sales': False,
        'complete_cost_proven': False,
        'actual_montreal_ai_collections_verified_by_this_instrument': False,
        'real_human_or_agent_buyer_identity_verified': False,
        'all_costs_including_paid_model_host_billing_known': False,
        'missing_admission_evidence': MISSING,
        'alternatives': rows,
        'selected_action': 'NO_DEPLOY_RETAIN_QUALIFIED_INCUMBENT',
        'outcome': 'ARITHMETIC_BOUND_ONLY_NOT_BUSINESS_INVENTION_OR_COMMERCE',
        'actual_trailing_365_profit_usd': None,
        'evidence_digest_scope': 'local authored normalized report only, NOT third-party raw bytes',
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='Fresh destination JSON, created exclusively')
    args = parser.parse_args()
    body = json.dumps(report(), indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            handle.write(body)
        print(json.dumps({'output': str(path), 'sha256': hashlib.sha256(body.encode()).hexdigest()}, sort_keys=True))
    else:
        print(body, end='')

if __name__ == '__main__':
    main()
