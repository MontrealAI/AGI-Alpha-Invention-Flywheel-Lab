# Ω GLOBAL LIFT 072 — frozen finite research protocol

Frozen before executing the new construction/search or inspecting candidate outcomes.
Date: 2026-11-16 UTC. Parent `main`: `172ea7a9b96ad123a879dde76101b944aa9cf131`.
Independent research-only branch, **not** financial owner PR #40, commercial integration, nor continuation of PR #401's incumbent-local search.

## Opportunity selection, comparable alternatives, and no-deploy

Considered (A) a verified complete commercial commission with actual dated buyer acceptance (currently no public consent or measurable willingness to pay; HOLD), (B) measured moderate-contrast EIT imaging intervention with reproduced strong conventional reconstructions (physical open dataset announced but no proven residual or authorized deployment; HOLD), (C) an independently checkable **new cubic graph of order 72 and diameter ≤5**, which would exceed the maintained published order-70 incumbent in a mathematically unresolved graph-network-design problem (selected as a research experiment, **not as a paying service**), and (D) no discovery/no deployment (retain existing champion).
Strong control: the published 70-vertex, degree-3, diameter-5 graph; the prior independent PR #401 attempted 676,270 incumbent-derived local extensions and found no record. **This trial uses a different, global topology family**: signed 2-sheet lifts of freely generated 36-vertex cubic base graphs. No claim of exhaustive search over all 72-vertex graphs.
Useful beneficiary hypothesis: constrained-degree network topology with smaller worst-case hop counts; no buyer, physical network, application superiority or demand is asserted.

## Registration

- Exactly 8 distinct initial seeds: `[2026111601,2026111602,2026111603,2026111604,2026111605,2026111606,2026111607,2026111608]`.
- For each, generate a simple 36-vertex cubic graph by repeatedly shuffling 108 stubs with standard `std::mt19937_64` until a simple graph is obtained, then assign an independent random binary voltage to each of its 54 undirected edges.
- Run **25,000 proposals per seed**, no adaptive expansion or favorable-seed selection. Propose a binary voltage flip 50% of the time or a two-edge degree-preserving base switch with probability 50%. Reject loops, parallel edges and unrepresentable swaps without quietly adding replacements. The chosen adjacency and voltage update are simultaneous, and are reverted on rejection.
- Score each completed 72-vertex lift as unordered vertex pairs at shortest-path distance >5, including disconnected pairs. All vertices must have degree 3 in each tested lift. Simulated-annealing acceptance probability for `Δscore>0` is `exp(-Δscore / T)`, with deterministic `T = 60*(1-step/25000)+0.25`; always accept `Δscore≤0`. Retain global best, including a failing graph and every seed's best, independently from the incumbent.
- Hard success: **exactly 72 vertices, simple, cubic, connected, diameter ≤5** checked by an independently written pure-stdlib Python BFS from the saved graph. A score of zero computed by the search alone does not count.
- No claim of impossibility for 72, for nonlifted graphs, or even for other 2-lift choices. Do not silently change this registered search after seeing results. If source mistakes require correction, preserve the initial failure and publish a prospective correction with the same frozen seeds and acceptance.
- Preserve actual compilation, evaluation counts, timing and failures. Unmeasured model/host dollars remain unknown. No paid APIs, new credentials, accounts, keys, outreach, external transactions or production deployment.
- Public result must distinguish mathematical witness from scientific priority (check strongest **open** and merged claims), verification from economic usefulness, and any historical tests from fresh discovery.
- No native account or financial claim is made. Any future economic realization requires one authorized canonical JournalAccount/Account and complete-cost actual beneficiary evidence.

## Stopping rule

Stop after the eight fixed 25k-proposal sequences (200,000 total, including invalid proposals) or an unavoidable platform termination; interrupted work remains incomplete, never an automatic pass. Never restart solely to obtain a favorable candidate. Each proposal, failed or accepted, counts towards the fixed denominator. The program may log a qualifying graph but must finish the registered denominator before statistical summaries; qualification can independently verify that retained graph.

Next decision: `GO` only if independently verified 72/5 graph and prior art remains ≤70; otherwise `HOLD_NO_RECORD` and preserve the failed graph, computational cost and concise applicability lesson.
