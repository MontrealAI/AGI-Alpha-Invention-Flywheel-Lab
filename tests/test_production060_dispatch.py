"""Producer regression tests; independent acceptance lives in a separate module."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from production060.dispatch import DispatchConfig, InputDataError, rolling_schedule, solve


def resources():
    return {"plants":[{"id":1,"source_mean_loading_rate":50,"loading_decks":1},
                      {"id":2,"source_mean_loading_rate":50,"loading_decks":1}],
            "trucks":[{"id":1,"capacity_m3":7.5,"home_plant":1},
                      {"id":2,"capacity_m3":10,"home_plant":2},
                      {"id":3,"capacity_m3":4.5,"home_plant":1}],
            "plant_travel_minutes":[[0,5.6],[7,0]],"source_files":[]}


def day(orders=None, travel=None):
    orders=orders or [{"id":1,"client_id":1,"volume_m3":16,"default_load_m3":7.5,
                       "release_min":0,"requested_min":120,"interval_min":30,"mix_id":7}]
    return {"id":"synthetic-unit","orders":orders,
            "travel_minutes":travel or [[14,7] for _ in orders],
            "missing_travel_order_ids":[],"travel_row_mapping_verified":True}


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.cfg=DispatchConfig(time_limit_s=0)

    def test_exact_decimal_partial_and_capacity(self):
        d=day();d["orders"][0]["volume_m3"]=15.1
        result=solve(resources(),d,config=self.cfg)
        rows=sorted(result["loads"],key=lambda r:r["load_index"])
        self.assertEqual([r["volume_m3"] for r in rows],[7.5,7.5,0.1])
        self.assertEqual(sum(Decimal(str(r["volume_m3"])) for r in rows),Decimal("15.1"))
        capacities={t["id"]:t["capacity_m3"] for t in resources()["trucks"]}
        self.assertTrue(all(r["volume_m3"]<=capacities[r["truck_id"]] for r in rows))
        changed=copy.deepcopy(d);changed["orders"][0]["volume_m3"]=15.2
        self.assertNotEqual(result["source_binding"]["instance_sha256"],
                            solve(resources(),changed,config=self.cfg)["source_binding"]["instance_sha256"])

    def test_client_load_zero_uses_default_but_oversize_refuses(self):
        d=day();d["orders"][0]["default_load_m3"]=0
        self.assertEqual(len(solve(resources(),d,config=self.cfg)["loads"]),3)
        d["orders"][0]["default_load_m3"]=11
        with self.assertRaisesRegex(InputDataError,"no truck can carry"):
            solve(resources(),d,config=self.cfg)

    def test_missing_travel_refuses_and_exclusion_is_explicit(self):
        d=day();d["travel_minutes"]=[]
        with self.assertRaisesRegex(InputDataError,"missing travel"):
            solve(resources(),d,config=self.cfg)
        result=solve(resources(),d,config=DispatchConfig(time_limit_s=0,missing_travel="exclude"))
        self.assertEqual(result["loads"],[])
        self.assertEqual(result["diagnostics"]["excluded_orders"][0]["order_id"],1)
        d=day();d["travel_row_mapping_verified"]=False
        with self.assertRaisesRegex(InputDataError,"mapping"):
            solve(resources(),d,config=self.cfg)

    def test_bay_contention_real_repair_and_return_arithmetic(self):
        r=resources();r["plants"][1]["source_mean_loading_rate"]=0
        orders=[]
        for oid in range(1,4):
            orders.append({"id":oid,"client_id":oid,"volume_m3":4,"default_load_m3":7.5,
                           "release_min":0,"requested_min":120,"interval_min":0,"mix_id":1})
        result=solve(r,day(orders),mode="nearest",config=self.cfg)
        trips=sorted(result["loads"],key=lambda x:x["bay_start"])
        for previous,current in zip(trips,trips[1:]):
            self.assertLessEqual(previous["bay_end"],current["bay_start"])
        self.assertGreater(result["objective"]["total_lateness_min"],0)
        for trip in trips:
            self.assertEqual(trip["bay_end"],trip["bay_start"]+20)
            self.assertEqual(trip["dispatch_time"],trip["bay_start"]+35)
            self.assertEqual(trip["return_time"],trip["unload_start"]+25+trip["outbound_travel_min"])
            self.assertEqual(trip["site_arrival"],trip["unload_start"])

    def test_truck_reuse_has_source_break_and_meal_before_reposition(self):
        r=resources();r["trucks"]=r["trucks"][:1]
        d=day();d["orders"][0].update(volume_m3=15,interval_min=200)
        rows=sorted(solve(r,d,config=self.cfg)["loads"],key=lambda x:x["bay_start"])
        a,b=rows
        self.assertEqual(b["previous_load_id"],a["load_id"])
        self.assertGreaterEqual(b["driver_break_start"],a["return_time"])
        self.assertEqual(b["driver_break_end"]-b["driver_break_start"],15)
        self.assertEqual(b["driver_meal_end"]-b["driver_meal_start"],30)
        self.assertEqual(b["driver_meal_end"],b["reposition_start"])

    def test_long_duty_flag_does_not_claim_legal_feasibility(self):
        r=resources();r["trucks"]=r["trucks"][:1]
        d=day(travel=[[140,140]])
        result=solve(r,d,config=self.cfg)
        self.assertEqual(result["diagnostics"]["shift_break_feasibility"],"requires_review")
        self.assertTrue(any("continuous_block" in f["reason"] for f in result["diagnostics"]["driver_review_flags"]))

    def test_release_applies_to_initial_reposition(self):
        d=day();d["orders"][0].update(release_min=119,requested_min=120)
        result=solve(resources(),d,config=self.cfg)
        self.assertTrue(all(r["reposition_start"]>=119 for r in result["loads"]))

    def test_mix_missing_flag_and_zero_rate_plant_disabled(self):
        r=resources();r["plants"][1]["source_mean_loading_rate"]=0
        d=day();d["orders"][0]["mix_id"]=None
        result=solve(r,d,config=self.cfg)
        self.assertEqual(result["diagnostics"]["missing_mix_order_ids"],[1])
        self.assertTrue(all(x["plant_id"]==1 for x in result["loads"]))

    def test_rolling_passes_only_visible_rows_and_preserves_committed(self):
        first={"id":1,"client_id":1,"volume_m3":7.5,"default_load_m3":7.5,
               "release_min":0,"requested_min":120,"interval_min":30,"mix_id":1}
        second={**first,"id":2,"release_min":130,"requested_min":200}
        d=day([first,second]);d.update(n_orders=2,total_quantity_m3=15,dynamic_order_count=1);snapshots=[]
        import production060.dispatch as module
        real=module.solve
        def capture(r,visible,**kw):
            self.assertTrue(all(o["release_min"]<=kw["now"] for o in visible["orders"]))
            self.assertNotIn("total_quantity_m3",visible)
            self.assertNotIn("n_orders",visible)
            snapshot=real(r,visible,**kw);snapshots.append(copy.deepcopy(snapshot));return snapshot
        with patch.object(module,"solve",capture):
            result=rolling_schedule(resources(),d,config=self.cfg)
        self.assertEqual([e["visible_order_ids"] for e in result["rolling_events"]],[[1],[1,2]])
        self.assertEqual(snapshots[0]["loads"][0],next(x for x in snapshots[1]["loads"] if x["order_id"]==1))
        self.assertEqual(result["diagnostics"]["frozen_load_ids"],["1:0"])
        with self.assertRaisesRegex(InputDataError,"future"):
            solve(resources(),d,config=self.cfg,scope="rolling",now=0)

    @unittest.skipUnless(importlib.util.find_spec("ortools"),"optional OR-Tools not installed")
    def test_cp_sat_same_budget_ordinary_and_cold_model_and_local_certificate(self):
        cfg=DispatchConfig(time_limit_s=1,window_size=8)
        d=day()
        ordinary=solve(resources(),d,mode="ordinary",config=cfg)
        cold=solve(resources(),d,mode="cold",config=cfg)
        baseline=solve(resources(),d,config=self.cfg)
        self.assertLessEqual(ordinary["objective"]["value"],baseline["objective"]["value"]+1e-6)
        self.assertEqual(ordinary["solver"]["name"],cold["solver"]["name"])
        self.assertIsNone(ordinary["objective"]["global_bound"])
        for receipt in ordinary["solver"]["windows"]:
            self.assertEqual(receipt["scope"],"restricted_window")
            if receipt.get("solver_objective") is not None:
                self.assertLessEqual(receipt["objective_bound"],receipt["solver_objective"]+1e-6)

    @unittest.skipUnless(importlib.util.find_spec("ortools"),"optional OR-Tools not installed")
    def test_public_development_rolling_native_solver_does_not_abort(self):
        root=Path(__file__).resolve().parents[1]
        if not (root/"production060/data/days/cdp_o15_03d.json").exists():
            self.skipTest("public operational development fixture not installed")
        # A native OR-Tools hint-repair abort previously killed a multi-day batch.
        # A child process contains that failure mode and tests the complete useful
        # output, rather than asserting a particular solver-parameter spelling.
        script="""
import json
from pathlib import Path
from production060.dispatch import DispatchConfig, rolling_schedule
from production060.acceptance import make_contract, verify
root=Path.cwd()
r=json.loads((root/'production060/data/resources.json').read_text())
d=json.loads((root/'production060/data/days/cdp_o15_03d.json').read_text())
cfg=DispatchConfig(time_limit_s=1.5)
results=[]
for mode in ('ordinary','retained'):
 a=rolling_schedule(r,d,mode=mode,config=cfg)
 verdict=verify(d,r,a,make_contract(d,r,mode=mode,planning_scope='rolling',config=a['config']))
 results.append(verdict['accepted'])
print(json.dumps(results))
"""
        result=subprocess.run([sys.executable,"-c",script],cwd=root,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[True,True])


if __name__=="__main__":
    unittest.main()
