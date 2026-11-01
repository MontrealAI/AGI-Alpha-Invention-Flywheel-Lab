"""Adversarial tests use hand-worked times, without importing the producer."""
import copy
import math
import unittest
from production060.acceptance import CONVENTIONS, canonical_sha256, make_contract, verify


def fixture():
    resources = {
        "schema_version": "cdp060-normalized-v1",
        "plants": [{"id": 1, "source_mean_loading_rate": 57.5, "loading_decks": 1},
                   {"id": 2, "source_mean_loading_rate": 52.5, "loading_decks": 1},
                   {"id": 3, "source_mean_loading_rate": 0, "loading_decks": 1}],
        "trucks": [{"id": 1, "capacity_m3": 8, "home_plant": 1},
                   {"id": 2, "capacity_m3": 4, "home_plant": 2}],
        "plant_travel_minutes": [[0, 30, 40], [50, 0, 60], [40, 60, 0]],
        "travel_minutes_multiplier_applied": 1.4,
        "source_files": [{"filename": "Plants.mat", "sha256": "a" * 64}],
        "parameters": {"DefaultQuantityPerTrip": 7.5, "DefaultLoadingTime": 10,
                       "DefaultPlantCleaningTime": 10, "DefaultUnloadingTime": 10,
                       "CleaningTimeAtTheDefaultSite": 15, "DriversPreparationTime": 15,
                       "DriverBreakTime": 15, "DriverMealTime": 30,
                       "GoogleTravelTimeMultiplier": 1.4}}
    day = {
        "schema_version": "cdp060-normalized-v1", "id": "hand-worked-day",
        "orders": [{"id": 1, "volume_m3": 8.2, "default_load_m3": 0,
                    "release_min": 0, "requested_min": 100, "interval_min": 150,
                    "mix_id": 7, "client_id": 1},
                   {"id": 2, "volume_m3": 4, "default_load_m3": 0,
                    "release_min": 200, "requested_min": 420, "interval_min": 0,
                    "mix_id": None, "client_id": 2}],
        "travel_minutes": [[20, 45, 60], [40, 10, 60]],
        "travel_row_mapping_verified": True, "missing_travel_order_ids": [],
        "operating_data_complete": True, "travel_minutes_multiplier_applied": 1.4,
        "source": {"sha256": "b" * 64}}
    cfg = {"loading_min": 10, "plant_cleaning_min": 10, "driver_preparation_min": 15,
           "unloading_min": 10, "site_cleaning_min": 15,
           "driver_break_min": 15, "driver_meal_min": 30,
           "default_load_m3": 7.5, "activation_weight": 120,
           "travel_weight": 1, "lateness_weight": 10, "missing_travel": "refuse",
           "window_size": 8, "candidate_trucks": 18, "time_limit_s": 0,
           "random_seed": 60}
    contract = make_contract(day, resources, config=cfg)
    rows = []
    # Bay times45,195,375; unloads100,250,420; returns145,295,455.
    specifications = [(1, 0, 7.5, 1, 45, 20, 0, None, 100),
                      (1, 1, 0.7, 1, 195, 20, 0, "1:0", 250),
                      (2, 0, 4, 2, 375, 10, 30, "1:1", 420)]
    for oid, index, volume, plant, start, out, reposition, previous, target in specifications:
        order, repstart, unload = day["orders"][oid - 1], start - reposition, start + 35 + out
        rows.append({
            "load_id": f"{oid}:{index}", "order_id": oid, "load_index": index,
            "volume_m3": volume, "plant_id": plant, "truck_id": 1,
            "release_min": order["release_min"], "decision_time": order["release_min"],
            "mix_id": order["mix_id"], "client_id": order["client_id"],
            "target_unload": target, "previous_load_id": previous,
            "bay_start": start, "loading_start": start, "loading_end": start + 10,
            "bay_end": start + 20, "dispatch_time": start + 35,
            "site_arrival": unload, "unload_start": unload, "unload_end": unload + 10,
            "site_clear": unload + 25, "return_time": unload + 25 + out,
            "outbound_travel_min": out, "return_travel_min": out,
            "reposition_start": repstart, "reposition_end": start, "reposition_min": reposition,
            "driver_break_start": repstart - 45 if previous else None,
            "driver_break_end": repstart - 30 if previous else None,
            "driver_meal_start": repstart - 30 if previous else None,
            "driver_meal_end": repstart if previous else None,
            "lateness_min": 0, "quality_status": "logistics_only_mix_not_certified"})
    artifact = {
        "schema_version": "production060-dispatch-v1", "instance_id": day["id"],
        "mode": "cold", "planning_scope": "offline", "planning_min": 0,
        "config": cfg, "conventions": dict(CONVENTIONS),
        "source_binding": copy.deepcopy(contract["source_binding"]), "loads": rows,
        "trucks": [{"truck_id": 1, "home_plant": 1, "capacity_m3": 8,
                    "load_ids": ["1:0", "1:1", "2:0"]}],
        "objective": {"value": 250, "activated_trucks": 1, "travel_min": 130,
                      "total_lateness_min": 0, "max_lateness_min": 0, "late_loads": 0,
                      "global_bound": None, "global_gap": None},
        "solver": {"name": "hand-worked", "available": False, "wall_time_s": 0,
                   "windows": [], "global_optimality_claim": False},
        "diagnostics": {"excluded_orders": [], "missing_mix_order_ids": [2],
                        "excluded_zero_rate_plants": [3], "frozen_load_ids": [],
                        "operating_end_min": 455, "driver_review_flags": [],
                        "shift_break_feasibility": "declared_rest_profile_satisfied_not_legal_certification",
                        "quality_feasibility": "unverified"}}
    return day, resources, artifact, contract


