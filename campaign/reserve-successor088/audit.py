"""Independent read-only audit of the frozen original run.py; no result edits."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reserve_original', ROOT / 'run.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def main():
    edges, source_hash = m.read()
    checked = 0
    maximum_difference = 0.0
    for failed in range(-1, len(edges)):
        # Entirely exclude zones, an independent formulation valid because all
        # original source and destination nodes are through-node IDs.
        ee = [e for i, e in enumerate(edges)
              if i != failed and e[0] >= 39 and e[1] >= 39]
        rr, cc, ww = zip(*ee)
        graph = csr_matrix((ww, (np.array(rr)-1, np.array(cc)-1)), shape=(416,416))
        oracle = dijkstra(graph, directed=True, indices=np.array(m.DEPOTS)-1)
        for i, depot in enumerate(m.DEPOTS):
            actual = m.routes(edges, failed, depot)
            for j, destination in enumerate(m.DEST):
                a, b = actual[j][0], oracle[i, destination-1]
                assert (np.isinf(a) and np.isinf(b)) or abs(a-b) < 1e-10, (failed,depot,destination,a,b)
                if np.isfinite(a):
                    maximum_difference = max(maximum_difference, abs(a-b))
                checked += 1
    # Adversary 1: a faster path through a zone must not be admitted.
    synthetic = [(117,1,1.0), (1,87,1.0), (117,87,5.0)]
    assert m.routes(synthetic,-1,117)[0][0] == 5.0
    # Adversary 2: losing the only legitimate edge cannot revive that shortcut.
    assert np.isinf(m.routes(synthetic,2,117)[0][0])
    incoming = {str(d):sum(a >= 39 and b == d for a,b,w in edges) for d in m.DEST}
    assert all(count == 0 for count in incoming.values())
    print(json.dumps({
        'audited_runner_sha256':hashlib.sha256((ROOT/'run.py').read_bytes()).hexdigest(),
        'source_sha256':source_hash,
        'independent_scipy_distance_checks':checked,
        'maximum_distance_difference':maximum_difference,
        'forbidden_zone_shortcut_rejected':True,
        'failed_direct_edge_disconnection_verified':True,
        'beneficiary_incoming_through_edge_counts':incoming,
        'interpretation':'Original beneficiary locations cannot receive service even without failure.'
    }, sort_keys=True))

if __name__ == '__main__':
    main()
