"""Frozen authored treasury-reconciliation tests; no provider credentials or money.

See docs/alpha-economic-engine/TREASURY_GATE_REVIEW.md, frozen before tests.
"""
import unittest

from connected_enterprise.alpha_economic.core import digest, parse, sign
from connected_enterprise.alpha_economic.gateway import TreasuryGateway


KEY = b"authored-review-hmac-key-not-live-0123456789"
NOW = 1794870000


def gateway_with(result):
    def send(method, url, headers, raw, *, hosts):
        request = parse(raw)["body"]
        receipt = {
            "kind": "treasury-receipt",
            "account": "authored-example-account",
            "mode": "test",
            "request_sha256": digest(request),
            "idempotency_key": request["idempotency_key"],
            "authorized": True,
            "result": result,
            "expires_at": NOW + 90,
        }
        return sign(receipt, KEY)

    return TreasuryGateway(
        "https://example.org", KEY, KEY, "authored-example-account",
        enabled=True, mode="test", sender=send, clock=lambda: NOW
    )


class ObligationReconciliationGateTests(unittest.TestCase):
    def test_reported_uncovered_obligations_must_block_transition(self):
        g = gateway_with({"obligations_covered": False, "costs_reconciled": True})
        with self.assertRaisesRegex((ValueError, PermissionError), "OBLIGATIONS"):
            g.advance(123)

    def test_omitted_coverage_must_not_default_to_success(self):
        g = gateway_with({"costs_reconciled": True})
        with self.assertRaisesRegex((ValueError, PermissionError), "OBLIGATIONS"):
            g.advance(123)

    def test_unreconciled_costs_must_block_transition(self):
        g = gateway_with({"obligations_covered": True, "costs_reconciled": False})
        with self.assertRaisesRegex((ValueError, PermissionError), "COSTS"):
            g.advance(123)

    def test_truthy_non_boolean_receipts_must_not_be_accepted(self):
        for field, value in (
            ("obligations_covered", "yes"),
            ("obligations_covered", 1),
            ("costs_reconciled", "yes"),
            ("costs_reconciled", 1),
        ):
            with self.subTest(field=field, value=value):
                result = {"obligations_covered": True, "costs_reconciled": True}
                result[field] = value
                with self.assertRaises((ValueError, PermissionError)):
                    gateway_with(result).advance(123)

    def test_explicitly_reconciled_signed_receipt_remains_usable(self):
        result = {
            "obligations_covered": True,
            "costs_reconciled": True,
            "time_hour": 123,
        }
        self.assertEqual(gateway_with(result).advance(123), result)


if __name__ == "__main__":
    unittest.main()
