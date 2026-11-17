# ALPHA Economic Engine 0.2 — authoritative obligation-reconciliation gate

Protocol frozen before adversarial tests or runtime changes on 2026-11-16 UTC.

## Source and ownership

- Owner branch: `feature/alpha-economic-engine-full-20261116`, immutable reviewed source `3a7beb3d6a7979ac49704f7aaf380274018e3731` (PR #419).
- This is a dependent, unmerged reviewer branch. It changes only the external treasury client protocol and its dedicated test, not the owner branch, Stripe/Checkout review PR #420, the canonical native financial account or any production provider.
- Scope: external authoritative gateway client `connected_enterprise/alpha_economic/gateway.py`. Existing signed receipts bind account, mode, request digest, nonce/idempotency key, time and HMAC but `advance()` currently forwards an unexamined `reconcile-obligations` result to a `LiveEngine.step()` caller that ignores the return. That may allow a new production transition after signed financial reconciliation reports uncovered obligations or unreconciled costs.

## Predeclared tests and stopping rule

In one immutable authored fake treasury world with signed, request-matched `treasury-receipt` envelopes:
1. Reconciliation result `obligations_covered:false`, `costs_reconciled:true` must fail closed without returning a success.
2. Missing `obligations_covered` must fail closed.
3. Result `obligations_covered:true`, `costs_reconciled:false` must fail closed.
4. String or integer truthy status must not count as Boolean true.
5. Only explicit `obligations_covered:true` AND `costs_reconciled:true` may return successfully; the result must still be the signed one.
6. The existing successful gateway snapshot/spend and complete owner integration tests must remain unchanged and pass.

No test modifies a real account, ledger, provider or claim. No concealed seed search, future-income reservation, new credentials, or executed transaction. Do not weaken independent account audit or historical liabilities. No commerce/profit result is implied. Stop for a protocol incompatibility; document rather than silently broaden semantic acceptance.

## Alternatives, verdict and handoff

Alternative A: trust the remote service's `authorized:true` alone (existing implementation); that is weaker because it can authorize a command whose business result itself reports financial failure. Alternative B: discard the remote result in the controller; this is also insufficient. Prefer a fail-closed typed gateway boundary while leaving the real authority to the external treasury. The external backend implementation remains missing; this is a protocol-fixture integrity improvement only.

Preserve the test-first failure, corrected exact-head CI and all existing outcomes separately. Review owner PR #419 for integration; no release or deployment claim.
