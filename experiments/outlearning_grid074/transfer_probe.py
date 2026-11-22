"""Replay the immutable K1 artifact on the independently specified K2 domain.

This is a development falsification probe, not a held-out commercial trial.
"""
import copy
import hashlib
import json
from pathlib import Path
import time
from retained_symmetry import construct
from provenance import record

ROOT = Path(__file__).parent


def run():
    frozen = json.loads((ROOT/"K1_FREEZE.json").read_text())
    for name, expected in frozen["files"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    start=time.process_time()
    thermal=json.loads((ROOT/"k1_card.json").read_text())
    grid=json.loads((ROOT/"k2_card.json").read_text())
    cases={"K1_thermal":construct(thermal),"K2_fixed_source":construct(grid)}
    # Counterfactual algebra unit test only: the evaluator fixes source=1.
    # Do not add this variant to its physical family or score it as confirmation.
    free=copy.deepcopy(grid);free["fixed"].remove("u")
    cases["counterfactual_unanchored_source_algebra_only"]=construct(free)
    assert cases["K1_thermal"]["has_witnessed_scale_ambiguity"]
    assert not cases["K2_fixed_source"]["has_witnessed_scale_ambiguity"]
    assert cases["counterfactual_unanchored_source_algebra_only"]["has_witnessed_scale_ambiguity"]
    result={
      "role":"development falsification; no fresh confirmation experiment",
      "retained_artifact_unchanged":True,
      "cases":cases,"cpu_seconds":time.process_time()-start,
      "decision":"Reject the transferred premise that K2 necessarily needs a scale-breaking reference. Fixed source anchors the tested scaling degree of freedom. Do not claim K2 is identifiable from noisy data, or that no reference can ever be useful.",
      "learned_advantage":False,
      "newly_enabled_business":False,
      "commercial_test":"not started; no accepted customer output/native account or profit claimed",
      "next":"Compare any remaining practical cost/robustness hypothesis to ordinary adaptive identification before funding a more realistic commissioning study. No confirmation sweep of the failed structural premise.",
    }
    (ROOT/"TRANSFER_RESULT.json").write_text(json.dumps(result,indent=2))
    record(ROOT,"k2_immutable_artifact_executed",[
      "K1 frozen generated source and observations", "independent K2 public exact branch-flow domain; fixed source=1",
    ],result["decision"],[ROOT/"retained_symmetry.py",ROOT/"k2_card.json",ROOT/"TRANSFER_RESULT.json"])
    return result


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
