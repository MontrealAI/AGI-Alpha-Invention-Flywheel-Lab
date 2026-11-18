import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from geometry import digest, geometry_scope, mission_digest
from photometry import compare_sql, evaluate, measure
from plan import build
from qualify import ROOT, qualification
from reference import construct_catalog
from verify import verify


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mission = json.loads((ROOT/"mission.json").read_text())
        cls.catalog = json.loads((ROOT/"catalog.json").read_text())

    def test_registered_outcomes_and_source_identities(self):
        result = qualification()
        self.assertEqual(result, json.loads((ROOT/"public.json").read_text()))
        self.assertEqual([(c["objective"], c["direct_objective"]) for c in result["cases"] if c["budget"] == 6],
                         [(5, 5), (3, 3)])
        self.assertLess(result["max_angle_difference_deg"], 0.1)

    def test_stale_plan_and_unallocated_time(self):
        p = build(self.mission, self.catalog)
        with self.assertRaisesRegex(ValueError, "identity"):
            verify({**self.mission, "max_slots": 5}, self.catalog, p)
        p["slots"][0]["utc"] = "2026-11-01T04:00:00Z"
        with self.assertRaisesRegex(ValueError, "unknown"):
            verify(self.mission, self.catalog, p)

    def test_fabricated_metadata_and_overlap(self):
        for field, replacement in [("ra_deg",0), ("target_id","ZTF26aaaaaaa"), ("min_alt_deg",math.nan)]:
            p = build(self.mission, self.catalog)
            p["slots"][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(self.mission, self.catalog, p)
        p = build(self.mission, self.catalog)
        p["slots"][1] = copy.copy(p["slots"][0])
        with self.assertRaisesRegex(ValueError, "repeated"):
            verify(self.mission, self.catalog, p)

    def test_whole_visits_and_optimality(self):
        repeat = {**self.mission, "visits_per_target": 2}
        p = build(repeat, self.catalog)
        p["slots"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            verify(repeat, self.catalog, p)
        p = build(self.mission, self.catalog)
        p["slots"], p["objective"] = [], 0
        with self.assertRaisesRegex(ValueError, "optimum"):
            verify(self.mission, self.catalog, p)

    def test_schema_time_and_empty_scope(self):
        for change in [{"max_slots":True},{"visits_per_target":1.5},{"max_slots":7},
                       {"slots_utc":self.mission["slots_utc"]*2},
                       {"min_target_alt_deg": float("inf")}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                build({**self.mission,**change}, self.catalog)
        for jd in [2461345.5,2461300.1]:
            c = copy.deepcopy(self.catalog)
            c["targets"][0]["alert_jd"] = jd
            with self.assertRaisesRegex(ValueError,"stale"):
                build(self.mission,c)
        empty = {**self.mission, "min_target_alt_deg":90}
        p = build(empty,self.catalog)
        self.assertEqual(verify(empty, self.catalog, p)["direct_objective"],0)

    def test_changed_geometry_requires_independent_new_measurement(self):
        m = {**self.mission, "site":{"latitude_deg":0,"longitude_deg":0}}
        p = build(m,self.catalog)
        with self.assertRaisesRegex(ValueError,"fresh reference"):
            verify(m,self.catalog,p)

    def test_flagged_and_unobserved_colors(self):
        cat = {"targets":[{"id":"test"},{"id":"unobserved"}]}
        row = {"i:objectId":"test","i:candid":1,"i:jd":2461347,"i:fid":1,"i:magpsf":18.,
               "i:sigmapsf":0.1,"i:isdiffpos":"t"}
        rows = [row, {**row,"i:candid":2,"i:fid":2,"i:jd":2461347.01,"i:isdiffpos":"f"},
                {**row,"i:candid":3,"i:fid":2,"i:jd":2461347.25}]
        bounds = [2461345.5,2461352.5]
        p = measure(cat,rows,bounds)
        self.assertEqual(p["missing_pair"],["test","unobserved"])
        self.assertTrue(compare_sql(cat,rows,bounds,p)["agrees"])
        with self.assertRaisesRegex(ValueError,"repeated"):
            measure(cat,rows+[row],bounds)
        with self.assertRaisesRegex(ValueError,"outside"):
            measure(cat,[{**row,"i:jd":bounds[1]}],bounds)

    def test_numeric_identity_preserves_history_and_rejects_changed_values(self):
        identical = {**self.mission, "site": {"latitude_deg":32,"longitude_deg":-111},
                     "guard_deg":1, "min_revisit_hours":18, "max_sun_alt_deg":-18, "min_target_alt_deg":30}
        self.assertEqual(mission_digest(identical), digest(self.mission))
        self.assertEqual(geometry_scope(identical,self.catalog), self.catalog["reference"]["scope_sha256"])
        frozen = build(self.mission,self.catalog)
        self.assertEqual(build(identical,self.catalog), frozen)
        self.assertTrue(verify(identical,self.catalog,frozen)["accepted"])
        for change in [{"site":{"latitude_deg":32.01,"longitude_deg":-111}}, {"guard_deg":1.001},
                       {"guard_deg":True}, {"guard_deg":"1"}, {"max_slots":True}, {"max_slots":6.0},
                       {"site":{"latitude_deg":True,"longitude_deg":-111}}, {"min_revisit_hours":None}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify({**identical,**change},self.catalog,frozen)
        # A pre-repair custom recipient hashed its input spelling. Verify the same exact old input
        # without opening a path for a different number or a boolean to satisfy it.
        old_catalog = copy.deepcopy(self.catalog)
        old_catalog["reference"]["scope_sha256"] = geometry_scope(identical,old_catalog,legacy=True)
        old = build(identical,old_catalog)
        old["mission_sha256"] = digest(identical)
        self.assertTrue(verify(identical,old_catalog,old)["accepted"])

    @unittest.skipUnless(shutil.which("node"), "Node runs the supplementary browser-number regression")
    def test_javascript_round_trip_through_recipient_cli(self):
        mission = {**self.mission, "visits_per_target":2}
        original = build(mission,self.catalog)
        receipt = {"mission":mission, "worklist":original}
        js = "process.stdout.write(JSON.stringify(JSON.parse(require('fs').readFileSync(0,'utf8'))))"
        exported = json.loads(subprocess.check_output(["node","-e",js],input=json.dumps(receipt).encode()))
        self.assertIs(type(exported["mission"]["site"]["latitude_deg"]),int)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            m, work = folder/"mission.json", folder/"worklist.json"
            m.write_text(json.dumps(exported["mission"]))
            work.write_text(json.dumps(exported["worklist"]))
            checked = subprocess.check_output([sys.executable,str(ROOT/"verify.py"),str(work),"--mission",str(m)])
            self.assertEqual(json.loads(checked)["direct_objective"],3)
            subprocess.run([sys.executable,str(ROOT/"plan.py"),"--mission",str(m),"--out",str(folder/"new")],
                           check=True,capture_output=True)
            self.assertEqual(json.loads((folder/"new/worklist.json").read_text()),original)

    def test_new_bytes_require_their_own_source_descriptor(self):
        descriptor = json.loads((ROOT/"sources/alerts-source.json").read_text())
        altered = (ROOT/"sources/fink-alerts.json").read_bytes() + b" "
        with self.assertRaisesRegex(ValueError,"hash/length"):
            construct_catalog(self.mission,altered,descriptor)
        with tempfile.TemporaryDirectory() as tmp:
            altered_rows = Path(tmp)/"rows.json"
            altered_rows.write_bytes((ROOT/"sources/fink-holdout.json").read_bytes()+b" ")
            with self.assertRaisesRegex(ValueError,"differ from source"):
                evaluate(observed_path=altered_rows)

    def test_sql_rejects_mutated_source_error_and_identity(self):
        results = evaluate()
        observations = json.loads((ROOT/"sources/fink-holdout.json").read_text())
        bounds = json.loads((ROOT/"sources/holdout-source.json").read_text())["interval_jd"]
        for field,value in [("formal_error_mag",0),("r_candid","lost precision"),
                            ("g_utc","2026-11-15T00:00:00.000Z"), ("g_error_mag",3)]:
            tampered = copy.deepcopy(results)
            tampered["pairs"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_sql(self.catalog,observations,bounds,tampered)


if __name__ == "__main__":
    unittest.main()
