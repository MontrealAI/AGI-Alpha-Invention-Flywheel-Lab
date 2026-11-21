"""Adversarial offline tests for OPEN-DEMAND211. All records are synthetic."""
from datetime import datetime, timezone
import json
import unittest

from tools import open_demand211 as m


FUTURE = "2026-11-29T16:00:00Z"
NOW = "2026-11-21T12:00:00Z"


def sample(tags=None, status="active", deadline=FUTURE, value=50000):
    return {
        "id": "test-synthetic-001",
        "ocid": "ocds-synthetic-test",
        "tag": ["tender"] if tags is None else tags,
        "buyer": {"id": "buyer-synthetic", "name": "Synthetic buyer (not real)"},
        "tender": {
            "title": "Synthetic evaluation service (not real)",
            "status": status,
            "tenderPeriod": {"endDate": deadline},
            "value": {"amount": value, "currency": "GBP"},
        }
    }


def payload(releases=None):
    return json.dumps({"releases": [sample()] if releases is None else releases}).encode()


class Contracts(unittest.TestCase):
    def test_positive_is_only_conditional_eligibility_review(self):
        r = m.summarize(payload(), NOW)
        self.assertEqual(r["records"][0]["decision"], "REVIEW_ELIGIBILITY_ONLY")
        self.assertEqual(r["operating_decision"], "HOLD_NO_BID_NO_DEPLOY")
        self.assertIsNone(r["cash_collected"])
        self.assertIsNone(r["complete_cost_profit"])
        self.assertEqual(r["eligibility_reviews_possible"], 1)
        self.assertTrue(r["source_notices_are_not_customers"])

    def test_award_not_open(self):
        r = m.summarize(payload([sample(["award"])]), NOW)
        self.assertIn("NOT_NEW_TENDER_RELEASE", r["records"][0]["reasons"])

    def test_mixed_award_tender_not_open(self):
        r = m.summarize(payload([sample(["tender", "award"])]), NOW)
        self.assertEqual(r["eligibility_reviews_possible"], 0)

    def test_closed(self):
        r = m.summarize(payload([sample(deadline="2026-11-20T10:00:00Z")]), NOW)
        self.assertIn("DEADLINE_NOT_FUTURE", r["records"][0]["reasons"])

    def test_inactive(self):
        r = m.summarize(payload([sample(status="complete")]), NOW)
        self.assertIn("NOT_EXPLICITLY_ACTIVE", r["records"][0]["reasons"])

    def test_unknown_time(self):
        r = m.summarize(payload([sample(deadline="2026-11-30")]), NOW)
        self.assertIn("DEADLINE_MISSING_OR_UNVERIFIABLE", r["records"][0]["reasons"])

    def test_missing_buyer(self):
        r = m.summarize(payload([{**sample(), "buyer": {}}]), NOW)
        self.assertIn("MISSING_PUBLIC_BUYER_OR_TITLE", r["records"][0]["reasons"])

    def test_negative_amount_is_not_money(self):
        r = m.summarize(payload([sample(value=-100)]), NOW)
        self.assertIsNone(r["records"][0]["declared_value"])
        self.assertIsNone(r["cash_collected"])

    def test_unknown_value_is_not_money(self):
        r = m.summarize(payload([sample(value=None)]), NOW)
        self.assertIsNone(r["records"][0]["declared_value"])

    def test_duplicate_keys(self):
        with self.assertRaisesRegex(m.Refusal, "DUPLICATE_KEY"):
            m.summarize(b'{"releases":[],"releases":[]}', NOW)

    def test_excess_records(self):
        with self.assertRaisesRegex(m.Refusal, "UNREQUESTED_RELEASE_COUNT"):
            m.summarize(payload([sample(), sample(), sample()]), NOW)

    def test_duplicate_release_id(self):
        with self.assertRaisesRegex(m.Refusal, "DUPLICATE_RELEASE_ID"):
            m.summarize(payload([sample(), sample()]), NOW)

    def test_oversize(self):
        with self.assertRaisesRegex(m.Refusal, "RESPONSE_SIZE_BOUND"):
            m.summarize(b"x" * (m.MAX_BYTES + 1), NOW)

    def test_malformed_and_nonfinite(self):
        for raw in [b"not json", b'{"releases": NaN}']:
            with self.assertRaises(m.Refusal):
                m.summarize(raw, NOW)

    def test_bad_observation_time(self):
        with self.assertRaisesRegex(m.Refusal, "OBSERVATION_TIME_INVALID"):
            m.summarize(payload(), "2026-11-21")

    def test_bad_chars_not_exported_as_identity(self):
        r = m.summarize(payload([{**sample(), "buyer": {"name": "A\nB"}}]), NOW)
        self.assertIsNone(r["records"][0]["buyer"])

    def test_canonical_receipt_is_deterministic(self):
        raw = payload()
        self.assertEqual(m.canonical(m.summarize(raw, NOW)),
                         m.canonical(m.summarize(raw, NOW)))


if __name__ == "__main__":
    unittest.main()
