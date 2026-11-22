# FRAME-PLATFORM235 — preregistered source-governance repair

## Frozen before either workflow modification

Date: 2026-11-22 UTC. Parent is the immutable draft PR #527 head `d328acc25eefa986ec3fe9a4841ce9b4b4e4fd01` on branch `experiment/frontier-framecost226-20261121`. Upstream PR #526 head is `04767e2b7628e9e4b470c910fd7a3c3c03202135`. Current protected main is `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.

Historical negative evidence: the complete Connected014 workflow #44956239656 and release qualification #44956239646 failed from `test_connected_platform_runtime064`. Both inherited `.github/workflows/frontier-framefix225.yml` and `.github/workflows/frontier-framecost226.yml` omit the mandatory first hosted job step that records `AGI_JOB_START_EPOCH` into `GITHUB_ENV`. Their 360-minute windows are already correct. PR #526's own Connected014 run #44950853830 had the same framefix failure. All historical runs remain failed.

## One minimal prospective correction

- Change exactly `.github/workflows/frontier-framefix225.yml` and `.github/workflows/frontier-framecost226.yml`; prepend to **each** job's `steps` a shell step, before checkout, with `echo "AGI_JOB_START_EPOCH=$(date +%s)" >> "$GITHUB_ENV"`.
- Do not modify scientific implementation, frozen inputs, expected outputs, math, test fixtures, tolerances, accounts, journals, keys, core release, ownership, resources, billing settings or job time caps.
- Use standard public `ubuntu-latest` and the existing six-hour job boundary; no paid API, GPU, outreach or deployment.

## Preregistered acceptance and stopping conditions

1. Diff contains exactly two YAML corrections plus this protocol. The upstream files and five pinned science blobs stay unchanged.
2. Exact branch-head CI must pass both scientific workflows on the PR and the full Connected014 platform suite, release engineering qualification and any applicable repository gates. Preserve negative runs and new failed attempts; fix attributable causes without weakening tests.
3. Normal merge/release and independently downloaded release operation are **not** claimed by a successful draft PR. The responsible science owner must review stacked integration; no unapproved cross-owner merge.
4. No extra scientific inference: existing 609-pair/1827 pair-scenario evidence is not a fresh result, physical experiment, buyer acceptance, beneficial successor, actual revenue or US$3B annual profit.

No existing financial signer, native account, nonempty operating queue, liability, writer lease, protected main or other owner branch may be accessed or changed. The original native-capital task's private authority remains unverified. Final decision stays HOLD / NO DEPLOY.
