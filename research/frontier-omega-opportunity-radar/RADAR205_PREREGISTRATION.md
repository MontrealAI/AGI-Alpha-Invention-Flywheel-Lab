# RADAR205 — intraday provenance and temporal eligibility (frozen before implementation)

Date: 2026-11-20 UTC. Research-only, dependent on PR #503 at exact source `9a0aef11e2f2d7449a4d5fd6fc7919d0db5bdbd1`. Its original owner remains responsible for PR #503 and any production integration. This is a separate review branch, not a cutover or a financial/native-account change.

## Falsifiable failure hypothesis

`frontier_radar.core.atlas_at()` and `core.assess()` use calendar-date comparison for source and record availability. The owner atlas has day-only `announced_at` and `sources[].date` claims; its current Opportunity cards have day-only `as_of` and `sources[].date`. A Friday 08:00 America/Toronto historical briefing can therefore include events whose available date is Friday even when the moment of publication cannot be established before briefing time. The same risk affects `assess()` and alert generation. Passing a suite that checks dates, but not intraday cutoffs, does not eliminate this look-ahead.

## Fixed acceptance before code

1. For any **day-only** evidence/research record dated 2026-11-20, at 2026-11-20T13:00:00Z (08:00 EST) the record is **not known eligible** and cannot appear in the briefing or trigger an alert. It becomes eligible only at or after 2026-11-21T00:00:00Z. This is a conservative information boundary, not a claim the event actually happened at midnight.
2. If `announced_at_instant`, `as_of_instant`, or source `available_at` is explicitly present, it must contain a timezone-aware ISO instant matching the declared date in UTC and must be <= the exact cutoff. A timestamp matching the date and earlier than the cutoff may make a record eligible during that same day. A timestamp after cutoff, timezone-naive, malformed, or incompatible with the declared UTC date is ineligible; do not fall back to calendar-date eligibility.
3. A record with multiple sources is available only when **every** required source is eligible. Unavailable atlas entries and opportunity records never appear as positive recommendations or alerts. Failed evidence remains recorded, not relabeled. At 2026-11-20T13:00:00Z, historical replay must not count later same-date events as visible. Same-day independent evidence remains unknown unless timestamped.
4. Preserve current exact-date historical replay semantics, no future-leakage, no duplicate alerts, and the current owner corpus. Keep the cutoff aware; tests must cover UTC vs Toronto crossover and a positive timestamped control, not merely rejection.
5. Do not modify upstream PR #503, its recorded results, live Friday alert automations, other owners, main, release, financial accounts or private artifacts. No real buyer/revenue/profit claim. If the regression cannot be reproduced, retain the negative finding and do not silently manufacture a fix.

### Scope

Deliver source-only correction plus focused adversarial regression tests on a dependent PR. Validate locally if possible, then verify exact-head GitHub workflows. A genuine test failure remains a failure until a prospective corrected run. The source is a *review candidate*; deploy or main merge is a separate owner decision.
