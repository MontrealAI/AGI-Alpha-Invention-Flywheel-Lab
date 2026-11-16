"""Fail-closed external Checkout expiry tests. All payments are authored fixtures.

These tests do not interact with Stripe, real buyers or an actual treasury.
The controller must not leave expired accepted orders spinning or silently book
an ambiguous payment as unrestricted earnings.
"""
from pathlib import Path
import tempfile
import unittest

from connected_enterprise.alpha_economic.core import digest, identifier
from connected_enterprise.alpha_economic.demo import example
from connected_enterprise.alpha_economic.live import LiveEngine
from connected_enterprise.alpha_economic.runtime import default_policy


class Agent:
    scope = "CONFIGURED_MODEL"


class Buyer:
    scope = "EXTERNAL_BUYER_GATEWAY"
    enabled = True


class Treasury:
    mode = "test"
    enabled = True

    def __init__(self):
        self.refunds = []
        self.begins = []

    def refund(self, contract, day, provider_refund):
        self.refunds.append((identifier(contract), provider_refund["id"]))
        return {"scope": "AUTHORED_TREASURY_FIXTURE", "refunded": True}

    def begin(self, *args):
        self.begins.append(args)
        raise AssertionError("Expired contracts must not start production")


class Payments:
    mode = "test"
    authorized = True

    def __init__(self, outcome):
        self.outcome = outcome
        self.checks = 0
        self.checkouts = 0
        self.refunds = []

    def checkout(self, *args):
        self.checkouts += 1
        raise AssertionError("Expired contracts must not create Checkout sessions")

    def checkout_status(self, contract, session):
        self.checks += 1
        assert session == "cs_test_authored"
        return self.outcome

    def refund(self, intent, amount, request_id):
        self.refunds.append((intent, amount, request_id))
        return {"id": "re_authored", "status": "succeeded"}


class ExpiredCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.contract = example()
        self.now = [self.contract["expires_at"] + 1]
        self.policy = default_policy()
        self.policy.update(scope="EXTERNAL_TEST", opening_microUSD=0, startup_microUSD=0)
        self.treasury = Treasury()

    def engine(self, outcome, with_checkout):
        payments = Payments(outcome)
        engine = LiveEngine(
            Path(self.temp.name) / "engine", self.policy, Agent(), Buyer(), {},
            self.treasury, payments,
            success_url="https://example.org/yes",
            cancel_url="https://example.org/no",
            authorized=True, clock=lambda: self.now[0],
        )
        job = identifier(self.contract)
        engine.state.add(job, self.contract, priority=1)
        engine.state.move(job, "QUALIFIED")
        data = {"consent": {"kind": "fixture"}}
        if with_checkout:
            data["checkout"] = {"id": "cs_test_authored"}
        engine.state.move(job, "CONSENTED", data)
        return engine, payments, job

    def test_expired_contract_never_creates_a_new_checkout(self):
        e, payments, job = self.engine({"pending": True}, with_checkout=False)
        self.assertTrue(e._advance_one(e.state.get(job)))
        self.assertEqual(e.state.get(job)["state"], "DECLINED")
        self.assertEqual(payments.checkouts, 0)
        self.assertEqual(payments.checks, 0)

    def test_provider_confirmed_expired_unpaid_checkout_does_not_wait_forever(self):
        e, payments, job = self.engine({"pending": True, "expired": True}, with_checkout=True)
        self.assertTrue(e._advance_one(e.state.get(job)))
        self.assertEqual(e.state.get(job)["state"], "DECLINED")
        self.assertEqual(payments.checks, 1)
        self.assertEqual(self.treasury.begins, [])

    def test_ambiguous_unexpired_checkout_requires_reconciliation(self):
        e, payments, job = self.engine({"pending": True, "expired": False}, with_checkout=True)
        self.assertFalse(e._advance_one(e.state.get(job)))
        self.assertEqual(e.state.get(job)["state"], "CONSENTED")
        self.assertTrue(e.state.paused())
        self.assertEqual(payments.checks, 1)

    def test_paid_order_after_contract_expiry_refunds_without_production(self):
        paid = {
            "scope": "STRIPE_TEST",
            "contract_sha256": digest(self.contract),
            "payment_intent": "pi_authored",
            "gross_microUSD": self.contract["price_microUSD"],
            "fee_microUSD": 0,
            "net_microUSD": self.contract["price_microUSD"],
        }
        e, payments, job = self.engine(paid, with_checkout=True)
        self.assertTrue(e._advance_one(e.state.get(job)))
        self.assertEqual(e.state.get(job)["state"], "REFUND_PENDING")
        self.assertTrue(e._advance_one(e.state.get(job)))
        self.assertEqual(e.state.get(job)["state"], "REFUNDED")
        self.assertEqual(payments.refunds, [("pi_authored", 1200, job)])
        self.assertEqual(len(self.treasury.refunds), 1)
        self.assertEqual(self.treasury.begins, [])

    def test_expired_checkout_while_contract_valid_is_declined(self):
        e, payments, job = self.engine({"pending": True, "expired": True}, with_checkout=True)
        self.now[0] = self.contract["expires_at"] - 1
        self.assertTrue(e._advance_one(e.state.get(job)))
        self.assertEqual(e.state.get(job)["state"], "DECLINED")
        self.assertEqual(payments.checks, 1)


if __name__ == "__main__":
    unittest.main()
