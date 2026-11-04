# Measured numerical renewal — prospective protocol

This is a bounded supporting experiment for SUCCESSOR Omega, not a new Blue Sky flagship or a claim of autonomous invention. The question is whether an implemented renewal mechanism can avoid numerical reconstruction work while preserving a separately checked computational outcome. No favorable renewal price is supplied.

## Data and role

Use MATPOWER 8.1, commit `1a828c7af590714499284e36ee9c81273388c594`: `case89pegase` for development; `case1354pegase` and `case2869pegase` for the registered evaluation. These are public, fictitious engineering test networks, explicitly not operational European-grid data. Preserve the upstream CC-BY-4.0 attribution, URLs and SHA-256 hashes. Do not commit raw datasets; retrieve transiently and bind their hashes. No actual grid, buyer, account or physical apparatus is accessed.

The outcome is the solution and branch-flow calculation of the stated DC linear model, not AC validity, physical safety, operator acceptance, commercial demand, or complete-cost profit.

## Construction and comparisons

Implement a change-to-renewal compiler. From two versioned case representations it identifies changed line coefficients, right-hand-side changes and structural changes, builds a low-rank update when applicable, otherwise rebuilds, and checks the newly computed result. Use established Sherman-Morrison-Woodbury algebra with attribution; do not call this a new numerical algorithm.

Compare (A) competent sparse refactorization with exact same-matrix factor reuse, (B) ordinary low-rank engineering with the same information, base factorization and numerical permissions, and (C) the compiler with context/difference checks and residual verification. B must not be denied reuse. Also record an unconditional rebuild control, but do not headline gains against it as superiority over B. The retained factorization is charged at preparation; renewed results are checked in the new numerical context. Historical qualification and real operating authority do not travel.

## Fixed cases and measurement

On each evaluation network create deterministic, independently baseline-relative changes: unchanged model; right-hand-side load change; one coefficient change; eight coefficient changes; 32 coefficient changes; transformer-ratio change; phase-shift change; and a changed numerical context requiring reconstruction. Use seed 20261103. Each coefficient change multiplies the existing nonzero reactance by 1.10 or 0.90 in alternating order. The automatic low-rank route is capped at 8 changed coefficients for this finite prototype; larger changes rebuild. This is an implementation choice, not a physical or business limit.

Measure parsing, assembly, initial factorization, change analysis, solving, current residual checking, and end-to-end renewal separately. Run 21 timing repetitions in deterministically shuffled arm order after one warm-up. Preserve all timings; report medians, not just the fastest run. Record CPU and wall time, environment, source hashes and operation counts. A publication replay may use a different environment; timing equality is not expected.

Compute an independently assembled direct reference and check normalized residual and solution agreement under a fixed 1e-8 tolerance. This is a numerical tolerance, not a guarantee of physical accuracy. Invalid inputs and failed checks must not be promoted. Include local regressions for stale context, mutation, singular inputs, unsupported changes and failed qualification.

## Successor task and scope

Construct a second output class: a multi-right-hand-side response/sensitivity calculation using the retained linear-system instrument, including new loads not present in the first solve. Compare fresh factorization, ordinary equally equipped reuse and compiler reuse; account for shared preparation and new adapter execution. This tests an executable reuse relationship, not autonomous discovery of the adapter or improvement of the invention process.

The implementation and all mappings are AI-assisted author construction in this session. They are not an independently controlled autonomous discovery campaign. No model inference cost is fabricated; unmeasured authoring/inference, integration and long-run maintenance costs remain explicitly unknown. Computational savings must not be converted into invented dollars or claimed complete lifecycle profit.

## Stopping and adverse results

Complete the two-network registered matrix and the successor comparison, preserve every failed or slower case, and stop. Debug implementation defects using the development case and retain consequential corrections. Do not tune to the evaluation timings, substitute easier networks or change the success threshold after observing results. A conventional tie or compiler overhead is a valid result. Independent-checker agreement is internal computational cross-checking, not external peer review.
