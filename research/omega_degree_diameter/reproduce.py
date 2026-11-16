"""Rebuild and independently check the finite Ω degree-diameter probe."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from verify import parse_incumbent, verify

HERE=Path(__file__).resolve().parent
FROZEN=json.loads((HERE/'run-exhaustive.json').read_text())
FROZEN_CANDIDATE=json.loads((HERE/'best72.json').read_text())
KEYS=('incumbent_order','target_order','best_pairs_beyond_5',
      'found_record','insertions_two','insertions_three',
      'vertex_triangle_expansions','min_two_edge_deficit',
      'min_three_edge_deficit','min_triangle_deficit',
      'proposed_degree_preserving_swaps','accepted_swaps',
      'attempts_setting','restarts','seed','exhaustive_3edge')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(output):
    output.mkdir(parents=True,exist_ok=True)
    binary=output/'omega_graph_search'
    candidate=output/'candidate_72.json'
    compiler=subprocess.run(['g++','--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
    subprocess.run(['g++','-O3','-std=c++17','-Wall','-Wextra','-o',str(binary),str(HERE/'search.cpp')],check=True)
    completed=subprocess.run([str(binary),str(HERE/'afy70_adjlist.txt'),str(candidate),
                              '12000','12','20261116','--exhaustive'],
                              capture_output=True,text=True,check=True)
    measured=json.loads(completed.stdout)
    for k in KEYS:
        if measured.get(k)!=FROZEN.get(k):
            raise AssertionError(f'REPLAY_DISAGREES {k}: {measured.get(k)!r} != {FROZEN.get(k)!r}')
    actual=json.loads(candidate.read_text())
    if actual['adjacency'] != FROZEN_CANDIDATE['adjacency']:
        raise AssertionError('SAVED_BEST_CANDIDATE_MISMATCH')
    reference=verify(parse_incumbent(HERE/'afy70_adjlist.txt'))
    result=verify(actual['adjacency'])
    if (reference['vertices'],reference['diameter'])!=(70,5):
        raise AssertionError('INCUMBENT_INVALID')
    if (result['vertices'],result['diameter'],result['pairs_beyond_diameter_cap'],result['record_beaten'])!=(72,6,34,False):
        raise AssertionError('CLAIM_MISMATCH')
    verdict={
      'schema':'montreal-ai/omega-degree-diameter-replay/v1',
      'status':'HOLD_NO_RECORD',
      'scientific_claim':'No record found in bounded 70-to-72 augmentation families and local random search',
      'scientific_nonclaim':'No upper bound on unrestricted cubic graphs; no novel constructive record; no AI superiority',
      'incumbent_reference':'https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/desc_g5.html',
      'incumbent_order':reference['vertices'],
      'incumbent_diameter':reference['diameter'],
      'candidate_verdict':result,
      'construction_arms':{k:measured[k] for k in KEYS if k not in ('incumbent_order','target_order','found_record','best_pairs_beyond_5')},
      'compiler':compiler,
      'source_sha256':{p:sha(HERE/p) for p in ['search.cpp','verify.py','afy70_adjlist.txt']},
      'candidate_sha256':sha(candidate),
    }
    (output/'verdict.json').write_text(json.dumps(verdict,indent=2,sort_keys=True)+'\n')
    (output/'search_receipt.json').write_text(json.dumps(measured,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':verdict['status'],'candidate_order':72,
                      'candidate_diameter':6,'excess_distance_pairs':34,
                      'total_exact_local_family_candidates':measured['insertions_two']+
                             measured['insertions_three']+measured['vertex_triangle_expansions'],
                      'source_bound':True,'output':str(output)},indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    if args.output_dir:
        replay(args.output_dir)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            replay(Path(tmp))

if __name__=='__main__': main()
