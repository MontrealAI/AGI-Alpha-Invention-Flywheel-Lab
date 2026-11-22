# PLATFORM-REPAIR234 — pre-change failure-bound repair protocol

## Immutable observed failure, 2026-11-22 UTC
Base: REGISTER-INTEROP233 PR #534 head `f93e8489f1448a513e617030b56ed2a0848e0a3c` (research branch; not main or released code). Current protected-source main: `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.

Two complete-suite GitHub Actions runs on PR #534 failed:
- Connected014 qualification #44988395781 (job 137103904746).
- Connected014 release qualification #44988395688 (job 137103904801).

Each independently executed the existing `tests/test_connected_platform_runtime064.py::CurrentWorkflowPlatformTests.test_all_current_jobs_use_the_public_standard_runner_and_platform_window`. Exactly two failing subtests: `.github/workflows/gc-ai-register231.yml` declares a 45-minute job window; `.github/workflows/registry-interop233.yml` declares 35 minutes. Required value is 360 minutes for all current standard hosted jobs. Both also omit the mandatory first job-start checkpoint step (verified from source); only the timeout assertion was reached in the observed historical failures. Historical fails remain historical fails.

## Frozen repair scope / boundaries
Change **only** these two workflow YAML files and this protocol. Keep the original source, tests, financial/runtime modules, experiment fixtures, observed government bytes, frozen preregistration and upstream PR #532/#534 branches unchanged. In each workflow, set `timeout-minutes: 360` and prepend a read-only first step that writes `AGI_JOB_START_EPOCH=$(date +%s)` to `$GITHUB_ENV`. Use `ubuntu-latest`, no custom or paid runners, no additional credentials, no source fetch beyond existing workflow behavior.

This branch is an integration-proposal **stacked on PR #534**. It does not alter the upstream owners' branches or constitute owner acceptance, CI pass, merge/release approval, or native finance ownership transfer. Preserve existing PR #532/#534 focused successes and their independent full-suite failures without retroactive relabeling. If the exact new head fails, capture the new failure and diagnose, do not change acceptance criteria.

## Verification gate
1. Exact-head source identity and diff show only the authorized YAML changes after the protocol.
2. Run the existing platform test and complete current Connected014 regression suite on the actual proposed head. Do not claim passing before GitHub jobs conclude.
3. Verify actual two official-source-focused job conclusions separately; no added government retrieval or proprietary input.
4. No protected main write, normal merge or release from this repair alone. Remaining full suite failures become explicit open blockers.

## Commercial and financial conclusion
Workflow governance repair only. New buyer demand, native economic revenue, beneficial asset transfer, real model costs and US$3B trailing-365 complete-cost profit remain unknown or unachieved. No bids, outreach, spending, paid model APIs, real transactions, keys, ledger mutations or production deployment.