class AcceptanceTests(unittest.TestCase):
    def test_hand_worked_schedule_and_exact_final_partial(self):
        receipt = verify(*fixture())
        self.assertTrue(receipt["accepted"], receipt["errors"])
        self.assertEqual(receipt["kpis"]["delivered_m3"], "12.2")
        self.assertEqual(receipt["kpis"]["value"], 250)
        self.assertEqual(receipt["kpis"]["missing_mix_order_ids"], [2])
        self.assertFalse(receipt["kpis"]["physical_quality_certified"])

    def assert_corruption(self, mutate, fragment):
        day, resources, artifact, contract = fixture()
        mutate(day, resources, artifact, contract)
        result = verify(day, resources, artifact, contract)
        self.assertFalse(result["accepted"], result)
        self.assertTrue(any(fragment in message for message in result["errors"]), result["errors"])

    def test_missing_load(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"].pop(), "missing or extra")

    def test_final_partial_cannot_round_away(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][1].update(volume_m3=0.699999999), "load volume")

    def test_wrong_truck_capacity(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][0].update(truck_id=2), "capacity exceeded")

    def test_summary_cannot_redefine_capacity(self):
        self.assert_corruption(lambda d, r, a, c: a["trucks"][0].update(capacity_m3=80), "truck summary")

    def test_hidden_future_release(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][2].update(decision_time=199), "hidden future")

    def test_outbound_travel_cannot_be_scaled_twice(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][0].update(site_arrival=108), "outbound travel mismatch")

    def test_return_teleport(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][0].update(return_time=125), "return travel mismatch")

    def test_reposition_direction(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][2].update(reposition_start=325, reposition_min=50), "directed reposition")

    def test_plant_bay_overlap(self):
        def overlap(d, r, a, c):
            second = a["loads"][1]
            for key in ("bay_start", "loading_start", "loading_end", "bay_end", "dispatch_time",
                        "site_arrival", "unload_start", "unload_end", "site_clear", "return_time",
                        "reposition_start", "reposition_end", "driver_break_start", "driver_break_end",
                        "driver_meal_start", "driver_meal_end"):
                second[key] -= 140
        self.assert_corruption(overlap, "loading bay overlap")

    def test_driver_rest(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][1].update(driver_break_start=140), "truck reuse before return")

    def test_predecessor_chain(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][2].update(previous_load_id="1:0"), "predecessor discontinuity")

    def test_false_objective(self):
        self.assert_corruption(lambda d, r, a, c: a["objective"].update(value=0), "false objective component: value")

    def test_wrong_source_hash(self):
        self.assert_corruption(lambda d, r, a, c: a["source_binding"].update(instance_source_sha256="c" * 64), "source_binding mismatch")

    def test_input_mutation_after_contract(self):
        self.assert_corruption(lambda d, r, a, c: d["orders"][0].update(requested_min=101), "request contract")

    def test_contract_and_artifact_cannot_relax_profile(self):
        def relax(d, r, a, c):
            a["config"]["driver_preparation_min"] = 0
            c["operating_config"]["driver_preparation_min"] = 0
        self.assert_corruption(relax, "frozen checker profile")

    def test_missing_travel_cannot_be_imputed(self):
        def missing(d, r, a, c):
            d["travel_minutes"][0][0] = None
            c["source_binding"] = make_contract(d, r)["source_binding"]
            a["source_binding"] = copy.deepcopy(c["source_binding"])
        self.assert_corruption(missing, "expected numeric minute")

    def test_unverified_mapping(self):
        def unmapped(d, r, a, c):
            d["travel_row_mapping_verified"] = False
            c["source_binding"] = make_contract(d, r)["source_binding"]
            a["source_binding"] = copy.deepcopy(c["source_binding"])
        self.assert_corruption(unmapped, "row mapping is unverified")

    def test_missing_mix_disclosure(self):
        self.assert_corruption(lambda d, r, a, c: a["diagnostics"].update(missing_mix_order_ids=[]), "mix identifiers")

    def test_no_global_or_quality_claim(self):
        self.assert_corruption(lambda d, r, a, c: a["solver"].update(global_optimality_claim=True), "global optimality")
        self.assert_corruption(lambda d, r, a, c: a["diagnostics"].update(quality_feasibility="certified"), "material quality")

    def test_nonfinite_time(self):
        self.assert_corruption(lambda d, r, a, c: a["loads"][0].update(bay_start=math.nan), "nonfinite")

    def test_client_default_and_decimal_quantity(self):
        d, r, a, c = fixture()
        d["orders"][0]["default_load_m3"] = 4.1
        c = make_contract(d, r)
        a["source_binding"] = copy.deepcopy(c["source_binding"])
        a["loads"][0]["volume_m3"] = 4.1
        a["loads"][1]["volume_m3"] = 4.1
        receipt = verify(d, r, a, c)
        self.assertTrue(receipt["accepted"], receipt["errors"])

    def test_driver_review_limit_is_disclosed_and_not_misrepresented_as_law(self):
        d, r, a, c = fixture()
        row = a["loads"][2]
        for key in ("bay_start", "loading_start", "loading_end", "bay_end", "dispatch_time",
                    "site_arrival", "unload_start", "unload_end", "site_clear", "return_time",
                    "reposition_start", "reposition_end", "driver_break_start", "driver_break_end",
                    "driver_meal_start", "driver_meal_end"):
            row[key] += 500
        row["lateness_min"] = 500
        a["objective"].update(value=5250, total_lateness_min=500, max_lateness_min=500, late_loads=1)
        a["diagnostics"].update(operating_end_min=955, shift_break_feasibility="requires_review",
                                driver_review_flags=[{"truck_id": 1,
                                    "reason": "duty_span_exceeds_declared_720_min_review_limit", "minutes": 910}])
        receipt = verify(d, r, a, c)
        self.assertTrue(receipt["accepted"], receipt["errors"])
        self.assertFalse(receipt["kpis"]["driver_legal_compliance_certified"])
        a["diagnostics"]["driver_review_flags"] = []
        receipt = verify(d, r, a, c)
        self.assertFalse(receipt["accepted"])
        self.assertTrue(any("driver review flags" in e for e in receipt["errors"]))

    def test_malformed_nested_metadata_fails_closed(self):
        self.assert_corruption(lambda d, r, a, c: a.update(diagnostics=[]), "malformed")

    def test_rolling_information_set_and_commitments(self):
        d, r, a, _ = fixture()
        a["planning_scope"], a["planning_min"] = "rolling", 200
        a["diagnostics"]["frozen_load_ids"] = ["1:0", "1:1"]
        a["rolling_events"] = [
            {"planning_min": 0, "visible_order_ids": [1], "committed_loads": [],
             "previous_plan_sha256": None, "plan_sha256": "a" * 64},
            {"planning_min": 200, "visible_order_ids": [1, 2], "committed_loads": copy.deepcopy(a["loads"][:2]),
             "previous_plan_sha256": "a" * 64, "plan_sha256": canonical_sha256(a)}]
        c = make_contract(d, r, planning_scope="rolling")
        receipt = verify(d, r, a, c)
        self.assertTrue(receipt["accepted"], receipt["errors"])
        a["rolling_events"][0]["visible_order_ids"].append(2)
        receipt = verify(d, r, a, c)
        self.assertFalse(receipt["accepted"])
        self.assertTrue(any("hidden future" in e for e in receipt["errors"]))
        a["rolling_events"][0]["visible_order_ids"] = [1]
        a["rolling_events"][1]["committed_loads"][0]["truck_id"] = 2
        receipt = verify(d, r, a, c)
        self.assertFalse(receipt["accepted"])
        self.assertTrue(any("commitment changed" in e for e in receipt["errors"]))


if __name__ == "__main__":
    unittest.main()
