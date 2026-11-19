"""Read-only smallest-unit fee feasibility for a prospective fee-bearing EVM offer.

Conditional arithmetic only: no blockchain access, actual payments, native
enterprise finance, real token exchange value or proof of willing buyers.
It must NOT substitute for canonical JournalAccount/Account receipts.
"""
from __future__ import annotations

from fractions import Fraction

UINT256_MAX = (1 << 256) - 1
MAX_FEE_BPS = 250


class PrecisionRefusal(ValueError):
    """Fail closed on a non-representable on-chain arithmetic input."""


def microfee_receipt(amounts: list[int], fee_bps: int) -> dict:
    """Model successful, compliant per-order EVM settlements in raw token units.

    Solidity 0.8.x's checked `principal * feeBps / 10000` floors per job,
    NOT once across many jobs. Bundling is a *different service contract*
    and its sole-job result is only a hypothetical comparison.
    """
    if type(fee_bps) is not int or not 0 <= fee_bps <= MAX_FEE_BPS:
        raise PrecisionRefusal("INVALID_FEE_BPS")
    if type(amounts) is not list or not amounts:
        raise PrecisionRefusal("NONEMPTY_FINITE_ORDERS_REQUIRED")
    per_order = []
    for amount in amounts:
        if type(amount) is not int or not 0 < amount <= UINT256_MAX:
            raise PrecisionRefusal("INVALID_RAW_PRINCIPAL")
        # Match Solidity's intermediate multiplication, not Python bigint
        if fee_bps and amount > UINT256_MAX // fee_bps:
            raise PrecisionRefusal("SOLIDITY_MULTIPLICATION_OVERFLOW")
        per_order.append(amount * fee_bps // 10_000)

    principal_sum = sum(amounts)
    fee_sum = sum(per_order)
    ideal = Fraction(principal_sum * fee_bps, 10_000)
    bundle_representable = (principal_sum <= UINT256_MAX and
                            (fee_bps == 0 or principal_sum <= UINT256_MAX // fee_bps))
    pooled = (principal_sum * fee_bps // 10_000) if bundle_representable else None
    return {
        "schema": "montreal.ai/microfee-conditional-v1",
        "role": "READ_ONLY_CONDITIONAL_RAW_UNIT_ARITHMETIC_NOT_REVENUE",
        "onchain_executed": False,
        "actual_collected_raw_fees": None,
        "actual_usd_revenue": None,
        "real_token_identity_and_decimals_verified": False,
        "raw_to_synthetic_unit_conversion": "UNESTABLISHED",
        "fee_bps": fee_bps,
        "number_of_independent_orders": len(amounts),
        "total_raw_principal": str(principal_sum),
        "per_order_raw_fees": [str(x) for x in per_order],
        "conditional_per_order_fee_sum_raw": str(fee_sum),
        "ideal_rational_fee_if_same_unit": str(ideal),
        "one_bundle_fee_raw_if_representable": (str(pooled) if pooled is not None else None),
        "one_bundle_is_distinct_contract_and_delivery": True,
        "difference_bundle_minus_independent_raw_if_representable":
            (str(pooled - fee_sum) if pooled is not None else None),
        "decision": "NO_DEPLOY_NO_REAL_PROFIT_CLAIM",
    }
