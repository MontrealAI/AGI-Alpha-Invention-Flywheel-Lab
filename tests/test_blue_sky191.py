"""Frozen Blue Sky 191 source-bound and adversarial structural tests."""
from decimal import Decimal
from fractions import Fraction
import copy
import json
from pathlib import Path
import tempfile
import unittest

from research.blue_sky191.transfer_identifiability import (
    Refused, ROOT, SOURCE, REG, SOURCE_SHA, REG_SHA,
    unique_keys, read_pinned, rational, source_rows, design_row, rank,
    predicted_force, toy_contrast, analyze, run,
)


class Transfer191Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = read_pinned(ROOT / SOURCE, SOURCE_SHA)
        cls.registration = read_pinned(ROOT / REG, REG_SHA)

    def test_01_exact_pinned_two_family_pure_rank(self):
        rows, counts = source_rows(self.fixture, self.registration)
        self.assertEqual(counts, {
            "Batch1_R496/s": 10, "Batch1_R496/d": 10,
            "Batch2_R1543/s": 8, "Batch2_R1543/d": 8,
        })
        self.assertEqual(len(rows), 36)
        self.assertEqual(rank(rows), 4)
        self.assertTrue(all(row[2] == row[5] == 0 for row in rows))

    def test_02_one_mixed_static_only(self):
        rows, _ = source_rows(self.fixture, self.registration)
        self.assertEqual(rank(rows + [design_row(1, 1, "s")]), 5)

    def test_03_one_mixed_dynamic_only(self):
        rows, _ = source_rows(self.fixture, self.registration)
        self.assertEqual(rank(rows + [design_row(1, 1, "d")]), 5)

    def test_04_both_mixed_phases_identify_six_columns_in_ideal_grammar(self):
        rows, _ = source_rows(self.fixture, self.registration)
        self.assertEqual(rank(rows + [design_row(1, 1, "s"), design_row(1, 1, "d")]), 6)

    def test_05_more_pure_rows_cannot_identify_interaction(self):
        rows, _ = source_rows(self.fixture, self.registration)
        many_pure = [design_row(i + 1, 0, "s") for i in range(100)]
        many_pure += [design_row(0, i + 1, "d") for i in range(100)]
        self.assertEqual(rank(rows + many_pure), 4)

    def test_06_pure_geometry_cannot_create_interaction_feature(self):
        for phase in ("s", "d"):
            for a, b in ((4, 0), (0, 4)):
                row = design_row(a, b, phase)
                self.assertEqual(row[2], 0)
                self.assertEqual(row[5], 0)
        self.assertEqual(design_row(1, 1, "s")[2], Fraction(1, 2))
        self.assertEqual(design_row(1, 1, "d")[5], Fraction(1, 2))

    def test_07_two_world_exact_counterexample_target_split(self):
        result = toy_contrast()
        self.assertTrue(result["pure_observations_indistinguishable"])
        self.assertEqual(result["alternative_mixed_ratio"], "13/6")
        self.assertEqual(Fraction(result["relative_improvement"]), Fraction(1, 12))
        self.assertLess(Fraction(result["source_target"]), Fraction(result["relative_improvement"]))
        self.assertFalse(result["world0_passes_target"])
        self.assertTrue(result["world1_passes_target"])

    def test_08_static_and_dynamic_observation_are_distinct(self):
        w0 = (2, 4, 0, 1, 2, 0)
        w1 = (2, 4, 1, 1, 2, 0)
        self.assertEqual(predicted_force(w0, 1, 1, "d"), predicted_force(w1, 1, 1, "d"))
        self.assertNotEqual(predicted_force(w0, 1, 1, "s"), predicted_force(w1, 1, 1, "s"))

    def test_09_strict_nonnegative_finite_values(self):
        for x in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), True, "1.2", 1.2):
            with self.subTest(x=str(x)), self.assertRaises(Refused):
                rational(x)
        for a, b, phase in ((0, 0, "s"), (-1, 3, "s"), (1, 1, "other")):
            with self.assertRaises(Refused):
                design_row(a, b, phase)
        with self.assertRaises(Refused):
            predicted_force((1, -1, 0, 1, 1, 0), 1, 1, "s")

    def test_10_reject_duplicate_json_and_source_hash_tamper(self):
        with self.assertRaisesRegex(Refused, "DUPLICATE_JSON_KEY"):
            json.loads('{"a": 1, "a": 2}', object_pairs_hook=unique_keys)
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "fake.json"
            p.write_text('{"schema":"fake"}')
            with self.assertRaisesRegex(Refused, "PINNED_SOURCE_CHANGED"):
                read_pinned(p, SOURCE_SHA)

    def test_11_reject_corrupted_source_alignment(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["calibration"][0]["phases"]["s"]["force_rows"][0][0] = Decimal("999")
        with self.assertRaisesRegex(Refused, "PAIRED_AREA_FORCE_ROWS_CHANGED"):
            source_rows(fixture, self.registration)

    def test_12_reject_changed_target_or_phase(self):
        registration = copy.deepcopy(self.registration)
        registration["necessary_construction_target"]["increase_in_static_dynamic_ratio_at_least"] = Decimal(".10")
        with self.assertRaisesRegex(Refused, "TARGET_CHANGED"):
            source_rows(self.fixture, registration)
        fixture = copy.deepcopy(self.fixture)
        fixture["calibration"][0]["phases"].pop("d")
        with self.assertRaisesRegex(Refused, "PUBLISHED_PHASES_CHANGED"):
            source_rows(fixture, self.registration)

    def test_13_exact_rational_rank_not_floating_threshold(self):
        self.assertEqual(rank([[1, 0], [1, Fraction(1, 10**40)]], ncols=2), 2)
        self.assertEqual(rank([[1, 0], [2, 0]], ncols=2), 1)
        with self.assertRaises(Refused):
            rank([[1, 2, 3]], ncols=2)

    def test_14_result_no_invented_physical_or_financial_claim(self):
        result = analyze(self.fixture, self.registration)
        self.assertEqual(result["nullity_of_pure_only_design"], 2)
        self.assertEqual(result["decision"], "HOLD_MIXED_TRANSFER_REQUIRES_MIXED_OBSERVATION")
        self.assertFalse(result["physical_instrument_qualified"])
        self.assertFalse(result["real_buyers_or_revenue"])
        self.assertIsNone(result["trailing_365_complete_cost_profit_usd"])
        self.assertEqual(len(result["comparison"]), 4)

    def test_15_create_only_output_and_immutable_source(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "result.json"
            result = run(p)
            self.assertEqual(json.loads(p.read_text())["decision"], result["decision"])
            with self.assertRaisesRegex(Refused, "ABSOLUTE_CREATE_ONLY_OUTPUT_REQUIRED"):
                run(p)


if __name__ == "__main__":
    unittest.main()
