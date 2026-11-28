import unittest

from research.possibility_observatory.hardware_history.__main__ import checked_receipt, retained


class HardwareHistoryTests(unittest.TestCase):
    def test_independent_arms_replay_same_externally_sourced_witnesses(self):
        receipt = checked_receipt()
        self.assertEqual(receipt["matched_cells"], 48)
        witnesses = receipt["witnesses_by_cutoff"]
        self.assertFalse(witnesses["2026-09-28"]["orderable"])
        self.assertTrue(witnesses["2026-09-29"]["orderable"])
        self.assertFalse(witnesses["2026-10-05"]["receipt-reported"])
        self.assertTrue(witnesses["2026-10-20"]["receipt-reported"])
        self.assertFalse(witnesses["2026-10-20"]["announcement"])
        self.assertTrue(witnesses["2026-10-21"]["announcement"])
        self.assertIsNone(receipt["established_firsts_in_observed_record"]["independent-application"])
        self.assertIsNone(receipt["established_firsts_in_observed_record"]["economic-feasibility"])

    def test_more_recent_announcement_is_not_evidence_of_delivery_or_performance(self):
        altered = [{"id": "new-announcement", "published": "2026-10-20",
                    "roles": ["announcement", "tracking-reported"]}]
        row = retained(altered)["2026-10-21"]
        self.assertEqual(row["announcement"], ["new-announcement"])
        self.assertEqual(row["tracking-reported"], ["new-announcement"])
        self.assertEqual(row["receipt-reported"], [])
        self.assertEqual(row["independent-application"], [])


if __name__ == "__main__":
    unittest.main()
