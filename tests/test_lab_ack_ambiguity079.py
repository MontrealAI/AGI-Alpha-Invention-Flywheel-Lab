"""Six preregistered adversarial checks for lab ACK ambiguity 079."""
import json
import unittest
from experiments.lab_ack_ambiguity079.proof import (
    ACTIONS, WORLDS, certificate, observed_recovery, unobserved
)


class LabAckAmbiguity079(unittest.TestCase):
    def test_same_ack_observation_has_no_both_safe_and_complete_action(self):
        result = certificate()
        self.assertEqual(result["world_count"], 2)
        self.assertEqual(result["identical_public_observation"], "ACK_LOST")
        self.assertEqual(result["blind_guaranteed_completion_policies"], [])
        self.assertEqual(len(ACTIONS), 3)
        self.assertTrue(all(unobserved("REFUSE", v)["safe"] for v in WORLDS.values()))
        self.assertTrue(all(not unobserved("REFUSE", v)["completed_correctly"] for v in WORLDS.values()))

    def test_retry_duplicates_effect_if_reply_lost_after_execution(self):
        self.assertEqual(unobserved("RETRY", 1)["effects"], 2)
        self.assertFalse(unobserved("RETRY", 1)["safe"])
        self.assertTrue(unobserved("RETRY", 0)["completed_correctly"])

    def test_claim_completion_undelivered_if_reply_lost_before_execution(self):
        self.assertFalse(unobserved("DECLARE_COMPLETED", 0)["completed_correctly"])
        self.assertTrue(unobserved("DECLARE_COMPLETED", 0)["safe"])
        self.assertTrue(unobserved("DECLARE_COMPLETED", 1)["completed_correctly"])

    def test_trustworthy_readback_allows_strong_ordinary_exactly_once(self):
        for original in WORLDS.values():
            result = observed_recovery(original, "READBACK")
            self.assertTrue(result["safe"] and result["completed_correctly"])
            self.assertEqual(result["effects"], 1)

    def test_retained_dedup_allows_strong_ordinary_exactly_once(self):
        for original in WORLDS.values():
            result = observed_recovery(original, "DURABLE_DEDUP")
            self.assertTrue(result["safe"] and result["completed_correctly"])
            self.assertEqual(result["effects"], 1)

    def test_stale_or_expired_rejections_and_zero_commercial_claim(self):
        stale = observed_recovery(1, "READBACK", stale=True)
        expired = observed_recovery(1, "DURABLE_DEDUP", expired=True)
        self.assertFalse(stale["safe"])
        self.assertFalse(expired["safe"])
        self.assertEqual((stale["effects"], expired["effects"]), (2, 2))
        result = json.loads(json.dumps(certificate()))
        self.assertEqual(result["decision"], "ABSTAIN_WHEN_UNOBSERVABLE_NONIDEMPOTENT")
        self.assertFalse(result["claims"]["physical_actuation"])
        self.assertEqual(result["claims"]["collected_revenue_usd"], 0)
        self.assertIsNone(result["claims"]["native_trailing365_profit_usd"])
        self.assertFalse(result["claims"]["target_3000000000_achieved"])


if __name__ == "__main__":
    unittest.main()
