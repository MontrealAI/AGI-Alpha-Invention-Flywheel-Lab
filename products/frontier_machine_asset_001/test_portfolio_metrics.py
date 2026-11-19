"""Economic metric boundaries: fixtures never become real sales."""
import tempfile
from pathlib import Path
import unittest

from market import Market, Merchant, PRODUCT_ID
from portfolio_metrics import asset_economics

PAYER_E = "0x" + "bb" * 20
PAYER_S = "7" * 44


def payment_fixture(q):
    return {
        "event_id": "TEST:" + q["tx_ref"],
        "chain": q["chain"], "finality": "finalized",
        "amount_units": q["amount_units"], "recipient": q["recipient"],
    }


class EconomicsTests(unittest.TestCase):
    def test_separate_token_units_and_non_revenue(self):
        with tempfile.TemporaryDirectory() as d:
            market = Market(
                Path(d) / "protected" / "market.db",
                Merchant(
                    eth_treasury="0x" + "aa" * 20,
                    eth_price_units=str(10**18),
                    eth_rpc="https://example.invalid/eth",
                    sol_treasury_owner="8" * 44,
                    sol_treasury_token_account="9" * 44,
                    sol_price_units="1000000",
                    sol_rpc="https://example.invalid/sol",
                ),
                verifier=payment_fixture,
            )
            task = {
                "contract": {
                    "id_field": "id",
                    "rules": [{"from": "v", "to": "x", "op": "strip"}],
                },
                "source_rows": [{"id": "1", "v": "  y  "}],
            }
            e = market.issue(PRODUCT_ID, task, "ethereum", PAYER_E, now=1700000000)
            s = market.issue(PRODUCT_ID, task, "solana", PAYER_S, now=1700000000)
            market.claim(e["order_id"], e["access_secret"], "0x" + "a" * 64,
                         now=1700000060)
            market.claim(s["order_id"], s["access_secret"], "B" * 88,
                         now=1700000060)
            market.deliver(s["order_id"], s["access_secret"])
            report = asset_economics(market.database)
            self.assertEqual(report["chain_activity"]["ethereum"]["orders"], 1)
            self.assertEqual(report["chain_activity"]["solana"]["orders"], 1)
            self.assertEqual(report["chain_activity"]["solana"]["delivered"], 1)
            self.assertEqual(report["chain_activity"]["ethereum"]["delivered"], 0)
            self.assertEqual(report["chain_activity"]["ethereum"]["fixture_transfers"], 1)
            self.assertEqual(report["chain_activity"]["solana"]["fixture_transfers"], 1)
            self.assertEqual(report["chain_activity"]["ethereum"]["live_verified_transfers"], 0)
            self.assertEqual(report["chain_activity"]["solana"]["live_transfer_raw_units"], "0")
            self.assertEqual(report["collected_fiat"], "UNKNOWN_NOT_ACCOUNTED")
            self.assertEqual(report["contribution_profit"], "NOT_ESTABLISHED")
            self.assertEqual(report["valuation"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
