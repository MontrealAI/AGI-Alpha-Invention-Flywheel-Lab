# Transition163 — preregistered cross-operation epoch reference (NONFINANCIAL)

Date: 2026-11-14. Parent source: protected `main` at `9f469d129dae71cf939e1be8a7d30ab824906cb4`. This is an **independent research reference** extending already-merged Transition156/157, **not** PR40 finance, not a native operator facade, not an account recovery, and not a new commercial flagship. Original T154/T155/T162 exact-source failure receipts remain failed.

## Specific observed gap and narrow construction

Actual [Transition162 owner-source test](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/43642449740) failed with `TRANSITION162_OLD_OPERATION_AND_NEW_PREPARE_BOTH_ACCEPTED`: old-source `operate` was active while new-source `prepare_upgrade` returned success. It was a synthetic control-plane test with mocked signer and run_world, **not** evidence of money loss. Existing Transition156 uses a file lease only for *preparation*, and therefore does not alone establish whole-operation epoch exclusion.

Construct an **isolated, nonfinancial** `operate_once` that uses the *same* existing `.prepare.lock` as `prepare_once` for the entire synthetic operating callback, validates expected/observed source checkpoint, refuses pending prepare, and durably publishes a create-only operation intent **before** callback plus a create-only completion receipt **after** a verified observed result. Preparation must refuse a dangling operation intent (including crash/restart) rather than accepting a new source without authenticated reconciliation. A recorded completed operation may be followed by a preparation only against its *current* observed checkpoint. Identical replay must not invoke the callback again, and a conflicting operation must be refused. This deliberately models **one finite operation** and does not provide repeated production operation or post-crash owner reconciliation.

## Fixed independent regressions (before implementation)

1. Two genuinely separate POSIX processes: old operation holds the shared lock and callback; concurrent new preparation cannot return while it is active. After operation changes observed checkpoint, stale new preparation refuses without authorization, original operation receipt unchanged. Use synchronization events, not favorable seeds/timing samples.
2. Serialized complete synthetic operation → fresh matching-source preparation is permitted only after completion and current checkpoint verification, with immutable operation intent/completion receipts. Cached identical operation returns byte-identically without a second callback; stale/forked observed checkpoint refuses.
3. Synthetic operation process terminates immediately after durable intent, before completion. New preparation and operation retries fail closed, and no second authorization callback occurs.
4. A prepared pending request blocks a new synthetic operation before its callback, and a different operation ID cannot replace a prior completed request.
5. All eight existing Transition156/157 tests continue passing with no behavior change on preparation-only directories.

Scope: only synthetic digest observations, fake callbacks and temporary files. No original account, private signing key, real HMAC, JournalAccount, native service work, source/version counters, liabilities, claim/maturity ordering or revenue is exercised. Passing this reference does **not** repair PR40 nor unblock source migration. An exclusive lock works only when **every** canonical real financial writer participates. Never install this as an alternative financial authority, relax source/archival guards, or claim production use.

## Required later P0 owner qualification

Owner source/custody handoff and reviewed canonical integration into one shared account lease; signed predecessor/current checkpoint, pending request and counter binding; genuine nonempty queued acceptance and settlement; crash/restart/replay/downgrade/fork/racing-writer rejection; due claims before maturity; same-account earned funding; protected normal release and independent downloaded-byte audit. No spending, paid APIs, outreach, new credentials, real transactions or deployment.

Verdicts here: reference engineering only; actual commerce UNQUALIFIED; fresh successor UNQUALIFIED; US$3B trailing-365 full-cost profit UNACHIEVED.
