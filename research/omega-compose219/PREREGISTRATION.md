# COMPOSE219 — preregistered independent dry-run integration

**Status at registration:** NOT EXECUTED. This is a read-only compatibility experiment, not an integration owner, production merge or qualification of economic discovery.

## Fixed source inputs

- Repository: `MontrealAI/AGI-Alpha-Invention-Flywheel-Lab`
- Protected/main checkpoint observed 2026-11-21: `f0987aa48d5c9136b28540f54eabf5367e63bbe6`
- Common PR #517 base: `109bdcb4ec3d2309f23ba2c9ab3c96df530aada1`
- PR #519 outcome-admission boundary: `e67c7bd8d9bdc198d82a4153bf4c702de8d01982`
- PR #520 foresight/invention/transfer: `fe346668e717d9b38977d43b4123224d2feada64`
- Earlier semantic counterexample and failure: PR #518, exact review head `02fe1cf9870604ce2a513f406917917eed168943`, four-case witness SHA-256 `8be5b7a88c5de52fcd219b78b69bf348016983d31b41d3154250bc86cc06ff4e` (must remain unchanged).

## Hypothesis and finite procedure

The two independent PRs have the same original base, and should be composed and tested before either is treated as qualified for the integrated HARNESS runtime. A clean Git merge alone is not evidence that the fail-closed outcome-admission repair and the foresight/transfer pipeline interoperate.

One fixed pair only; no alternate heads, cherry-picked seeds or automatic retries. Check out the exact PR #520 commit in an ephemeral GitHub runner checkout, fetch PR #519 head, verify both exact identities and merge-base, then attempt `git merge --no-commit --no-ff` of #519 onto #520. **No merge commit or push**, no file modifications in either owner branch. Record conflicts verbatim. If no conflict, run the full HARNESS Python tests, Node tests, and independent boundary/foresight test suites from the combined working tree, using the repo's existing package requirements. Preserve test exit codes, failures, resource observations, and source-diff metadata.

## Preregistered result and stopping rule

- **ACHIEVED (engineering only):** exact pins verified, composition conflict-free and all executed full Python+Node suites exit zero. Explicitly label output `COMPOSED_UNCOMMITTED_WORKTREE_ONLY` and specify tests and resource receipts.
- **FAILED:** ref mismatch, non-common source, conflicting merge, dependency/setup failure or any test failure. Preserve failure; do not relabel or retry under a different identity.
- **BLOCKED:** platform/access restrictions that prevent the intended test. Record the exact boundary, never infer pass from absence.
- **UNQUALIFIED regardless of pass:** owner integration decision, protected merge, published/released operation, real customer value/revenue, full-cost comparative productivity, semantic truth, useful first economic invention, independent distinct successor advantage and US$3 billion trailing-365 complete-cost profit.

An optional future independent action is for the designated integration owner to resolve code conflicts, repeat source-bound qualification and ship a normally protected release. This review grants no financial, account, signing-key, merchant, external-customer or deployment authority. Actual task `01a18fa7-ffc6-7384-8bb4-ea6012cfb0f7` custody remains unknown; never infer inactivity.

## Alternatives before further implementation

A. Retain #519 only as a fail-closed product safety boundary; B. retain #520 only as unfinished research with explicit no-outcome claims; C. compose them for a single correctly bounded research runtime; D. no-deploy. The test assesses C's engineering compatibility, not its economic superiority. The strongest human, autonomous-provider, self-service and no-purchase options remain relevant economic comparators but are not invented as observed demand.

No new spending, paid APIs, outreach, purchase, transaction, production deployment, private credentials or changed canonical accounts. Preserve all historical failed runs and older releases unchanged.
