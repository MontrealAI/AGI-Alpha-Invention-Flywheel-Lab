# HARNESS132 — duplicate-verdict provenance falsifier (registered before source repair)

**Frozen base:** draft PR #330 exact head `537dd4814bd9c3b0aaf6d0e021d786d6bb009dae`; this is a stacked, separately owned review, not a new customer release or a direct edit to the PR #330 owner's branch. Current main at registration: `1d64b69dcadb494d60f666c635fbecf74ebeeefc`.

**Observed original behavior:** `module_passed` in the frozen source treats the exact excluded G1 skip as dispensable and checks that the remaining lines end in `... ok`. It accepts a log with (a) the exception recorded as both skipped and passed for the *same test identity*, or (b) any other test identity recorded as passed twice. A single captured unittest run cannot support both verdicts or duplicate one identity; treating either as positive evidence overstates what the retained log establishes. This is a **log reconciliation integrity** issue, not a demonstration of a forged external workflow or account compromise.

**Registered tests before implementation:**
1. An unrelated passing G1 test followed by the one allowed skip and a conflicting PASS of that same excluded identity must fail.
2. Two PASS records for one ordinary `test_bridge` identity must fail (G1 and default module checks).
3. One ordinary PASS plus exactly one permitted documented G1 skip must pass in the G1 scope, but not in another criterion or without G1 scope.

**Allowed prospective fix:** In the narrow existing `module_passed` parser, detect repeated full unittest method identities before applying the one G1 exemption; reject duplicates; retain existing strict skip identity/reason, all other failures, source/archive bindings, canonical account logic and commercial eligibility gates. Add adversarial tests without relaxing earlier assertions. No test-run or source-hash rewriting.

**Evidence policy:** Historical PR330 and release statuses are unchanged. Local pre-fix counterexamples return `True` for both negative cases. The new code must make all registered negatives fail closed and preserve the positive, followed by exact-head GitHub Actions qualification; the fixed result does not prove storefront readiness, authenticated providers, demand, profit or a new productive invention.

**Decision:** additive review for PR330 owner's consideration; do not merge stacked review wholesale into main or claim a new release before owner-safe composition and protected workflow qualification.
