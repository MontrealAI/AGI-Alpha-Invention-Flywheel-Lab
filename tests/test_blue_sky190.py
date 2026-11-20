"""Exact synthetic and exposed-source tests; original failed results not rewritten."""
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from research.blue_sky190.calibration_contract import (
    Refused,ROOT,SOURCE_REL,REG_REL,SOURCE_SHA256,REG_SHA256,
    unique,pinned_json,rows_intervals,feasible,calculate,analyze,run,
)

class Witness190Tests(unittest.TestCase):
    def test_01_consistent_exact_origin_law(self):
        r=calculate([[1,0,2,0],[2,0,4,0],[3,0,6,0]])
        self.assertTrue(r["origin_linear_constant_supported_by_authored_boxes"])
        self.assertEqual(r["coefficient_intersection"],["2","2"])
        self.assertEqual(r["minimal_extra_relative_force_error_q"],"0")
        self.assertIsNone(r["conflicting_row_pair"])

    def test_02_conflicting_exact_pair_and_q(self):
        raw=[[1,0,2,0],[2,0,5,0]]
        r=calculate(raw)
        self.assertFalse(r["origin_linear_constant_supported_by_authored_boxes"])
        self.assertEqual(r["active_q_pair_zero_based"],[1,0])
        self.assertEqual((r["conflicting_row_pair"]["max_lower_row_zero_based"],
                          r["conflicting_row_pair"]["min_upper_row_zero_based"]),(1,0))
        self.assertAlmostEqual(float(r["minimal_extra_relative_force_error_q"]),1/9,13)
        self.assertFalse(feasible(rows_intervals(raw),Decimal(".10")))
        self.assertTrue(feasible(rows_intervals(raw),Decimal(".12")))

    def test_03_reordering_preserves_exact_minimum(self):
        rows=[[1,Decimal(".01"),Decimal("2.1"),Decimal(".02")],
              [2,Decimal(".04"),Decimal("5.3"),Decimal(".03")],
              [3,Decimal(".08"),Decimal("7.0"),Decimal(".08")]]
        x,y=calculate(rows),calculate(list(reversed(rows)))
        self.assertEqual(x["minimal_extra_relative_force_error_q"],
                         y["minimal_extra_relative_force_error_q"])
        q=Decimal(x["minimal_extra_relative_force_error_q"])
        self.assertTrue(feasible(rows_intervals(rows),q+Decimal("1e-40")))
        if q>0:
            self.assertFalse(feasible(rows_intervals(rows),q-Decimal("1e-12")))

    def test_04_original_errors_can_cover_common_law(self):
        r=calculate([[1,0,2,Decimal(".5")],[2,0,5,Decimal("1")]])
        self.assertTrue(r["origin_linear_constant_supported_by_authored_boxes"])
        self.assertEqual(r["minimal_extra_relative_force_error_q"],"0")

    def test_05_invalid_area_force_and_nonfinite_refused(self):
        for rows in ([[1,1,2,0],[2,0,4,0]],
                     [[1,0,-2,0],[2,0,4,0]],
                     [[1,0,Decimal("NaN"),0],[2,0,4,0]],
                     [[1,0,2,0]]):
            with self.subTest(rows=str(rows)),self.assertRaises(Refused):
                calculate(rows)

    def test_06_negative_q_refused(self):
        with self.assertRaises(Refused):
            feasible(rows_intervals([[1,0,2,0],[2,0,5,0]]),Decimal("-0.01"))

    def test_07_duplicate_json_field_refused(self):
        with self.assertRaises(Refused):
            json.loads('{"a":1,"a":2}',object_pairs_hook=unique)

    def test_08_tampered_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"fixture.json"
            f.write_text('{"schema":"wrong"}')
            with self.assertRaisesRegex(Refused,"PINNED_SOURCE_BYTES_CHANGED"):
                pinned_json(f,SOURCE_SHA256)

    def test_09_fixed_source_all_six_and_original_three_conflicts(self):
        r=analyze(pinned_json(ROOT/SOURCE_REL,SOURCE_SHA256),
                  pinned_json(ROOT/REG_REL,REG_SHA256))
        self.assertEqual(len(r["blocks"]),6)
        self.assertEqual(r["unresolved_selected_blocks"],
                         ["Batch1_R496/s","Batch1_R496/d","Batch2_R1543/d"])
        self.assertEqual(r["decision"],"HOLD_INCONSISTENT_CALIBRATION_BOXES")
        self.assertFalse(r["new_physical_instrument_qualified"])
        self.assertIsNone(r["trailing_365_profit_usd"])

    def test_10_specific_source_row_witnesses(self):
        r=analyze(pinned_json(ROOT/SOURCE_REL,SOURCE_SHA256),
                  pinned_json(ROOT/REG_REL,REG_SHA256))
        m={(b["family"],b["phase"]):b["conflicting_row_pair"] for b in r["blocks"]}
        for key,expected in {("Batch1_R496","s"):(1,2),
                             ("Batch1_R496","d"):(4,2),
                             ("Batch2_R1543","d"):(7,1)}.items():
            actual=m[key]
            self.assertEqual((actual["max_lower_row_zero_based"],
                              actual["min_upper_row_zero_based"]),expected)

    def test_11_create_only_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"RESULT.json"
            result=run(p)
            self.assertEqual(json.loads(p.read_text())["decision"],result["decision"])
            with self.assertRaises(Refused):
                run(p)

if __name__=="__main__":
    unittest.main()
