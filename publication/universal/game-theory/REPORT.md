# Game Theory mission · Strategic allocation with hidden payoff scenarios

The executed ambition was **Build Frontier AI for Game Theory.** This first mission constructed, exercised and retained a local research solver for a class of zero-sum strategic-allocation games. Included Codex carried out the research and construction. The workbench can return this recorded assisted mission and its executable result with the original ambition intact.

## Research choice

| Direction investigated | Evaluation and choice |
| --- | --- |
| Imperfect-information extensive games | Sequence form represents games with perfect recall compactly. This is an appropriate direction for a rule-complete extensive game with many dependent choices. [Koller, Megiddo and von Stengel](https://doi.org/10.1006/game.1996.0051) |
| Best-response-driven equilibrium | A double oracle can solve implicit games by computing one best response for each player and solving restricted games. It has strong practical uses and known worst-case limitations. It serves here as an executed comparator. [Adam et al.](https://doi.org/10.1609/aaai.v35i6.16641) · [Zhang and Sandholm](https://doi.org/10.24963/ijcai.2024/336) |
| Structured resource allocation with hidden payoffs | Exact integer actions and separable payoff structure let us pose an independently checkable question with many implicit pure profiles. This was the selected working scope. [Ahmadinejad et al.](https://doi.org/10.1287/moor.2018.0971) · [Behnezhad et al.](https://doi.org/10.1609/AAAI.V31I1.10620) |

## Model and implementation

The row actor distributes a fixed integer budget across lanes. The adversary selects one of the declared payoff scenarios together with a feasible allocation for its scenario-specific budget. It may choose its strategy after learning the row distribution, while the actual row sample remains private. The payoff is the sum of each scenario's lane weight times the sign of the difference between the two allocated amounts. Both actors use the same payoff units within the declared game. Equal allocations contribute zero.

The solver creates a unit flow on an acyclic graph of lane index and cumulative resource use. Each feasible allocation is a path. Cumulative probability by lane gives the expected local payoff for each opposing choice using at most two cumulative mass coefficients. Each scenario has shortest-path potential inequalities. The common value must be at most each scenario's terminal potential. The sparse HiGHS IPM program produces a row flow. Its inequality multipliers recover a joint distribution over adversary scenarios and their flows. [Construction code](solve.py)

The constructor rounds to a conserved integer flow, then exports explicit probability mass on paths with a common denominator of one billion. The separate Python standard-library verifier checks game and policy contracts, reconstructs exact lane masses, and searches every feasible pure deviation by integer budget dynamic programming. The minimum against the row mix is an exact lower bound and the maximum against the adversary mix is an exact upper bound. Every mixed deviation is a weighted average of pure ones. Thus the two bounds enclose the true value of the declared game. The verifier admits narrow certificates within one part per million of the largest scenario weight total, with a scale floor of one. An LP status alone supplies no acceptance. [Verifier](verify.py) · [Frozen benchmark plan](BENCHMARK-PLAN.json)

Flow-graph size is polynomial in the numerical budgets, making it pseudo-polynomial in the binary-encoded inputs. Both the solver and the verifier rely on additive lane payoffs and exact finite integer budgets. The model represents worst-case scenarios and does not infer the scenario distribution from data. Scenario weights, application fit, and real-world payoffs require separate evidence.

## Executed example and development checks

The [two-lane example](EXAMPLE.json) assigns one credit. The hidden scenario controls which lane carries 100 of the 101 payoff points. A common equiprobable policy proves both value bounds at **−49.5**. Optimizing for one nominal scenario commits entirely to its preferred lane and gives **−99** when evaluated against the other scenario. A policy with foreknowledge of the scenario would attain **0**. This difference is a consequence of the tested information structure. [Portable certificate](EXAMPLE-CERTIFICATE.json) · [Standalone verification](EXAMPLE-VERIFICATION.json)

An exhaustive development check compared reported bounds to direct payoff enumeration on 30 small generated games. All 60 candidate and explicit-matrix computations matched the exact recomputation across 4,982 enumerated action pairs. Their accuracy scope is the generated development set. [Development checks](DEVELOPMENT-CHECKS.json)

| Development model | Pure action pairs | Sparse LP median seconds | Explicit HiGHS median seconds | Double oracle median seconds |
| --- | ---: | ---: | ---: | ---: |
| Four lanes with two scenarios | 6,664 | 0.0122 | 0.0075 | 0.0352 |
| Single-lane zero-budget edge | 2 | 0.0028 | 0.0023 | 0.0028 |
| Seven lanes with three scenarios | 38,996,734,623 | 0.2649 | Outside registered explicit matrix budget | 0.4544 |

Development timings are medians over three warm-process trials with alternating arm order. They include model preparation, optimizer and verifier. The actual sparse program on the seven-lane case used 12,653 nonzero coefficients. An earlier development formulation took 2.886 seconds there. Cumulative mass and IPM reduced measured development time and were frozen before the independent inputs were disclosed. Both qualifying methods are worth retaining. The explicit method was faster on the four-lane case. These measurements support no general latency claim. [Development performance](DEVELOPMENT-PERFORMANCE.json)

## Independently authored held games

A separate Codex evaluator froze six inputs at 01:34:24 UTC on 25 November 2026. The candidate and comparison plan were frozen at 01:37:14 UTC. The evaluator copied and checked their exact hashes, ran the submitted source on the concealed games, and independently enumerated all pure deviations with rational arithmetic. The candidate path and the independent path use different code and different best-response algorithms. The evaluator's explicit-matrix minimax was a separate formulation using the same HiGHS optimizer family. The separate context ran in the same authorized workspace. [Frozen held games](../evaluator/held-games.json) · [Independent code](../evaluator/verify-game.py) · [Independent report](../evaluator/game-run-v1/INDEPENDENT-REPORT.json)

| Held game | Implicit action pairs | Candidate interval width | Candidate | Explicit HiGHS | Double oracle |
| --- | ---: | ---: | --- | --- | --- |
| Single lane | 3 | 0 | Pass | Pass | Pass |
| Zero-value lanes | 21 | 0 | Pass | Pass | Pass |
| Asymmetric budgets | 1,960 | 0.000000003 | Pass | Pass | Pass |
| Shared policy | 50,880 | 0.000000023 | Pass | Pass | Pass |
| Distinct scenario budgets | 9,520 | 0 | Pass | Pass | Pass |
| Implicit scale | 211,775,256 | 0.000000055 | Pass | Outside registered matrix budget | Pass |

The evaluator's exact lower and upper bounds agreed with the submitted verifier for all 17 produced certificates. The separate full-matrix value agreed for all five materialized games. On the largest held game, the candidate's exact enclosure was **[−8.120545101, −8.120545046]** from an LP with 4,868 nonzero coefficients. Double oracle also qualified in 69 iterations. Its startup-inclusive wall time there was 1.436 seconds versus 0.766 seconds for the candidate, in one local trial. The dense comparator was faster on the zero-value-lane case and double oracle was faster on the distinct-budget case. The preregistered 250,000-cell cutoff limited explicit-matrix execution. One malformed mass certificate was rejected by both verifiers. Both found a width of 24 and withheld qualification from a feasible but suboptimal pure policy. The exact cases, comparators, and timings can be replayed with Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. [Evaluator replay](../evaluator/run-held-games.py)

## Follow-on construction

An exploratory experiment after the held run used the retained solver as a component to design a one-bit disclosure. It evaluated all three partitions of the `shared-policy` game's scenarios. Conditional strategies maximize the worst case within the observed group. The best question, whether the scenario is `high-north`, raised the model's guaranteed payoff from about **−4.9693** to **−3.1349**, an improvement enclosed by **[1.834381564, 1.834381601]**. Complete disclosure would permit about **−2.7204**. All seven subgroup bounds were recomputed exactly with the evaluator's algorithm by the construction context, and all seven agreed with separate explicit-matrix minimax. This construction can rank truthful information designs within the declared model. Its guarantees assume accurate, costless disclosure. It leaves observation cost, real-life calibration and recursive improvement open. [Disclosure tool](information-value.py) · [Certificates and score](INFORMATION-VALUE.json) · [Replay checks](INFORMATION-VALUE-CHECKS.json)

## Retained capability

Three neutral local entry points construct a strategy, run a conventional comparison or replay its exact certificate. The verified bounds and witness allocations are portable. Saved certificate verification runs locally with Python's standard library. The scoped research solver and certificate verifier are **GO** for the tested zero-sum allocation model. General game-playing intelligence, superiority over all relevant solvers, commercial productivity, and recursive improvement are **NO-GO** as qualified claims. A later authorized decision could supply data for payoff calibration and predictive validation.
