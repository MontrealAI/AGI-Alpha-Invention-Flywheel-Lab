# Ω 072 — one distinct global graph construction, executed and independently rejected

**Verdict: HOLD_NO_RECORD.** The intended new record would be a connected simple cubic graph on 72 vertices with diameter at most 5; the strongest published incumbent remains 70 vertices (Alegre–Fiol–Yebra, 1986). This attempt produced a *valid 72-vertex cubic graph of diameter 7*, with **115 unordered vertex pairs** at distances greater than 5. Neither a new mathematical record nor an economic product was created.

The experiment was prospectively frozen in [PROTOCOL.md](PROTOCOL.md) at commit `9cfb11756ee05f4b9731e668355e44dff3410c53`, before any candidate evaluation. New source-only route: global **2-sheet signed voltage lifts** of random 36-vertex cubic bases, with both voltage-flip and base-edge-switch moves. This differs from [PR #401](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/401)'s 676,270 local transformations of the published 70-vertex graph. It is not a claim of an unconstrained/global optimum over graphs.

Eight registered independent seeds, each exactly 25,000 proposals, completed: **200,000 proposed transitions total**. All invalid proposals were counted, and no favorable-seed resampling or post-outcome horizon extension was performed. The per-seed best violations were 132, 125, 129, **115**, 119, 149, 148 and 120. The best witness was proposed at step 24,325 under seed 2026111604. A separate standard-library Python full all-pairs BFS verified graph simplicity, cubic degrees, connectivity, actual diameter 7 and the failing 115-pair count. Five adversarial unit tests passed. The retained actual complete eight-seed record and graph are [RUN.json](RUN.json); independent witness verdict is [VERDICT.json](VERDICT.json).

## Reproduce

On a POSIX machine with C++17 g++ and Python 3.11+, from the repository root:

```sh
cd research/omega_voltage_lift_072
python3 -m unittest -v test_research.py
g++ -O3 -std=c++17 -Wall -Wextra search.cpp -o /tmp/omega72-search
/tmp/omega72-search /tmp/omega72-run.json
python3 -S verify.py --input /tmp/omega72-run.json --output /tmp/omega72-verdict.json
cmp RUN.json /tmp/omega72-run.json
cmp VERDICT.json /tmp/omega72-verdict.json
```

The source-matched GitHub Actions workflow uses standard no-fee public-repository compute and preserves all job outcomes. A successful CI is an *engineering reproduction*, not a mathematical discovery. Historical negative cases in PR #401 and the original graph remain unchanged. Do not conflate 115 violating pairs here and 34 in another restricted family with a lower bound on arbitrary cubic graphs: neither search proves nonexistence of a 72/5 graph.

## Evidence, alternatives and cost

- Independent maintained graph table [Comellas (updated 14 November 2026)](https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/desc_g5.html) and [published 70-node adjacency](https://web.mat.upc.edu/francesc.comellas/delta-d/desc_g/adjacencies/adjD5/AlFiYe70_Z_adjlist.txt).
- Source search SHA-256 `fc66f0a56ae680aac08e27637d10653c3267ec29a94dcc312577968f2260651a`; saved run SHA-256 `b61452febd5e8393b2987fd9aed595120ae322f87f6df0d33ef1c814e9f3e1c7`. These hash the published executable and recorded local witness bytes, not external web resources.
- Local complete search measured **4.15 seconds of user CPU, 4.16 seconds wall**, about 1,664 KB maximum resident memory for the search process. The independent tests and developer preparation add overhead. GitHub resources require separate receipts; actual monetary host/model billing remains **unknown**, not zero.
- The registered opportunity screen also considered (1) buyer-accepted paid commissioning, (2) measured EIT imaging, and (3) nonentry. Neither commercial route currently had a verified beneficiary residual or admissible buyer consent, so this scoped research route was chosen. No new spending, buyers, delivery, finance, deployment or authentic native account operations occurred.
- Claimed scope is a **finite search in one restricted family**. The strongest specialist SAT/CP and group-theoretic methods remain outside the comparison. This cannot establish autonomous improvement over experts or a causal fresh successor, let alone trailing-year profit.

**Tried → outcome → lesson → next:** Fixed-seed random base-graph 2-lift annealing → best diameter 7, 115 violating pairs → local voltage/base switches in this registration did not remove the global diameter obstruction → retain source and negative witness; pursue materially different specialist-grade global constructions or stronger evidence of a commercially meaningful residual. **NO CLAIM / NO DEPLOY.** Reuse only as an applicability-bounded research control, never as financial operating authority.
