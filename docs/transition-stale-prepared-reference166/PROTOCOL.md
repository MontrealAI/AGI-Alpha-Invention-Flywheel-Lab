# Transition166 — isolated reference correction of stale cached preparation

## Frozen source and scope (before implementation)

Owner PR #40 exact source `ced6c1cb004887dcdafaea59a2976020be649f8e`; base `integration/transition-recovery-025`. Independently observed T165 failure: `28b4df5aa87a95cdb754d709de32719ed52b5fa8`, hosted run `43689421296`, remains **FAILED**. Owner PR #40 is the sole authoritative integration source; this **separate research branch** does not update the owner branch, current `main`, signed source, account, key, real queue, release or liability. Its proposed patch is *not* accepted for financial use or authority reassignment.

## Exact preregistered construction and tests

One minimal candidate change only: in `connected_enterprise.operations.prepare_upgrade`, reject an observed `STATE.json` whose digest differs from the caller's fixed `expected_checkpoint_sha256` **before** any existing identical-request early return or source/signing side effect. Preserve existing guard semantics, canonical `read_operator`, and all other implementation. Do not modify the test or evaluator to force success.

Run the **unchanged** T165 disposable synthetic scenario with the exact prior source test bytes, plus the existing `tests.test_transition_authorization_reuse` eight controls. The fixed T165 schedule checks successful preparation against A, identical idempotent retry against A, advance only disposable STATE to B, and rejection of stale retry against B with no new signer, source copy, descriptor or history mutation. All nine tests must pass. Preserve stderr, exit code, source identity, and any negatives. Additional qualification of original HMAC, Account, JournalAccount, nonempty operating queues, cross-process leases, crash idempotence, source-composition and public downloaded release is **not performed** by these tests and cannot be inferred.

## Completion boundary

A passing result demonstrates only a **same-call, already-observed checkpoint digest precondition** in a frozen synthetic fixture. It does not eliminate a concurrent check-then-use race, authenticate STATE or preserve financial liabilities. The existing financial owner must independently port/qualify a full authenticated current-state check under the shared exclusive writer lease, recheck before any financial commit and prove actual nonempty original account/queue continuation before protected integration and release. The current proposed reference is **NO MERGE / NO DEPLOY** as a financial authority. Resource receipt: no new spending or paid model API; actual GitHub-hosted execution timings from CI, whole-account billing unknown. Commercial receipts and US$3B T365 target remain unqualified.
