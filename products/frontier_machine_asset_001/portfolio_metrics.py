"""Read-only asset-level economic evidence, never synthetic USD profit."""
import sqlite3

from payment_receipts import ETH_TOKEN, SOL_MINT


def asset_economics(database):
    """Count real and fixture receipts separately; do not infer cash/profit.

    Ethereum and Solana raw units are NOT summed across networks. A final
    chain event is a payment observation, not a full business financial audit.
    """
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        orders = db.execute(
            "SELECT chain, state, amount_units FROM orders").fetchall()
        settlements = db.execute("""
            SELECT o.chain, o.state, o.amount_units, s.mode
            FROM orders o JOIN settlements s ON o.order_id=s.order_id
        """).fetchall()
    by_chain = {
        "ethereum": {"token_contract": ETH_TOKEN, "orders": 0, "delivered": 0,
                     "live_verified_transfers": 0, "live_transfer_raw_units": "0",
                     "fixture_transfers": 0},
        "solana": {"token_mint": SOL_MINT, "orders": 0, "delivered": 0,
                   "live_verified_transfers": 0, "live_transfer_raw_units": "0",
                   "fixture_transfers": 0},
    }
    for order in orders:
        if order["chain"] not in by_chain:
            raise ValueError("UNKNOWN_ASSET_CHAIN")
        target = by_chain[order["chain"]]
        target["orders"] += 1
        target["delivered"] += int(order["state"] == "DELIVERED")
    for settlement in settlements:
        target = by_chain[settlement["chain"]]
        if settlement["mode"] == "LIVE_RPC":
            target["live_verified_transfers"] += 1
            target["live_transfer_raw_units"] = str(
                int(target["live_transfer_raw_units"]) + int(settlement["amount_units"]))
        elif settlement["mode"] == "TEST_FIXTURE_NOT_REVENUE":
            target["fixture_transfers"] += 1
        else:
            raise ValueError("UNKNOWN_SETTLEMENT_PROVENANCE")
    return {
        "schema": "montreal.ai/frontier-assets-economics/v0",
        "chain_activity": by_chain,
        "collected_fiat": "UNKNOWN_NOT_ACCOUNTED",
        "token_fiat_conversion": "NOT_PERFORMED",
        "recognized_sales_revenue": "NOT_ESTABLISHED",
        "contribution_profit": "NOT_ESTABLISHED",
        "invention_superiority": "NOT_ESTABLISHED",
        "valuation": "NOT_ESTABLISHED",
        "evidence": "READ_ONLY_LOCAL_LEDGER; no independent financial audit",
    }
