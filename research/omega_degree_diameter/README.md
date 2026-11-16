# 🌌♾️ GOAL GENESIS Ω — An actual open-frontier attempt

**Question:** Can we construct an undirected *simple* graph with more than 70 vertices, maximum degree 3, and diameter at most 5?

**Executed verdict on November 16, 2026: `HOLD_NO_RECORD`.** No qualifying graph was found; this is not evidence that no such graph exists, not a novel world record, not an established autonomous breakthrough, and not an economic or real-world beneficiary outcome. It is a reproducible negative result within *specified local extension families* of the strongest published 70-vertex incumbent.

## Ground truth: the serious incumbent

Francesc Comellas's [maintained Degree/Diameter table](https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/desc_g5.html), last modified November 14, 2026, reports **70** for degree 3 and diameter 5, originally due to Alegre, Fiol and Yebra (1986). The [publisher's 70-vertex adjacency list](https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/adjacencies/adjD5/AlFiYe70_Z_adjlist.txt) was transcribed into `afy70_adjlist.txt`. Its edges, all 105, were independently verified to give a connected cubic graph of diameter exactly 5. Source origin and citation accompany the bytes; this checked-in copy's hash, not an assumed original-URL hash, binds the replay.

The Moore bound is 94; no optimality theorem settles the cell. A useful necessary condition is that any graph with at least 71 vertices, maximum degree 3 and diameter at most 5 must be cubic: a vertex of degree ≤2 could reach at most `1 + 2*(1+2+4+8+16) = 63` vertices within five steps. The handshaking lemma then forces even order. **72 is the first possible new record order**, but it is not known to be constructible.

## Actual computation, not an authored toy witness

We compared three complete local two-vertex augmentation families of the *real* incumbent:

| Family | Constructions evaluated (identifying the two new vertex labels up to exchange) | Best unordered vertex pairs still separated by >5 edges |
|---|---:|---:|
| Delete two disjoint incumbent edges, attach new vertices to their endpoints and each other | 10,500 (all symmetry-reduced assignments) | 34 |
| Delete three pairwise vertex-disjoint incumbent edges, connect their endpoints to two new degree-3 vertices | 665,560 (all, modulo swapping the two new vertices) | 46 |
| Replace one degree-3 incumbent vertex by a triangle on three vertices, reattaching its former neighbors | 210 (all, modulo exchanging new vertices) | 64 |

A separate deterministic, degree-preserving double-edge-swap simulated-annealing attempt used 12 restart batches under seed `20261116`. It proposed 10,966 valid swaps, accepted 2, and found no improvement on the best graph. Search-score numbers are **computed**, and the selected candidate is independently checked by a stdlib-only BFS verifier; the entire bounded exhaustive search is replayed in `reproduce.py` rather than represented as a theorem about all graphs.

The best 72-vertex candidate has **108 edges, maximum degree 3, diameter 6, and 34 unordered pairs with shortest-path distance 6**. It **fails** the accepted record test. In particular, the best three-edge and triangle minima are not claims about other methods, structures, experts, or the full mathematical search space. More capable algebraic, SAT/CP, voltage-lift, genetic or global graph search may succeed.

## Reproduce the precise claim

All source and tests are included and use no paid API, hosted model, third-party Python package or financial service. `g++` (C++17) and Python 3.11+ are required.

```sh
cd research/omega_degree_diameter
python3 -m unittest -v test_research.py
python3 reproduce.py --output-dir /tmp/omega-dd-replay
python3 -S verify.py --graph best72.json --report-only
```

The exact replay compiles `search.cpp`, performs every registered local extension and bounded local search with the fixed seed, compares results and the complete retained graph to saved outputs, and issues a separate Python verdict. It rejects malformed loops, duplicates, asymmetry and overdegree; a candidate that misses diameter 5 fails strict verification. `run-exhaustive.json` preserves the actual original run including non-reproducible wall-clock timing, and `best72.json` preserves the actual best candidate. Hosted CI is source-bound and must pass before declaring a repository-qualified replay.

## Institutional lessons and next gate

This investigation used structural inheritance from the *strongest real incumbent*; adversarial checking of benchmark definitions; multiple genuinely different construction topologies; an objective transformation from arbitrary graph improvement to a hard diametric certificate; independent BFS measurement; preserved failing evidence; and an explicit decision not to report success or economics without it.

**But the Eight Fundamental Mechanisms have not demonstrated an advantage over a specialist or a leading AI mathematician.** A new institutional capability would be an accepted record **and** a fair comparison of full discovery cost against strong outside techniques. A genuine compounding claim would additionally require a different fresh problem improved by an inherited, independently verified capability.

Next: attempt structurally different, unrestricted constructions beyond these local extensions. A SAT/CP-SAT encoding or graph-lift search with a published strong domain control is a plausible follow-on, but is not reported as executed here. An expert review of the incumbent, construction enumeration and source provenance would strengthen external confidence. Existing Blue Sky 064 scientific and commercial candidates remain HOLD; this scoped mathematical attempt does **not** replace them.

See [institutional mission #395](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/395). The failed candidate is evidence, not a flagship.
