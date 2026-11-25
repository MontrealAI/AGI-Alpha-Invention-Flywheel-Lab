
"""Score already-frozen DPP arm outputs against independent document readings."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

STATE = {"supported", "contradicted", "insufficient", "conflicting"}

def read(path):
    raw=path.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def load_predictions(path):
    raw, fingerprint=read(path)
    if isinstance(raw,dict):
        if isinstance(raw.get("cases"), list):
            raw=raw["cases"]
        elif isinstance(raw.get("predictions"), list):
            raw=raw["predictions"]
        elif all(isinstance(row,dict) for row in raw.values()):
            raw=[{"id":id,**row} for id,row in raw.items()]
    if not isinstance(raw,list):
        raise ValueError("Expected a list of frozen prediction records.")
    result={}
    for row in raw:
        if not isinstance(row,dict) or not isinstance(row.get("id"),str) or row["id"] in result:
            raise ValueError("Prediction has missing or non-unique case ID.")
        result[row["id"]]=row
    return result,fingerprint

def grade(cases, reference, predictions):
    wanted={case["id"]:case for case in cases}
    if set(reference)!=set(wanted) or set(predictions)-set(wanted):
        raise ValueError("Mismatch between declared cases and oracle/predictions.")
    scores=[]
    for id,case in wanted.items():
        expected=reference[id]
        seen=predictions.get(id,{})
        by_source={source["id"]:source for source in case["sources"]}
        cited=seen.get("evidence")
        ids_valid=(isinstance(cited,list) and all(isinstance(item,str) and item in by_source for item in cited)
                   and len(cited)==len(set(cited)))
        wanted_ids=expected["evidence"]
        provenance=ids_valid and any(set(cited)==set(row) for row in wanted_ids)
        disposition=seen.get("decision") in STATE and seen["decision"]==expected["decision"]
        rationale=seen.get("reason")
        explainable=isinstance(rationale,str) and bool(rationale.strip())
        scores.append({"id":id,"field":case["field"],"expected":expected["decision"],"observed":seen.get("decision"),
                       "decision_correct":disposition,"evidence_exact":provenance,
                       "reason_present":explainable,"fully_accepted":disposition and provenance and explainable,
                       "unsafe_false_support":seen.get("decision")=="supported" and not (disposition and provenance),
                       "observed_evidence":cited, "reference_evidence_choices":wanted_ids,
                       "rationale":rationale,"evaluator_reason":expected["reason"]})
    return {
        "cases":len(scores),
        "correct_dispositions":sum(row["decision_correct"] for row in scores),
        "exact_evidence":sum(row["evidence_exact"] for row in scores),
        "whole_case_acceptance":sum(row["fully_accepted"] for row in scores),
        "false_supported":sum(row["unsafe_false_support"] for row in scores),
        "expected_distribution":dict(Counter(row["expected"] for row in scores)),
        "missing":sum(row["observed"] is None for row in scores),
        "scores":scores,
    }

def main():
    cmd=argparse.ArgumentParser(description=__doc__)
    cmd.add_argument("input",type=Path)
    cmd.add_argument("reference",type=Path)
    cmd.add_argument("prediction",type=Path)
    cmd.add_argument("destination",type=Path)
    cmd.add_argument("--frozen-prediction-sha256",required=True)
    args=cmd.parse_args()
    cases,input_sha=read(args.input)
    ref,oracle_sha=read(args.reference)
    predictions,prediction_sha=load_predictions(args.prediction)
    if args.frozen_prediction_sha256!=prediction_sha:
        raise ValueError("Predictions changed after the arm output was frozen.")
    evidence=grade(cases,ref,predictions)
    evidence.update(input_sha256=input_sha,oracle_sha256=oracle_sha,predictions_sha256=prediction_sha,
                    evaluation_scope="Supplied documents and registered engineering claim dimensions only. Reason presence is machine-checked; reviewer compares substantive rationale separately.")
    with args.destination.open("x",encoding="utf-8") as file:
        json.dump(evidence,file,ensure_ascii=False,indent=2)
        file.write("\n")
    print(json.dumps({key:value for key,value in evidence.items() if key!="scores"}))

if __name__=="__main__":
    main()
