# APD001 — Proof-carrying atomic result sale (experimental)

**Engineering experiment, not a new product or commercial achievement.** Implemented on an isolated branch from main. The buyer funds a local-EVM ETH escrow for a graph whose adjacency is cryptographically committed. A seller produces an explicit 3-coloring certificate; *the same successfully executed EVM transaction* checks every edge and pays without a discretionary post-delivery buyer signature. Invalid or unfulfilled commitments remain refundable after expiry. This addresses the precise buyer-discretion problem witnessed in [PR #491](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/491), but **only for computable certificates with an agreed on-chain verifier**.

## Research construct, with strong outside options

- **Executable result:** a correct 3-coloring of the precommitted graph, for n=3..32. Solving can be computationally hard; verifying a witness is cheaper. The finite 3..8-vertex ordinary control already solves our authored cases. No general computational advantage is claimed.
- **Voluntary terms:** a hypothetical buyer agrees to graph/fee/expiry and funds it; the seller may decline to compute. No buyer, funding or seller was actually recruited. Expiry/availability, software correctness, private transaction leakage, execution gas, reorgs, adverse token behavior and resource costs still matter.
- **Comparison:** competent self-service / ordinary solver; buyer-discretion escrow (fails in specified adversarial information pattern); independent-verifier escrow (requires trustworthy service); checkable proof automatic settlement (possible added fee/gas and data leak); no-deploy. **No price-demand curves or observed willingness to pay.** A zero-comparison or tie cannot be marketed as a superior service.
- **Narrow physical/digital limit:** correct graph coloring isn't a scientific measurement, real-world delivery or optimization optimality guarantee. Buyer can learn a witness in public mempool even if inclusion/finality later fails. Seller-only claim invocation does not prevent that visibility. Chain execution, payment gas, possible fee rounding, cash-flow, tax, support, refunds, independent acceptance and ownership have not been costed for commerce.
- **Source/finance boundary:** source-main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`, preregistration commit `1064283d016f17bc71297228684ed04def403279`; PR486 owner contract original blob `ef6fc9f03a3fc284df7e63d3ad1b20de1bfd2f83`, untouched. No canonical enterprise account read/write, no secret handling, no genuine funding, no real ETH or ERC20 token use.

## Reproduce safely

Run `cd campaign/atomic-proof-delivery-20261119`, then `python3 -m unittest discover -s . -p 'test_ordinary_control.py' -v` and `python3 ordinary_control.py --output /absolute/new/control.json`. With installed Foundry run `forge test -vv --gas-report`. The dedicated Actions workflow runs on a free standard public-repository runner with a 360-minute platform window. Its outcome, not this README, is qualification. Failed cases remain failed and all subsequent repairs require prospective commits.

## Claim tiers and next economic gate

**Source engineering** requires exact-head CI with valid K3/C4 payout, impossible K4 refusal, certificate checks, unauthorized/replay and refund invariants, plus gas receipt and a competent ordinary control. **Productive benefit** requires a real outcome valuable enough to justify solving and a buyer who can use the certificate. **Economic benefit** requires buyer consent, real accepted work, independently collected fee, complete delivery/chain/computational/security/support/acquisition costs and remaining obligations. **New frontier invention** would require causal superiority over fully endowed strong alternatives and fresh tasks, not the contract name. **$3B trailing-365 profit** is not established by any test.

Until these stronger gates: **HOLD / NO DEPLOY / NO BID**. Not a registered production asset and not suitable for wholesale release or normal merge merely because tests pass.
