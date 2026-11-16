"""Independent negative controls. Do not change acceptance after the search."""
import copy, unittest
from verify import graph_verdict, InvalidGraph, no_duplicates

def fixture():
    # Six 12-cycles with one opposite matching per vertex: 72 vertices, 108
    # edges, cubic and disconnected. Must never pass the diameter gate.
    edges=[]
    for b in range(6):
        off=12*b
        for i in range(12):
            u,v=off+i,off+(i+1)%12
            edges.append(sorted([u,v]))
        for i in range(6):
            edges.append([off+i,off+i+6])
    return {"n":72,"edges":edges,"best_violations":0,"total_proposals":200000,
            "per_seed":[{"seed":2026111601+i,"valid_proposals":25000,"invalid_proposals":0,"accepted_proposals":0,"best_violations":0} for i in range(8)]}

class ResearchTests(unittest.TestCase):
    def test_disconnected_graph_with_forged_zero_rejected(self):
        with self.assertRaisesRegex(InvalidGraph,"SEARCH_SCORE_MISMATCH"):
            graph_verdict(fixture())
    def test_duplicate_edge_rejected(self):
        a=fixture();a["edges"][0]=a["edges"][1]
        with self.assertRaises(InvalidGraph):graph_verdict(a)
    def test_invalid_degree_rejected(self):
        a=fixture();a["edges"][0]=[0,2]
        with self.assertRaises(InvalidGraph):graph_verdict(a)
    def test_duplicate_json_field_rejected(self):
        with self.assertRaisesRegex(InvalidGraph,"DUPLICATE_JSON_FIELD"):
            no_duplicates([("n",72),("n",73)])
    def test_missing_seed_rejected(self):
        a=fixture();a["per_seed"][0]["seed"]=1
        # Correct score to isolate registration from topology.
        a["best_violations"]=graph_verdict_unchecked_score(a)
        with self.assertRaisesRegex(InvalidGraph,"SEED_REPLACEMENT"):
            graph_verdict(a)

def graph_verdict_unchecked_score(a):
    # A fixture-independent exact count: six disconnected components of size12
    # implies 6*5/2 * 12*12 =2160 cross-component pairs, plus any >5 within.
    from collections import deque
    adj=[set() for _ in range(72)]
    for u,v in a["edges"]:adj[u].add(v);adj[v].add(u)
    count=0
    for u in range(72):
        dist={u:0};q=deque([u])
        while q:
            x=q.popleft()
            for y in adj[x]:
                if y not in dist:dist[y]=dist[x]+1;q.append(y)
        count+=sum((v not in dist or dist[v]>5) for v in range(u+1,72))
    return count

if __name__=="__main__":unittest.main()
