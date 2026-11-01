"""Check the adversary against independently hand-computed propagation."""
import copy
import math
import unittest

from test_production060_acceptance import fixture
from production060.stress import (delay_fixed_assignments, fixed_timing_violations,
                                  run_scenario, shocked_inputs)


class TravelStressTests(unittest.TestCase):
    def test_zero_shock_preserves_physics_and_objective(self):
        day, resources, schedule, contract = fixture()
        stressed, fleet = shocked_inputs(day, resources, 0)
        fixed = fixed_timing_violations(stressed, fleet, schedule)
        replay = delay_fixed_assignments(stressed, fleet, schedule)
        self.assertTrue(fixed["physical_feasible"])
        self.assertTrue(replay["accepted"], replay)
        self.assertEqual(replay["schedule"]["objective"]["value"], 250)

    def test_twentyfive_percent_fixed_plan_fails_actual_travel(self):
        day, resources, schedule, contract = fixture()
        stressed, fleet = shocked_inputs(day, resources, .25)
        fixed = fixed_timing_violations(stressed, fleet, schedule)
        self.assertFalse(fixed["physical_feasible"])
        first = next(v for v in fixed["violations"] if v["load_id"] == "1:0" and v["constraint"] == "outbound_arrival")
        self.assertEqual(first["shortfall_min"], 5)
        directed = next(v for v in fixed["violations"] if v["load_id"] == "2:0" and v["constraint"] == "reposition_arrival")
        self.assertEqual(directed["shortfall_min"], 7.5)
        self.assertFalse(fixed["infeasible_plan_has_realized_objective"])

    def test_hand_computed_delay_propagates_return_rest_and_next_loading(self):
        day, resources, schedule, _ = fixture()
        stressed, fleet = shocked_inputs(day, resources, .25)
        replay = delay_fixed_assignments(stressed, fleet, schedule)
        self.assertTrue(replay["accepted"], replay)
        rows = replay["schedule"]["loads"]
        self.assertEqual([r["bay_start"] for r in rows], [45, 200, 392.5])
        self.assertEqual([r["unload_start"] for r in rows], [105, 260, 440])
        self.assertEqual([r["return_time"] for r in rows], [155, 310, 477.5])
        self.assertEqual(replay["schedule"]["objective"]["total_lateness_min"], 35)
        self.assertEqual(replay["schedule"]["objective"]["value"], 632.5)
        self.assertTrue(fixed_timing_violations(stressed, fleet, replay["schedule"])["physical_feasible"])

    def test_shock_cannot_reapply_conversion_change_target_or_input(self):
        day, resources, schedule, contract = fixture()
        snapshots = copy.deepcopy((day, resources, schedule, contract))
        stressed, fleet = shocked_inputs(day, resources, .50)
        self.assertEqual(stressed["travel_minutes"][0][0], 30)
        self.assertEqual(stressed["travel_minutes_multiplier_applied"], 1.4)
        replay = delay_fixed_assignments(stressed, fleet, schedule)
        for before, after in zip(schedule["loads"], replay["schedule"]["loads"]):
            for key in ("volume_m3", "load_id", "target_unload", "truck_id", "plant_id"):
                self.assertEqual(before[key], after[key])
        self.assertEqual((day, resources, schedule, contract), snapshots)

    def test_actual_existing_dispatcher_replan_is_independently_accepted(self):
        day, resources, schedule, contract = fixture()
        report = run_scenario(day, resources, schedule, contract, .25)
        self.assertFalse(report["fixed_plan"]["physical_feasible"])
        self.assertTrue(report["replan"]["receipt"]["accepted"], report["replan"])
        self.assertTrue(report["replan"]["physical_replay"]["physical_feasible"])
        self.assertEqual(report["replan"]["observed_min"], 0)
        self.assertIn("offline all-orders-known", report["replan"]["scope"])
        self.assertIn("no_midtrip", report["scope"])

    def test_rolling_recourse_preserves_release_information_scope(self):
        from production060.acceptance import make_contract
        from production060.dispatch import DispatchConfig, rolling_schedule
        day, resources, original, _ = fixture()
        config = DispatchConfig(**original["config"])
        nominal = rolling_schedule(resources, day, mode="cold", config=config)
        contract = make_contract(day, resources, mode="cold", planning_scope="rolling", config=original["config"])
        report = run_scenario(day, resources, nominal, contract, .10)
        self.assertTrue(report["replan"]["receipt"]["accepted"], report["replan"])
        self.assertIn("rolling releases remain hidden", report["replan"]["scope"])

    def test_missing_travel_and_invalid_shocks_refuse(self):
        day, resources, _, _ = fixture()
        for increase in (-.1, math.nan, math.inf, True):
            with self.assertRaises(ValueError):
                shocked_inputs(day, resources, increase)
        day["travel_minutes"][0][0] = None
        with self.assertRaises(ValueError):
            shocked_inputs(day, resources, .25)


if __name__ == "__main__":
    unittest.main()
