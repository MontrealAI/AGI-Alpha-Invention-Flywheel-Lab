# Prospective workflow-platform composition repair — 2026-11-19

## Source freeze and ownership
Independent additive corrective research branch at exact parent `087e945e01b90ae8af23aecce54e0f578af71763` (draft PR #488). This branch is a **dependent review proposal**, not a replacement for the owners of PR #484, PR #486, PR #487 or PR #488, and not a separate integration or finance owner. Main and the released Connected014 runtime remain untouched. No account or wallet, secrets, custody or payments are required.

Original pre-intervention Git blobs:
- `.github/workflows/frontier-economic-foundry.yml`: `e804615927f4c76143802c8c50be24794d87560f`
- `.github/workflows/frontier-machine-asset-001.yml`: `ba21b3b6797fa21c9a16f8b55f528af29749bd50`

Original source-matched hosted failures (retain as failed, not retroactive successes):
- https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44617831944
- https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44617832033
- https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44617832078

These showed *exactly three* violations in `test_connected_platform_runtime064.CurrentWorkflowPlatformTests.test_all_current_jobs_use_the_public_standard_runner_and_platform_window`: `discovery-evidence` had `15` instead of `360` minutes; `evm-contract` had `20` instead of `360`; `offline-check` had `5` instead of `360`. Other checked jobs are not changed. Job-level start-clock markers are required by the active resource policy.

## Registered intervention and decision
Prospectively change only the three job platform-window fields to `timeout-minutes: 360` and introduce the required first job step, `echo "AGI_JOB_START_EPOCH=$(date +%s)" >> "$GITHUB_ENV"`. Keep `ubuntu-latest`, permissions, original product code, policy tests, and every existing job command unchanged. Do not change finance source, source guards, release logic or archive limits. Preserve original failures. The first newly executing exact-head CI is the first qualification; if it fails for any reason, retain its failure. Any later repair is a separately identified correction, not a retroactive pass.

For the *specific* platform policy criterion, acceptance requires the complete corresponding original repository tests without failures under the corrected exact head, not just passing this text check. Normal release requires all its own gates, including publication and downloaded operation. No silent bypass of broad CI; any skipped publish path remains skipped.

Engineering decision alternatives: (A) retain broken inherited source and hold; (B) minimal independently reviewed workflow correction, chosen for exact root-cause repair; (C) weaken the platform checker or publication gate, **rejected**; (D) no integration/deploy pending owner review, retained as default. This is not a new productive business or Blue Sky flagship.

## Financial/commercial boundaries
No native original account transition, nonempty queue migration, paid buyer, executed financial settlement, new revenue, fee-bearing product, valuation, measured full campaign billing or US$3 billion trailing-365-day complete-cost profit is established. PR #486 contract and PR #488 checked reference remain immutable on this branch. No real EVM deployment or outgoing transaction. No routine approvals requested, but owner integration and all protected branch/release requirements remain. HOLD / NO BID / NO DEPLOY.
