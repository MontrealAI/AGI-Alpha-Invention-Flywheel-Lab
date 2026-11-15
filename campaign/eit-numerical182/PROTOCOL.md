# EIT182 — source-precision decision guard (frozen after observed failure, before repair)

Date: 2026-11-15 UTC. Exact parent: `c1227fb33581f0d0a7947d787f02f573fb89b082` (EIT181 draft PR381).
Scope: narrow, additive corrective branch. This is **not** a fresh scientific confirmation or a renewed physical-source experiment.

## Original observed failure (immutable)

GitHub Actions run [43762772669](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/43762772669), job 132961047957, is **FAILED**: the root test suite ran 2,575 tests; exactly two EIT180 tests failed (`test_02_global_gain_is_a_strong_ordinary_control` and `test_03_global_offset_affine_ordinary_can_win`). They expected `REJECT_INCREMENTAL_STRUCTURE`, but source returned `CONDITIONAL_REPEAT_STRUCTURE_ONLY`. Do not relabel or rerun that workflow for a favorable history. The original EIT177 invalid-MAT failure and all earlier evidence remain unchanged.

## Diagnosis and target invariant

A residual from the best competent ordinary global fit at floating-point roundoff (near machine epsilon of measured voltage amplitude) must **not** be interpreted as ≥10% scientifically consequential incremental channel structure, even if per-column affine has a slightly smaller rounding error. The original percentage calculation divides two nearly zero errors. Keep true nonzero channel-structured synthetic signal and numerical decisions for the actual physical source unchanged unless explicitly demonstrated by a separate, frozen, source-bound experiment.

Implement one local, unit-aware, scale-relative machine-precision eligibility gate for the EIT180 *decision only*: for finite 2-D voltage arrays, compute a tolerance of 64 × IEEE-754 double epsilon × maximum absolute first/second holdout amplitude. If the best ordinary heldout RMS is at/below the tolerance, `CONDITIONAL_REPEAT_STRUCTURE_ONLY` must never be issued, even if the percentage difference exceeds 10%. Report the tolerance and suppression as diagnostic fields. Keep existing true-signal improvement threshold (10%), per-column no-more-than-double-identity rule, prior model definitions, train/holdout split, source/protocol bindings, finance code and all original tests unchanged.

## Fixed qualification and rejection cases

1. 1.7× global gain and 1.3×+7 global affine (the exact failed original fixtures) reject incremental structure, with roundoff-eligible gate asserted.
2. The same gain-only example at factors 1e-9 and 1e9 rejects without a hardcoded absolute error threshold; no downloaded measurement required.
3. Nontrivial distinct per-channel gain+offset remains conditional when its heldout advantage is genuine and larger than the precision floor.
4. The existing EIT180 14 controls and EIT181 15 controls continue passing; retain the genuine failed run.
5. No change to original physical EIT180/EIT181 result receipts, no third public dataset download, no changed failure status and no new financial execution.

Run deterministic local controls and hosted exact-head applicable CI, no automatic reruns to change outcomes. All real physical, reconstruction, clinical, buyer and commercial qualification remains unestablished; no original account, signing authority, keys or obligations may be touched.

## Resources and stopping rule

Use standard public-repository CI (ubuntu-latest, mandatory first-start marker, 360-minute platform timeout, no paid APIs or custom runners). One corrective candidate, no after-the-fact threshold search. Stop this repair if it fails the fixed tests; preserve failure and investigate independently before altering the proposed guard. Historical failures and owner boundaries remain intact.
