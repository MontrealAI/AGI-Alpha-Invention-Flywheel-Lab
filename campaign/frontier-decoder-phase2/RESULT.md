# Phase-two terminal result: implementation works; hypothesis not supported

**Engineering PASS; frozen diagnostic NEGATIVE. Stop this branch; no tuning.**

[Executed workflow](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41357844990)
verified at source `d995dc430324ded6fd55767f3eff618c17698b1d`. This later
result-only commit does not claim a new executed source qualification.

## What actually ran
- Identical pinned Tesseract source/compiler/dependency lock, pristine then patched
  builds; all six new C++ candidate-list tests and three upstream regressions pass.
  The three upstream tests also pass on pristine. Binding checks and eleven
  cross-binary first-goal/max-goals=1 cases pass.
- Twenty fixed syndromes: **four development plus sixteen fresh**, not twenty
  fresh confirmation shots. All three matched arms complete every case:60calls.
- No timeout, worker error, fallback, search failure, invalid candidate or rejected
  completed shot in any arm. No truth enters policy and no postselection occurs.
- List mode returns64 distinct physical configurations on each shot (1280total),
  but **all20 pools contain exactly one logical class**. All stop at `goal_limit`.
  First-goal and final-minimum costs are identical; no prediction changes.
- Observed logical failures are0/20 in each arm. This tiny mixed development/fresh
  diagnostic establishes neither a precise error rate nor superiority.

| Arm | Median decode | Maximum decode | Candidates/shot |
|---|---:|---:|---:|
| A: pristine, residual pruning on |52.53ms|772.17ms|1|
| B: pristine, residual pruning off |52.15ms|1157.12ms|1|
| C: list mode, residual pruning off |141.21ms|1276.90ms|64|

C median first-goal time is53.71ms. C total pushes318960, pops132414,
expanded4409; maximum pushes51990. Actual baseline work counters are unknown.
Timing includes only reported scopes, not a hard-real-time or tail guarantee.
`actual_config.orders=20` describes precomputed detector orders; every registered
call explicitly invokes order0 only, with beam5,queue200000 and64goal limit.

Exact scientific stop: `finished_no_competing_classes_stop_branch`.
No larger list, altered beam, new seed, stronger noise or follow-on campaign was run.

## Failures, cost scope and coverage limits
The two local builds remain unexplained pre-compilation SIGKILL failures; they are
summarized in README, not relabeled as successes. First public attempt failed after
successful C++ tests because Python3.12 loaded a3.13-built extension; zero diagnostic
shots ran. [CI_ATTEMPT_1.json](CI_ATTEMPT_1.json) preserves that failure. The narrow
ABI repair aligned runtime with upstream3.13; no kernel/protocol tuning occurred.

The successful attempt spent639.21s in setup/build/tests (pristine build518.02s,
incremental modified build67.92s), separately from86.12s diagnostic elapsed time.
Failed first public setup/build/tests cost529.63s. These are measured wall scopes,
not total project costs; earlier local attempts and unmeasured engineering/model
costs are not erased or assumed zero. No paid runner/service or storage upload used.

Actual witness uniqueness and duplicate-DEM XOR aggregation tests pass, but the
`duplicate_goals` branch is **not exercised**: zero duplicates in toy and circuit
outputs. No full upstream test-suite, hardware or independent certification claim.
The pool is partial, not an exact coset partition function. This is supporting
frontier research, not an established industry flagship, newly economical useful
computation, consequential enabling cycle or profit result. Conditional commercial
simulation and real-world claims require separately stated assumptions/evidence.

## Retained lesson and evidence
Continuing one frontier can add many *same-class* configurations without
exposing logical competition. Retain the bounded instrument and its regression
checks; do not confuse candidate count with the missing logical-class diversity.

- [Compact diagnostic aggregates](RESULT.json)
- [Successful build and test receipt](CI_ATTEMPT_2.json)
- [Frozen protocol](FROZEN_PROTOCOL.md), unchanged hash690f67c6…

Only compact source/evidence is public. No binaries, shot archives, Actions
artifacts or cache uploads. No PR, merge, release, deployment or new experiment.
