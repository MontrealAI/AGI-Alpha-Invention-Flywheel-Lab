# Ω ALPHA — verifier-strategy counterexample protocol (19 November 2026)

**Prerecorded before the intervention.** Parent: original owner draft PR #486 at `a3a803edbce39caf69e9a335579f75dcb45df9ec`, dependent on draft PR #484. This is an *independent, additive, review-only* witness; no owner-source, financial-ledger, released-main, token, wallet or credential modifications. Never merge this dependent branch wholesale.

## Pinned source and economic question

- Owner EVM implementation: `products/frontier_mechanism_foundry/contracts/FrontierProofExchange.sol`, Git blob `ef6fc9f03a3fc284df7e63d3ad1b20de1bfd2f83`.
- Owner synthetic evaluator: `products/frontier_mechanism_foundry/invent.py`, Git blob `9f86912d5bdbd724cef6783ae46540968a380064`.
- Hypothesis to **try to falsify**: the synthetic buyer-escrow seller-profit/fee calculation remains realizable if the buyer is also the sole verifier, the delivered benefit is visible before payment, there are no legally enforceable or reputational penalties for withholding attestation, and the seller/buyer can decline.
- Not a claim that all digital goods are visible before payment, that any real participant behaves dishonestly, or that a buyer-selected *honest* independent verifier cannot work. Record both compliant and adverse behavior.

## Frozen finite test cases — no new seeds

Use locally minted **simulated** ERC-20 balances, Solidity 0.8.24, a 1% fee, one disclosed job with principal 1000 raw units and expiry 100 seconds after opening; counterparties are synthetic addresses only.

1. Buyer-selected verifier = buyer; seller submits artifact commitment. Buyer does not accept; after expiry refund succeeds, seller and treasury receive zero, buyer recovers full principal; late acceptance is impossible. Seller has already incurred any *externally modeled* production cost.
2. Identical job with independent, cooperative verifier: timely acceptance pays seller 990 and treasury 10, then buyer refund is rejected.
3. Nominally independent but noncooperative verifier: submitted artifact can expire and buyer can refund, with no seller payment. This is a negative scenario, not a claim of independent-verifier inevitability.
4. Buyer-verifier job with no seller delivery: expiry refund succeeds and no merchant work is implied.

For separate exact-rational illustrative utilities use price 100, customer value 150 *if the artifact is accessible before attestation*, seller production cost 40, platform fee 1, independent verification fee 3 when relevant, zero modeled network/other costs and outside option zero. Compare (a) buyer-verifier escrow with rational withholding and rational seller non-entry, (b) cooperative independent escrow, (c) fee-free cooperative independently verified incumbent, (d) direct prepayment with a competent seller assumed to deliver, (e) no-deploy. No entry is the predicted outcome of (a) **within the stated finite game**, not evidence that no real buyer would ever pay. Show original favorable synthetic buyer-escrow output separately from the resulting adversarial payment path. Never confuse a computed payoff with actual revenue or with funded native capital.

## Qualification and stopping rule

- First publish this file as an immutable Git commit; only then create the separate test/instrument and CI. No source edits, token movement, real commerce, new spending or account changes.
- CI must check both original Git blob hashes before execution; retain *all four* EVM scenarios and deterministic economic alternatives, no cherry-picked seeds or weakened controls.
- Use standard public GitHub runners, six-hour platform job window, first-step execution clock and existing toolchain. Report exact-head success/failure independently of full-suite inherited checks, including known old timeout failures.
- PASS only if original code is pinned, each intended chain state is observed, normal acceptance/refund control succeeds, and synthetic comparative results are internally consistent. A failed expected EVM sequence stays FAILED, not repaired by changing the declared protocol.
- The key decision is whether fee-bearing buyer-verifier escrow is *incentive-compatible under this adversarial information pattern*. If not, reject it as a viable general-sale mechanism under those assumptions and require actual enforceable acceptance, reveal discipline or credible independent verifier before claiming voluntary profitable commerce.
- Cost: collect actual wall/CPU where feasible; real model, infrastructure, gas and operator bill remain unknown. No production value, actual willingness-to-pay, source-matched release/download qualification, annual profit, new invention or recursive improvement is proven by this witness.
