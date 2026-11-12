"""Adversarial regression on frozen, synthetic-only market-access witness."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from experiments.market_identifiability076.proof import (
    aggregate, frozen_worlds, private_duplicate_claim_ids, witness
)


class MarketIdentifiability076(unittest.TestCase):
    def test_frozen_worlds_have_same_entire_public_projection(self):
        a, b = frozen_worlds()
        self.assertEqual(aggregate(a), aggregate(b))
        self.assertEqual(aggregate(a)[0]["Tot_Benes"], 1)
        self.assertEqual(aggregate(a)[0]["Tot_Srvcs"], 2)
        self.assertEqual(aggregate(a)[0]["Tot_Bene_Day_Srvcs"], 2)
        self.assertEqual(aggregate(a)[0]["Avg_Mdcr_Pymt_Amt"], "64.00")

    def test_strong_ordinary_authorized_exact_id_audit_distinguishes(self):
        a, b = frozen_worlds()
        self.assertFalse(private_duplicate_claim_ids(a))
        self.assertTrue(private_duplicate_claim_ids(b))

    def test_any_public_only_rule_must_share_same_prediction(self):
        a, b = frozen_worlds()
        public_rule = lambda rows: json.dumps(aggregate(rows), sort_keys=True)
        self.assertEqual(public_rule(a), public_rule(b))
        self.assertNotEqual(private_duplicate_claim_ids(a), private_duplicate_claim_ids(b))

    def test_tampered_reported_payment_changes_projection(self):
        a, b = frozen_worlds()
        b = copy.deepcopy(b)
        b[1]["medicare_paid"] = "63.00"
        self.assertNotEqual(aggregate(a), aggregate(b))

    def test_malformed_missing_unknown_and_invalid_amount_rejected(self):
        original, _ = frozen_worlds()
        for bad in (
            {k: v for k, v in original[0].items() if k != "claim_id"},
            dict(original[0], extra="forbidden"),
            dict(original[0], medicare_paid="NaN"),
            dict(original[0], medicare_paid="-0.01"),
            dict(original[0], medicare_paid="1.123"),
            dict(original[0], services=0),
            dict(original[0], services=True),
        ):
            with self.subTest(bad=str(bad)[:100]), self.assertRaises(ValueError):
                aggregate([bad])

    def test_explicit_nonentry_and_no_monetary_achievement(self):
        out = witness()
        self.assertEqual(out["decision"], "NO_DEPLOY")
        self.assertFalse(out["public_only_identifiability"])
        self.assertTrue(out["both_worlds_same_public_input"])
        self.assertEqual(out["world_count"], 2)
        self.assertTrue(out["synthetic_only"])
        self.assertEqual(out["collected_revenue_usd"], 0)
        self.assertIsNone(out["native_trailing_365_profit_usd"])
        self.assertFalse(out["target_3000000000_achieved"])
        self.assertEqual(hashlib.sha256(json.dumps(out["public_projection"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(), out["public_projection_sha256"])
        prereg = json.loads((Path(__file__).resolve().parents[1] / "experiments/market_identifiability076/PREREGISTRATION.json").read_text())
        self.assertEqual(prereg["acceptance"]["total_worlds"], out["world_count"])
        self.assertEqual(prereg["claims"]["real_customers"], 0)


if __name__ == "__main__":
    unittest.main()
