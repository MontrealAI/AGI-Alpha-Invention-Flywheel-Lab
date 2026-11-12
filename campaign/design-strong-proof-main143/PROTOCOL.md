# Review143 — stronger native business-design proof on exact protected main

**Status:** prospective, read-only, non-adopting compatibility comparison. Frozen before the executable workflow.
**Exact protected main:** `fe8ac39b56bc70c6b07555eed54574bd23ea2cc4`.
**Stronger reviewed proof source:** PR #115 head `56a2ec5800b9b86cb8de719ccc0e8af211d3f6b5`.
**Original weaker source for interpretation only:** PR #77 head `cd5281b0ae7b484572bfb35ccb7e51ef5b3be4b3`.
**Ownership:** PR77 retains design ownership; PR40 retains native-finance ownership; PR348 is a separate evidence branch, not a merge vehicle. No source/financial/ledger/key edits to those branches.

## Why this is worth testing

The previously successful PR348 composition runs *unchanged original* PR77, whose successor witness has known adverse-cost counterexamples: a collected positive successor can hide a required second investment invoice, shared-enabler loss, rejected/refunded order cost or transitive downstream loss. Its success is a narrow source-interface compatibility result, not a qualified adoption of the economic proof. PR115 has independently reviewed stronger transitive-connected component accounting and a heldout loss veto; its 13/13 original-stack checks are source-scoped to an older base. Whether the **unchanged stronger two executing source/test files** work with current protected main remains an independent question.

## Frozen experiment and stopping rule

1. Checkout both exact commit SHAs in isolated working trees, with read-only Actions credentials and no checkout credential persistence. Verify Git HEAD matches each pinned SHA. Require that protected main has neither `connected_enterprise/design_flywheel.py` nor `tests/test_connected_design_flywheel041.py`; abort rather than clobber any existing file. Copy **only** those two unchanged files from PR115 to the disposable main checkout, verify byte equality, record SHA-256 and list of overwritten main files (must be empty).
2. Before any synthetic operation, run **all** PR115 focused/adversarial tests unchanged; those contain the shared-capacity refunded loss, transitive third-hop loss, missing/unearned invoice, unrelated-loss exclusion and heldout rejection cases. A failed test is a failure, not an opportunity to tune market, proof threshold or source.
3. Execute the original exactly one registered 14-day simulation demo with exposed development seed **341014** and confirmation seed **341015** on the composed current-main canonical engine, then its independent `verify`. Require positive same-account source-linked EARNED-funded successor proof *and* positive matched profit delta *and* a holdout decision that does not veto the candidate, if the source provides that decision. If this stricter candidate does not pass, retain that negative verdict and do not reselect seeds.
4. Preserve only public key-free outcome and source/resource receipts, not the disposable directories containing ephemeral simulated account keys and state. Job logs remain immutable historical evidence. Source hashes and the exact CI link bind the result. No new spending, paid models, real customer data, real transfers, external credentials or production deployment.
5. Evaluate conditional outcomes distinctly from true incremental buyer LTV, complete host costs, voluntary real demand, native authoritative old-account migration, all strong outside choices, forward recurrence/retention and T365 US$3B. Even a full pass does not qualify those stronger claims; stop this single bounded review after tests/demo/independent verification. Do not promote PR115 source into main from this branch.

## Acceptance matrix and decision

- Source collision/authority protection: pass only with zero overwritten main files, exact pinned source identities, no external state.
- Focused adversarial regression suite: all PR115 tests pass (no selective omission).
- Current-main native operation: one original registered demo and independent audit pass with unchanged seeds.
- Stronger witness: transitive linked costs + all required EARNED invoices, adverse losses, heldout veto logic; source tests pass, observed public verdict separately recorded.
- Whole repository: **all** applicable hosted exact-head checks must complete successfully. A standalone job success does not cancel a failure elsewhere (including platform windows or archive guard).
- If successful, recommendation is **independent source-owner forward integration review**, not wholesale merge; if failed, preserve and diagnose.
- Real commerce/cold-start invention/3B profit: **not established**, regardless of this experiment's result.

The initial PR348 full-CI fail at head `432f4cb...` was specifically missing the required first-step platform clock marker, and is preserved in its own workflows. This workflow starts its clock before checkout with a standard `AGI_JOB_START_EPOCH` `GITHUB_ENV` receipt. Historical and future failures must remain failed.
