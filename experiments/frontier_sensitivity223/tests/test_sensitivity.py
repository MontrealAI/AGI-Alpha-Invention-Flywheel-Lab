"""Preregistered synthetic boundary checks, no empirical uncertainty calibration."""
import sys
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import sensitivity as s


class Sensitivity223(unittest.TestCase):
    def test_zero_uncertainty_matches_recorded_comparison(self):
        self.assertTrue(s.fixed_assignment_guaranteed([D("10"),D("1")],0,D("0")))
        self.assertFalse(s.fixed_assignment_guaranteed([D("1"),D("10")],0,D("0")))

    def test_cell_cannot_be_simultaneously_high_and_low(self):
        # Candidate low=9 and other high=2. Its own upper=11 is not a second cell.
        self.assertTrue(s.fixed_assignment_guaranteed([D("10"),D("1")],0,D("1")))
        # But when the other cell is high enough, assigned guarantee genuinely fails.
        self.assertFalse(s.fixed_assignment_guaranteed([D("10"),D("10")],0,D("1")))

    def test_equal_boundary(self):
        self.assertTrue(s.fixed_assignment_guaranteed([D("9.5"),D("10")],0,D("0")))
        self.assertFalse(s.fixed_assignment_guaranteed([D("9.5"),D("10.6")],0,D("0")))

    def test_nonnumeric_or_negative_bound_fails_closed(self):
        with self.assertRaises(ValueError):
            s.robust_amidation_incidence([[D("10"),D("0")]],D("-0.01"))
        with self.assertRaises(ValueError):
            s.fixed_assignment_guaranteed([D("10")],0,D("0"))
        with self.assertRaises(ValueError):
            s.fixed_assignment_guaranteed([D("NaN"),D("1")],0,D("0"))

    def test_pairwise_exact_two_error_radius(self):
        subs=["s1"]
        ligands=["L1","L2"]
        cells={("s1","L1"):D("0"),("s1","L2"):D("20.5")}
        self.assertEqual(s.robust_ethanol_incidence(subs,ligands,cells,D("0.25"))[1],[[0]])
        self.assertEqual(s.robust_ethanol_incidence(subs,ligands,cells,D("0.26"))[1],[[]])

    def test_empty_requirement_not_silently_removed(self):
        result=s.qualified_min_cover(["o0","o1"],[[0],[]])
        self.assertEqual(result["status"],"INFEASIBLE_FULL_UNIVERSE")
        self.assertEqual(result["empty_rows"],[1])

    def test_exact_independent_checker_for_small_instance(self):
        result=s.qualified_min_cover(["a","b","c"],[[0,1],[1,2]])
        self.assertEqual(result["status"],"OPTIMAL")
        self.assertEqual(result["minimum_options"],1)
        self.assertEqual(result["selected_option_ids"],["b"])
        self.assertTrue(result["independent_checker"]["accepted"])

    def test_tampered_source_refused(self):
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/"amidation.csv"
            fake.write_bytes(b"x\n")
            with self.assertRaisesRegex(ValueError,"PINNED_INPUT_CHANGED"):
                s.pinned_bytes(fake,s.SOURCE_HASHES["amidation.csv"])

    def test_registered_protocol_and_retained_asset_pins(self):
        p=s.validated_parent()
        self.assertEqual(p["pin"]["owner_head"],"b211c461874051f29827345fc96f82d0d196fc12")
        self.assertEqual(tuple(p["cases"]["error_radii_percentage_points"]),s.RADII)


if __name__=="__main__":
    unittest.main()
