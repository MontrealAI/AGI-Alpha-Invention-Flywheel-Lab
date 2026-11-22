"""Local, source-bound negative controls for the Ω open degree-diameter probe."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify import parse_incumbent, verify

HERE=Path(__file__).resolve().parent
BASE=HERE/'afy70_adjlist.txt'
BEST=HERE/'best72.json'
SUMMARY=HERE/'run-exhaustive.json'


class DegreeDiameterEvidenceTests(unittest.TestCase):
    def test_published_incumbent_has_correct_exact_parameters(self):
        graph=parse_incumbent(BASE)
        result=verify(graph)
        self.assertEqual((result['vertices'],result['edges'],result['diameter']),(70,105,5))
        self.assertEqual((result['degree_min'],result['degree_max']),(3,3))
        self.assertFalse(result['record_beaten'])

    def test_72_vertex_candidate_fails_the_frozen_record_threshold(self):
        graph=json.loads(BEST.read_text())['adjacency']
        result=verify(graph)
        self.assertEqual((result['vertices'],result['edges'],result['diameter']),(72,108,6))
        self.assertEqual(result['pairs_beyond_diameter_cap'],34)
        self.assertEqual(result['unreachable_ordered_pairs'],0)
        self.assertFalse(result['accepted'])
        self.assertFalse(result['record_beaten'])

    def test_record_acceptance_rejects_false_positives(self):
        graph=json.loads(BEST.read_text())['adjacency']
        malformed=copy.deepcopy(graph)
        malformed[0].append(0)
        with self.assertRaisesRegex(ValueError,'NON_SIMPLE_GRAPH'):
            verify(malformed)
        malformed=copy.deepcopy(graph)
        malformed[0].append(malformed[0][0])
        with self.assertRaisesRegex(ValueError,'NON_SIMPLE_GRAPH'):
            verify(malformed)
        malformed=copy.deepcopy(graph)
        v,w=0,malformed[0][0]
        malformed[0].remove(w)
        with self.assertRaisesRegex(ValueError,'ASYMMETRIC_GRAPH'):
            verify(malformed)
        malformed=copy.deepcopy(graph)
        # Any additional edge attached to a cubic vertex exceeds the cap.
        w=next(x for x in range(72) if x!=0 and x not in malformed[0])
        malformed[0].append(w);malformed[w].append(0)
        with self.assertRaisesRegex(ValueError,'DEGREE_OVER_CAP'):
            verify(malformed)

    def test_odd_order_above_70_is_mathematically_unreachable(self):
        # If degree <=2 at one root, its radius-5 Moore ball has <=63 vertices.
        # So a 71+ vertex degree-3 diameter-5 graph must be cubic. The
        # handshaking lemma then forces the graph order to be even.
        radius_5_with_degree2_root=1+2*sum(2**i for i in range(5))
        self.assertEqual(radius_5_with_degree2_root,63)
        self.assertEqual((3*72)%2,0)
        self.assertEqual((3*71)%2,1)

    def test_combinatorial_construction_class_sizes_independently(self):
        graph=parse_incumbent(BASE)
        edges=[(v,w) for v,row in enumerate(graph) for w in row if v<w]
        self.assertEqual(len(edges),105)
        disjoint_pairs=0
        disjoint_triples=0
        for i,(a,b) in enumerate(edges):
            for j in range(i+1,len(edges)):
                c,d=edges[j]
                if len({a,b,c,d}) != 4:continue
                disjoint_pairs+=1
                for k in range(j+1,len(edges)):
                    e,f=edges[k]
                    if len({a,b,c,d,e,f})==6:disjoint_triples+=1
        self.assertEqual((disjoint_pairs*2,disjoint_triples*4,70*3),
                         (10500,665560,210))
        run=json.loads(SUMMARY.read_text())
        self.assertEqual((run['insertions_two'],run['insertions_three'],run['vertex_triangle_expansions']),
                         (10500,665560,210))
        self.assertFalse(run['found_record'])
        self.assertEqual(run['best_pairs_beyond_5'],34)
        self.assertEqual((run['min_two_edge_deficit'],run['min_three_edge_deficit'],run['min_triangle_deficit']),
                         (34,46,64))

    def test_independent_verifier_runs_without_packages(self):
        cmd=[sys.executable,'-S',str(HERE/'verify.py'),'--graph',str(BEST),'--report-only']
        result=subprocess.run(cmd,check=True,capture_output=True,text=True)
        report=json.loads(result.stdout)
        self.assertFalse(report['accepted'])
        self.assertEqual(report['pairs_beyond_diameter_cap'],34)
        strict=subprocess.run(cmd[:-1],check=False,capture_output=True,text=True)
        self.assertEqual(strict.returncode,2)


if __name__=='__main__':
    unittest.main()
