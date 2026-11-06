"""Independent adversarial tests of the offline continuity proposal."""
import copy
import unittest

from campaign.continuity_omega_20261106.continuity_proof import benchmark, check_restore, digest, make_proof, ordinary_independent_reconciliation, replay, verify_proof


class ContinuityProofTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {"seq": 1, "kind": "commit", "order": "a", "cents": 200},
            {"seq": 2, "kind": "commit", "order": "b", "cents": 500},
            {"seq": 3, "kind": "deliver", "order": "a"},
        ]
        self.restore = replay(self.events)
        self.anchor = digest(self.events)

    def test_complete_restore(self):
        p = make_proof(self.events, self.restore, self.anchor, 1, 5)
        self.assertTrue(p["accepted"])
        self.assertTrue(verify_proof(p, self.events, self.restore, self.anchor, 1, 5))

    def test_missing_obligation_detected(self):
        p = make_proof(self.events, {"a": self.restore["a"]}, self.anchor, 1, 5)
        self.assertEqual(p["failures"], ["RESTORED_OBLIGATIONS_DIFFER"])

    def test_replayed_order_and_terminal(self):
        for malformed in [
            self.events + [{"seq": 3, "kind": "deliver", "order": "a"}],
            self.events + [{"seq": 4, "kind": "deliver", "order": "a"}],
            self.events + [{"seq": 4, "kind": "commit", "order": "a", "cents": 200}],
        ]:
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    replay(malformed)

    def test_anchor_mismatch_and_tampering(self):
        modified = copy.deepcopy(self.events)
        modified[0]["cents"] = 201
        p = make_proof(modified, replay(modified), self.anchor, 1, 5)
        self.assertIn("EVENT_TAPE_ANCHOR_MISMATCH", p["failures"])
        self.assertFalse(verify_proof(p, modified, replay(modified), digest(modified), 1, 5))

    def test_forged_success_rejected(self):
        p = make_proof(self.events, {"a": self.restore["a"]}, self.anchor, 1, 5)
        p["accepted"] = True
        p["failures"] = []
        self.assertFalse(verify_proof(p, self.events, {"a": self.restore["a"]}, self.anchor, 1, 5))

    def test_invalid_amount_bool_and_duration(self):
        for cents in (True, 0, -1, 3.14):
            bad = [{"seq": 1, "kind": "commit", "order": "a", "cents": cents}]
            with self.subTest(amount=cents), self.assertRaises(ValueError):
                replay(bad)
        self.assertIn("INVALID_DURATION", check_restore(self.events, self.restore, self.anchor, True, 5))

    def test_future_refund_does_not_clear_missing_order(self):
        bad = self.events + [{"seq": 4, "kind": "refund", "order": "b"}]
        self.assertNotEqual(replay(bad), self.restore)
        self.assertIn("RESTORED_OBLIGATIONS_DIFFER", check_restore(bad, self.restore, digest(bad), 1, 5))

    def test_competent_comparator_is_independent_replay(self):
        self.assertTrue(ordinary_independent_reconciliation(self.events, self.restore, self.anchor, 1, 5))
        self.assertFalse(ordinary_independent_reconciliation(self.events, {"a": self.restore["a"]}, self.anchor, 1, 5))
        self.assertFalse(ordinary_independent_reconciliation(self.events, self.restore, "0" * 64, 1, 5))
        self.assertFalse(ordinary_independent_reconciliation(self.events, self.restore, self.anchor, 6, 5))

    def test_predeclared_fixture_tie_and_no_deploy(self):
        result = benchmark()
        self.assertEqual(result["case_count"], 4)
        self.assertTrue(result["all_registered_verdicts_match"])
        self.assertTrue(result["competent_conventional_tie"])
        self.assertFalse(result["portable_proof_advantage_over_strong_control_established"])
        self.assertIn("NO_DEPLOY", result["recommended_action"])


if __name__ == "__main__":
    unittest.main()
