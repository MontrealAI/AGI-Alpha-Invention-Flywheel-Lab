"""Independent standard-library graph certificate checker for 72-cubic experiment."""
from __future__ import annotations
import argparse
from collections import deque
import json
from pathlib import Path

class InvalidGraph(ValueError):
    pass

def no_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise InvalidGraph("DUPLICATE_JSON_FIELD")
        out[k] = v
    return out

def graph_verdict(payload):
    if not isinstance(payload, dict) or payload.get("n") != 72 or type(payload.get("n")) is not int:
        raise InvalidGraph("EXPECTED_72_VERTICES")
    edges = payload.get("edges")
    if not isinstance(edges, list) or len(edges) != 108:
        raise InvalidGraph("EXPECTED_108_EDGES")
    neighbours = [set() for _ in range(72)]
    for pair in edges:
        if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int or x < 0 or x >= 72 for x in pair):
            raise InvalidGraph("INVALID_EDGE")
        u,v = pair
        if u >= v or v in neighbours[u]:
            raise InvalidGraph("LOOP_REVERSED_OR_DUPLICATED_EDGE")
        neighbours[u].add(v);neighbours[v].add(u)
    if any(len(neighbours[i])!=3 for i in range(72)):
        raise InvalidGraph("NOT_CUBIC")
    invalid_pairs=0
    max_distance=0
    connected=True
    for root in range(72):
        dist=[-1]*72
        dist[root]=0
        q=deque([root])
        while q:
            u=q.popleft()
            for v in neighbours[u]:
                if dist[v]==-1:
                    dist[v]=dist[u]+1;q.append(v)
        for v in range(root+1,72):
            if dist[v]<0:
                connected=False
                invalid_pairs+=1
            elif dist[v]>5:
                invalid_pairs+=1
            if dist[v]>max_distance:
                max_distance=dist[v]
    if payload.get("best_violations") != invalid_pairs or type(payload.get("best_violations")) is not int:
        raise InvalidGraph("SEARCH_SCORE_MISMATCH")
    p=payload.get("per_seed")
    if not isinstance(p,list) or len(p)!=8 or payload.get("total_proposals")!=200000:
        raise InvalidGraph("PROTOCOL_DENOMINATOR_MISMATCH")
    if sorted([x.get("seed") for x in p]) != list(range(2026111601,2026111609)):
        raise InvalidGraph("SEED_REPLACEMENT")
    for x in p:
        if any(type(x.get(k)) is not int for k in ("valid_proposals","invalid_proposals","accepted_proposals","best_violations")):
            raise InvalidGraph("INVALID_COUNTER")
        if x["valid_proposals"]+x["invalid_proposals"] != 25000 or x["accepted_proposals"]>x["valid_proposals"] :
            raise InvalidGraph("PROPOSAL_COUNTER_TAMPER")
    if min(x["best_violations"] for x in p) != invalid_pairs:
        raise InvalidGraph("GLOBAL_MINIMUM_NOT_LINKED_TO_SEED")
    owner = [x for x in p if x["seed"] == payload.get("best_seed")]
    if len(owner) != 1 or owner[0]["best_violations"] != invalid_pairs or owner[0].get("best_step") != payload.get("best_step"):
        raise InvalidGraph("WINNING_SEED_OR_STEP_MISMATCH")
    return {"accepted_new_record": connected and max_distance<=5 and invalid_pairs==0,
            "connected":connected,"diameter":max_distance if connected else None,"violating_pairs":invalid_pairs,
            "n":72,"degree":3,"edges":108,"registered_proposals":200000}

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output")
    args=p.parse_args()
    obj=json.loads(Path(args.input).read_text(),object_pairs_hook=no_duplicates)
    verdict=graph_verdict(obj)
    result=json.dumps(verdict,sort_keys=True,indent=2)+"\n"
    if args.output:Path(args.output).write_text(result)
    print(result,end="")
if __name__=="__main__":main()
