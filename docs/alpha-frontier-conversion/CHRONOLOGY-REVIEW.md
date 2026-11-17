# FRONTIER Ω → ALPHA chronological provenance review (frozen before tests)

**Review owner:** independent, nonfinancial; **reviewed exact source:** `fcbc6961321ee67a72ba69276b4b37bcccaeba8a` (PR #423), based on the existing PR #419 and PR #422 owners. This branch is dependent on PR #423, not an alternative integration owner. Preserve all earlier failed traces and financial authority unchanged.

## Source-inspection finding and prospective predictions

`Reservoir.compare` checks ordered capability-observation days, and `frontier_bridge.admission_preflight` replays exact instruments and signatures. Neither verifies that a registered trial's `run_on` could chronologically follow its own frontier observation, nor that a trial recorded for a future day is usable to approve a request *now*. A locally signed buyer request and source-hashed authored trial do not make an impossible trial date genuine evidence.

Freeze **two deterministic negative cases** using the existing `ConversionTests` setup, matching native buyer contract, costs, ordinary control, host checker, current and historical instruments and no external service:
1. Current capability is observed on 2026-11-09, but its otherwise passing registered trial says `run_on=2026-11-08`; historical trial says `run_on=2026-11-16`. The preflight must refuse it with `TRIAL_CHRONOLOGY`.
2. Both trials are given `run_on=2099-01-01`; the simulated request is evaluated at existing fixture `now` in November 2026. A future-dated execution record must not qualify present intake.

**Positive controls:** retain all existing owner tests, existing same-day matched retrospective replay, buyer signing, host evaluator, full cost envelope, no new account, and unchanged historical/strong ordinary comparison. Same-day retrospective old-method replay is allowed (old method may be rerun later); there is no new requirement that the historical replay happen before the next frontier announcement.

**Prospective correction only after observing red:** check `before.observed_on <= old.run_on <= submit_day` and `after.observed_on <= new.run_on <= submit_day` inside preflight before intake intent creation. This rejects time contradictions but cannot prove model provenance or that the recorded replay really happened on the stated day. No change to native finance, payment, signing, historical immutable trial records, or ledger. Preserve the original red result and run exact-head positive/negative CI separately; do not describe a passing test as actual customer evidence.

**Acceptance:** two registered regression failures on unrepaired source, corrected exact-head positive and negative tests through source-matched hosted CI, no altered incumbent, and independent handoff to PR #423 owner. Full branch CI and actual released-byte operation are distinct gates. No synthetic profit or model billing claim.
