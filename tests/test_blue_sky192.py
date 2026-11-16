"""Blue Sky 192: prospective falsifier for within-world target semantics.

The protocol is frozen separately at cfcdbdfabed7a1b1cc514b629b9259f3f11af8a2.
Original tests/test_blue_sky191.py is unchanged.
"""
import unittest
from fractions import Fraction
from research.blue_sky191 import transfer_identifiability as t


class WithinWorldTarget192(unittest.TestCase):
    WORLD0 = (2, 4, 0, 1, 2, 0)
    WORLD1 = (2, 4, 1, 1, 2, 0)
    LOW = (1, 0)
    HIGH = (1, 1)

    def test_01_target_uses_within_world_operation(self):
        self.assertTrue(callable(getattr(t, "within_world_improvement", None)),
                        "BLUE_SKY192_WITHIN_WORLD_FUNCTION_MISSING")
        self.assertEqual(t.within_world_improvement(self.WORLD0, self.LOW, self.HIGH), Fraction(0))
        self.assertEqual(t.within_world_improvement(self.WORLD1, self.LOW, self.HIGH), Fraction(1, 12))

    def test_02_unchanged_geometry_is_not_a_5_percent_operating_gain(self):
        self.assertEqual(t.within_world_improvement(self.WORLD0, self.HIGH, self.HIGH), 0)
        self.assertEqual(t.within_world_improvement(self.WORLD1, self.HIGH, self.HIGH), 0)

    def test_03_its_same_world_denominator_is_low_state_not_another_world(self):
        result = t.toy_contrast()
        self.assertIn("within_world_target", result, "BLUE_SKY192_EXPLICIT_WORLD_TARGET_REQUIRED")
        target = result["within_world_target"]
        self.assertEqual(target["states"], {"low": [1, 0], "high": [1, 1]})
        self.assertEqual(target["world0"], {"low_ratio": "2", "high_ratio": "2",
                                            "improvement": "0", "target_met": False})
        self.assertEqual(target["world1"], {"low_ratio": "2", "high_ratio": "13/6",
                                            "improvement": "1/12", "target_met": True})
        self.assertTrue(target["contact_states_are_hypothetical_not_measured"])

    def test_04_cross_world_quotient_is_not_acceptance(self):
        result = t.toy_contrast()
        self.assertTrue(result["within_world_target"]["between_world_comparison_not_acceptance"])
        self.assertEqual(result["relative_improvement"], "1/12")
        self.assertFalse(result["world0_passes_target"])
        self.assertTrue(result["world1_passes_target"])

    def test_05_nonpositive_dynamic_force_must_fail_closed(self):
        bad = (1, 2, 0, 0, 0, 0)
        if not callable(getattr(t, "within_world_improvement", None)):
            self.fail("BLUE_SKY192_DYNAMIC_DENOMINATOR_CHECK_MISSING")
        with self.assertRaises(t.Refused):
            t.within_world_improvement(bad, self.LOW, self.HIGH)

    def test_06_structural_negative_and_artifact_scope_unchanged(self):
        pinned=t.analyze(t.read_pinned(t.ROOT/t.SOURCE,t.SOURCE_SHA),
                         t.read_pinned(t.ROOT/t.REG,t.REG_SHA))
        self.assertEqual(pinned["exact_rational_design_ranks"]["published_pure_only"],4)
        self.assertEqual(pinned["exact_rational_design_ranks"]["pure_plus_both_mixed_phases"],6)
        self.assertFalse(pinned["physical_instrument_qualified"])
        self.assertFalse(pinned["real_buyers_or_revenue"])
        self.assertIsNone(pinned["trailing_365_complete_cost_profit_usd"])


if __name__ == "__main__":
    unittest.main()
