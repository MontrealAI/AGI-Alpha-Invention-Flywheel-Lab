# Blue Sky 192 — repair within-world target semantics (prospective test freeze, 16 November 2026)

**Source parent:** exact dependent Blue Sky 191 head `f690c810f05ba13341e6d3ee0fce78ee3dcf5d72` (draft PR #391), itself based on main `11f72c9411bb8b51b1a2b1890c9d52b74a4c40b4`. This is a separate review branch, not a mutation or acceptance of PR #391, financial owner PR #40, native keys/accounts, physical instrument, or published release. Read repository instructions before implementation. Preserve all original CI failures and all exposed source inputs.

## Adversarial scientific question

Blue Sky 191's `toy_contrast()` currently computes `ratio(world1, A=B=1)/ratio(world0, A=B=1)-1`, labeling it an 8.333% **load-selective** response. However that quotient compares **two different physical coefficient worlds at the same geometry**. It is not the registered success criterion: a >=5% increase in static/dynamic friction **within the same world** when the contact state changes with indentation. The result can be numerically identical while its causal semantics are wrong. This is a source-review hypothesis observed before freezing, not a prospectively discovered issue.

## Fixed finite falsifier and constructive correction

Keep the two original synthetic worlds and same six-parameter nonnegative interaction grammar: world0=(2,4,0,1,2,0); world1=(2,4,1,1,2,0). Both give identical predictions for all pure-family measurements. Declare exactly two **hypothetical contact states**: LOW (A=1,B=0), HIGH (A=1,B=1). LOW is pure A; HIGH engages both families. These are conceptual rational areas and NOT the measured contact areas, exact registered 0.01/0.10 mm height geometry, or physical transfer evidence.

Compute `R(world, state) = F_s(world,state)/F_d(world,state)` and `improvement(world) = R(world,HIGH)/R(world,LOW)-1` **within one world**. Fixed expected exact results:
- world0 LOW=2 HIGH=2, improvement 0: 5% target FAIL.
- world1 LOW=2 HIGH=13/6, improvement 1/12: 5% target PASS.
- For either world, LOW=HIGH as the same single contact state has zero improvement. A pure across-world numerator at fixed contact state is not a valid target evaluation.

Freeze one no-change adversarial predicate plus the positive contrast. First commit tests against original implementation (record failing workflow, if executed); then repair only the isolated research code, without changing original threshold or source rows. Keep old result fields backwards compatible, but add explicit geometry/state and within-world verdicts so downstream readers cannot misinterpret. Preserve all original 15 Blue Sky 191 tests unchanged. New source checks must reject zero dynamic denominator and no-operating-change claims. Use exact Fraction arithmetic. The complete branch shall pass both old and new tests with an independently derived source-level arithmetic check; original failure stays failed. A source-bound GitHub Actions workflow records exact head and outputs compact JSON, with bounded current platform time. Standard free hosted runner only; no paid models/keys.

## Comparators, decision and stop

A: repeat pure-contact calibration only; B: hypothetical mixed-surface construction with paired LOW/HIGH states and independent withheld future load/velocity/wear measurements; C: strongest competent existing passive clutch and active control with their real complete costs; D: no deployment. This test proves only logical underidentification and the correctly formulated **synthetic** target split. Real mixed-surface physical transfer, measured operating-state areas, safety, counterpart consent, costs, capacity, rights, full finance and original-account migration remain unknown. Result always HOLD/NO BID/NO DEPLOY, including if all tests pass; no claim of a 5% measured improvement, new industry, better inventor, paid commerce or US$3B trailing-365 profit. Existing operator/main and other owners remain intact. Do not optimize seeds, tune hypothetical contact states after seeing results, or weaken the fixed threshold.
