# Retained Game Theory mechanism · Break-even observation fees

The new instrument computes the largest one-time fee a decision maker can pay for a private noisy observation while preserving a better worst-case payoff than the optimized no-observation policy. Both tested implementations returned equivalent fee decisions on all three new declared games and all 15 quoted prices. Reuse of the retained sparse solver met the registered runtime threshold in two cases. The ordinary explicit method was faster on the smallest case.

## Scope and comparison

The decision maker commits to one specified observation or the strongest blind alternative before the opponent reacts. The opponent can respond to the chosen instrument. The signal drawn remains private. The calculation subtracts the fixed observation fee from the forced-acquisition minimax value. It bounds the break-even fee by subtracting the endpoints of the exact no-observation and zero-fee observation intervals in opposite directions. The result is stated in the same synthetic payoff units as the lane weights. It assumes a one-time fixed fee and a fixed channel.

The retained arm called the exact previously qualified sparse path-flow solver. The competent conventional arm enumerated the entire normal-form payoff matrix from exact channel weights, used a conventional HiGHS primal program and recovered opponent probabilities from its dual multipliers. Both arms produced feasible rounded strategies and exact certificates. A separate all-action verifier independently recomputed the first certificate for each forced subgame in both arms. The experiment author selected its three transparent cases before computation and used the separately developed verifier. [Frozen protocol](PLAN.json) · [Exact source and input registration](REGISTRATION.json)

Seven repetitions allocated the same contract to each arm, with alternating order. The timing includes two optimizations and exact verification for each fee result. The retained constructor also checks its own certificate during the solve, so the common verification is an additional check within its observed time. Wall times cover process-local work and include the first optimizer initialization in the initial recorded sample. [Run and certificates](RESULT.json)

| New declared game | Certified retained break-even fee interval | Sparse nonzeros | Normal-form payoff entries | Median retained / ordinary wall |
| --- | --- | --- | --- | --- |
| Opposed two-lane | [2.25, 2.25] | 165 | 24 | 5.47 / 3.63 ms |
| Three warehouse states | [0.0272727185, 0.0272727340] | 938 | 31,310 | 11.30 / 20.79 ms |
| Overlapping probe | [0.0760223258, 0.0760223540] | 1,628 | 139,860 | 26.74 / 102.92 ms |

Sparse coefficients and explicit matrix entries are descriptive counts across both subproblems. They account for different representations. Both implementations accepted all cases in every registered repetition. The declared gate required at least 20% lower retained median wall time on at least two of three cases. The retained arm met it on two cases. It was about 51% slower on the opposed two-lane case, so retain the conventional route for small explicit work.

Removing the retained optimizer and using the conventional arm preserved all accepted outcomes. Removal of the observation itself leaves two copies of the optimized blind game. The break-even threshold in that ablation is exactly zero. The 0-unit quote was below all three observed thresholds. The three positive quotes of 0.5, 1 and 2 were below threshold in the first game and above it in the other two. All three decisions skipped the 3-unit quote. Replication should compare exact intervals and pricing outcomes, with timings expected to vary by host and load.

## Reproduction

Use the same repository layout, Python 3.12, NumPy 2.3.5 and SciPy 1.17.0. Choose a fresh output path.

~~~sh
cd publication/mission-executor/transfer
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 run_transfer.py --output transfer-replay.json
~~~

Registration SHA-256 is `95a81b6e3224ad9f0e0206b23a7c1e703a929c61c25a823dd954150b9ffb58fe`. The recorded first-run result SHA-256 is `b632cd997a9ca3a0bd19969b59bac92eac4bfeafdb1f079cf7eca6289340936a`.

**GO** for converting the retained mechanism into a new verified fee decision on the declared synthetic contracts. The timing comparison supports bounded computation transfer. Complete construction cost, actual adoption, economic return, and improved ability to invent a later mechanism remain unmeasured.

### Supplementary implicit comparator

A separately registered sensitivity run reused these three cases to compare sparse execution with double oracle. Both methods delivered overlapping exact intervals and all matching quote decisions. Over five paired repeats, median sparse / double-oracle times were **7.80 / 7.59 ms**, **14.05 / 55.67 ms**, and **24.77 / 118.53 ms**. The ordinary explicit method remains the strongest measured small-case route. The supplementary run used the same synthetic cases and shared the exact verifier. The original timing verdict therefore remains a bounded computation comparison. [Supplementary freeze](ORACLE-REGISTRATION.json) · [Supplementary run](ORACLE-RESULT.json)
