"""Adversarial tests for exposed-source selection bound; no physical rerun."""
import unittest
from research.eit_select103.analysis import (
    ROWS, ROWS_SHA256, unpack, read_rows, evaluate)
from hashlib import sha256


class TestEitSelect103(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows()

    def test_original_projection_hash(self):
        self.assertEqual(sha256(ROWS.encode()).hexdigest(), ROWS_SHA256)

    def test_exact_original_denominator(self):
        self.assertEqual(len(self.rows), 21)
        self.assertEqual(len({r["target"] for r in self.rows}), 21)
        self.assertEqual(sum(len(r["truth"]) for r in self.rows), 168)

    def test_byte_encoding(self):
        self.assertEqual(unpack("81"), (1, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual(unpack("00"), (0,) * 8)

    def test_bad_bytes_rejected(self):
        for value in ("FF", "g0", "0", "000", None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                unpack(value)

    def test_source_tampering_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROJECTION_CHANGED"):
            read_rows(ROWS.replace("04 05", "00 05"))

    def test_missing_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "EXACT_21"):
            read_rows("\n".join(ROWS.splitlines()[:-1]), pinned=False)

    def test_duplicate_target_rejected(self):
        rows = list(self.rows)
        rows[1] = dict(rows[0])
        with self.assertRaisesRegex(ValueError, "EXACT_21"):
            evaluate(rows)

    def test_invalid_binary_values_rejected(self):
        rows = list(self.rows)
        rows[0] = dict(rows[0], truth=(1, 2, 0, 0, 0, 0, 0, 0))
        with self.assertRaisesRegex(ValueError, "EXACT_BINARY"):
            evaluate(rows)
        rows[0] = dict(self.rows[0], truth=(True,) + self.rows[0]["truth"][1:])
        with self.assertRaisesRegex(ValueError, "EXACT_BINARY"):
            evaluate(rows)

    def test_original_strong_controls_unchanged(self):
        result = evaluate(self.rows)
        self.assertEqual(result["correct_by_fixed_arm"],
                         {"full76": 147, "direct40": 146, "impute40": 146})
        self.assertEqual(result["correct_by_majority_vote"], 146)

    def test_exact_clairvoyant_select_only_ceiling(self):
        result = evaluate(self.rows)
        self.assertEqual(result["unanimously_wrong"], 20)
        self.assertEqual(result["unanimously_correct"], 145)
        self.assertEqual(result["disagreement_positions"], 3)
        self.assertEqual(result["select_only_oracle_upper_bound_correct"], 148)
        self.assertEqual(sum(result["unanimous_errors_by_material"]), 20)
        self.assertEqual(sum(result["unanimous_errors_by_quadrant"]), 20)

    def test_tight_bound_on_all_binary_three_voter_inputs(self):
        for mask in range(8):
            options = [(mask >> i) & 1 for i in range(3)]
            for truth in (0, 1):
                self.assertEqual(int(truth in options),
                                 1 - int(all(p != truth for p in options)))

    def test_financial_and_physical_claims_not_invented(self):
        result = evaluate(self.rows)
        self.assertEqual(result["actual_new_acquisitions"], 0)
        self.assertEqual(result["financial_native_actions"], 0)
        self.assertIsNone(result["complete_cost_profit_usd"])
        self.assertFalse(result["usd_3b_trailing365_qualified"])
        self.assertFalse(result["clairvoyant_oracle_executable"])


if __name__ == "__main__":
    unittest.main()
