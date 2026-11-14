"""Frozen blue-sky120 physical identity checks; not a commercial acceptance test."""
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from research.regolith120 import (
    ILLUSTRATIVE_VOLTS, REPORTED_ANODIC_EFFICIENCY, REPORTED_G_H,
    STUDIED_MAX_A_CM2, STUDIED_MIN_A_CM2, TARGET_G_H, envelope, record,
)


class Regolith120Tests(unittest.TestCase):
    def test_reported_rate_required_current_in_frozen_interval(self):
        o = envelope(REPORTED_G_H, REPORTED_ANODIC_EFFICIENCY,
                     STUDIED_MIN_A_CM2, STUDIED_MAX_A_CM2, ILLUSTRATIVE_VOLTS)
        current = Decimal(o["conditional_required_current_A"])
        self.assertTrue(Decimal("6.2") <= current <= Decimal("6.5"))
        self.assertFalse(o["conditional_area_m2_if_studied_current_densities_transfer"]
                         ["is_measurement_of_electrode_area"])
        self.assertFalse(o["is_physical_throughput_demonstration"])

    def test_one_kg_target_is_a_constraint_not_an_achieved_rate(self):
        o = envelope(TARGET_G_H, REPORTED_ANODIC_EFFICIENCY,
                     STUDIED_MIN_A_CM2, STUDIED_MAX_A_CM2, ILLUSTRATIVE_VOLTS)
        amps = Decimal(o["conditional_required_current_A"])
        self.assertTrue(Decimal("3800") <= amps <= Decimal("4100"))
        area = o["conditional_area_m2_if_studied_current_densities_transfer"]
        self.assertTrue(Decimal(".38") <= Decimal(area["lower"]) <= Decimal(".70"))
        self.assertTrue(Decimal(".38") <= Decimal(area["upper"]) <= Decimal(".70"))
        self.assertLess(Decimal(area["lower"]), Decimal(area["upper"]))
        kwh = Decimal(o["illustrative_electricity"]
                      ["conditional_kWh_per_kg_at_same_efficiency_and_voltage"])
        self.assertTrue(Decimal("11") <= kwh <= Decimal("12"))
        self.assertFalse(o["illustrative_electricity"]["is_observed_process_energy_or_cost"])

    def test_source_record_does_not_make_buyers_or_costs(self):
        o = record()
        self.assertEqual(o["decision"], "HOLD_NO_BID_NO_DEPLOY")
        self.assertIsNone(o["qualified_native_profit_trailing_365_USD"])
        self.assertIsNone(o["measured_lunar_demand_units"])
        self.assertEqual(o["collected_revenue_USD"], "0")
        self.assertFalse(o["same_account_native_financing_executed"])
        self.assertFalse(o["actual_commerce"])
        self.assertTrue(all(a["complete_cost_USD"] is None
                            for a in o["alternatives"][:3]))
        self.assertEqual(len(o["alternatives"]), 4)

    def test_reject_invalid_efficiency_rates_densities_and_voltages(self):
        base = ("1.61", "0.8574", "0.6", "1.0", "3.0")
        for index, bad in [
            (0, "0"), (0, "-1"), (0, "NaN"), (1, "0"), (1, "1.01"),
            (1, "-0.5"), (2, "0"), (3, "0"), (3, "NaN"),
            (4, "0"), (4, "-3"), (4, "Infinity"),
        ]:
            with self.subTest(index=index, bad=bad), self.assertRaises(ValueError):
                args = list(base)
                args[index] = bad
                envelope(*args)
        with self.assertRaisesRegex(ValueError, "DENSITY_INTERVAL_REVERSED"):
            envelope("1", ".85", "1.0", ".6", "3")

    def test_cli_receipt_is_immutable_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            cmd = [sys.executable, "-m", "research.regolith120",
                   "--output", str(path)]
            ok = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(json.loads(path.read_text())["decision"],
                             "HOLD_NO_BID_NO_DEPLOY")
            initial = path.read_bytes()
            refused = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(path.read_bytes(), initial)


if __name__ == "__main__":
    unittest.main()
