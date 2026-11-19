# 🌌♾️ MONTREAL.AI — Ω ALPHA Economic Mechanism Foundry

**Mission:** Discover what frontier intelligence makes possible. Invent the economic mechanism. Deploy it. Earn from genuine use. Compound.

**Owner / beneficiary:** MONTREAL.AI. **Scope:** owned, fee-bearing productive protocols—not consulting, patents, speculative token issuance or a customer-service business.

**Status: RESEARCH PROTOTYPE / HOLD / NO DEPLOY / NO REVENUE.** This is an implementable *bounded method for repeated experiments*, not proof that an AI system can autonomously discover new commercial inventions or improve itself indefinitely. It continues [FRONTIER Ω Machine Asset 001](../frontier_machine_asset_001/README.md) without changing its financial controls.

## Implemented

1. **Discover (bounded):** invent.py exhaustively compares 25 candidate arrangements across direct settlement, buyer-verifier escrow, and independent-verifier escrow, with fee and expiry policies. Includes no-entry and fee-free escrow alternatives.
2. **Construct:** Escrow candidates produce parameters for the executable Solidity reference in contracts/FrontierProofExchange.sol. This real code uses immutable fees, seller artifact commitments, buyer-selected verifier and refund at expiry.
3. **Verify:** Synthetic buyer/seller economic calculations use exact rational arithmetic. Selection is from development cases only; the holdout is evaluated after selection. EVM tests exercise transfers, refunds, unauthorized acceptance, replay and taxed-token deposits.
4. **Retain:** registry.py stores result identities, failures and hash-linked experiment records across distinct missions. Successor comparisons avoid assuming inherited advantage.
5. **Commercial gate:** No mainnet deployment, actual sales, real token transfers, customer billing, new merchant account, public endpoint or new paid service.

### Reproduce the discovery loop

Python 3.10+ standard library only, no external services or credentials:

~~~sh
cd products/frontier_mechanism_foundry
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 invent.py --brief examples/brief-agent.json --successor examples/brief-science.json --out /tmp/frontier-foundry-first.json
python3 registry.py --register /tmp/frontier-foundry-inventions.jsonl --result /tmp/frontier-foundry-first.json
python3 registry.py --register /tmp/frontier-foundry-inventions.jsonl
~~~

The output contains a bounded search result, synthetic accounting, independent holdout, source digest, successor comparison and explicit HOLD verdict. The local research register is single-writer and its hash chain cannot protect against a malicious administrator.

### Test the EVM fee mechanism locally

~~~sh
cd products/frontier_mechanism_foundry
forge test -vv
~~~

GitHub Actions runs the same isolated EVM tests. The contract is **not deployed** and has not received an independent security audit. Off-chain quality and verifier integrity are not proven by an artifact hash. Fees accrue only from transactions users voluntarily route through **that specific contract**. Other participants can fork the publicly available escrow, including at zero fee.

### Both $AGIALPHA assets remain valid

- **Ethereum mainnet:** $AGIALPHA at 0xA61a3B3a130a9c20768EEBF97E21515A6046a1fA, 18 decimals, a candidate ERC-20 for a separately approved contract deployment.
- **Solana mainnet-beta:** valid $AGIALPHA mint tWKHzXd5PRmxTF5cMfJkm2Ua3TcjwNNoSRUqx6Apump, recognized by the predecessor's existing direct-transfer evidence adapter. **The Solidity escrow is Ethereum-only; it does not constitute a Solana on-chain program.**

No actual treasury address or on-chain deployment has been supplied or invented. No token bridge, mint, fee extraction or transfer was performed.

## Why the breakthrough is still missing

Existing [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) registries address agent identity, reputation and validation. Existing [Uniswap v4 hooks](https://developers.uniswap.org/docs/protocols/v4/concepts/hooks) and [hook fees](https://developers.uniswap.org/docs/protocols/v4/guides/custom-accounting) support programmable fee capture. Other escrow and machine-payment systems provide strong alternative implementations. Our current mechanism is a **reference baseline**, not an invented economic moat.

The engine's finite grammar searches and configures a constrained family of arrangements; it does not autonomously discover new physical laws, novel mathematics, proprietary market demand or universally superior protocols. The development and holdout examples are authored synthetic cases, not independent customer evidence.

## Next consequential gate

Select and test an economically consequential missing productive mechanism that existing full-stack alternatives cannot adequately supply. Include actual buyer need, first-party sources, latest frontier enabling change, a genuinely needed new means, full-comparator cost, authority, safety, prospective acceptance and post-deployment compensation. If the strongest ordinary route works, retain HOLD.

The complete progression to qualify is: **newly enabled outcome → accepted instrument → strong baseline advantage → real voluntary buyer → reconciled funds and costs → second deployment → genuinely improved discovery on a different fresh task**.

The $5 billion laboratory valuation remains a highly ambitious financing objective, not a presently supported conclusion.

See [EVIDENCE_AND_NEXT_GATE.md](EVIDENCE_AND_NEXT_GATE.md) for the status and next research gate.
