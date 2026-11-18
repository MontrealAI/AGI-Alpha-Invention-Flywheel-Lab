# Frontier Ω watch-clock idempotence — preregistered test repair (18 November 2026 UTC)

**Base source and immutable historical negative:** dependent review PR #456 at `f69d8451c148f3db5d4c4ceb71bf57f12fb0d323`; whole-root campaign run [44275496362](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44275496362), job 134702435007, genuinely **FAILED** with 2,662 tests executed, 1 ERROR and 2 skipped. The error is `test_real_worker_receives_later_submitted_problem`, where the unmodified test calls `refresh('2026-11-17')` after the live worker has recorded the actual UTC date 2026-11-18. The durable clock correctly rejects a backward mutation (`REFRESH_CLOCK_REGRESSION_USE_READ_ONLY_PLAN`). The original result must stay failed.

**Constraint and scope.** Preserve the production clock-regression guard, source/event identity, original test's live subprocess and later-submitted inbox observation, research-task uniqueness, no-purchase restrictions, all financial source and state, earlier runs, original integration owner PR #429, all released bytes and task 01a18fa7-ffc6-7384-8bb4-ea6012cfb0f7. Make a dependent *draft* review, not an integration or release.

**Predeclared pass/fail checks (before code modification):**
1. Run the original real `watch --interval .1 --cycles 7` to completion and verify that a newly submitted synthetic public signal is ingested.
2. Read the durable `inventory_clock.as_of` actually written by that worker (not system-date guessing or a hardcoded prior day), and assert it is a valid ISO date no earlier than the synthetic event date; hold its value across fresh process reopening.
3. Calling `refresh(observed_clock)` on the same inventory must add **zero** research tasks and not reopen or supersede any task; independently compare the immutable queue (IDs, state, hash, note) before/after.
4. Calling `refresh(date strictly earlier than observed_clock)` must still raise exactly `REFRESH_CLOCK_REGRESSION_USE_READ_ONLY_PLAN`; this is an adversarial guard control, not a skip or a relaxed acceptance.
5. First qualify a focused prospective test on exact new source, then require the unchanged whole-root `python -m unittest discover -s tests -v` to pass in a GitHub hosted exact-head job. Preserve and report any remaining failed workflows. No random-seed changes or repeat-until-pass.
6. Compare the branch with the fixed base and refuse changes outside this test and evidence/protocol. Full 2662-test run's source and timestamp are required for any future clean-run claim.

**Interpretation.** This repairs a wall-clock-dependent *test harness* assumption, not the underlying live research economics, customer acceptance or a capability crossing. A green CI run is not a paid contract, P0 finance transition, normal merge, source-matched published release, or trailing-year profit.
