"""Offline accounting and commerce-contract tests: no network, no money."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gate import checked_request, produce
from market import Market, Merchant, PRODUCT_ID
from payment_receipts import PaymentRejected, ETH_TOKEN, SOL_MINT

ETH_PAYER = "0x" + "bb" * 20
ETH_TREASURY = "0x" + "aa" * 20
SOL_PAYER = "7" * 44
SOL_OWNER = "8" * 44
SOL_TREASURY = "9" * 44


def request():
    return {
        "contract": {"id_field": "id",
                     "rules": [{"from": "x", "to": "out", "op": "strip"}]},
        "source_rows": [{"id": "a", "x": "  hello  "}],
    }


def test_evidence(quote):
    return {
        "event_id": "TEST_CHAIN_EVENT:" + quote["tx_ref"],
        "chain": quote["chain"],
        "amount_units": quote["amount_units"],
        "recipient": quote["recipient"],
        "finality": "finalized",
        "source": "offline_fixture_not_chain",
    }


def merchant():
    return Merchant(
        eth_treasury=ETH_TREASURY, eth_price_units=str(2 * 10**18),
        eth_rpc="https://example.invalid/rpc",
        sol_treasury_owner=SOL_OWNER, sol_treasury_token_account=SOL_TREASURY,
        sol_price_units="1000000", sol_rpc="https://example.invalid/rpc",
    )


class CommerceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "private" / "market.sqlite3"
        self.market = Market(self.db, merchant(), verifier=test_evidence)

    def tearDown(self):
        self.temp.cleanup()

    def issue(self, chain="solana"):
        payer = SOL_PAYER if chain == "solana" else ETH_PAYER
        return self.market.issue(PRODUCT_ID, request(), chain, payer, now=1700000000)

    def claim(self, q, tx_ref="B" * 88):
        return self.market.claim(q["order_id"], q["access_secret"], tx_ref,
                                 now=1700000060)

    def test_catalog_has_both_real_token_identities(self):
        cat = self.market.catalog()
        self.assertEqual(cat["accepted_tokens"]["ethereum"]["contract"], ETH_TOKEN)
        self.assertEqual(cat["accepted_tokens"]["solana"]["mint"], SOL_MINT)
        self.assertEqual(cat["commercial_demand"], "NOT_ESTABLISHED")

    def test_disabled_by_default(self):
        market = Market(Path(self.temp.name) / "off.sqlite3", merchant())
        self.assertFalse(market.catalog()["quotes_enabled"])
        with self.assertRaises(PaymentRejected):
            market.issue(PRODUCT_ID, request(), "solana", SOL_PAYER)

    def test_solana_quote_has_order_memo(self):
        q = self.issue()
        self.assertEqual(q["chain"], "solana")
        self.assertEqual(q["amount_units"], "1000000")
        self.assertTrue(q["order_memo"].startswith("FRONTIER-OMEGA:" + q["order_id"]))
        self.assertIn(SOL_MINT, q["token"])

    def test_ethereum_quotes_are_exact_and_distinct(self):
        a = self.issue("ethereum")
        b = self.issue("ethereum")
        self.assertNotEqual(a["amount_units"], b["amount_units"])
        self.assertEqual(a["token"], ETH_TOKEN)
        self.assertTrue(a["erc20_exact_amount_binding"])
        self.assertGreater(int(a["amount_units"]), 2 * 10**18)

    def test_no_delivery_before_payment(self):
        q = self.issue()
        with self.assertRaises(PaymentRejected):
            self.market.deliver(q["order_id"], q["access_secret"])

    def test_no_access_with_wrong_secret(self):
        q = self.issue()
        with self.assertRaises(PaymentRejected):
            self.market.status(q["order_id"], "wrong")
        with self.assertRaises(PaymentRejected):
            self.market.claim(q["order_id"], "wrong", "B" * 88, now=1700000060)

    def test_test_payment_delivers_but_never_claims_real_revenue(self):
        q = self.issue()
        claimed = self.claim(q)
        self.assertEqual(claimed["state"], "TEST_VERIFIED")
        self.assertEqual(claimed["company_revenue"], "SIMULATED_ZERO")
        out = self.market.deliver(q["order_id"], q["access_secret"])
        self.assertEqual(out["delivery"][0]["out"], "hello")
        self.assertTrue(out["acceptance"]["accepted"])
        self.assertEqual(out["economic_status"], "TEST_ONLY_NO_REAL_REVENUE")
        self.assertFalse(self.market.status(q["order_id"], q["access_secret"])["real_revenue_established"])

    def test_idempotent_claim_and_delivery(self):
        q = self.issue()
        first = self.claim(q)
        self.assertEqual(self.claim(q), first)
        delivered = self.market.deliver(q["order_id"], q["access_secret"])
        self.assertEqual(self.market.deliver(q["order_id"], q["access_secret"]), delivered)

    def test_prevent_replay_on_another_quote(self):
        a, b = self.issue(), self.issue()
        self.claim(a)
        with self.assertRaisesRegex(PaymentRejected, "TRANSFER_ALREADY_CLAIMED"):
            self.claim(b)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM settlements").fetchone()[0], 1)

    def test_denied_unsupported_asset(self):
        with self.assertRaises(PaymentRejected):
            self.market.issue("fake-invention", request(), "solana", SOL_PAYER)

    def test_bad_source_cannot_be_quoted(self):
        payload = request()
        payload["source_rows"][0]["id"] = ""
        with self.assertRaises(ValueError):
            self.market.issue(PRODUCT_ID, payload, "solana", SOL_PAYER)

    def test_unknown_network_refused(self):
        with self.assertRaises(PaymentRejected):
            self.market.issue(PRODUCT_ID, request(), "devnet", SOL_PAYER)

    def test_claim_expired_after_grace(self):
        q = self.issue()
        with self.assertRaisesRegex(PaymentRejected, "CLAIM_WINDOW_CLOSED"):
            self.market.claim(q["order_id"], q["access_secret"], "B" * 88,
                              now=1700000000 + 1800 + 86401)

    def test_verified_payload_must_match(self):
        bad = lambda quote: {**test_evidence(quote), "recipient": "fake"}
        m = Market(Path(self.temp.name) / "bad.sqlite3", merchant(), verifier=bad)
        q = m.issue(PRODUCT_ID, request(), "solana", SOL_PAYER, now=1700000000)
        with self.assertRaisesRegex(PaymentRejected, "VERIFIER_RESULT_INCOMPLETE"):
            m.claim(q["order_id"], q["access_secret"], "B" * 88,
                    now=1700000060)

    def test_live_cannot_use_stub_verifier(self):
        with self.assertRaises(ValueError):
            Market(Path(self.temp.name) / "live.sqlite3", merchant(),
                   live=True, verifier=test_evidence)

    def test_source_is_not_confused_with_revenue(self):
        q = self.issue()
        self.claim(q)
        with sqlite3.connect(self.db) as db:
            mode = db.execute("SELECT mode FROM settlements").fetchone()[0]
        self.assertEqual(mode, "TEST_FIXTURE_NOT_REVENUE")

    def test_quote_contains_no_private_keys(self):
        q = self.issue()
        self.assertNotIn("private_key", json.dumps(q).lower())
        self.assertNotIn("seed_phrase", json.dumps(q).lower())


if __name__ == "__main__":
    unittest.main()
