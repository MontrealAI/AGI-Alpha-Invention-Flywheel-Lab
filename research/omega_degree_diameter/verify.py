"""Independent stdlib-only graph verifier for undirected degree-diameter records.

Accepts a JSON adjacency-list document {"adjacency": [[...], ...]} or the
original published NetworkX adjacency text; computes all-pairs BFS, refusing
loops, duplicates, asymmetric edges, excessive degree, and disconnection.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path


def parse_incumbent(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    graph = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        row = [int(x) for x in line.split()]
        if row[0] != len(graph):
            raise ValueError('Not a complete, ordered incumbent list')
        graph.append([])
        for w in row[1:]:
            graph[-1].append(w)
    # NetworkX format supplies an undirected edge only once; restore reverse.
    n = len(graph)
    forward = [tuple(row) for row in graph]
    for v in range(n):
        for w in forward[v]:
            if not (v < w < n):
                raise ValueError('Input not strict forward-edge NetworkX format')
            graph[w].append(v)
    return [sorted(row) for row in graph]


def verify(graph, degree_cap=3, diameter_cap=5):
    n = len(graph)
    if n == 0:
        raise ValueError('EMPTY_GRAPH')
    if any(not isinstance(row, list) for row in graph):
        raise ValueError('INVALID_ROWS')
    for v, row in enumerate(graph):
        if any(type(w) is not int or not 0 <= w < n for w in row):
            raise ValueError('INVALID_VERTEX')
        if len(row) != len(set(row)) or v in row:
            raise ValueError('NON_SIMPLE_GRAPH')
        if len(row) > degree_cap:
            raise ValueError('DEGREE_OVER_CAP')
    for v, row in enumerate(graph):
        for w in row:
            if v not in graph[w]:
                raise ValueError('ASYMMETRIC_GRAPH')
    pairs_far = 0
    unreachable = 0
    diam = 0
    histogram = [0] * (n + 1)
    max_degrees = max(map(len,graph))
    for root in range(n):
        distance = [-1] * n
        distance[root] = 0
        q = deque([root])
        while q:
            u = q.popleft()
            for v in graph[u]:
                if distance[v] == -1:
                    distance[v] = distance[u] + 1
                    q.append(v)
        if -1 in distance:
            unreachable += distance.count(-1)
        diam = max(diam,max(distance))
        for d in distance:
            if d >= 0:
                histogram[d] += 1
            if d > diameter_cap or d == -1:
                pairs_far += 1
    return {'vertices':n, 'edges':sum(map(len,graph))//2, 'degree_max':max_degrees,
        'degree_min':min(map(len,graph)), 'diameter':diam if not unreachable else None,
        'unreachable_ordered_pairs':unreachable,
        'pairs_beyond_diameter_cap':pairs_far//2,
        'diameter_cap':diameter_cap, 'degree_cap':degree_cap,
        'accepted': max_degrees<=degree_cap and unreachable == 0 and diam<=diameter_cap,
        'record_beaten': n>70 and max_degrees<=degree_cap and unreachable==0 and diam<=diameter_cap,
        'distance_histogram_ordered':histogram[:max(diam+1,1)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph',required=True)
    parser.add_argument('--published-incumbent',action='store_true')
    parser.add_argument('--report-only',action='store_true',help='inspect a failing candidate without claiming an accepted record')
    args=parser.parse_args()
    if args.published_incumbent:
        graph=parse_incumbent(args.graph)
    else:
        document=json.loads(Path(args.graph).read_text())
        graph=document['adjacency']
    result=verify(graph)
    result['input_sha256']=hashlib.sha256(Path(args.graph).read_bytes()).hexdigest()
    print(json.dumps(result,indent=2))
    if not result['accepted'] and not args.report_only:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
