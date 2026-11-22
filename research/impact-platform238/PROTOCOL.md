# IMPACT-PLATFORM238 — pre-change source-only platform repair

## Immutable observed upstream failure (2026-11-22)

**Original owner:** PR #530, `experiment/impact-continuation229-20261121`, exact head `a4dc8c8429cf92c3550cf9ea9d45cdf0e1f13fc7` on protected main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. Preserve this owner branch and its historical outcomes; this is an independent dependent repair proposal.

Three original hosted workflow runs **failed**: bounded qualification [#44970624049](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44970624049), Connected014 [#44970624084](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44970624084), release-qualification [#44970624085](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44970624085). Independent exact-job logs identify the same existing guard in all three: `tests/test_connected_platform_runtime064.py::CurrentWorkflowPlatformTests.test_all_current_jobs_use_the_public_standard_runner_and_platform_window`; the new research workflow has `timeout-minutes: 20` rather than required `360`. The first job step already records `AGI_JOB_START_EPOCH` into `GITHUB_ENV` before checkout, so no additional start step is justified. These red runs remain failures.

## Frozen correction and tests

After committing THIS protocol before implementation, modify only `.github/workflows/impact-continuation229.yml` to replace **the single job's** `timeout-minutes: 20` with `timeout-minutes: 360`. Preserve every other byte of that workflow, the synthetic observations, source, exact tests, two original business/science fixtures, and original evidence. Use only normal `ubuntu-latest` public runner, unchanged read-only token permissions, and existing job-start marker. No new spending, API keys or paid runners.

Verify exact-parent and exact-child blob identities and the two-file diff; rerun the original platform rule and complete applicable tests via current standard GitHub Actions on **new** SHA. Keep every new failure as failure. Pass only if completed checks actually succeed, not merely queued or skipped. Record any platform-independent semantic/economic failures separately. Do not force merge into main or alter PR #530 source; original owner decides integration. No branch source is released until normal protected merge/publication and actual downloaded-source checks.

## Economic and ownership boundary

Source-only workflow remediation is neither a new frontier productive capability, approved government deliverable, customer outcome, legal compliance judgment, cash collection nor native account migration. No original signer, ledger, nonempty queue, liability or financial source access. P0 owner task `01a18fa7-ffc6-7384-8bb4-ea6012cfb0f7` remains separate and its current authority is unverified. This repair does not authorize procurement participation, production or real transactions. Complete-cost profit and US$3B trailing-365 milestone remain unachieved.