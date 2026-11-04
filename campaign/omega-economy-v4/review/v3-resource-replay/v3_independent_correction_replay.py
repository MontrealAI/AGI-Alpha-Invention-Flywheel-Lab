"""Independent resource review of a bounded V3 solver case followed by a normal successor."""
from pathlib import Path
from unittest.mock import patch
import argparse
import copy
import hashlib
import json
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument("source", type=Path)
p.add_argument("before", type=Path)
p.add_argument("v4_control", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
src = a.source.resolve()
sys.path.insert(0, str(src))
from mechanism_harness import mechanism_campaign, mechanism_native, cart_native, reach_native
from commercial.ledger import digest

def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

paths = ("mechanism_harness/mechanism_campaign.py", "mechanism_harness/mechanism_native.py",
         "tests/test_omega_mechanisms_v3.py")
start = {name: file_sha(src / name) for name in paths}
before = json.loads(a.before.read_bytes())["v3"]
control = json.loads(a.v4_control.read_bytes())
cases = ((391101, "complementary"), (391102, "substitute"))
gen = mechanism_campaign.market
def bounded_market(seed, family):
    spec = gen(seed, family)
    if seed == 391101:
        spec["limits"]["max_rounds"] = 1
    return spec

with patch.object(mechanism_campaign, "market", side_effect=bounded_market):
    result = mechanism_campaign.execute(cases)
rows = result["cases"]
fields = {"total_rows_built": "total_rows_built", "total_deviation_checks": "deviation_checks",
          "construction_cpu_ns": "construction_cpu_ns"}
sums = {top: {arm: sum(row["runs"][arm][entry] for row in rows) for arm in rows[0]["runs"]}
        for top, entry in fields.items()}
assert all(result[k] == v for k, v in sums.items())
assert [row["status"] for row in rows] == before["statuses"] == ["UNRESOLVED", "VERIFIED"]
assert result["completed_cases"] == 1 and result["registered_cases"] == 2
assert sums["total_rows_built"] == before["all_case_rows"]
assert sums["total_deviation_checks"] == before["all_case_checks"]
assert [r["prior_discovery_rows"] for r in rows] == [0, 45]
assert rows[1]["memory_before"] is None
mechanism_campaign.audit_resources(result)
forged = copy.deepcopy(result)
forged["construction_cpu_ns"]["bundle"] += 1
try:
    mechanism_campaign.audit_resources(forged)
except ValueError as error:
    tamper = str(error)
else:
    raise AssertionError("forged aggregate CPU was accepted")
assert tamper == "CAMPAIGN_RESOURCE_TOTAL_CHANGED"
assert control["statuses"] == ["UNRESOLVED", "VERIFIED"] and control["all_rows"]
assert control["first_inherited_rows"] == control["next_prefix"] == 180
assert start == {name: file_sha(src / name) for name in paths}

maps = {name: fn() for name, fn in (("v3", mechanism_native.source_identity),
        ("v4", cart_native.source_identity), ("paid_reach", reach_native.source_identity))}
assert digest(maps["v4"]) == "05594b2569b72362daec83b136e743da949ae384411dc05837981281eb44e3a6"
assert digest(maps["paid_reach"]) == "72ce9400200c8201a5c60bb7a299b9206cf00d0ae70fa2baf36433ff5ac49010"
receipt = {
    "schema": "omega/independent-v3-unresolved-cost-replay/v1", "accepted": True,
    "source_checkout_head": subprocess.check_output(["git","-C", str(src),"rev-parse","HEAD"], text=True).strip(),
    "source_files_sha256": start, "source_stable": True,
    "review_script_sha256": file_sha(Path(__file__)),
    "pre_repair_file_sha256": file_sha(a.before), "v4_control_file_sha256":file_sha(a.v4_control),
    "fixture": {"market_cases": cases, "only_first_max_rounds": 1, "new_operating_accounts":0},
    "registered_cases": 2, "completed_cases": 1, "status": [r["status"] for r in rows],
    "before_reported_rows": before["reported_rows"], "before_incurred_rows": before["all_case_rows"],
    "after_reported_and_recomputed": sums, "prior_discovery_rows": [r["prior_discovery_rows"] for r in rows],
    "before_successor_prior_rows": before["next_prior_inherited_rows"], "unresolved_memory_transferred":False,
    "aggregate_cpu_tamper_rejection":tamper,
    "native_source_maps": {k: {"files":len(v),"digest":digest(v)} for k,v in maps.items()},
    "earlier_v4_control": {"retained_partial_work":True,"incurred_and_carried_rows":180},
    "reviewer_note": "Initial independent wrapper expected a truncated rejection code. The target correctly refused the mutation; the reviewer was corrected to the observed full code and rerun on identical source.",
}
with a.output.open("x") as f:
    json.dump(receipt, f, sort_keys=True, indent=2)
    f.write("\n")
print(a.output, file_sha(a.output), sums["total_rows_built"], receipt["native_source_maps"])
