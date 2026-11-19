# Independent outbound ERC-20 settlement invariant — frozen prospective review

Date: 2026-11-19. Source reviewed: PR #486 at `a3a803edbce39caf69e9a335579f75dcb45df9ec`, based on PR #484 `b333a5f4ac9495b9c8259170597239a1792bf1ac`.
Original contract Git blob: `ef6fc9f03a3fc284df7e63d3ad1b20de1bfd2f83` (`products/frontier_mechanism_foundry/contracts/FrontierProofExchange.sol`).
Original factory Git blob: `4cbe9b7577f70adbc451fa45b7d6857674134f8d`.
Neither original contract, factory, tests, accounts nor another owner's branch may be changed in this review.

## Questions frozen before witness construction
Does `accept` enter terminal `Accepted` even when a payment token truthfully funds the escrow but short-transfers, or returns success without transferring, on the outbound seller/treasury payment? A caller may believe the full principal has been finally settled although funds were underpaid or stranded. A successful `open` balance-delta check must be retained and demonstrated. Compare with an ordinary conforming ERC-20 control.

## Predeclared tests, no favorable-selection policy
Use three **local mock** token behaviors in a deterministic Foundry environment, with the same buyer/seller/verifier, 1000 units principal, 100bps fee, nonzero hash, and no mainnet actions:
1. **Conforming:** `transferFrom` and `transfer` both transfer full units. Expected seller=990, treasury=10, escrow=0, Accepted.
2. **Outgoing-transfer tax:** honest 1000-unit inbound deposit; `transfer` burns one unit from the seller's 990-unit payment while reporting success (treasury's 10-unit payment is exact). Test whether the original contract reaches Accepted with seller=989, treasury=10, escrow=0; this would violate full-credit settlement while conserving token liabilities by burn.
3. **Outgoing no-op returning true:** honest 1000-unit inbound deposit; `transfer` reports true but does not move money. Test whether original contract reaches Accepted, seller=0, treasury=0, escrow=1000, and buyer refund is thereafter rejected. This would be a false-final-settlement condition on a noncompliant token.

Tests should distinguish a *witness that an unsafe state exists* from *passing a safety qualification*. If a negative case is blocked by the original contract, report falsification, not silent test substitution. All source and run identifiers must be reported. No assertion that either anomalous behavior exists in the actual $AGIALPHA token is permitted without independent on-chain evidence. The known source is a research prototype, not a security audit or a deployed contract.

## Exit/owner boundary
A focused CI result and exact pinned code witness provide an owner-facing finding; they do not justify protected merge, real deployment, financial transitions or live treasury activation. The original owner may consider requiring exact outbound balance deltas or a narrower verified-token allowlist plus independent audit; no fix is prescribed as qualified in advance. Existing repository-wide workflow invariants (360-minute standard runner, start clock marker) must be respected. Preserve any failed workflows and all historical experimental evidence as failed.
