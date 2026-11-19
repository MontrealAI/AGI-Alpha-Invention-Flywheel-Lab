# Preregistered check: exact-credit payout reference — 2026-11-19

Owner of this independent *additive research branch*: AGI ALPHA continuation. Parent: independent #487 exact-head `a6aa5e72181a2b28e8f9b39aae880e9d85b112ad`, which is dependent on implementation-owner #486. No writing to the original contract, original owner branch, main, native financial account, keys or production release. A subsequent owner independently decides whether any ideas or code are adopted.

## Original source and observed failure

- Frozen original PR486 contract commit: `a3a803edbce39caf69e9a335579f75dcb45df9ec`.
- Frozen original `FrontierProofExchange.sol` Git blob: `ef6fc9f03a3fc284df7e63d3ad1b20de1bfd2f83`.
- Parent #487 original-token witness: `OutboundSettlementWitness.t.sol`, never edit it.
- Historical original no-op and seller-shortfall *negative* outcomes remain violations. Green detection tests mean the violations were actually seen, not approval.

## Prospective interventions, outcomes, stopping

Produce only a separate `FrontierProofExchangeChecked` reference with the original nonreentrant job, approval, expiry, fee and status logic. Change the outbound transfer invariant: require the escrow's token balance to decline by exactly the requested amount and the intended recipient's token balance to increase by exactly that amount in the same transaction. Reject seller/treasury aliasing to simplify independent credit accounting. On any abnormal transfer, the EVM revert must restore both earlier transfers and original job status, preserving refund rights. Apply the exact-credit guard to both acceptance and refund, and retain the exact inbound deposit guard.

Freeze before writing the implementation; run **all** following registered cases once on the first candidate: conforming token completes 990/10 from a 1000 principal at 1% fee; seller-only one-unit shortfall must revert without acceptance and later allow exact refund; outbound transfer returning true without moving funds must revert without acceptance and later allow refund; outbound true/no-op refund must itself revert without terminal state and later succeed when token conforms; buyer-credit shortfall on refund must revert without deleting the buyer claim. Include optional extra deterministic adversarial regressions but preserve all five outcomes, including failures. Original negative witness stays independent comparator.

Use existing public-repo hosted Foundry/solc 0.8.24 and standard Actions, no purchase or real chain calls, with 360-minute job ceiling/start-clock and exact original blob guard. Single first exact-head hosted run is the confirmatory result: if compilation or any case fails, retain it FAILED; a prospective repair is separate and cannot relabel the first result. No seed/sample shopping.

## Limited claim, alternatives and business decision

Compare (A) original status-finalizing escrow, (B) checked local reference, (C) existing competent fee-free/standard guarded escrow, (D) no deployment. The new check may remove a specific simulated settlement fault but DOES NOT authenticate token balances against a malicious token, prove cryptographic outcome truth, authorize a token, deliver a new customer outcome, establish willingness to pay, compete with ordinary secure escrow, or earn any money. If all tests pass, verdict is **ENGINEERING REFERENCE ONLY / NO DEPLOY / NO BID** absent independently accepted productive outcome, buyer demand, token audit, approved treasury, complete costs and production authority. Full host/model billing remains unknown unless measured.

## Handoff/ownership and costs

Do not modify #486 or #487 files, transfer control of the original native JournalAccount, create a replacement ledger, sign a legacy checkpoint, or weaken any guard. Retain failed historical runs. Report source, tests, host telemetry if available, liabilities (none created), qualified boundary, and next owner decision. Future profit is not spendable cash; US$3B trailing-365 target remains unachieved.
