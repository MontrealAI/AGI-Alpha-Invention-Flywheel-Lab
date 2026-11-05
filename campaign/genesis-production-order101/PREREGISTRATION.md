# GENESIS101: native production commitment before delivery — frozen protocol

**Status:** preregistered prior to executable correction and confirmation results. Base: GENESIS owner PR #229 exact integration head `eabff02d76780af962cc4f6ba6e3f6353b47c52c`. Separate research branch; do not write the owner's branch, main, old journals or historical keys.

## Claim and independent falsifier

Registered GENESIS production is prepaid at integer hour `24*(i+1)`; the delivery is independently prepared at hour `+1`, then collected or refunded at hour `+2`. A native journal can faithfully record a genuine production spend **after** preparing the output or collecting payment, while the GENESIS audit presently reconciles only spend identity, amount, funding and receipt. That must not certify an earned-funded (or seed-funded) delivery as if the registered production commitment preceded delivery. The reviewed P1 finding is [PR229 review thread 4475864807](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/229#discussion_r4475864807).

## Fixed tests and stop rule

All tests use newly created, disposable **real** `flexibility063.native.BusinessAccount` / canonical `JournalAccount` simulated accounts, frozen GENESIS source + exact manifest, genuine prospective terms, original solver and verifier, replay-verifiable native journal and actual receipts. No financial export rewriting, alternative ledger, copied key, virtual receipt, fabricated revenue or modified historical account. Public execution rows are independently assembled from the actual native events; no private authority is exported.

- **C0 (normal):** the unchanged canonical funded pilot completes, remains auditable and has at least one accepted, pre-funded delivery.
- **C1 (late after collection):** one first-order genuine native delivery is prepared at registered hour +1, released at +2, and only then receives a genuine native production spend at +2. Mandatory canonical audit **must reject** `REGISTERED_PRODUCTION_COMMITMENT_ORDER_CHANGED`, even if the spend receipt says `EARNED` and the ledger and journal both replay.
- **C2 (same-hour inversion):** one first-order delivery is prepared at registered hour, genuine native production spending follows on that **same hour**, and native release is at +2. Mandatory audit **must reject** `REGISTERED_PRODUCTION_COMMITMENT_ORDER_CHANGED`, so a correct spending date alone cannot hide inverted native sequence.
- **C3 (checkpoint/regression):** genuine pre-production, partially complete account and ordinary completed resume continue to audit and preserve native financial bytes (no new fictitious expense). This test must not weaken refusal/failed-resource accounting or the original tax, fixed-cost, offer, registered native capital and tail guards.

Native independent oracle: identify each connected spend by `request.id` and canonical `receipt.native_event_sequence`, its registered day, and the native `prepare`/`release` or `refund` event sequences and hours. For a completed funded delivery, enforce exact spend hour and spend sequence before prepare and collection; refusal still incurs actual cost. Reject genuinely extra, missing, duplicated or shifted production commitments. No recomputed ledger balances, no retrospective re-signing. Preserve original failed GENESIS098 chronology trace as failed.

**Decision** (all cases fixed now): C0/C3 fail => repair or reject; C1/C2 accepted => blocker remains; success only if every required case executes with an expected canonical accept/reject, existing protected finance source unchanged, and exact-head CI/regression passes. No cherry-picked runs, weakened guards or baseline financial restatement. Independent reviewer must inspect any source correction before protected merge. No release, new profit, paid buyer, tax calibration, P0 legacy queue migration, causal invention or US$3B claim follows from engineering qualification alone.
