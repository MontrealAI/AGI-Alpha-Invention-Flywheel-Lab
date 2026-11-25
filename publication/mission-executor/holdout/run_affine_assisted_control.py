"""Known-case authored comparator. The workflow runs real computations from two declared proposal fixtures."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

from mission_reference import ORACLES
from run_held_runtime import read_registered, source_manifest, mission_spec, _affine_args, summarize_affine, jwrite


def field(name):
    return {"field":name}


def op(name,*args):
    return {"op":name,"args":list(args)}


def definition(broken=False):
    c1,o1,c2,o2,target=map(field,("c1","o1","c2","o2","target"))
    dc,do=op("sub",c2,c1),op("sub",o2,o1)
    valid=op("and",op("not",op("eq",c1,c2)),op("not",op("eq",o1,o2)))
    computed=op("add",c1,op("div",op("mul",op("sub",target,o1),dc),do))
    projected=op("add",o1,op("div",op("mul",op("sub",computed,c1),do),dc))
    outputs={"command":op("if",valid,computed,None),"round_trip_mm":op("if",valid,projected,None)}
    if broken:
        outputs["command"]=op("formula",target)
    return {"name":"Inverse affine calibration","inputs":["c1","c2","o1","o2","target"],"outputs":outputs}


def main():
    p=ArgumentParser()
    p.add_argument("repo",type=Path)
    p.add_argument("source_manifest",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    root=args.repo.resolve()
    source_manifest(root,args.source_manifest)
    sys.path.insert(0,str(root/"products/alpha-genesis-harness"))
    from bridge.universal_missions import UniversalMissionService
    from bridge.workflow_demo import FixtureRuntime
    case=read_registered()["m01"]
    known=case["input"]
    name="inverse-affine.json"
    build=lambda broken: {"tool":"construct_instrument","name":name,"spec":definition(broken=broken)}
    checks=[{"tool":"run_instrument","name":name,"input":_affine_args(known,target)}
            for target in known["targets"]]
    proposals=[
        {"summary":"Rejouons la forme d'expression refusée pour obtenir un diagnostic réel.",
         "actions":[build(True),checks[0]],"done":False},
        {"summary":"Le test a refusé l'opération inconnue. Représentons la calibration par les opérations arithmétiques prises en charge.",
         "actions":[build(False),*checks],"done":True},
    ]
    args.output.mkdir(parents=True,exist_ok=False)
    jwrite(args.output/"AUTHORED-PROPOSALS.json",proposals)
    begin=perf_counter()
    runtime=FixtureRuntime(proposals)
    service=UniversalMissionService(runtime,args.output/"workspace")
    spec=mission_spec(case,"fixture","authored-constructor",max_turns=2,max_output_tokens=1024)
    try:
        ident=service.submit(spec)["id"]
        first=service.step(ident)
        assert first["status"]=="ready"
        assert any(e["kind"]=="tool_refused" and "Unsupported expression operation" in e["detail"]["reason"]
                   for e in first["events"])
        second=service.step(ident)
        assert second["status"]=="needs_review"
        archive=service.export(ident)
    finally:
        service.close()
    duration=perf_counter()-begin
    expected=ORACLES[case["oracle"]](known)
    scope=summarize_affine(case,expected,archive["state"],archive["files"],[])
    assert scope["qualification"]=="ACCEPT",scope
    assert "Unsupported expression operation" in runtime.calls[1]["prompt"]
    jwrite(args.output/"CHECKPOINT.json",archive)
    jwrite(args.output/"CONTROL-RECEIPT.json",{
        "case":"m01",
        "proposal_mode":"Codex-authored, known-case fixture packets supplied by evaluator",
        "model_requests":0,
        "limits":"This is an actual same-runtime comparator with declared authored proposals, not a fresh holdout passed by a local model. Constructor knows the original fixture.",
        "elapsed_seconds_of_runtime":duration,
        "authorship_elapsed":"not measured",
        "exact_backend_manifest_sha256":sha256(args.source_manifest.read_bytes()).hexdigest(),
        "independently_recomputed":scope,
        "frozen_authoritative_executions":archive["state"]["actions"],
    })
    print(json.dumps(scope,ensure_ascii=False))


if __name__=="__main__":
    main()
